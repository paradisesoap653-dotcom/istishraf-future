"""قراءة أرقام حقيقية من الويب عبر SerpApi (فيسبوك + اتجاهات جوجل).

سبب وجوده: قراءة صفحة فيسبوك بأنفسنا تفشل (تحجب الطلبات الآلية)، وSerpApi
يرجّع بيانات الصفحة منظّمة، ومنها عدد المتابعين كما يعرضه فيسبوك نفسه.
كذلك يوفّر Google Trends لقياس اهتمام الناس بكلمة معيّنة في بلد محدّد.

قواعد صارمة:
- لا نُخمّن: إن لم تصل قيمة موثوقة نرجّع خطأ واضحًا ولا نكتب رقمًا.
- الرقم القادم من فيسبوك مختصر («2.8K»)، فنسجّله تقريبيًا ونعلن ذلك.
- كل نداء يكلّف بحثًا واحدًا من رصيد المستخدم، فلا نكرّر النداء بلا سبب.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import httpx

from .research_integrity import clean_project_title

_API = 'https://serpapi.com/search.json'
_TIMEOUT = 45.0

GEO_LABELS = {
    'SD': 'السودان',
    'US': 'الولايات المتحدة',
    'SA': 'السعودية',
    'AE': 'الإمارات',
    'EG': 'مصر',
}


def key() -> str:
    return (os.environ.get('SERPAPI_KEY') or '').strip()


def is_configured() -> bool:
    return bool(key())


def _get(params: Dict[str, Any], timeout: float = _TIMEOUT) -> Dict[str, Any]:
    params = {k: v for k, v in params.items() if v not in (None, '')}
    params['api_key'] = key()
    resp = httpx.get(_API, params=params, timeout=timeout)
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        raise RuntimeError(f'رد غير مفهوم من مزوّد البحث (HTTP {resp.status_code})')
    if isinstance(data, dict) and data.get('error'):
        raise RuntimeError(str(data['error'])[:180])
    if resp.status_code != 200:
        raise RuntimeError(f'HTTP {resp.status_code}')
    return data


def parse_compact(value: Any) -> Optional[int]:
    """«2.8K» ← 2800، «1.2M» ← 1200000، «١٢٬٤٥٦» ← 12456."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return int(number) if number > 0 else None
    text = str(value).strip().replace('٬', '').replace(',', '').replace('٫', '.')
    match = re.search(r'([\d.]+)\s*([KMB])?', text, re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or '').upper()
    factor = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000}.get(unit, 1)
    result = int(number * factor)
    return result if result > 0 else None


def facebook_profile(reference: str) -> Dict[str, Any]:
    """بيانات صفحة فيسبوك من رابطها أو معرّفها."""
    ref = (reference or '').strip()
    if not ref:
        raise ValueError('أدخل رابط صفحة فيسبوك أولًا')
    if '/share/' in ref:
        raise ValueError(
            'رابط «مشاركة» من فيسبوك لا يُقرأ آليًا. افتح الرابط في فيسبوك، '
            'ثم انسخ العنوان الظاهر في الأعلى (مثل facebook.com/اسم_الصفحة) والصقه هنا'
        )
    ref = re.sub(r'^https?://', '', ref)
    ref = re.sub(r'^(www\.|m\.|web\.)', '', ref)
    ref = re.sub(r'^facebook\.com/', '', ref)
    ref = ref.split('?')[0].strip('/').split('/')[0]
    if not ref:
        raise ValueError('الرابط لا يحتوي اسم صفحة صالحًا')
    data = _get({'engine': 'facebook_profile', 'profile_id': ref})
    profile = data.get('profile_results') or {}
    followers_text = profile.get('followers')
    followers = parse_compact(followers_text)
    if followers is None:
        raise RuntimeError('الصفحة لم تُرجع عدد متابعين (قد تكون مغلقة أو غير موجودة)')
    return {
        'name': profile.get('name') or '',
        'profile_type': profile.get('profile_type') or '',
        'url': profile.get('url') or f'https://www.facebook.com/{ref}',
        'followers': followers,
        'followers_text': str(followers_text),
        'phone': profile.get('phone') or '',
        'category': profile.get('category') or '',
    }



# ── منشورات الصفحة الحقيقية ──
# الهدف: لا نولّد منشورات من الخيال فقط، بل نبدأ من منشورات منشورة فعلًا
# على صفحة صاحب المشروع، فنكون أمام مادة يمكن للقارئ فتحها والتحقق منها.
_POST_PATH_HINTS = ('/posts/', '/videos/', '/photos/', '/reel/', '/permalink',
                    'story_fbid', '/p/', '/watch')

_REF_CLEAN_RE = re.compile(r'^(?:https?://)?(?:www\.|m\.|web\.)?facebook\.com/', re.I)


def normalize_page_ref(reference: str) -> str:
    """اسم الصفحة من أي شكل رابط: facebook.com/اسم ← اسم."""
    ref = (reference or '').strip()
    ref = _REF_CLEAN_RE.sub('', ref)
    ref = ref.split('?')[0].strip('/')
    return ref.split('/')[0] if ref else ''


def facebook_page_posts(reference: str, limit: int = 8,
                        topic: str = '') -> List[Dict[str, str]]:
    """منشورات حقيقية من صفحة فيسبوك (غلاف متوافق للدالة العامة)."""
    return page_posts('facebook', reference, limit=limit, topic=topic)


# ── ما يقوله الناس عن الحساب ──
# منشورات صاحب المشروع نصف الصورة فقط. النصف الآخر آراء من حوله: من يذكره،
# ومن يعلّق على موضوعه، ومن ينقل عنه. نبحث عن ذكره خارج حساباته ونحتفظ
# بما يقوله الآخرون — لا نولّد آراء المتابعين من الخيال.
_MENTION_DOMAINS = ('facebook.com', 'tiktok.com', 'x.com', 'twitter.com', 'reddit.com',
                    'instagram.com', 'youtube.com', 't.me', 'threads.net', 'linkedin.com',
                    'blogspot.', 'medium.com', 'wordpress.com')


def _label_candidates(reference: str, name: str = '') -> List[str]:
    """صيغ ذكر الحساب: اسمه الظاهر، ثم معرّفه."""
    out: List[str] = []
    for value in (name, str(reference or '').strip().lstrip('@')):
        value = ' '.join(str(value or '').split())
        if value and value not in out and len(value) > 2:
            out.append(value)
    return out


def page_mentions(platform: str, reference: str, limit: int = 6,
                  topic: str = '', name: str = '') -> List[Dict[str, str]]:
    """ما ينشره الآخرون عن الحساب أو عن موضوعه، على المنصّات، بروابطهم.

    نستبعد منشورات الحساب نفسه: هذه ليست أصواتًا حوله بل صوته.
    """
    plat = str(platform or '').strip().lower() or detect_platform(reference)
    rule = _PLATFORM_RULES.get(plat)
    if not rule:
        raise ValueError('منصّة غير مدعومة')
    ref = normalize_any_ref(plat, reference)
    if not ref:
        raise ValueError('الرابط لا يحتوي اسم حساب صالحًا')

    labels = _label_candidates(ref, name)
    if not labels:
        return []
    words = _topic_words(topic, 4)

    mentions: List[Dict[str, str]] = []
    seen = set()
    ref_low = ref.lower().lstrip('@')
    for label in labels[:2]:
        if len(mentions) >= int(limit):
            break
        query = f'"{label}"' + (f' {words}' if words else '')
        try:
            data = _get({'engine': 'google', 'q': query, 'num': 10, 'hl': 'ar'})
        except Exception:  # noqa: BLE001 - ذكر الحساب إضافة، وفشله لا يُسقط القراءة
            continue
        for item in data.get('organic_results') or []:
            link = str(item.get('link') or '').strip()
            low = link.lower()
            if not link or ref_low in low:
                continue                      # كلام الحساب نفسه
            if not any(domain in low for domain in _MENTION_DOMAINS):
                continue                      # نريد كلام الناس لا صفحات تعريفية
            if link in seen:
                continue
            text = str(item.get('snippet') or item.get('title') or '').strip()
            if len(text) < 25:
                continue
            seen.add(link)
            mentions.append({
                'platform': plat,
                'url': link,
                'title': str(item.get('title') or '')[:140],
                'text': text[:400],
                'date': str(item.get('date') or ''),
                'found_by': label,
            })
            if len(mentions) >= int(limit):
                break
    return mentions


# ── منصّات متعدّدة: فيسبوك، تيك توك، إكس ──
# المبدأ: رابط الصفحة ليس زينة في التقرير، بل مدخل نقرأ منه المحتوى المنشور
# فعلًا، ثم نبحث داخل الصفحة نفسها عن الموضوع المطروح.
_PLATFORM_RULES: Dict[str, Dict[str, Any]] = {
    'facebook': {
        'domains': ('facebook.com',),
        'hints': ('/posts/', '/videos/', '/photos/', '/reel/', '/permalink',
                  'story_fbid', '/p/', '/watch'),
        'label': 'فيسبوك',
    },
    'tiktok': {
        'domains': ('tiktok.com',),
        'hints': ('/video/', '/photo/'),
        'label': 'تيك توك',
    },
    'twitter': {
        'domains': ('x.com', 'twitter.com'),
        'hints': ('/status/', '/statuses/'),
        'label': 'إكس (تويتر)',
    },
}

_HANDLE_PREFIXES = ('@',)


def detect_platform(reference: str) -> str:
    """المنصّة من شكل الرابط. المجرّد (اسم صفحة) يبقى فيسبوك كما كان."""
    text = str(reference or '').strip().lower()
    if not text:
        return ''
    for plat, rule in _PLATFORM_RULES.items():
        if any(domain in text for domain in rule['domains']):
            return plat
    if text.startswith('@'):
        return ''          # «@اسم» يصلح لتيك توك وإكس: لا نخمّن
    return 'facebook'


def normalize_any_ref(platform: str, reference: str) -> str:
    """اسم الحساب/الصفحة من أي شكل رابط لتلك المنصّة."""
    rule = _PLATFORM_RULES.get(platform)
    if not rule:
        return ''
    ref = str(reference or '').strip()
    ref = re.sub(r'^https?://', '', ref, flags=re.I)
    ref = re.sub(r'^(?:www\.|m\.|mobile\.|web\.)', '', ref, flags=re.I)
    low = ref.lower()
    for domain in rule['domains']:
        if low.startswith(domain + '/'):
            ref = ref[len(domain) + 1:]
            break
        if low.rstrip('/') == domain:
            ref = ''
            break
    ref = ref.split('?')[0].split('#')[0].strip('/')
    handle = ref.split('/')[0].strip()
    return handle


def _topic_words(topic: str, limit: int = 5) -> str:
    """كلمات الموضوع للبحث داخل الصفحة (نُسقط كلمات الوصل القصيرة)."""
    words = [w for w in re.split(r'[\s،,.؛;:!؟?"\'«»()\[\]]+', str(topic or '')) if len(w) > 2]
    return ' '.join(words[:limit])


def page_posts(platform: str, reference: str, limit: int = 8,
               topic: str = '') -> List[Dict[str, str]]:
    """منشورات حقيقية منشورة على الحساب، مع روابطها كما هي.

    لا نكتفي بقراءة الصفحة: نبحث داخلها عن الموضوع المطروح (site:حساب + موضوع)
    حتى تكون التعليقات على مادة قريبة من سياق المشروع، لا على أي منشور قديم.
    """
    plat = str(platform or '').strip().lower() or detect_platform(reference)
    rule = _PLATFORM_RULES.get(plat)
    if not rule:
        raise ValueError('القراءة من رابط الصفحة متاحة لفيسبوك وتيك توك وإكس')
    ref = normalize_any_ref(plat, reference)
    if not ref:
        raise ValueError('الرابط لا يحتوي اسم حساب صالحًا')

    query = f"site:{rule['domains'][0]}/{ref}"
    words = _topic_words(topic)
    if words:
        query = f"{query} {words}"

    data = _get({'engine': 'google', 'q': query, 'num': max(int(limit) * 2, 10), 'hl': 'ar'})
    posts: List[Dict[str, str]] = []
    seen = set()
    ref_low = ref.lower()
    for item in data.get('organic_results') or []:
        link = str(item.get('link') or '').strip()
        low = link.lower()
        if not link or not any(domain in low for domain in rule['domains']):
            continue
        if ref_low not in low:
            continue                      # نتيجة من حساب آخر
        if not any(hint in low for hint in rule['hints']):
            continue                      # صفحة/بروفايل لا منشور
        if link in seen:
            continue
        snippet = str(item.get('snippet') or '').strip()
        title = str(item.get('title') or '').strip()
        text = snippet or title
        if len(text) < 20:
            continue
        seen.add(link)
        posts.append({
            'platform': plat,
            'url': link,
            'title': title[:140],
            'text': text[:400],
            'date': str(item.get('date') or ''),
        })
        if len(posts) >= int(limit):
            break
    return posts


_SEGMENT_SPLIT = re.compile(r'[—–\-:|/\\،,؛;«»()\[\]]')


def _keyword_ladder(word: str) -> List[str]:
    """كلمات مرشّحة من الأخصّ إلى الأعمّ: الجملة، ثم أوّل مقطع، ثم أوّل كلمتين، ثم كلمة واحدة."""
    base = ' '.join(str(word or '').split())
    out: List[str] = []

    def add(value: str) -> None:
        item = ' '.join(str(value or '').split()).strip(' -—–:|/،,;؛')
        if item and item not in out:
            out.append(item)

    add(base)
    head = _SEGMENT_SPLIT.split(base)[0] or base
    add(head)
    tokens = head.split()
    if len(tokens) > 1:
        add(' '.join(tokens[:2]))
        add(tokens[0])
    btokens = base.split()
    if len(btokens) > 2:
        add(' '.join(btokens[:2]))
        add(btokens[0])
    return out


_NO_DATA_MARKERS = ("hasn't returned any results", 'returned any results',
                    'لم يُرجع بيانات كافية')


def _is_empty_result(exc: Exception) -> bool:
    """هل الفشل سببه أن جوجل لا يملك بيانات عن الكلمة (لا خطأ في الخدمة)؟"""
    text = str(exc)
    return any(marker in text for marker in _NO_DATA_MARKERS)


def _trend_values(word: str, geo: str, months: int, timeout: float) -> List[int]:
    data = _get({
        'engine': 'google_trends',
        'q': word,
        'geo': geo,
        'data_type': 'TIMESERIES',
        'date': f'today {months}-m',
    }, timeout=timeout)
    timeline: List[Dict[str, Any]] = ((data.get('interest_over_time') or {}).get('timeline_data') or [])
    values: List[int] = []
    for point in timeline:
        series = point.get('values') or [{}]
        extracted = series[0].get('extracted_value')
        if isinstance(extracted, int):
            values.append(extracted)
    if not values:
        raise RuntimeError('جوجل لم يُرجع بيانات كافية عن هذه الكلمة في هذا البلد')
    return values


def _describe(values: List[int]) -> Dict[str, Any]:
    average = round(sum(values) / len(values), 1)
    peak = max(values)
    latest = values[-1]
    if len(values) >= 8:
        recent = sum(values[-4:]) / 4
        earlier = sum(values[:-4]) / max(len(values) - 4, 1)
        if recent > earlier * 1.3 and recent > 1:
            direction = 'صاعد'
        elif recent < earlier * 0.7:
            direction = 'هابط'
        else:
            direction = 'مستقر'
    else:
        direction = 'مستقر'
    if average < 3:
        # بيانات ضئيلة جدًا (قفزات متفرقة بين أصفار): لا يصحّ وصفها بصعود أو هبوط
        direction = 'لا اتجاه واضح'
    if average < 3:
        level = 'منخفض جدًا'
    elif average < 10:
        level = 'منخفض'
    elif average < 35:
        level = 'متوسط'
    else:
        level = 'مرتفع'
    return {
        'average': average,
        'peak': peak,
        'latest': latest,
        'direction': direction,
        'level': level,
        'points': len(values),
    }


def trend_summary(keyword: str, geo: str = 'SD', months: int = 3,
                  timeout: float = _TIMEOUT) -> Dict[str, Any]:
    """ملخّص اهتمام البحث من Google Trends (متوسط، قمة، اتجاه).

    لماذا سلّم المحاولات: جوجل يُرجع «لا نتائج» لجُمل طويلة أو كلمات قليلة الحجم
    في بلد صغير. فبدل أن نفشل أمام المستخدم، نُقصّر الكلمة ثم نوسّع النطاق
    (البلد ← الولايات المتحدة ← العالم) ونسجّل بصراحة أي كلمة ونطاق استُخدما.
    """
    word = clean_project_title(keyword)
    if not word:
        raise ValueError('أدخل الكلمة التي تريد قياس اهتمام الناس بها')
    geo0 = (geo or 'SD').strip().upper()[:2]
    months = max(1, min(int(months or 3), 12))

    candidates = _keyword_ladder(word)
    exact = candidates[0]
    shorter = candidates[1:] or candidates
    # خطة المحاولات: الجملة كما هي في البلد المطلوب أولًا (وهي الأدقّ)،
    # ثم كلمة أقصر في البلد ثم في نطاق أوسع.
    plan = [(exact, geo0)]
    for candidate in shorter[:2]:
        for scope in [geo0, 'US', '']:
            pair = (candidate, scope)
            if pair not in plan:
                plan.append(pair)
    plan = plan[:6]  # كل محاولة تكلّف رصيد بحث، فلا نُفرط

    attempts: List[str] = []
    for candidate, scope in plan:
        try:
            values = _trend_values(candidate, scope, months, timeout)
        except RuntimeError as exc:
            if not _is_empty_result(exc):
                raise  # خطأ في الخدمة نفسها (مفتاح/شبكة): لا نُكرّره
            attempts.append(f'{candidate} / {GEO_LABELS.get(scope, scope or "العالم")}')
            continue
        summary = _describe(values)
        summary.update({
            'keyword': candidate,
            'requested_keyword': word,
            'geo': scope,
            'geo_label': GEO_LABELS.get(scope, scope or 'العالم'),
            'months': months,
            'source': 'google_trends',
        })
        notes: List[str] = []
        if candidate != word:
            notes.append(f'قِسنا «{candidate}» بدل الجملة الكاملة، '
                         'لأن جوجل لا يملك بيانات كافية عن الجملة الطويلة.')
        if scope != geo0:
            notes.append(f'النطاق الجغرافي: {summary["geo_label"]}، '
                         'لأن البيانات في النطاق المطلوب غير كافية.')
        if notes:
            summary['note'] = ' '.join(notes)
        return summary

    raise RuntimeError(
        'جوجل لا يملك بيانات كافية عن هذه الكلمة في النطاقات المتاحة. '
        'جرّب كلمة واحدة قصيرة (اسم شخص أو شركة) بدل جملة كاملة.'
    )
