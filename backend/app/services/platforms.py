"""سجل المنصّات المدعومة في المحاكاة.

السياق: المحرّك كان يشتغل على منصّتين غربيّتين (twitter/reddit) فقط، وهذا لا
يشبه الواقع السوداني حيث النقاش الفعلي يمشي في فيسبوك ومجموعات واتساب
وتيك توك. هذا الملف يجعل مجموعة المنصّات قرارًا واحدًا يقرأه المحرّك
والسيناريو والتقرير معًا، ويضمن أن **السيناريو يستخدم نفس مجموعة المنصّات**
التي استُخدمت في المحاكاة الأصلية، وإلا صارت المقارنة بلا معنى.

كل منصّة هنا وصف سلوكي، وليست ادّعاء بقياس: الأرقام التي تنتج عنها تُصنَّف
«افتراض» إلا إذا أدخل المستخدم أرقامه الحقيقية.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

# مفتاح المنصّة → وصفها السلوكي
PLATFORMS: Dict[str, Dict[str, Any]] = {
    'facebook': {
        'label': 'فيسبوك',
        'kind': 'public',
        'reach': 1.0,
        'forms': 'منشور، تعليق، مشاركة',
        'behaviour': (
            'نقاش عام واسع: صفحات محلية ومجموعات مدينة أو مهنة، تعليقات طويلة '
            'وحوارات أسرية، انتقال سريع للنقاش من صفحة إلى مجموعة'
        ),
    },
    'whatsapp': {
        'label': 'واتساب',
        'kind': 'semi_private',
        'reach': 0.55,
        'forms': 'رسالة في مجموعة، حالة (ستوري)، رسالة صوتية محوَّلة',
        'behaviour': (
            'مجموعات مغلقة للأهل والزملاء والجيران: ثقة عالية، انتشار داخل '
            'المجموعة لا خارجها، محتوى قصير وأصوات وأحيانًا إعادة إرسال '
            'مقطع دون مصدره'
        ),
    },
    'tiktok': {
        'label': 'تيك توك',
        'kind': 'public',
        'reach': 1.3,
        'forms': 'فيديو قصير، تعليق تحت الفيديو، رد فيديو',
        'behaviour': (
            'جمهور شاب: فيديو قصير وساخر وحاد أحيانًا، الانتشار بالمشاهدة لا '
            'بالمتابعة، والتعليقات أقصر وأكثر مباشرة'
        ),
    },
    'twitter': {
        'label': 'تويتر (إكس)',
        'kind': 'public',
        'reach': 0.8,
        'forms': 'تغريدة، اقتباس، رد',
        'behaviour': 'نخبة وصحافيون وناشطون: نقاش مكتوب سريع ومختصر',
    },
    'reddit': {
        'label': 'ريديت',
        'kind': 'public',
        'reach': 0.3,
        'forms': 'منشور، تعليق',
        'behaviour': 'مجتمعات متخصّصة: نقاش طويل مع مصادر',
    },
}

# الافتراضي للسودان (يُطلب «parallel") — ريديت أُعيدت منصّةً خامسة بطلب صاحب المشروع
DEFAULT_SET: List[str] = ['facebook', 'whatsapp', 'tiktok', 'twitter', 'reddit']

# ترتيب ثابت لعرض الأسماء
ORDER: List[str] = ['facebook', 'whatsapp', 'tiktok', 'twitter', 'reddit']


def normalize(value: Any) -> List[str]:
    """يحوّل مدخلات المستخدم إلى قائمة منصّات صالحة (ويرفض أي اسم مجهول)."""
    if value in (None, '', 'parallel', 'both', 'all'):
        return list(DEFAULT_SET)
    if isinstance(value, str):
        raw: Iterable[str] = [p for p in value.replace(';', ',').split(',')]
    elif isinstance(value, (list, tuple, set)):
        raw = value
    else:
        return list(DEFAULT_SET)

    out: List[str] = []
    for item in raw:
        key = str(item).strip().lower()
        key = {'x': 'twitter', 'whatsapp_business': 'whatsapp', 'fb': 'facebook',
               'tik_tok': 'tiktok', 'tiktok_video': 'tiktok'}.get(key, key)
        if key in PLATFORMS and key not in out:
            out.append(key)
    return out or list(DEFAULT_SET)


def label(platform: str) -> str:
    return PLATFORMS.get(platform, {}).get('label', platform or 'منصّة')


def labels(platforms: Sequence[str]) -> str:
    names = [label(p) for p in (platforms or [])]
    if not names:
        return '—'
    if len(names) == 1:
        return names[0]
    return '، '.join(names[:-1]) + ' و' + names[-1]


def prompt_block(platforms: Sequence[str]) -> str:
    """سطور عربية تشرح للمحرّك سلوك كل منصّة، تُحقن في البرومبت."""
    lines = []
    for p in platforms:
        info = PLATFORMS.get(p)
        if not info:
            continue
        lines.append(
            f'- "{p}" ({info["label"]}): أشكال الفعل = {info["forms"]}. السلوك: {info["behaviour"]}.'
        )
    return '\n'.join(lines)


def breakdown(platforms: Sequence[str]) -> str:
    """وصف مختصر لتوزيع المنصّات، يُكتب في التقرير تحت وسم «افتراض»."""
    return ' · '.join(f'{label(p)}' for p in (platforms or []))


def preferred_for(index: int, platforms: Sequence[str]) -> str:
    """منصّة أساسية لكل وكيل، بتوزيع ثابت حتى لا تتراكم كل الأفعال في منصّة واحدة."""
    seq = list(platforms or DEFAULT_SET)
    if not seq:
        return 'facebook'
    # ترتيب دائري مع إزاحة بسيطة لتفادي نمط ميكانيكي ظاهر
    return seq[(index * 3 + 1) % len(seq)]
