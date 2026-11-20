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


def trend_summary(keyword: str, geo: str = 'SD', months: int = 3,
                  timeout: float = _TIMEOUT) -> Dict[str, Any]:
    """ملخّص اهتمام البحث من Google Trends (متوسط، قمة، اتجاه)."""
    word = clean_project_title(keyword)
    if not word:
        raise ValueError('أدخل الكلمة التي تريد قياس اهتمام الناس بها')
    geo = (geo or 'SD').strip().upper()[:2]
    months = max(1, min(int(months or 3), 12))
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
        'keyword': word,
        'geo': geo,
        'geo_label': GEO_LABELS.get(geo, geo),
        'months': months,
        'average': average,
        'peak': peak,
        'latest': latest,
        'direction': direction,
        'level': level,
        'points': len(values),
        'source': 'google_trends',
    }
