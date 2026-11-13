"""
LLM客户端封装
统一使用OpenAI格式调用
"""

import json
import logging
import os
import re
import time
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config
from .openai_chat_compat import create_chat_completion, extract_chat_completion_text


logger = logging.getLogger(__name__)

# بعض النماذج (مثل gpt-oss على Groq) تنادي أداة مدمجة من تلقاء نفسها عندما ترى
# وسومًا مثل <tool_call> في التعليمات، فيرفض المزوّد الطلب برسالة
# "Tool choice is none, but model called a tool". هذه رسالة تذكير تُضاف عند الحدوث.
TOOL_GUARD_MESSAGE = (
    "تنبيه نظام: لا تستخدم واجهة الأدوات المدمجة ولا تُصدر أي tool_call. "
    "استدعاء الأدوات هنا يُكتب كنص عادي داخل وسم <tool_call> ... </tool_call> فقط، "
    "وأي رد منك يجب أن يكون نصًا عاديًا."
)


class LLMResponseError(ValueError):
    """A safe, structured error for unusable model responses."""

    def __init__(self, message: str, *, finish_reason: Optional[str] = None):
        super().__init__(message)
        self.finish_reason = finish_reason


def _is_response_format_unsupported(error: Exception) -> bool:
    """Detect an explicit provider rejection of JSON response_format."""

    if getattr(error, "status_code", None) not in {400, 422}:
        return False

    body = getattr(error, "body", None)
    if not isinstance(body, dict):
        return False

    details = body.get("error", body)
    if not isinstance(details, dict):
        return False

    param = str(details.get("param") or "").strip().lower()
    if param == "response_format" or param.startswith("response_format."):
        return True

    message = str(details.get("message") or "").lower()
    if "response_format" not in message:
        return False

    code = str(details.get("code") or "").lower()
    unsupported_codes = {
        "unsupported_parameter",
        "unsupported_value",
        "unknown_parameter",
        "invalid_parameter",
    }
    unsupported_phrases = (
        "not support",
        "unsupported",
        "unknown parameter",
        "unrecognized parameter",
    )
    return code in unsupported_codes or any(
        phrase in message for phrase in unsupported_phrases
    )


def _clean_chat_text(content: str) -> str:
    """Remove common reasoning wrappers and an outer Markdown JSON fence."""

    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
    cleaned = cleaned.lstrip("\ufeff")
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    return cleaned.strip()


def _contains_additional_json_container(content: str) -> bool:
    """Return True when trailing text embeds another JSON object or array."""

    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\[{]", content):
        try:
            value, _ = decoder.raw_decode(content[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, (dict, list)):
            return True
    return False


# مزوّدون مجانيون إضافيون يُستخدمون تلقائيًا إذا وُجد مفتاحهم في البيئة.
# لا تحتوي هذه القائمة أي سر: المفاتيح تُقرأ من متغيّرات البيئة بالاسم فقط.
BUILTIN_FALLBACK_PROVIDERS = [
    # Google AI Studio: طبقة مجانية دائمة بلا بطاقة (والسودان ضمن الدول المدعومة)
    {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "model": "gemini-3.6-flash", "api_key_env": "GEMINI_API_KEY", "extra": {"reasoning_effort": "low"}},
    {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "model": "gemini-3.5-flash-lite", "api_key_env": "GEMINI_API_KEY", "extra": {"reasoning_effort": "low"}},
    {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "model": "gemini-3.8-flash", "api_key_env": "GEMINI_API_KEY", "extra": {"reasoning_effort": "low"}},
    # NVIDIA NIM: طبقة مجانية بلا بطاقة
    {"base_url": "https://integrate.api.nvidia.com/v1", "model": "openai/gpt-oss-120b", "api_key_env": "NVIDIA_API_KEY"},
    {"base_url": "https://integrate.api.nvidia.com/v1", "model": "meta/llama-3.3-70b-instruct", "api_key_env": "NVIDIA_API_KEY"},
    # OpenRouter: نماذج :free بلا بطاقة
    {"base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-oss-20b:free", "api_key_env": "OPENROUTER_API_KEY"},
    # Cerebras: لم يبقَ مجانيًا فعليًا (يشترط وسيلة دفع) — يُستخدم فقط إن وُجد مفتاح
    {"base_url": "https://api.cerebras.ai/v1", "model": "gpt-oss-120b", "api_key_env": "CEREBRAS_API_KEY"},
]


def describe_fallback_providers() -> List[Dict[str, Any]]:
    """وصف المزوّدين المجانيين وحالة وجود مفاتيحهم (بلا كشف أي مفتاح)."""
    described = []
    for item in BUILTIN_FALLBACK_PROVIDERS:
        key_env = item.get("api_key_env")
        described.append({
            "provider": (item.get("base_url") or "").split("//")[-1].split("/")[0],
            "model": item.get("model"),
            "key_env": key_env,
            "key_present": bool(key_env and os.environ.get(key_env)),
        })
    return described


def probe_providers(limit: int = 3, timeout: float = 60.0) -> List[Dict[str, Any]]:
    """اختبار حقيقي (بلا كشف المفتاح) لكل مزوّد بديل له مفتاح في البيئة."""
    results: List[Dict[str, Any]] = []
    for item in BUILTIN_FALLBACK_PROVIDERS:
        key = os.environ.get(str(item.get("api_key_env") or ""))
        if not key:
            continue
        label = f"{item['model']} @ {item['base_url']}"
        try:
            client = OpenAI(api_key=key, base_url=item["base_url"], timeout=timeout)
            response = create_chat_completion(
                client,
                model=item["model"],
                messages=[{"role": "user", "content": "أجب بكلمة واحدة فقط: تم"}],
                max_tokens=64,
                extra=item.get("extra"),
            )
            results.append({
                "target": label,
                "ok": True,
                "reply": (extract_chat_completion_text(response) or "")[:40],
            })
        except Exception as exc:  # noqa: BLE001
            results.append({"target": label, "ok": False, "error": str(exc)[:200]})
        if len(results) >= limit:
            break
    return results


def _error_text(error: Exception) -> str:
    """نص الخطأ كاملًا (رسالة + تفاصيل) لتصنيفه بدقة."""
    parts = [str(error)]
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        parts.append(json.dumps(body, ensure_ascii=False))
    return " ".join(parts).lower()


def _is_daily_quota_error(error: Exception) -> bool:
    """نفاد الحصة اليومية للنموذج → ننتقل إلى نموذج/مزوّد آخر بدل الانتظار."""
    detail = _error_text(error)
    return (
        "tokens per day" in detail
        or "tpd" in detail
        or "requests per day" in detail
        or "rpd" in detail
        or "daily quota" in detail
        or "per day" in detail
    )


def _is_model_missing_error(error: Exception) -> bool:
    """النموذج غير موجود أو أُوقف → نتجاوزه بهدوء."""
    detail = _error_text(error)
    status = getattr(error, "status_code", None)
    if status == 404:
        return True
    return any(
        phrase in detail
        for phrase in (
            "does not exist",
            "not found",
            "decommissioned",
            "model_not_found",
            "no such model",
            "unknown model",
            "not supported for model",
        )
    )


def _is_rate_limit_error(error: Exception) -> bool:
    """حدّ لحظي (في الدقيقة) → انتظار قصير ثم إعادة المحاولة على نفس النموذج."""
    detail = _error_text(error)
    return any(
        token in detail
        for token in (
            " 413", "413 ", "429", "tokens per minute", "tpm",
            "rate limit", "rate_limit", "too many requests",
        )
    )


class LLMClient:
    """LLM客户端"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        # قائمة المرشّحين: النموذج الأساسي ثم النماذج/المزوّدون البديلون.
        # الهدف: ألا يتوقف الموقع كله حين تنفد حصة نموذج واحد في اليوم.
        self._candidates = self._build_candidates()
        self._candidate_index = 0

    def _build_candidates(self) -> List[Dict[str, Any]]:
        """يبني قائمة (عميل، اسم نموذج) تبدأ بالنموذج الأساسي."""
        candidates: List[Dict[str, Any]] = [
            {"client": self.client, "model": self.model, "label": f"{self.model} (أساسي)"}
        ]
        seen = {self.model}

        raw_models = (getattr(Config, "LLM_FALLBACK_MODELS", "") or "").strip()
        model_list = [m.strip() for m in raw_models.split(",") if m.strip()]
        if not model_list and "groq" in (self.base_url or "").lower():
            # حصص Groq المجانية منفصلة لكل نموذج، فهذا يضاعف السعة بلا أي دفع.
            model_list = ["openai/gpt-oss-20b"]

        for name in model_list:
            if name in seen:
                continue
            seen.add(name)
            candidates.append({
                "client": self.client,
                "model": name,
                "label": f"{name} (نموذج بديل)",
            })

        raw_providers = (getattr(Config, "LLM_FALLBACK_PROVIDERS", "") or "").strip()
        env_providers: List[Any] = []
        if raw_providers:
            try:
                env_providers = json.loads(raw_providers)
            except json.JSONDecodeError:
                logger.warning("LLM_FALLBACK_PROVIDERS ليس JSON صالحًا؛ تم تجاهله")
                env_providers = []
        if not isinstance(env_providers, list):
            env_providers = []

        for item in [*env_providers, *BUILTIN_FALLBACK_PROVIDERS]:
            if not isinstance(item, dict):
                continue
            base = item.get("base_url")
            model = item.get("model")
            key = item.get("api_key")
            if not key and item.get("api_key_env"):
                key = os.environ.get(str(item["api_key_env"]))
            if not (base and model and key):
                continue
            try:
                candidates.append({
                    "client": OpenAI(api_key=key, base_url=base),
                    "model": model,
                    "label": f"{model} @ {base}",
                    "extra": item.get("extra"),
                })
            except Exception as exc:  # noqa: BLE001
                logger.warning("تعذر تهيئة مزوّد بديل %s: %s", base, exc)

        logger.info(
            "مرشّحو النموذج (%s): %s",
            len(candidates),
            ", ".join(c["label"] for c in candidates),
        )
        return candidates

    def _current_candidate(self) -> Dict[str, Any]:
        index = min(self._candidate_index, len(self._candidates) - 1)
        return self._candidates[index]

    def _advance_candidate(self, reason: str) -> bool:
        """ينتقل للمرشّح التالي؛ يعيد False إذا لم يبقَ بديل."""
        if self._candidate_index >= len(self._candidates) - 1:
            logger.error("لا يوجد نموذج بديل بعد: %s", reason)
            return False
        self._candidate_index += 1
        nxt = self._current_candidate()
        logger.warning("التحويل إلى %s بسبب: %s", nxt["label"], reason[:160])
        return True

    def _create_completion(
        self,
        *,
        messages: List[Dict[str, str]],
        temperature: Optional[float],
        max_tokens: Optional[int],
        response_format: Optional[Dict[str, Any]],
    ) -> Any:
        """Send one raw Chat Completions request through the compatibility layer."""

        # المزوّدون المجانيون يقيّدون الطلبات: حدّ في الدقيقة (TPM) وحدّ يومي
        # (TPD) لكل نموذج. لذلك: ننتظر عند الحدّ اللحظي، وننتقل تلقائيًا إلى
        # نموذج أو مزوّد بديل عند نفاد الحصة اليومية، بدل إسقاط التقرير.
        attempts = 0
        rotations = 0
        guard_messages: List[Dict[str, str]] = []
        while True:
            candidate = self._current_candidate()
            try:
                return create_chat_completion(
                    candidate["client"],
                    model=candidate["model"],
                    messages=[*messages, *guard_messages],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    extra=candidate.get("extra"),
                )
            except Exception as exc:  # noqa: BLE001 - نفحص نوع الخطأ من نصه
                detail = str(exc)
                lowered = detail.lower()

                tool_call_conflict = (
                    "called a tool" in detail
                    or "tool_choice" in detail
                    or "tool call" in lowered
                )
                if tool_call_conflict and attempts < 2:
                    attempts += 1
                    logger.warning(
                        "النموذج نادى أداة مدمجة رغم عدم تمرير أدوات؛ إعادة المحاولة مع تذكير (%s)",
                        attempts,
                    )
                    # نضع التذكير في رسالة النظام الأولى نفسها: بعض النماذج
                    # (gpt-oss) ترفض رسالة system في نهاية المحادثة.
                    merged = [dict(m) for m in messages]
                    if merged and merged[0].get("role") == "system":
                        merged[0]["content"] = f"{merged[0]['content']}\n\n{TOOL_GUARD_MESSAGE}"
                        guard_messages = []
                        messages_to_send = merged
                    else:
                        guard_messages = [{"role": "user", "content": TOOL_GUARD_MESSAGE}]
                        messages_to_send = None
                    if messages_to_send is not None:
                        # إعادة المحاولة فورًا بنسخة معدّلة
                        try:
                            return create_chat_completion(
                                candidate["client"],
                                model=candidate["model"],
                                messages=merged,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                response_format=response_format,
                                extra=candidate.get("extra"),
                            )
                        except Exception:  # noqa: BLE001
                            pass
                    continue

                if tool_call_conflict and rotations < len(self._candidates) + 2:
                    # النموذج يصرّ على نداء أدوات مدمجة → ننتقل إلى نموذج/مزوّد آخر
                    rotations += 1
                    if self._advance_candidate(detail):
                        attempts = 0
                        guard_messages = []
                        continue
                    raise

                if _is_daily_quota_error(exc) and rotations < len(self._candidates) + 2:
                    rotations += 1
                    if self._advance_candidate(detail):
                        attempts = 0
                        guard_messages = []
                        continue
                    raise

                if _is_model_missing_error(exc) and rotations < len(self._candidates) + 2:
                    rotations += 1
                    if self._advance_candidate(detail):
                        attempts = 0
                        guard_messages = []
                        continue
                    raise

                if _is_rate_limit_error(exc):
                    if attempts < 2:
                        attempts += 1
                        wait_seconds = (
                            62
                            if ("413" in detail or "tokens per minute" in lowered)
                            else 20
                        )
                        logger.warning(
                            "حدّ معدّل الطلبات من المزوّد؛ إعادة المحاولة بعد %s ثانية (محاولة %s)",
                            wait_seconds,
                            attempts,
                        )
                        time.sleep(wait_seconds)
                        continue
                    if rotations < len(self._candidates) + 2 and self._advance_candidate(detail):
                        rotations += 1
                        attempts = 0
                        guard_messages = []
                        continue
                    raise

                raise
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式（如JSON模式）
            
        Returns:
            模型响应文本
        """
        response = self._create_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        content = extract_chat_completion_text(response)
        return _clean_chat_text(content)
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: Optional[int] = 4096,
        max_attempts: int = 1,
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回JSON
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            max_attempts: 内容生成尝试次数（不含一次明确的JSON模式能力降级）
            
        Returns:
            解析后的JSON对象
        """
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        response_format: Optional[Dict[str, str]] = {"type": "json_object"}
        request_max_tokens = max_tokens
        last_error: Optional[LLMResponseError] = None

        for attempt in range(1, max_attempts + 1):
            # JSON-mode capability negotiation is separate from content
            # regeneration. An explicit response_format rejection may add one
            # request, but it must not consume a content attempt.
            while True:
                try:
                    response = self._create_completion(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=request_max_tokens,
                        response_format=response_format,
                    )
                except Exception as error:
                    if (
                        response_format is not None
                        and _is_response_format_unsupported(error)
                    ):
                        logger.warning(
                            "LLM provider explicitly rejected response_format; "
                            "retrying once with prompt-only JSON guidance"
                        )
                        response_format = None
                        continue
                    raise
                break

            try:
                return self._parse_json_response(response)
            except LLMResponseError as error:
                last_error = error
                if attempt >= max_attempts:
                    raise

                # A caller-supplied cap is the common cause of a partial JSON
                # object. Omit it for the one bounded retry so the provider can
                # use its model-specific output limit.
                had_token_cap = request_max_tokens is not None
                request_max_tokens = None
                logger.warning(
                    "LLM returned unusable JSON (finish_reason=%s); "
                    "retrying content generation%s",
                    error.finish_reason or "unknown",
                    " without an output token cap" if had_token_cap else "",
                )

        if last_error is not None:  # pragma: no cover - defensive loop guard
            raise last_error
        raise LLMResponseError("LLM did not produce a JSON response")

    @staticmethod
    def _parse_json_response(response: Any) -> Dict[str, Any]:
        choices = getattr(response, "choices", None) or []
        if not choices:
            raise LLMResponseError("LLM returned no choices")

        choice = choices[0]
        finish_reason = getattr(choice, "finish_reason", None)
        if finish_reason == "length":
            raise LLMResponseError(
                "LLM JSON output was truncated at the token limit",
                finish_reason=finish_reason,
            )
        if finish_reason not in {None, "stop"}:
            raise LLMResponseError(
                f"LLM JSON generation stopped unexpectedly ({finish_reason})",
                finish_reason=finish_reason,
            )

        content = _clean_chat_text(extract_chat_completion_text(response))
        if not content:
            raise LLMResponseError(
                "LLM returned empty JSON content",
                finish_reason=finish_reason,
            )

        try:
            value = json.loads(content)
        except json.JSONDecodeError as strict_error:
            # Some compatible providers append a short explanation after an
            # otherwise complete JSON object. Accept only an object decoded
            # from the beginning; never repair or invent truncated JSON.
            try:
                value, end = json.JSONDecoder().raw_decode(content)
            except json.JSONDecodeError:
                raise LLMResponseError(
                    "LLM returned invalid JSON "
                    f"(line {strict_error.lineno}, column {strict_error.colno})",
                    finish_reason=finish_reason,
                ) from strict_error

            trailing = content[end:].strip()
            if trailing:
                if _contains_additional_json_container(trailing):
                    raise LLMResponseError(
                        "LLM returned multiple JSON values",
                        finish_reason=finish_reason,
                    )
                logger.warning("Ignoring text after a complete LLM JSON object")

        if not isinstance(value, dict):
            raise LLMResponseError(
                "LLM JSON response must be a top-level JSON object",
                finish_reason=finish_reason,
            )

        return value
