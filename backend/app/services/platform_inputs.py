"""أرقام المستخدم الحقيقية لكل منصّة.

الفكرة: المحاكاة تعرف سلوك كل منصّة (فيسبوك/واتساب/تيك توك/تويتر) لكنها لا تعرف
حجم جمهور صاحب المشروع. عندما يُدخل أرقامه الحقيقية (متابعو الصفحة، أعضاء
المجموعات، متوسط مشاهدات تيك توك…) تتحوّل هذه القيم من «افتراض» إلى «مدخل»،
وتُستخدم كأوزان توزّع الأفعال بين المنصّات في المحاكاة والسيناريو.

القاعدة الحاكمة: لا نختلق رقمًا. ما لم يُدخله المستخدم يبقى افتراضًا معلنًا في
قسم «الافتراضات وحدود الثقة».
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence

from . import platforms as platform_registry

MAX_VALUE = 1_000_000_000

# الحقول المعروضة لكل منصّة: (المفتاح، التسمية، تلميح)
FIELDS: Dict[str, List[Dict[str, str]]] = {
    'facebook': [
        {'key': 'followers', 'label': 'متابعو الصفحة', 'hint': 'مثال: 12000'},
        {'key': 'avg_reach', 'label': 'متوسط وصول المنشور', 'hint': 'اتركه فارغًا إن لم تعرفه'},
    ],
    'whatsapp': [
        {'key': 'group_members', 'label': 'أعضاء المجموعة (المجموع)', 'hint': 'مثال: 850'},
        {'key': 'groups_count', 'label': 'عدد المجموعات', 'hint': 'مثال: 3'},
    ],
    'tiktok': [
        {'key': 'followers', 'label': 'متابعو الحساب', 'hint': 'مثال: 4000'},
        {'key': 'avg_views', 'label': 'متوسط مشاهدات الفيديو', 'hint': 'مثال: 15000'},
    ],
    'twitter': [
        {'key': 'followers', 'label': 'متابعو الحساب', 'hint': 'مثال: 2500'},
    ],
    'reddit': [
        {'key': 'members', 'label': 'أعضاء المجتمع', 'hint': 'مثال: 900'},
    ],
}

# المفتاح الأساسي الذي يعبّر عن حجم الجمهور في كل منصّة
_PRIMARY = {
    'facebook': 'followers',
    'whatsapp': 'group_members',
    'tiktok': 'avg_views',
    'twitter': 'followers',
    'reddit': 'members',
}

# حجم افتراضي صغير للمنصّة التي لم يُدخل لها أرقام، حتى لا تُحرم من الأفعال
_FALLBACK_BASE = 800.0


def fields_for(platforms: Sequence[str]) -> List[Dict[str, Any]]:
    """حقول الإدخال لعرضها في الواجهة، بحسب المنصّات المتاحة."""
    out: List[Dict[str, Any]] = []
    for plat in platforms:
        fields = FIELDS.get(plat)
        if not fields:
            continue
        out.append({
            'platform': plat,
            'label': platform_registry.label(plat),
            'fields': fields,
        })
    return out


def validate(raw: Any, platforms: Optional[Sequence[str]] = None) -> Dict[str, Dict[str, int]]:
    """ينقّي مدخلات المستخدم: منصّات معروفة، حقول معروفة، أعداد صحيحة موجبة."""
    allowed_platforms = list(platforms or platform_registry.ORDER)
    clean: Dict[str, Dict[str, int]] = {}
    if not isinstance(raw, dict):
        return clean
    for plat, values in raw.items():
        key = str(plat).strip().lower()
        if key not in FIELDS or key not in allowed_platforms or not isinstance(values, dict):
            continue
        kept: Dict[str, int] = {}
        valid_keys = {f['key'] for f in FIELDS[key]}
        for field, value in values.items():
            if field not in valid_keys:
                continue
            try:
                number = int(float(str(value).replace(',', '').replace('٬', '').strip()))
            except (TypeError, ValueError):
                continue
            if number <= 0:
                continue
            kept[field] = min(number, MAX_VALUE)
        if kept:
            clean[key] = kept
    return clean


def has_inputs(inputs: Any) -> bool:
    return bool(validate(inputs))


def reach_scores(inputs: Dict[str, Dict[str, int]],
                 platforms: Sequence[str]) -> Dict[str, float]:
    """حجم جمهور تقديري لكل منصّة من أرقام المستخدم (أو بديل صغير جدًا)."""
    scores: Dict[str, float] = {}
    for plat in platforms:
        values = inputs.get(plat) or {}
        size = float(values.get(_PRIMARY.get(plat, 'followers'), 0) or 0)
        if plat == 'whatsapp' and size:
            groups = float(values.get('groups_count', 1) or 1)
            size = size  # group_members يُدخل كمجموع كل المجموعات
            if groups <= 1:
                size = size
        if plat == 'facebook' and values.get('avg_reach'):
            # الوصول الفعلي أدق من عدد المتابعين حين يتوفّر
            size = float(values['avg_reach'])
        if size <= 0:
            size = _FALLBACK_BASE
        # الجذر التربيعي يكبح هيمنة منصّة واحدة (تيك توك بمشاهدات ضخمة كانت
        # تبتلع ٧٨٪ من الأفعال)، ثم نضرب في مضاعف الانتشار من سجل المنصّات.
        scores[plat] = (size ** 0.5) * float(platform_registry.PLATFORMS[plat]['reach'])
    return scores


MAX_SHARE = 0.45  # لا منصّة تأخذ أكثر من ٤٥٪ من الأفعال


def weights(inputs: Dict[str, Dict[str, int]], platforms: Sequence[str]) -> Dict[str, float]:
    scores = reach_scores(inputs, platforms)
    total = sum(scores.values()) or 1.0
    shares = {p: scores[p] / total for p in scores}
    capped = {p: min(v, MAX_SHARE) for p, v in shares.items()}
    rest = 1.0 - sum(capped.values())
    if rest > 1e-9:
        room = {p: shares[p] for p in capped if capped[p] < MAX_SHARE}
        room_total = sum(room.values()) or 1.0
        for p, v in room.items():
            capped[p] = min(MAX_SHARE, capped[p] + rest * (v / room_total))
    final_total = sum(capped.values()) or 1.0
    return {p: round(capped[p] / final_total, 4) for p in capped}


def targets(inputs: Dict[str, Dict[str, int]], platforms: Sequence[str],
            total_actions: int) -> Dict[str, int]:
    """توزيع عدد الأفعال على المنصّات بحسب الأوزان (بأكبر باقٍ، وبحد أدنى فعل)."""
    if not platforms:
        return {}
    total_actions = max(int(total_actions), len(platforms))
    w = weights(inputs, platforms)
    raw = {p: w.get(p, 0) * total_actions for p in platforms}
    out = {p: max(1, int(raw[p])) for p in platforms}
    # صحّح الفارق على الأكبر وزنًا
    diff = total_actions - sum(out.values())
    order = sorted(platforms, key=lambda p: raw[p] - int(raw[p]), reverse=True)
    i = 0
    while diff != 0 and order:
        p = order[i % len(order)]
        if diff > 0:
            out[p] += 1
            diff -= 1
        elif out[p] > 1:
            out[p] -= 1
            diff += 1
        i += 1
        if i > total_actions * 4:
            break
    return out


def _fmt(number: int) -> str:
    return f"{number:,}".replace(',', '٬')


def summary_line(inputs: Dict[str, Dict[str, int]], platforms: Sequence[str]) -> str:
    """سطر عربي يذكر الأرقام كما أدخلها المستخدم (يُكتب في التقرير)."""
    parts: List[str] = []
    for plat in platforms:
        values = inputs.get(plat) or {}
        if not values:
            continue
        bits = []
        for field in FIELDS.get(plat, []):
            if field['key'] in values:
                bits.append(f"{field['label']} {_fmt(values[field['key']])}")
        if bits:
            parts.append(f"{platform_registry.label(plat)}: " + '، '.join(bits))
    return ' · '.join(parts)


def prompt_block(inputs: Dict[str, Dict[str, int]], platforms: Sequence[str],
                 total_actions: int = 0) -> str:
    """كتلة تُحقن في برومبت المحرّك: الأرقام + الأوزان + التوزيع المطلوب."""
    if not inputs:
        return ''
    lines = ['أرقام قدّمها صاحب المشروع بنفسه (تُعامل كمعطى، لا تُغيَّر ولا تُختلق):']
    for plat in platforms:
        values = inputs.get(plat) or {}
        if not values:
            continue
        bits = [
            f"{f['label']} {_fmt(values[f['key']])}"
            for f in FIELDS.get(plat, []) if f['key'] in values
        ]
        lines.append(f'- {platform_registry.label(plat)}: ' + '، '.join(bits))
    w = weights(inputs, platforms)
    if w:
        share = '، '.join(
            f"{platform_registry.label(p)} {round(w[p] * 100)}٪" for p in platforms if p in w
        )
        lines.append(f'حصة كل منصّة من الجمهور بحسب هذه الأرقام: {share}.')
    if total_actions:
        t = targets(inputs, platforms, total_actions)
        dist = '، '.join(f"{platform_registry.label(p)} {t[p]}" for p in platforms)
        lines.append(f'وزّع الأفعال على المنصّات بهذا التقريب: {dist} (المجموع {total_actions}).')
    return '\n'.join(lines)


# ---------------------------------------------------------------- storage

def _path(simulation_id: str) -> str:
    """مسار مطلق تحت مجلد الرفع.

    مهم: دوال التخزين في هذا المشروع تعمل على مسارات مطلقة (تُحوَّل لاحقًا إلى
    مفتاح نسبي في Postgres). تمرير مسار نسبي كان يُحلّ مقابل مجلد العمل على
    Vercel (للقراءة فقط) فيفشل الحفظ.
    """
    from ..config import Config

    return os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id, 'platform_inputs.json')


def load(simulation_id: str) -> Dict[str, Dict[str, int]]:
    """يقرأ أرقام المستخدم المحفوظة لهذه المحاكاة (فارغة إن لم تُدخل)."""
    try:
        from ..models import storage

        raw = storage.read_json(_path(simulation_id))
        return validate(raw or {})
    except Exception:  # noqa: BLE001
        return {}


def save(simulation_id: str, raw: Any,
         platforms: Optional[Sequence[str]] = None) -> Dict[str, Dict[str, int]]:
    from ..models import storage

    clean = validate(raw, platforms)
    storage.write_json(_path(simulation_id), clean)
    return clean
