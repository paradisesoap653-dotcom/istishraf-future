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

# حقل تواصل واحد (جوال/واتساب) يعرفه الناس ويُذكر في المحاكاة والتقرير
CONTACT = {
    'key': 'phone',
    'label': 'رقم واتساب / خط التواصل',
    'hint': 'مثال: ‎+249 9x xxx xxxx',
}

# اهتمام الناس بكلمة المشروع (من Google Trends) — معطى واقعي لا يُختلق
INTEREST = {
    'key': 'interest',
    'label': 'اهتمام البحث على جوجل',
    'hint': 'مثال: ركشتك · السودان · آخر ٣ أشهر',
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
            # الرقم القادم من فيسبوك مختصر (2.8K) فنعلّمه تقريبيًا
            if key == 'facebook' and values.get('followers_approx'):
                kept['followers_approx'] = 1
            clean[key] = kept
    return clean


def _clean_phone(raw):
    """يقبل أرقام الهواتف بصياغات مختلفة ويحتفظ بها كما كتبها المستخدم."""
    if not isinstance(raw, str):
        return ''
    text = raw.strip()
    digits = sum(1 for ch in text if ch.isdigit())
    if digits < 6:
        return ''
    if any(not (ch.isdigit() or ch in '+-() ') for ch in text):
        return ''
    return text[:24]


def validate_with_contact(raw, platforms=None):
    """مثل validate، مع حفظ رقم التواصل إن وُجد."""
    clean = validate(raw, platforms)
    if isinstance(raw, dict):
        contact = raw.get('contact') or {}
        phone = _clean_phone((contact or {}).get('phone') if isinstance(contact, dict) else contact)
        if phone:
            clean['contact'] = {'phone': phone}
        interest = _clean_interest(raw.get('interest'))
        if interest:
            clean['interest'] = interest
    return clean


def _clean_interest(raw):
    """ينقّي ملخّص اهتمام البحث القادم من Google Trends."""
    if not isinstance(raw, dict):
        return {}
    keyword = str(raw.get('keyword') or '').strip()[:60]
    if not keyword:
        return {}
    try:
        average = float(raw.get('average') or 0)
    except (TypeError, ValueError):
        average = 0.0
    try:
        peak = int(float(raw.get('peak') or 0))
    except (TypeError, ValueError):
        peak = 0
    if average <= 0 and peak <= 0:
        return {}
    months = raw.get('months')
    try:
        months = max(1, min(int(months or 3), 12))
    except (TypeError, ValueError):
        months = 3
    geo = str(raw.get('geo') or 'SD').strip().upper()[:2]
    return {
        'keyword': keyword,
        'geo': geo,
        'geo_label': str(raw.get('geo_label') or '')[:30],
        'months': months,
        'average': round(average, 1),
        'peak': peak,
        'latest': max(0, min(int(float(raw.get('latest') or 0)), 100)),
        'direction': str(raw.get('direction') or '')[:24],
        'level': str(raw.get('level') or '')[:20],
        'source': 'google_trends',
    }


def interest_of(inputs):
    if not isinstance(inputs, dict):
        return {}
    return _clean_interest(inputs.get('interest'))


def contact_of(inputs):
    if not isinstance(inputs, dict):
        return ''
    contact = inputs.get('contact') or {}
    return _clean_phone(contact.get('phone')) if isinstance(contact, dict) else ''


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


_AR_DIGITS = str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩')


def _num_ar(value) -> str:
    """صياغة رقم عربية (٤٥٬٠٠٠ / ١٫١) حتى لا يختلط اللاتيني بالعربي في التقرير."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number):
        text = f"{int(number):,}".replace(',', '٬')
    else:
        text = f"{number:.1f}".replace('.', '٫')
    return text.translate(_AR_DIGITS)


def _fmt(number: int) -> str:
    """أرقام عربية موحّدة مع بقية التقرير (كانت لاتينية فتختلط بالعربية)."""
    return f"{number:,}".replace(',', '٬').translate(_AR_DIGITS)


def summary_line(inputs: Dict[str, Dict[str, int]], platforms: Sequence[str],
                 multiline: bool = False) -> str:
    """سطر عربي يذكر الأرقام كما أدخلها المستخدم (يُكتب في التقرير)."""
    parts: List[str] = []
    for plat in platforms:
        values = inputs.get(plat) or {}
        if not values:
            continue
        bits = []
        for field in FIELDS.get(plat, []):
            if field['key'] in values:
                mark = ''
                if plat == 'facebook' and field['key'] == 'followers' and values.get('followers_approx'):
                    mark = '≈ '
                bits.append(f"{field['label']} {mark}{_fmt(values[field['key']])}")
        if bits:
            parts.append(f"{platform_registry.label(plat)}: " + '، '.join(bits))
    phone = contact_of(inputs)
    if phone:
        # عزل اتجاه الرقم حتى يظهر بالترتيب الصحيح داخل نص عربي (من اليسار لليمين)
        parts.append(f"رقم التواصل \u2066{phone}\u2069")
    interest = interest_of(inputs)
    if interest:
        where = interest.get('geo_label') or interest.get('geo')
        line = (
            f"اهتمام البحث على جوجل عن «{interest['keyword']}» ({where}، آخر {_num_ar(interest['months'])} أشهر): "
            f"متوسط {_num_ar(interest['average'])} من ١٠٠، "
            f"المستوى {interest['level'] or 'غير محدد'}، الاتجاه {interest['direction'] or 'مستقر'}"
        )
        # لا نعرض «أعلى قمة» حين يكون المتوسط أقل من ٣: القمة حينها قفزة واحدة
        # معزولة بين أصفار، وعرضها يوهم باهتمام لم يحدث.
        try:
            low = float(interest.get('average') or 0) < 3
        except (TypeError, ValueError):
            low = False
        if low:
            line += "، والبيانات ضئيلة جدًا فلا تصلح للحكم على حجم الاهتمام"
        else:
            line += f"، أعلى قمة {_num_ar(interest['peak'])}"
        parts.append(line)
    if multiline:
        # كل رقم في سطر مستقل: في ملف PDF العربي يتشابك ترتيب الأجزاء إذا جاءت
        # في سطر واحد مع رقم تواصل وأرقام لاتينية.
        return "\n".join(f"• {part}" for part in parts)
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
    phone = contact_of(inputs)
    if phone:
        lines.append(f'- رقم التواصل الذي يعرفه الناس ويتناقلونه: {phone} (لا تخترع رقمًا غيره).')
    interest = interest_of(inputs)
    if interest:
        where = interest.get('geo_label') or interest.get('geo')
        lines.append(
            f"- اهتمام البحث الحقيقي على جوجل عن «{interest['keyword']}» في {where} خلال آخر "
            f"{_num_ar(interest['months'])} أشهر: متوسط {_num_ar(interest['average'])} من ١٠٠ "
            f"(أعلى قمة {_num_ar(interest['peak'])}، الاتجاه {interest['direction'] or 'مستقر'}). "
            "استخدم هذا كدليل على حجم الاهتمام الفعلي ولا تخترع أرقامًا أخرى."
        )
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
        return validate_with_contact(raw or {})
    except Exception:  # noqa: BLE001
        return {}


def save(simulation_id: str, raw: Any,
         platforms: Optional[Sequence[str]] = None) -> Dict[str, Dict[str, int]]:
    from ..models import storage

    clean = validate_with_contact(raw, platforms)
    storage.write_json(_path(simulation_id), clean)
    return clean
