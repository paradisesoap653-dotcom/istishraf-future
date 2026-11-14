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

logger = get_logger('mirofish.scenario')

SCENARIOS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'scenarios')
MAX_ROUNDS = 3
MIN_ROUNDS = 1
MAX_CHANGE_LEN = 400

# كلمات مؤشر النبرة (تقريبي، شفاف للمستخدم)
_SUPPORT_WORDS = (
    'أؤيد', 'مؤيد', 'موافق', 'أوافق', 'ممتاز', 'جيد', 'مفيد', 'إيجابي',
    'تأييد', 'مناسب', 'مقبول', 'حل', 'نجاح', 'مرحب', 'مشجع', 'أحب',
)
_SKEPTIC_WORDS = (
    'لكن', 'مخاوف', 'خوف', 'رفض', 'سيئ', 'خطر', 'مشكلة', 'سلبي', 'انتقاد',
    'تحفظ', 'استغلال', 'شكوى', 'تذمر', 'غير مقبول', 'غاضب', 'احتجاج',
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


def load_run_actions(simulation_id: str) -> List[Dict[str, Any]]:
    """وقائع المحاكاة المنشورة (twitter + reddit)."""
    base = _sim_dir(simulation_id)
    actions: List[Dict[str, Any]] = []
    for plat in ('twitter', 'reddit'):
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

    return {
        'interactions': len(actions),
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


def _normalize_llm_actions(rounds_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r_idx, r_item in enumerate(rounds_data, start=1):
        if not isinstance(r_item, dict):
            continue
        for act in (r_item.get('actions') or []):
            if not isinstance(act, dict):
                continue
            out.append({
                'round': r_item.get('round') or r_idx,
                'platform': act.get('platform') or 'twitter',
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

المطلوب الآن: **سيناريو بديل** — أعد تشغيل {rounds} جولتين/جولات على نفس هؤلاء الوكلاء،
مع تطبيق هذا التغيير على الافتراضات:
«{change}»

اكتب تفاعلات واقعية ومتنوعة (تأييد، تحفظ، أرقام، مقترحات عملية) تُظهر أثر التغيير
على سلوك الناس. غيّر ما يتغيّر فعلًا بسبب التغيير، ولا تكرر النص الأصلي حرفيًا.

أعد JSON فقط بهذا الشكل:
{{"rounds": [{{"round": 1, "actions": [{{"agent_id": 0, "platform": "twitter", "action_type": "CREATE_POST", "content": "..."}}]}}],
  "analysis": "قراءة تحليلية قصيرة (٣ إلى ٥ أسطر) للفرق بين السيناريو والوضع الأصلي"}}"""


def _run_llm(simulation_id: str, change: str, rounds: int,
             baseline: Dict[str, Any]) -> Dict[str, Any]:
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
        for idx, p in enumerate(profiles[:12])
    ] or [{'agent_id': 0, 'name': 'وكيل 0', 'persona': ''}]

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


def _markdown(payload: Dict[str, Any]) -> str:
    """نسخة قابلة للتحميل بصيغ التقرير نفسها."""
    old = payload['baseline']
    new = payload['scenario']
    rows = [
        ('عدد التفاعلات', old['interactions'], new['interactions']),
        ('عدد المنشورات', old['posts'], new['posts']),
        ('عدد التعليقات', old['comments'], new['comments']),
        ('الوكلاء المشاركون', old['agents'], new['agents']),
        ('نبرة مؤيدة %', old['support_pct'], new['support_pct']),
        ('نبرة متحفظة %', old['skeptic_pct'], new['skeptic_pct']),
    ]
    lines = [
        f"# سيناريو مقارن — {payload.get('change', '')}",
        '',
        f"التقرير الأصلي: `{payload.get('report_id', '')}` · "
        f"جولات السيناريو: {payload.get('rounds', '')}",
        '',
        '## المؤشرات (محسوبة من وقائع المحاكاة)',
        '',
        '| المؤشر | الوضع الأصلي | السيناريو | الفرق |',
        '|---|---|---|---|',
    ]
    for label, a, b in rows:
        try:
            diff = round(float(b) - float(a), 1)
            diff_txt = f"{'+' if diff > 0 else ''}{diff}"
        except (TypeError, ValueError):
            diff_txt = '—'
        lines.append(f'| {label} | {a} | {b} | {diff_txt} |')

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
    resp = _run_llm(simulation_id, change, rounds, baseline)

    rounds_data = resp.get('rounds') if isinstance(resp.get('rounds'), list) else []
    actions = _normalize_llm_actions(rounds_data)
    if not actions:
        raise ScenarioError('لم تُنتج المحاكاة تفاعلات كافية لهذا السيناريو، حاول بصياغة أخرى.')

    scenario_metrics = compute_metrics(actions)

    payload = {
        'scenario_id': 'scn_' + uuid.uuid4().hex[:12],
        'report_id': report_id,
        'simulation_id': simulation_id,
        'change': change,
        'rounds': rounds,
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
