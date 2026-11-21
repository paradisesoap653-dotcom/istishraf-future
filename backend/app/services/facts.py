"""مراجع الأرقام الموثّقة (الطبقة الأولى من خطة دقة المعلومات).

الفكرة: النموذج لا يكتب الرقم الواقعي بيده، بل يكتب مرجعًا بالشكل ``{{fact:f03}}``،
ويُرقّى المرجع بعد التوليد من مقتطف مسجَّل مع رابط وتاريخ. النموذج لا يستطيع تحريف
رقم لم يكتبه، وأي مرجع لا يقابل مفتاحًا معروفًا يبقى ظاهرًا للقارئ كعلامة خطأ بدل
أن يُملأ برقم مُخترع.

كل الدوال هنا بلا اعتماديات خارجية وبلا Flask، لتُختبر وحدها.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

# {{fact:f01}} — تسمح بمسافات داخل الأقواس، ومفتاح من حروف/أرقام/شرطة/نقطة.
KEY_RE = re.compile(r"\{\{\s*fact\s*:\s*([A-Za-z0-9_.\-]+)\s*\}\}")

MAX_VALUE_CHARS = 220
MAX_FACTS = 12


def _clip(text: Any, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit].strip()


def build_from_bundle(bundle: Optional[Dict[str, Any]], *, limit: int = MAX_FACTS) -> Dict[str, Dict[str, Any]]:
    """يبني مفاتيح ``f01..fn`` من وقائع البحث المحفوظة.

    نأخذ فقط ما له رابط: نتيجة بلا رابط ليست مصدرًا، ومفتاحها سيدفع النموذج
    إلى الكتابة من ذاكرته. ونحفظ المقتطف كما هو لأن عليه يقوم التحقق الحرفي
    لاحقًا (claim_check).
    """
    if not bundle:
        return {}
    topic = bundle.get("topic") or {}
    items: List[Dict[str, Any]] = []
    items.extend(topic.get("facts") or [])
    items.extend(topic.get("news") or [])

    facts: Dict[str, Dict[str, Any]] = {}
    for item in items:
        url = _clip(item.get("url"), 300)
        snippet = _clip(item.get("snippet"), MAX_VALUE_CHARS)
        if not url or not snippet:
            continue
        key = f"f{len(facts) + 1:02d}"
        facts[key] = {
            "value": snippet,
            "quote": snippet,
            "title": _clip(item.get("title"), 160),
            "url": url,
            "publisher": _clip(item.get("source"), 80),
            "date": _clip(item.get("date"), 40),
        }
        if len(facts) >= limit:
            break
    return facts


def prompt_block(facts: Dict[str, Dict[str, Any]]) -> str:
    """كتلة تُحقن في برومبت التقرير: المفاتيح المتاحة + القاعدة الصارمة."""
    if not facts:
        return ""
    lines = [
        "## مفاتيح أرقام موثّقة (إلزامية عند ذكر أي رقم واقعي)",
        "لا تكتب أي رقم واقعي بنفسك. اكتب مكانه المرجع فقط، مثال: «استثمرت {{fact:f01}}».",
        "كل مرجع لا يظهر في القائمة أدناه سيُترك ظاهرًا في التقرير كخطأ.",
    ]
    for key, fact in facts.items():
        meta = " — ".join(part for part in (fact.get("publisher"), fact.get("date")) if part)
        lines.append(f"- {{{{{key}}}}} = {fact['value']}" + (f" [{meta}]" if meta else ""))
    return "\n".join(lines)


def render(text: str, facts: Dict[str, Dict[str, Any]]) -> Tuple[str, List[str], List[str]]:
    """يستبدل المراجع بقيمها. يعيد (النص، المفاتيح المستخدمة، المفاتيح المفقودة)."""
    used: List[str] = []
    missing: List[str] = []

    def _sub(match: re.Match) -> str:
        key = match.group(1)
        fact = facts.get(key)
        if not fact:
            missing.append(key)
            return match.group(0)
        if key not in used:
            used.append(key)
        return fact["value"]

    rendered = KEY_RE.sub(_sub, text or "")
    return rendered, used, missing


def sources_block(facts: Dict[str, Dict[str, Any]], used: Iterable[str]) -> str:
    """قائمة مصادر مختصرة للـPDF: الرابط والتاريخ لكل رقم استُخدم فعلًا."""
    rows: List[str] = []
    for index, key in enumerate(used, start=1):
        fact = facts.get(key) or {}
        meta = "، ".join(part for part in (fact.get("publisher"), fact.get("date")) if part)
        rows.append(f"{index}. [{key}] {fact.get('url', '')}" + (f" ({meta})" if meta else ""))
    if not rows:
        return ""
    return "### مصادر الأرقام\n" + "\n".join(rows)


def unresolved_keys(text: str) -> List[str]:
    """المراجع التي بقيت في النص بعد الترقية (يجب أن تكون صفرًا)."""
    return [match.group(1) for match in KEY_RE.finditer(text or "")]


def load_for_simulation(simulation_id: str) -> Dict[str, Dict[str, Any]]:
    """مفاتيح محاكاة معيّنة: ملف محفوظ إن وُجد، وإلا تُبنى من وقائع بحثها."""
    if not simulation_id:
        return {}
    try:
        from ..models import storage

        saved = storage.read_json_fresh(f"simulations/{simulation_id}/facts.json") or {}
        if isinstance(saved, dict) and saved.get("facts"):
            return saved["facts"]
    except Exception:  # noqa: BLE001 - الحفظ اختياري، وغيابه لا يُفشل التقرير
        pass

    try:
        from . import web_research

        bundle = web_research.load(f"simulations/{simulation_id}") or web_research.load(simulation_id)
    except Exception:  # noqa: BLE001
        return {}
    return build_from_bundle(bundle)
