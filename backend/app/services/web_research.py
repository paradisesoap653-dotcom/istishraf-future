"""Topic research with explicit provenance and conservative geographic scope.

Search snippets are retained as unverified retrieval records, not established
facts. This module does not fetch full pages or measure population opinion.
Local Sudan enrichment is conditional; there is no default study country.
Additional query angles are recorded as a plan only, not silently executed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from . import serp_lookup
from .research_integrity import clean_project_title, build_evidence_ledger, plan_queries, EVIDENCE_POLICY

TOPIC_TTL_HOURS = 12
PULSE_TTL_HOURS = 6
MAX_TOPIC_SOURCES = 8
MAX_NEWS_SOURCES = 6

# كلمات تدلّ على أن الموضوع سوداني (فنضيف النبض المحلي)
SUDAN_HINTS = (
    'السودان', 'سوداني', 'الخرطوم', 'بورتسودان', 'دارفور', 'أمدرمان', 'كسلا',
    'عطبرة', 'الجزيرة', 'سنار', 'ود مدني', 'نيالا', 'بنكك', 'أوكاش', 'فوري',
    'الجنيه السوداني', 'ركشة', 'مركوب', 'سودان',
)

# أسئلة النبض الحياتي: تُطرح على محرّك الأخبار دوريًا
PULSE_QUERIES = (
    'السودان أسعار السوق والسلع اليوم',
    'السودان أخبار اليوم الخرطوم',
)


# ============================== أدوات داخلية ==============================

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _storage():
    try:
        from ..models import storage as _s
        return _s
    except Exception:  # pragma: no cover
        return None


def _cache_dir() -> str:
    base = os.environ.get('WEB_RESEARCH_CACHE_DIR') or '/tmp/istishraf_research'
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        return '/tmp'
    return base


def _cache_key(name: str) -> str:
    digest = hashlib.sha1(name.encode('utf-8')).hexdigest()[:16]
    return os.path.join(_cache_dir(), f'{digest}.json')


def _cache_read(name: str, ttl_hours: float) -> Optional[Dict[str, Any]]:
    path = _cache_key(name)
    payload: Optional[Dict[str, Any]] = None
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as handle:
                payload = json.load(handle)
        else:
            store = _storage()
            if store is not None:
                payload = store.read_json(path)
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return None
    try:
        stamped = datetime.fromisoformat(str(payload.get('fetched_at')))
    except Exception:
        return None
    if stamped.tzinfo is None:
        stamped = stamped.replace(tzinfo=timezone.utc)
    if _now() - stamped > timedelta(hours=ttl_hours):
        return None
    return payload


def _cache_write(name: str, payload: Dict[str, Any]) -> None:
    path = _cache_key(name)
    try:
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False)
    except Exception:
        pass
    try:
        store = _storage()
        if store is not None:
            store.write_json(path, payload)
    except Exception:
        pass


def is_cached(name: str, ttl_hours: float) -> bool:
    return _cache_read(name, ttl_hours) is not None


def _clean(text: Any, limit: int = 400) -> str:
    value = re.sub(r'\s+', ' ', str(text or '')).strip()
    return value[:limit]


def _result_to_fact(item: Dict[str, Any], source_label: str = '') -> Optional[Dict[str, str]]:
    title = _clean(item.get('title'), 200)
    snippet = _clean(item.get('snippet') or item.get('description') or '', 400)
    if not (title or snippet):
        return None
    raw_source = item.get('source')
    if isinstance(raw_source, dict):
        raw_source = raw_source.get('name') or ''
    return {
        'title': title,
        'snippet': snippet,
        'source': _clean(raw_source if isinstance(raw_source, str) else source_label, 80),
        'url': _clean(item.get('link') or item.get('url'), 300),
        'date': _clean(item.get('date') or item.get('published_at'), 40),
        'content_level': 'search_snippet',
        'verification_status': 'unverified',
    }


# ============================== البحث نفسه ==============================

def search_topic(topic: str, *, max_results: int = MAX_TOPIC_SOURCES,
                 timeout: float = 30.0) -> List[Dict[str, str]]:
    """بحث جوجل عادي عن الموضوع → وقائع منظّمة."""
    data = serp_lookup._get({  # noqa: SLF001 - نفس الوحدة، نستخدم نداءها الداخلي
        'engine': 'google',
        'q': topic,
        'hl': 'ar' if re.search(r'[\u0600-\u06ff]', topic) else 'en',
        'num': max(4, min(int(max_results), 10)),
    }, timeout=timeout)
    facts: List[Dict[str, str]] = []
    for item in (data.get('organic_results') or [])[:max_results]:
        fact = _result_to_fact(item)
        if fact:
            facts.append(fact)
    # «أسئلة الناس» مادة ممتازة لفهم ما يقلق الجمهور فعلًا
    for block in (data.get('related_questions') or [])[:4]:
        fact = _result_to_fact({
            'title': block.get('question'),
            'snippet': block.get('snippet'),
            'link': block.get('link'),
            'source': 'أسئلة يبحث عنها الناس',
        })
        if fact:
            facts.append(fact)
    return facts


def search_news(topic: str, *, max_results: int = MAX_NEWS_SOURCES,
                window: str = 'qdr:m', timeout: float = 30.0) -> List[Dict[str, str]]:
    """أخبار حديثة عن الموضوع (آخر شهر افتراضيًا)."""
    data = serp_lookup._get({  # noqa: SLF001
        'engine': 'google_news',
        'q': topic,
        'hl': 'ar' if re.search(r'[\u0600-\u06ff]', topic) else 'en',
        'tbs': window,
    }, timeout=timeout)
    facts: List[Dict[str, str]] = []
    for item in (data.get('news_results') or [])[:max_results]:
        source = ''
        src = item.get('source')
        if isinstance(src, dict):
            source = src.get('name') or ''
        elif isinstance(src, str):
            source = src
        fact = _result_to_fact(item, source_label=source)
        if fact:
            if source and not fact['source']:
                fact['source'] = _clean(source, 80)
            facts.append(fact)
    return facts


def gather_topic(topic: str, *, with_news: bool = True,
                 use_cache: bool = True, max_results: int = MAX_TOPIC_SOURCES) -> Dict[str, Any]:
    """حزمة بحث كاملة عن موضوع واحد (مع ذاكرة مؤقتة)."""
    query = _clean(topic, 240)
    if not query:
        return {'ok': False, 'error': 'لا يوجد موضوع للبحث', 'facts': [], 'news': []}
    cache_name = f'topic::evidence-v1::{query}::{int(with_news)}::{max_results}'
    if use_cache:
        cached = _cache_read(cache_name, TOPIC_TTL_HOURS)
        if cached:
            cached['cached'] = True
            return cached

    payload: Dict[str, Any] = {
        'ok': False,
        'topic': query,
        'fetched_at': _now().isoformat(),
        'facts': [],
        'news': [],
        'queries': [query],
        'query_plan': plan_queries(query),
        'executed_angles': ['baseline'],
        'errors': [],
    }
    try:
        payload['facts'] = search_topic(query, max_results=max_results)
        payload['ok'] = bool(payload['facts'])
    except Exception as exc:  # noqa: BLE001
        payload['errors'].append(f'بحث جوجل: {exc}')
    if with_news:
        try:
            payload['news'] = search_news(query)
            payload['ok'] = payload['ok'] or bool(payload['news'])
        except Exception as exc:  # noqa: BLE001
            payload['errors'].append(f'بحث الأخبار: {exc}')
    payload['evidence_ledger'] = build_evidence_ledger(
        payload['facts'] + payload['news'], retrieved_at=payload['fetched_at'])
    if payload['ok']:
        try:
            _cache_write(cache_name, payload)
        except Exception:
            pass
    return payload


def sudan_pulse(*, use_cache: bool = True) -> Dict[str, Any]:
    """نبض الشارع السوداني الآن: أخبار + أسعار سوق (يبحث عنه مرة كل ٦ ساعات)."""
    if use_cache:
        cached = _cache_read('sudan_pulse', PULSE_TTL_HOURS)
        if cached:
            cached['cached'] = True
            return cached
    payload: Dict[str, Any] = {
        'ok': False,
        'fetched_at': _now().isoformat(),
        'news': [],
        'queries': list(PULSE_QUERIES),
        'errors': [],
    }
    for query in PULSE_QUERIES:
        try:
            payload['news'].extend(search_news(query, max_results=4, window='qdr:w'))
        except Exception as exc:  # noqa: BLE001
            payload['errors'].append(f'{query}: {exc}')
    payload['ok'] = bool(payload['news'])
    if payload['ok']:
        try:
            _cache_write('sudan_pulse', payload)
        except Exception:
            pass
    return payload


def mentions_sudan(text: str) -> bool:
    haystack = (text or '').lower()
    return any(hint.lower() in haystack for hint in SUDAN_HINTS)


# ============================== التخزين بجانب المحاكاة ==============================

def research_path(sim_dir: str) -> str:
    return os.path.join(sim_dir, 'research.json')


def save(sim_dir: str, payload: Dict[str, Any]) -> None:
    path = research_path(sim_dir)
    try:
        os.makedirs(sim_dir, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except Exception:
        pass
    try:
        store = _storage()
        if store is not None:
            store.write_json(path, payload)
    except Exception:
        pass


def load(sim_dir: str) -> Optional[Dict[str, Any]]:
    path = research_path(sim_dir)
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as handle:
                return json.load(handle)
        store = _storage()
        if store is not None:
            data = store.read_json(path)
            if isinstance(data, dict):
                return data
    except Exception:
        return None
    return None


def gather_for_simulation(requirement: str, *, title: str = '',
                          sim_dir: Optional[str] = None,
                          use_cache: bool = True) -> Dict[str, Any]:
    """يجمع حزمة البحث لمحاكاة كاملة: الموضوع + (إن كان سودانيًا) النبض المحلي."""
    clean_title = clean_project_title(_clean(title, 200))
    main_query = _clean(requirement, 220) or clean_title
    bundle: Dict[str, Any] = {
        'fetched_at': _now().isoformat(),
        'requirement': _clean(requirement, 1200),
        'title': clean_title,
        'topic': gather_topic(main_query, use_cache=use_cache) if main_query else None,
        'pulse': None,
        'ok': False,
        'errors': [],
    }
    # Local enrichment is opt-in by explicit geographic context, never by
    # language, currency, profession, or an unrelated publisher name.
    scope = f'{requirement} {clean_title}'.casefold()
    if re.search(r'السودان|سوداني|\bsudan(?:ese)?\b', scope):
        bundle['pulse'] = sudan_pulse(use_cache=use_cache)
    bundle['ok'] = bool((bundle['topic'] or {}).get('ok') or (bundle['pulse'] or {}).get('ok'))
    if sim_dir:
        save(sim_dir, bundle)
    return bundle


# ============================== بناء نص للبرومبت ==============================

def _fact_lines(facts: Sequence[Dict[str, str]], limit: int = 8) -> List[str]:
    lines: List[str] = []
    for fact in list(facts)[:limit]:
        title = fact.get('title') or ''
        snippet = fact.get('snippet') or ''
        source = fact.get('source') or ''
        date = fact.get('date') or ''
        meta = ' — '.join([part for part in (source, date) if part])
        body = f'{title}. {snippet}'.strip()
        body = body[:300]
        url = fact.get('url') or ''
        label = ' | '.join(part for part in (meta, url) if part)
        lines.append(f'- {body}' + (f' [{label}]' if label else ''))
    return lines


def prompt_block(bundle: Optional[Dict[str, Any]], *, max_facts: int = 8) -> str:
    """كتلة عربية تُحقن في البرومبت: ما وجدناه فعلًا + قاعدة عدم الاختراع."""
    if not bundle:
        return ''
    topic = bundle.get('topic') or {}
    pulse = bundle.get('pulse') or {}
    facts = topic.get('facts') or []
    news = topic.get('news') or []
    pulse_news = pulse.get('news') or []

    parts: List[str] = []
    if facts or news:
        parts.append('## نتائج بحث عن الموضوع — مقتطفات غير متحقق منها بالكامل')
        lines = _fact_lines(facts, max_facts)
        lines += _fact_lines(news, max(2, max_facts - len(lines)))
        parts.extend(lines)
    if pulse_news:
        parts.append('\n## ما يجري في السودان الآن (أخبار حديثة)')
        parts.extend(_fact_lines(pulse_news, 6))
    if not parts:
        return ''
    parts.append(
        '\n### كيف تستخدم هذه الوقائع\n'
        '- نتائج البحث مقتطفات وليست قراءة كاملة للمصادر، ولا تثبت وحدها صحة الادعاء أو تمثيل المجتمع.\n'
        '- استخدم هذه المعلومات لفهم الموضوع بعمق: الأسماء، الأرقام الرسمية المذكورة، '
        'الجهات، التواريخ، وما يشتكي منه الناس فعلًا.\n'
        '- لا تخترع رقمًا أو خبرًا أو اسمًا غير مذكور هنا أو في المستند. إن لم تجد '
        'معلومة، اكتب «غير متوفر» بدل التخمين.\n'
        '- عندما تستشهد برقم من هذه القائمة، اذكر مصدره وتاريخه كما هما مكتوبان.\n'
        '- اربط الموضوع بما يعيشه الناس: السعر، الوقت، الطريق، الكهرباء، البنك، '
        'الأمن، العمل — لا الكلمات الكبيرة وحدها.'
    )
    parts.append(EVIDENCE_POLICY)
    return '\n'.join(parts).strip()


def summary_line(bundle: Optional[Dict[str, Any]]) -> str:
    """سطر قصير للواجهة: هل البحث نجح وكم مصدرًا."""
    if not bundle:
        return 'لم يُجرَ بحث ويب لهذه المحاكاة'
    topic = bundle.get('topic') or {}
    pulse = bundle.get('pulse') or {}
    n_facts = len(topic.get('facts') or []) + len(topic.get('news') or [])
    n_pulse = len(pulse.get('news') or [])
    if not n_facts and not n_pulse:
        return 'تعذّر البحث في الويب (لا مصادر) — أكملنا بلا وقائع خارجية'
    bits = []
    if n_facts:
        bits.append(f'{n_facts} نتيجة عن الموضوع')
    if n_pulse:
        bits.append(f'{n_pulse} خبرًا عن السودان')
    stamp = ''
    fetched = topic.get('fetched_at') or pulse.get('fetched_at')
    if fetched:
        try:
            stamped = datetime.fromisoformat(fetched)
            stamp = stamped.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M')
        except Exception:
            stamp = ''
    return 'بحث الويب: ' + '، '.join(bits) + (f' (آخر تحديث {stamp} UTC)' if stamp else '')
