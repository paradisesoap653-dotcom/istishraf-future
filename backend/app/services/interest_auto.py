"""قياس اهتمام البحث تلقائيًا عند إنشاء المحاكاة.

لماذا: كان على المستخدم أن يضغط زرًا لجلب اهتمام Google Trends. الآن يُقاس
تلقائيًا باسم المشروع لحظة إنشاء المحاكاة، ويُحفظ مع بقية الأرقام كـ«مدخل»
يدخل في برومبت المحاكاة وسطر المدخلات داخل التقرير.

ضوابط:
- لا نكسر إنشاء المحاكاة أبدًا: أي فشل هنا يُسجَّل ويُتجاهل.
- ذاكرة مؤقتة ٧ أيام لكل كلمة/بلد، فلا نستهلك رصيد المستخدم مرتين لنفس الكلمة.
- مهلة قصيرة (١٢ ثانية) حتى لا تتأخر الاستجابة.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from ..utils.logger import get_logger

logger = get_logger('mirofish.interest_auto')

CACHE_TTL_SECONDS = 7 * 24 * 3600
FETCH_TIMEOUT = 12.0


_SEPARATORS = ('—', '–', '|', '·', ':', ' - ', '\n', '/')


def keyword_for(project: Any) -> str:
    """أفضل كلمة للقياس: اسم المشروع مقصوصًا عند الشُرَط، وإلا أول كلمات المطلوب.

    سبب القصّ: أسماء المشاريع تُكتب غالبًا «ركشتك — جولة كاملة»، وقياس الاهتمام
    يحتاج الاسم وحده («ركشتك») وإلا رجع صفرًا لأن لا أحد يبحث عن العنوان كاملًا.
    """
    raw = (getattr(project, 'name', '') or '').strip()
    if not raw:
        text = (getattr(project, 'simulation_requirement', '') or '').strip()
        if not text:
            return ''
        raw = ' '.join(text.split()[:4])
    for sep in _SEPARATORS:
        if sep in raw:
            raw = raw.split(sep)[0]
    raw = ' '.join(raw.split()).strip(' .،,-«»"\'')
    words = raw.split()
    if len(words) > 4:
        raw = ' '.join(words[:4])
    return raw[:60]


def _cache_path() -> str:
    from ..config import Config

    return os.path.join(Config.OASIS_SIMULATION_DATA_DIR, '_cache', 'google_trends.json')


def _read_cache() -> Dict[str, Dict[str, Any]]:
    try:
        from ..models import storage

        data = storage.read_json(_cache_path())
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _write_cache(cache: Dict[str, Dict[str, Any]]) -> None:
    try:
        from ..models import storage

        # لا نُكبّر الملف بلا حد: نُبقي آخر ٥٠ كلمة فقط
        if len(cache) > 50:
            ordered = sorted(cache.items(), key=lambda kv: kv[1].get('ts', 0), reverse=True)[:50]
            cache = dict(ordered)
        storage.write_json(_cache_path(), cache)
    except Exception:  # noqa: BLE001
        pass


def ensure_interest(simulation_id: str, keyword: str, geo: str = 'SD') -> Optional[Dict[str, Any]]:
    """يضمن وجود قياس اهتمام محفوظ لهذه المحاكاة (من الذاكرة أو من جوجل)."""
    if not simulation_id or not keyword:
        return None
    from . import platform_inputs as pi
    from . import platforms as pr
    from . import serp_lookup

    current = pi.load(simulation_id)
    if (current.get('interest') or {}).get('keyword'):
        return current['interest']

    cache_key = f"{keyword.strip().lower()}|{geo}"
    cache = _read_cache()
    cached = cache.get(cache_key) or {}
    trend = None
    if cached.get('ts') and (time.time() - float(cached['ts'])) < CACHE_TTL_SECONDS:
        trend = cached.get('data')
    if not trend:
        if not serp_lookup.is_configured():
            return None
        trend = serp_lookup.trend_summary(keyword, geo, timeout=FETCH_TIMEOUT)
        cache[cache_key] = {'ts': time.time(), 'data': trend}
        _write_cache(cache)

    current['interest'] = trend
    pi.save(simulation_id, current, pr.ORDER)
    return pi.interest_of(current)
