"""محاكاة سيناريو مقارن.

الفكرة: بدل إعادة محاكاة كاملة من الصفر عند تعديل افتراض واحد، نعيد تشغيل
جولات قليلة على **نفس** الوكلاء ونفس السياق بعد التغيير المطلوب، ثم نقارن
المؤشرات مع الوقائع الأصلية.

كل الأرقام المقارنة تُحسب من وقائع المحاكاة نفسها (ملفات actions.jsonl)
وليس من كلام النموذج؛ ما يكتبه النموذج يُعرض بوسم «قراءة تحليلية (استنتاج)».
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..config import Config
from ..models import storage
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from . import platform_inputs
from . import platforms as platform_registry

logger = get_logger('mirofish.scenario')

SCENARIOS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'scenarios')
MAX_ROUNDS = 3
MIN_ROUNDS = 1
MAX_CHANGE_LEN = 400

# كلمات مؤشر النبرة (تقريبي، شفاف للمستخدم)
_SUPPORT_WORDS = (
    'أؤيد', 'مؤيد', 'موافق', 'أوافق', 'ممتاز', 'جيد', 'مفيد', 'إيجابي',
    'تأييد', 'مناسب', 'مقبول', 'قبول', 'حل', 'نجاح', 'مرحب', 'مشجع', 'أحب',
    'رضا', 'ارتياح', 'تحسن', 'دعم', 'إشادة', 'ثقة', 'مرونة', 'تحسين', 'إقبال',
)
_SKEPTIC_WORDS = (
    'لكن', 'مخاوف', 'خوف', 'رفض', 'سيئ', 'خطر', 'مشكلة', 'سلبي', 'انتقاد',
    'تحفظ', 'استغلال', 'شكوى', 'تذمر', 'غير مقبول', 'غاضب', 'احتجاج',
    'مطالب', 'قلق', 'تحذير', 'سخط', 'عدم رضا', 'تأخير', 'انهيار', 'فوضى',
)


class ScenarioError(Exception):
    """خطأ قابل للعرض للمستخدم بالعربية."""


# ---------------------------------------------------------------- helpers

def _sim_dir(simulation_id: str) -> str:
    return os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    """يقرأ ملف jsonl من التخزين الدائم (يعيد [] إن لم يوجد)."""
    try:
        if not storage.exists(path):
            return []
        local = storage.ensure_local(path)
        out: List[Dict[str, Any]] = []
        with open(local, 'r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict) and not item.get('event_type'):
                    out.append(item)
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning('تعذر قراءة %s: %s', path, exc)
        return []


def discover_platforms(simulation_id: str) -> List[str]:
    """المنصّات التي جرت عليها المحاكاة فعلًا (بقراءة ملف أفعال كل منصّة).

    السيناريو **يجب** أن يستخدم نفس المجموعة، وإلا صارت المقارنة بين وضعين
    مختلفين لا بين افتراضين. لا نعتمد على سرد المجلدات لأن التخزين الدائم
    مِلفّي لا شجري (Vercel + Neon)، فنفحص كل منصّة معروفة على حدة.
    """
    base = _sim_dir(simulation_id)
    found: List[str] = []
    candidates = list(platform_registry.ORDER)
    try:
        local = storage.ensure_local(base)
        if os.path.isdir(local):
            for entry in sorted(os.listdir(local)):
                if entry not in candidates:
                    candidates.append(entry)
    except Exception:  # noqa: BLE001
        pass

    for plat in candidates:
        try:
            if storage.exists(os.path.join(base, plat, 'actions.jsonl')):
                found.append(plat)
        except Exception:  # noqa: BLE001
            continue
    if found:
        ordered = [p for p in platform_registry.ORDER if p in found]
        ordered += [p for p in found if p not in ordered]
        return ordered
    # تقارير قديمة: ملف أفعال واحد بلا مجلدات منصّات
    try:
        if storage.exists(os.path.join(base, 'actions.jsonl')):
            return ['twitter', 'reddit']
    except Exception:  # noqa: BLE001
        pass
    return []

def load_run_actions(simulation_id: str) -> List[Dict[str, Any]]:
    """وقائع المحاكاة المنشورة على كل منصّاتها."""
    base = _sim_dir(simulation_id)
    actions: List[Dict[str, Any]] = []
    for plat in discover_platforms(simulation_id):
        actions.extend(_read_jsonl(os.path.join(base, plat, 'actions.jsonl')))
    return actions


def _tone(text: str) -> str:
    t = text or ''
    support = sum(1 for w in _SUPPORT_WORDS if w in t)
    skeptic = sum(1 for w in _SKEPTIC_WORDS if w in t)
    if support > skeptic:
        return 'support'
    if skeptic > support:
        return 'skeptic'
    return 'neutral'


def compute_metrics(actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """مؤشرات موضوعية تُحسب من الوقائع نفسها (وليس من تقدير النموذج)."""
    posts = [a for a in actions if (a.get('action_type') or '').upper() == 'CREATE_POST']
    comments = [a for a in actions if (a.get('action_type') or '').upper() == 'CREATE_COMMENT']
    participants = {a.get('agent_id') for a in actions if a.get('agent_id') is not None}
    rounds = {a.get('round') for a in actions if a.get('round') is not None}
    platforms: Dict[str, int] = {}
    for a in actions:
        p = a.get('platform') or 'other'
        platforms[p] = platforms.get(p, 0) + 1

    texts = []
    for a in actions:
        args = a.get('action_args') or {}
        content = args.get('content') if isinstance(args, dict) else None
        if content:
            texts.append(str(content))
    tones = [_tone(t) for t in texts]
    total_texts = len(tones) or 1

    def pct(n: int) -> float:
        return round(100.0 * n / total_texts, 1)

    n_rounds = len(rounds) or 1

    def per_round(n: int) -> float:
        return round(n / n_rounds, 1)

    return {
        'interactions': len(actions),
        'interactions_per_round': per_round(len(actions)),
        'posts_per_round': per_round(len(posts)),
        'comments_per_round': per_round(len(comments)),
        'posts': len(posts),
        'comments': len(comments),
        'agents': len(participants),
        'rounds': len(rounds),
        'platforms': platforms,
        'support_pct': pct(tones.count('support')),
        'skeptic_pct': pct(tones.count('skeptic')),
        'neutral_pct': pct(tones.count('neutral')),
        'texts': total_texts if tones else 0,
    }


def _normalize_llm_actions(rounds_data: List[Dict[str, Any]],
                            allowed: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r_idx, r_item in enumerate(rounds_data, start=1):
        if not isinstance(r_item, dict):
            continue
        for act in (r_item.get('actions') or []):
            if not isinstance(act, dict):
                continue
            allowed_set = allowed or ['twitter', 'reddit']
            raw_platform = str(act.get('platform') or '').strip().lower()
            raw_platform = {'x': 'twitter', 'fb': 'facebook'}.get(raw_platform, raw_platform)
            if raw_platform in allowed_set:
                platform = raw_platform
            else:
                # منصّة غير موجودة في المحاكاة الأصلية: نضعها على منصّة مسموحة
                # بالتناوب بدل حشرها كلها في تويتر.
                platform = allowed_set[len(out) % len(allowed_set)]
            out.append({
                'round': r_item.get('round') or r_idx,
                'platform': platform,
                'agent_id': act.get('agent_id'),
                'action_type': (act.get('action_type') or 'CREATE_POST').upper(),
                'action_args': {'content': act.get('content') or ''},
            })
    return out


# ---------------------------------------------------------------- run

_PROMPT = """أنت محرك محاكاة اجتماعية متعدد الوكلاء في منصة «استشراف المستقبل».

الطلب الأصلي الذي شُغّلت عليه المحاكاة:
{requirement}

السياق السردي:
{narrative}

الوكلاء المشاركون:
{agents}

نتائج المحاكاة الأصلية (باختصار):
{baseline}

{research_block}

المطلوب الآن: **سيناريو بديل** — أعد تشغيل {rounds} جولتين/جولات على نفس هؤلاء الوكلاء،
مع تطبيق هذا التغيير على الافتراضات:
«{change}»

اكتب تفاعلات واقعية ومتنوعة (تأييد، تحفظ، أرقام، مقترحات عملية) تُظهر أثر التغيير
على سلوك الناس. غيّر ما يتغيّر فعلًا بسبب التغيير، ولا تكرر النص الأصلي حرفيًا.

قواعد إلزامية:
- اللغة: العربية الفصحى المبسطة في كل محتوى الفعل والتحليل. لا تكتب أي جملة
  بالإنجليزية (يجوز أسماء الأعلام والأرقام والرموز فقط).
- عدد الجولات: {rounds} بالضبط، ولكل جولة ٤ إلى ٦ أفعال.
- المنصّات المسموحة (نفس منصّات المحاكاة الأصلية): {platform_list}.
  لا تخترع منصّة أخرى، واحترم طبيعة كل منصّة في شكل المحتوى:
{platform_rules}
- لا تجعل كل الأفعال على منصّة واحدة: استخدم منصّتين على الأقل في كل جولة.
{inputs_block}
{culture_block}
- امزج بين "CREATE_POST" و"CREATE_COMMENT" في كل جولة (لا تجعلها منشورات فقط).
- استخدم agent_id من قائمة الوكلاء أعلاه فقط.

أعد JSON فقط بهذا الشكل:
{{"rounds": [{{"round": 1, "actions": [{{"agent_id": 0, "platform": "{example_platform}", "action_type": "CREATE_POST", "content": "..."}}]}}],
  "analysis": "قراءة تحليلية قصيرة (٣ إلى ٥ أسطر) للفرق بين السيناريو والوضع الأصلي"}}"""


def _culture_block(config: Dict[str, Any]) -> str:
    """طبقة الروح السودانية في السيناريو (تُهمَل بهدوء إن تعذّرت)."""
    try:
        from . import sudanese_culture

        requirement = (config or {}).get('simulation_requirement') or ''
        return sudanese_culture.prompt_block(requirement)
    except Exception:  # noqa: BLE001
        return ''


def _research_block(sim_dir: str) -> str:
    """وقائع بحث الويب المحفوظة مع المحاكاة — لتظلّ المقارنة على الموضوع نفسه."""
    try:
        from . import web_research

        bundle = web_research.load(sim_dir)
        block = web_research.prompt_block(bundle, max_facts=6)
        return block
    except Exception:  # noqa: BLE001
        return ''


def _run_llm(simulation_id: str, change: str, rounds: int,
             baseline: Dict[str, Any],
             allowed: Optional[List[str]] = None) -> Dict[str, Any]:
    sim_dir = _sim_dir(simulation_id)
    config_path = os.path.join(sim_dir, 'simulation_config.json')
    config: Dict[str, Any] = {}
    try:
        if storage.exists(config_path):
            raw = storage.read_text(config_path)
            config = json.loads(raw) if raw else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning('تعذر قراءة إعدادات المحاكاة: %s', exc)

    profiles: List[Dict[str, Any]] = []
    profiles_path = os.path.join(sim_dir, 'reddit_profiles.json')
    try:
        if storage.exists(profiles_path):
            raw = storage.read_text(profiles_path)
            loaded = json.loads(raw) if raw else []
            if isinstance(loaded, list):
                profiles = loaded
    except Exception as exc:  # noqa: BLE001
        logger.warning('تعذر قراءة ملفات الوكلاء: %s', exc)

    agents = [
        {
            'agent_id': int(p.get('user_id', idx)) if str(p.get('user_id', idx)).isdigit() else idx,
            'name': p.get('name') or p.get('username') or f'وكيل {idx}',
            'persona': (p.get('persona') or p.get('bio') or '')[:160],
        }
        for idx, p in enumerate(profiles[:16])
    ] or [{'agent_id': 0, 'name': 'وكيل 0', 'persona': ''}]

    allowed = list(allowed or ['twitter', 'reddit'])
    for idx, agent in enumerate(agents):
        agent['primary_platform'] = platform_registry.preferred_for(idx, allowed)

    baseline_txt = json.dumps(
        {k: baseline.get(k) for k in ('interactions', 'posts', 'comments', 'agents',
                                      'support_pct', 'skeptic_pct')},
        ensure_ascii=False,
    )

    prompt = _PROMPT.format(
        requirement=config.get('simulation_requirement') or '—',
        narrative=(config.get('event_config') or {}).get('narrative_direction') or '—',
        agents=json.dumps(agents, ensure_ascii=False),
        baseline=baseline_txt,
        rounds=rounds,
        change=change,
        platform_list='، '.join(f'"{p}" ({platform_registry.label(p)})' for p in allowed),
        platform_rules=platform_registry.prompt_block(allowed),
        inputs_block=platform_inputs.prompt_block(
            platform_inputs.load(simulation_id), allowed, rounds * 6
        ) or '',
        culture_block=_culture_block(config),
        research_block=_research_block(sim_dir),
        example_platform=(allowed[0] if allowed else 'facebook'),
    )

    llm = LLMClient()
    resp = llm.chat_json(
        messages=[
            {'role': 'system', 'content': 'أجب بـ JSON صالح فقط يمثل وقائع المحاكاة.'},
            {'role': 'user', 'content': prompt},
        ],
        temperature=0.75,
    )
    if not isinstance(resp, dict):
        raise ScenarioError('لم يصل رد صالح من محرك المحاكاة، حاول مرة أخرى.')
    return resp


def _arabic_ratio(texts: List[str]) -> float:
    """نسبة الأحرف العربية من كل الأحرف الهجائية: كشف لخروج الناتج بلغة أخرى."""
    arabic = latin = 0
    for text in texts:
        for ch in text or '':
            code = ord(ch)
            if 0x0600 <= code <= 0x06FF:
                arabic += 1
            elif ('a' <= ch <= 'z') or ('A' <= ch <= 'Z'):
                latin += 1
    total = arabic + latin
    return (arabic / total) if total else 1.0


def _content_texts(actions: List[Dict[str, Any]]) -> List[str]:
    return [
        str((a.get('action_args') or {}).get('content') or '')
        for a in actions
    ]


def _markdown(payload: Dict[str, Any]) -> str:
    """نسخة قابلة للتحميل بصيغ التقرير نفسها."""
    old = payload['baseline']
    new = payload['scenario']
    rows = [
        ('تفاعلات لكل جولة', old.get('interactions_per_round'), new.get('interactions_per_round')),
        ('منشورات لكل جولة', old.get('posts_per_round'), new.get('posts_per_round')),
        ('تعليقات لكل جولة', old.get('comments_per_round'), new.get('comments_per_round')),
        ('الوكلاء المشاركون', old['agents'], new['agents']),
        ('نبرة مؤيدة %', old['support_pct'], new['support_pct']),
        ('نبرة متحفظة %', old['skeptic_pct'], new['skeptic_pct']),
    ]
    lines = [
        f"# سيناريو مقارن — {payload.get('change', '')}",
        '',
        f"التقرير الأصلي: {payload.get('report_id', '')} · جولات السيناريو: {payload.get('rounds', '')}",
        f"المنصّات (نفس منصّات المحاكاة الأصلية): {platform_registry.labels(payload.get('platforms') or [])}",
    ]
    inputs_line = platform_inputs.summary_line(
        payload.get('platform_inputs') or {}, payload.get('platforms') or []
    )
    if inputs_line:
        lines.append(f"أرقام مقدَّمة من صاحب المشروع (مدخل): {inputs_line}")
    lines += [
        '',
        '## المؤشرات (محسوبة من وقائع المحاكاة)',
        '',
    ]
    # سطور بدل جدول الأنابيب: العربية في الجداول النصية تُقرأ مقلوبة في بعض
    # القارئات، والسطر الواحد واضح في Markdown وWord وPDF على السواء.
    for label, a, b in rows:
        try:
            diff = round(float(b) - float(a), 1)
            diff_txt = f"+{diff}" if diff > 0 else f"{diff}"
        except (TypeError, ValueError):
            diff_txt = '—'
        lines.append(f"- **{label}**: الأصل {a} — السيناريو {b} (الفرق {diff_txt})")

    # توزيع الأفعال على المنصّات: يوضّح أن المقارنة جرت على نفس المجموعة
    old_plats = old.get('platforms') or {}
    new_plats = new.get('platforms') or {}
    if old_plats or new_plats:
        keys = [p for p in platform_registry.ORDER if p in old_plats or p in new_plats]
        keys += [p for p in set(old_plats) | set(new_plats) if p not in keys]
        for key in keys:
            lines.append(
                f"- **أفعال {platform_registry.label(key)}**: الأصل {old_plats.get(key, 0)}"
                f" — السيناريو {new_plats.get(key, 0)}"
            )

    lines += [
        '',
        '## التغيير المطبَّق',
        '',
        payload.get('change', ''),
        '',
        '## قراءة تحليلية (استنتاج)',
        '',
        payload.get('analysis') or '—',
        '',
        '> الأرقام أعلاه محسوبة من وقائع المحاكاة. القراءة التحليلية استنتاج من النموذج وليست قياسًا.',
    ]
    return '\n'.join(lines)


def run_and_compare(report_id: str, simulation_id: str, change: str,
                    rounds: int = 2) -> Dict[str, Any]:
    """يشغّل السيناريو ويحفظه ويعيد نتيجة المقارنة كاملة."""
    change = (change or '').strip()
    if not change:
        raise ScenarioError('اكتب التغيير المطلوب أولًا.')
    if len(change) > MAX_CHANGE_LEN:
        change = change[:MAX_CHANGE_LEN]

    rounds = max(MIN_ROUNDS, min(int(rounds or 2), MAX_ROUNDS))

    baseline_actions = load_run_actions(simulation_id)
    if not baseline_actions:
        raise ScenarioError('لا توجد وقائع محاكاة محفوظة لهذا التقرير، فلا يمكن المقارنة.')

    baseline = compute_metrics(baseline_actions)
    allowed = discover_platforms(simulation_id)

    resp: Dict[str, Any] = {}
    actions: List[Dict[str, Any]] = []
    # محاولتان كحد أقصى: النموذج يخرج أحيانًا بالإنجليزية رغم التعليمات،
    # والمنصة عربية بالكامل، فلا نقبل نتيجة غير عربية.
    for attempt in range(2):
        resp = _run_llm(simulation_id, change, rounds, baseline, allowed)
        rounds_data = resp.get('rounds') if isinstance(resp.get('rounds'), list) else []
        actions = _normalize_llm_actions(rounds_data, allowed)
        texts = _content_texts(actions) + [str(resp.get('analysis') or '')]
        if actions and _arabic_ratio(texts) >= 0.5:
            break
        logger.warning('السيناريو خرج بغير العربية (محاولة %s)', attempt + 1)
        actions = []

    if not actions:
        raise ScenarioError('لم يخرج السيناريو بالعربية، حاول مرة أخرى أو أعد صياغة التغيير.')

    scenario_metrics = compute_metrics(actions)

    payload = {
        'scenario_id': 'scn_' + uuid.uuid4().hex[:12],
        'report_id': report_id,
        'simulation_id': simulation_id,
        'change': change,
        'rounds': rounds,
        'platforms': allowed,
        'platform_inputs': platform_inputs.load(simulation_id),
        'status': 'completed',
        'baseline': baseline,
        'scenario': scenario_metrics,
        'analysis': (resp.get('analysis') or '').strip(),
        'samples': [
            {
                'agent': a.get('agent_id'),
                'platform': a.get('platform'),
                'type': a.get('action_type'),
                'content': (a.get('action_args') or {}).get('content', '')[:400],
            }
            for a in actions[:12]
        ],
        'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    payload['markdown'] = _markdown(payload)
    save_scenario(payload)
    return payload


# ---------------------------------------------------------------- storage

def _scenario_path(report_id: str, scenario_id: str) -> str:
    return os.path.join(SCENARIOS_DIR, report_id, f'{scenario_id}.json')


def save_scenario(payload: Dict[str, Any]) -> None:
    try:
        storage.write_json(
            _scenario_path(payload['report_id'], payload['scenario_id']), payload
        )
    except Exception as exc:  # noqa: BLE001
        # عدم الحفظ لا يُفشل التجربة؛ النتيجة تُعرض الآن وتُفقد لاحقًا فقط.
        logger.warning('تعذر حفظ السيناريو: %s', exc)


def list_scenarios(report_id: str) -> List[Dict[str, Any]]:
    folder = os.path.join(SCENARIOS_DIR, report_id)
    out: List[Dict[str, Any]] = []
    try:
        if not storage.exists(folder):
            return out
        for name in storage.listdir(folder):
            if not name.endswith('.json'):
                continue
            try:
                data = storage.read_json(os.path.join(folder, name))
            except Exception:  # noqa: BLE001
                continue
            if isinstance(data, dict):
                data.pop('markdown', None)
                out.append(data)
    except Exception as exc:  # noqa: BLE001
        logger.warning('تعذر سرد السيناريوهات: %s', exc)
    out.sort(key=lambda item: item.get('created_at') or '', reverse=True)
    return out


def get_scenario(report_id: str, scenario_id: str) -> Optional[Dict[str, Any]]:
    try:
        data = storage.read_json(_scenario_path(report_id, scenario_id))
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- suggestions

_SUGGEST_PROMPT = """أنت مساعد في منصة «استشراف المستقبل».

موضوع الدراسة/التقرير:
{requirement}

ما يجري فعلًا حول هذا الموضوع (بحث ويب حديث):
{research}

أهم ما تكلّم عنه الناس في المحاكاة:
{hot}

اقترح {count} تغييرات افتراضية **تخصّ هذا الموضوع نفسه** بحيث يمكن اختبار أثرها
بمحاكاة قصيرة على نفس الوكلاء. لكل اقتراح:
- «change»: جملة واحدة قصيرة (حتى ٩٠ حرفًا) تصف التغيير بدقة، كأنها افتراض قابل للقياس
  (مثال صحيح لموضوع عمولة: «خفض العمولة من ١٠٪ إلى ٥٪»).
- «why»: سطر واحد يوضح ما الذي سيتغيّر في سلوك الناس إن طبّقنا هذا الافتراض.

شروط:
- لا تقترح أشياء عامة لا علاقة لها بالموضوع (مثل «زيادة الوعي» إن كان الموضوع سعرًا).
- لا تكرّر الاقتراح نفسه بصيغتين.
- العربية فقط، بلا أي حرف لاتيني إلا الأرقام والرموز.

أعد JSON فقط:
{{"suggestions": [{{"change": "...", "why": "..."}}]}}"""


def _hot_topics(config: Dict[str, Any], bundle: Optional[Dict[str, Any]]) -> str:
    bits: List[str] = []
    events = (config.get('event_config') or {})
    for key in ('hot_topics',):
        value = events.get(key)
        if isinstance(value, list) and value:
            bits.extend(str(v) for v in value[:6])
    narrative = events.get('narrative_direction')
    if narrative:
        bits.append(str(narrative)[:160])
    if bundle:
        for fact in ((bundle.get('topic') or {}).get('facts') or [])[:4]:
            title = (fact.get('title') or '').strip()
            if title:
                bits.append(title[:120])
    return '\n'.join(f'- {b}' for b in bits) or '—'


_LEADIN = (
    'توقعات مستقبلية حول', 'توقعات حول', 'دراسة حول', 'دراسة عن', 'تحليل حول',
    'محاكاة حول', 'محاكاة عن', 'تأثير', 'قياس', 'استشراف', 'بحث عن', 'بحث حول',
)


def _short_subject(requirement: str) -> str:
    """يستخرج موضوعًا قصيرًا من نص الطلب بدل نسخ الجملة كلها مقطوعة."""
    text = (requirement or '').strip().split('\n')[0]
    for sep in ('。', '.', '؟', '?'):
        if sep in text:
            text = text.split(sep)[0]
    for lead in _LEADIN:
        if text.startswith(lead):
            text = text[len(lead):].strip(' :：-—')
            break
    words = text.split()
    short = ' '.join(words[:5]).strip(' «»"')
    return short[:60] if short else 'الموضوع'


def _fallback_suggestions(requirement: str, hot_topics: List[str] | None = None) -> List[Dict[str, str]]:
    """اقتراحات بديلة عند تعذّر النموذج — من موضوع الدراسة أو من كلمات النقاش نفسها."""
    topics = [str(t).strip() for t in (hot_topics or []) if str(t).strip()]
    if topics:
        first = topics[0][:40]
        second = (topics[1] if len(topics) > 1 else first)[:40]
        return [
            {
                'change': f'ماذا لو زاد «{first}» بشكل واضح خلال شهر؟',
                'why': 'نرى هل يتحوّل النقاش إلى غضب أم يبقى شكوى متفرقة.',
            },
            {
                'change': f'ماذا لو خفّ «{second}» بعد قرار أو حملة رسمية؟',
                'why': 'نرى هل يهدأ الناس أم يظهر شكّ في جدّية القرار.',
            },
            {
                'change': f'ماذا لو ظهر عامل جديد يفاقم «{first}» عند الشباب؟',
                'why': 'نرى من يحمل العبء الأكبر ومن يتحرّك أولًا.',
            },
        ]
    subject = _short_subject(requirement)
    return [
        {
            'change': f'تشديد في «{subject}»: قيود أو تكلفة أعلى على الناس',
            'why': 'نرى هل يزيد التحفظ والغضب أم يتكيّف الناس.',
        },
        {
            'change': f'تخفيف في «{subject}»: تسهيل وتكلفة أقل',
            'why': 'نرى هل يزيد التأييد والاستخدام أم يبقى الشك.',
        },
        {
            'change': f'حملة توعية واسعة حول «{subject}»',
            'why': 'نرى هل يتغيّر فهم الناس للموضوع وحدّة كلامهم.',
        },
    ]


def suggest_changes(report_id: str, simulation_id: str, count: int = 3) -> Dict[str, Any]:
    """اقتراحات تغييرات جاهزة للتجربة، مشتقّة من موضوع التقرير لا من قالب ثابت."""
    count = max(2, min(int(count or 3), 4))
    sim_dir = _sim_dir(simulation_id)
    config: Dict[str, Any] = {}
    try:
        raw = storage.read_text(os.path.join(sim_dir, 'simulation_config.json'))
        if raw:
            config = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning('تعذر قراءة إعدادات المحاكاة للاقتراحات: %s', exc)

    requirement = (config.get('simulation_requirement') or '').strip()
    if not requirement:
        try:
            from .report_agent import ReportManager

            report = ReportManager.get_report(report_id)
            requirement = (getattr(report, 'simulation_requirement', '') or '').strip()
        except Exception:  # noqa: BLE001
            requirement = ''

    bundle = None
    try:
        from . import web_research

        bundle = web_research.load(sim_dir)
    except Exception:  # noqa: BLE001
        bundle = None

    research_bits = ''
    if bundle:
        try:
            from . import web_research

            research_bits = web_research.prompt_block(bundle, max_facts=5)
        except Exception:  # noqa: BLE001
            research_bits = ''

    suggestions: List[Dict[str, str]] = []
    try:
        llm = LLMClient()
        resp = llm.chat_json(
            messages=[
                {'role': 'system', 'content': 'أجب بـ JSON صالح فقط.'},
                {'role': 'user', 'content': _SUGGEST_PROMPT.format(
                    requirement=requirement or '—',
                    research=research_bits or 'لا توجد وقائع بحث متاحة.',
                    hot=_hot_topics(config, bundle),
                    count=count,
                )},
            ],
            temperature=0.7,
        )
        raw_items = (resp or {}).get('suggestions') if isinstance(resp, dict) else None
        if isinstance(raw_items, list):
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                change = str(item.get('change') or '').strip()[:120]
                if not change:
                    continue
                latin = sum(1 for ch in change if ch.isascii() and ch.isalpha())
                if latin and latin > max(3, len(change) * 0.2):
                    continue  # اقتراح غير عربي
                if any(change == existing['change'] for existing in suggestions):
                    continue
                suggestions.append({
                    'change': change,
                    'why': str(item.get('why') or '').strip()[:160],
                })
    except Exception as exc:  # noqa: BLE001
        logger.warning('تعذر توليد اقتراحات السيناريو: %s', exc)

    hot_list: List[str] = []
    try:
        events = (config.get('event_config') or {})
        if isinstance(events.get('hot_topics'), list):
            hot_list = [str(x) for x in events['hot_topics'] if str(x).strip()]
    except Exception:  # noqa: BLE001
        hot_list = []

    from_model = bool(suggestions)
    for item in _fallback_suggestions(requirement, hot_list):
        if len(suggestions) >= count:
            break
        if any(item['change'] == existing['change'] for existing in suggestions):
            continue
        suggestions.append(item)

    return {
        'requirement': requirement,
        'suggestions': suggestions[:count],
        'from_model': from_model,
        'research': bool(research_bits),
    }
