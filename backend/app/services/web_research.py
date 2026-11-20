"""Topic research with explicit provenance and conservative geographic scope.

Search snippets are retained as unverified retrieval records, not established
facts. Several query angles are executed inside a hard call budget; angles that
the budget did not reach are recorded as *not executed*, never implied.
A small number of pages may be retrieved (limits in page_retrieval) and the
snippets are then checked for textual support against that retrieved text.
Retrieval is not verification: it proves reachability, not truth.
Local Sudan enrichment is conditional; there is no default study country.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from . import claim_check
from . import page_retrieval
from . import serp_lookup
from .research_integrity import (
    EVIDENCE_POLICY,
    build_evidence_ledger,
    clean_project_title,
    plan_queries,
    plan_search_queries,
    resolve_search_budget,
)

CACHE_VERSION = 'evidence-v2'
TOPIC_TTL_HOURS = 12
PULSE_TTL_HOURS = 6
MAX_TOPIC_SOURCES = 8
MAX_NEWS_SOURCES = 6
DEFAULT_PAGE_FETCHES = 2

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


def _env_number(name: str):
    raw = str(os.environ.get(name) or '').strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def search_budget() -> Dict[str, Any]:
    """ميزانية النداءات: افتراضات محافظة، ويمكن للمشغّل تعديلها بالبيئة."""
    overrides = {
        'max_query_calls': _env_number('ISTISHRAF_SEARCH_QUERY_CALLS'),
        'max_news_calls': _env_number('ISTISHRAF_SEARCH_NEWS_CALLS'),
        'max_results_per_call': _env_number('ISTISHRAF_SEARCH_RESULTS_PER_CALL'),
        'per_call_timeout_seconds': _env_number('ISTISHRAF_SEARCH_TIMEOUT'),
    }
    return resolve_search_budget({k: v for k, v in overrides.items() if v is not None})


def page_budget() -> Dict[str, Any]:
    # الصفر قيمة صريحة تعني «لا سحب صفحات»، لا «استخدم الافتراضي».
    raw = _env_number('ISTISHRAF_PAGE_FETCHES')
    return page_retrieval.resolve_page_budget({
        'max_pages': DEFAULT_PAGE_FETCHES if raw is None else raw,
    })


def search_multi_angle(topic: str, *, budget: Optional[Dict[str, Any]] = None,
                       searcher=None, timeout: Optional[float] = None) -> Dict[str, Any]:
    """ينفّذ زوايا البحث المتاحة داخل الميزانية، ويسجّل ما لم يُنفَّذ بصراحة.

    لا يتجاوز عدد النداءات الميزانية أبدًا، والفشل يُسجّل فشلًا لا نجاحًا،
    ونتيجة فارغة تُسجّل «لا نتائج» لا «تمّ البحث بنجاح».
    """
    budget = budget or search_budget()
    run = searcher or search_topic
    plan = plan_search_queries(topic, budget=budget)
    max_calls = int(budget['max_query_calls'])
    call_timeout = float(timeout if timeout is not None else budget['per_call_timeout_seconds'])

    records: List[Dict[str, Any]] = []
    facts: List[Dict[str, str]] = []
    errors: List[str] = []
    used = 0
    for step in plan:
        entry = {'angle': step['angle'], 'query': step['query'], 'priority': step['priority']}
        if used >= max_calls:
            entry['status'] = 'skipped_budget'
            entry['results'] = 0
            records.append(entry)
            continue
        used += 1
        try:
            found = list(run(step['query'], max_results=step['max_results'], timeout=call_timeout) or [])
        except Exception as exc:  # noqa: BLE001 - الفشل يُسجَّل ولا يُخفى
            entry['status'] = 'error'
            entry['results'] = 0
            entry['error'] = str(exc)[:180]
            errors.append(f"{step['angle']}: {str(exc)[:160]}")
            records.append(entry)
            continue
        entry['results'] = len(found)
        entry['status'] = 'executed' if found else 'empty'
        records.append(entry)
        facts.extend(found)

    executed = [r['angle'] for r in records if r['status'] in {'executed', 'empty'}]
    skipped = [r['angle'] for r in records if r['status'] == 'skipped_budget']
    failed = [r['angle'] for r in records if r['status'] == 'error']
    # الأشدّ سوءًا يغلب في التسمية، والحالتان تُسجَّلان معًا في skipped/failed_angles
    if used == 0:
        status = 'not_started'
    elif len(failed) == used:
        status = 'failed'
    elif failed:
        status = 'partial_errors'
    elif skipped:
        status = 'partial_budget'
    else:
        status = 'complete'
    return {
        'facts': facts,
        'angles': records,
        'executed_angles': executed,
        'skipped_angles': skipped,
        'failed_angles': failed,
        'errors': errors,
        'budget': {'max_query_calls': max_calls, 'used': used,
                   'exhausted': bool(skipped), 'remaining': max(0, max_calls - used)},
        'status': status,
    }


def gather_topic(topic: str, *, with_news: bool = True,
                 use_cache: bool = True, max_results: int = MAX_TOPIC_SOURCES,
                 multi_angle: bool = True, retrieve_pages: bool = True,
                 budget: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """حزمة بحث كاملة عن موضوع واحد (مع ذاكرة مؤقتة وحدود صريحة)."""
    query = _clean(topic, 240)
    if not query:
        return {'ok': False, 'error': 'لا يوجد موضوع للبحث', 'facts': [], 'news': []}
    budget = budget or search_budget()
    pages_budget = page_budget()
    cache_name = (f'topic::{CACHE_VERSION}::{query}::{int(with_news)}::{max_results}'
                  f'::{int(multi_angle)}::{int(retrieve_pages)}'
                  f'::q{budget["max_query_calls"]}::n{budget["max_news_calls"]}'
                  f'::p{pages_budget["max_pages"]}')
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
        'queries': [],
        'query_plan': plan_queries(query),
        'executed_angles': [],
        'search_report': {},
        'errors': [],
        'pages': [],
        'verification': {},
        'evidence_ledger': {},
    }
    try:
        if multi_angle:
            run = search_multi_angle(query, budget=budget)
            payload['facts'] = run['facts']
            payload['queries'] = [r['query'] for r in run['angles']
                                  if r['status'] in {'executed', 'empty'}]
            payload['executed_angles'] = run['executed_angles']
            payload['skipped_angles'] = run['skipped_angles']
            payload['search_report'] = {
                'status': run['status'], 'angles': run['angles'], 'budget': run['budget'],
            }
            payload['errors'].extend(run['errors'])
        else:
            payload['facts'] = search_topic(
                query, max_results=min(int(max_results), int(budget['max_results_per_call'])),
                timeout=float(budget['per_call_timeout_seconds']))
            payload['queries'] = [query]
            payload['executed_angles'] = ['baseline']
            payload['search_report'] = {
                'status': 'complete' if payload['facts'] else 'empty',
                'angles': [{'angle': 'baseline', 'query': query,
                            'status': 'executed' if payload['facts'] else 'empty',
                            'results': len(payload['facts'])}],
                'budget': {'max_query_calls': 1, 'used': 1, 'exhausted': False, 'remaining': 0},
            }
    except Exception as exc:  # noqa: BLE001
        payload['errors'].append(f'بحث الموضوع: {exc}')
        payload['search_report'] = {'status': 'failed', 'angles': [], 'budget': {}}
    payload['ok'] = bool(payload['facts'])

    if with_news and int(budget['max_news_calls']) > 0:
        try:
            payload['news'] = search_news(
                query, max_results=min(int(budget['max_results_per_call']), MAX_NEWS_SOURCES),
                timeout=float(budget['per_call_timeout_seconds']))
            payload['ok'] = payload['ok'] or bool(payload['news'])
        except Exception as exc:  # noqa: BLE001
            payload['errors'].append(f'بحث الأخبار: {exc}')

    payload['evidence_ledger'] = build_evidence_ledger(
        payload['facts'] + payload['news'], retrieved_at=payload['fetched_at'])

    if retrieve_pages:
        payload['pages'] = _retrieve_source_pages(payload['evidence_ledger'], pages_budget)
        payload['evidence_ledger'] = _apply_pages(payload['evidence_ledger'], payload['pages'])
        payload['verification'] = claim_check.verify_snippets(
            payload['evidence_ledger'].get('sources') or [], payload['pages'])

    if payload['ok']:
        try:
            _cache_write(cache_name, payload)
        except Exception:
            pass
    return payload


def _retrieve_source_pages(ledger: Dict[str, Any], pages_budget: Dict[str, Any]) -> List[Dict[str, Any]]:
    urls = [source.get('url') for source in (ledger.get('sources') or []) if source.get('url')]
    try:
        return page_retrieval.retrieve_pages(urls, budget=pages_budget)['pages']
    except Exception:  # noqa: BLE001 - تعذّر السحب لا يوقف البحث
        return []


def _apply_pages(ledger: Dict[str, Any], pages: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """يرفع مستوى المصدر إلى «نص كامل» فقط إن سُحب فعلًا، ويصحّح حدود السجلّ."""
    fetched = {str(page.get('url')): page for page in (pages or []) if page.get('status') == 'fetched'}
    sources = ledger.get('sources') or []
    for source in sources:
        page = fetched.get(str(source.get('url')))
        if page:
            source['content_level'] = 'full_page'
            source['retrieved_characters'] = int(page.get('chars') or 0)
            source['page_truncated'] = bool(page.get('truncated'))
        else:
            source['content_level'] = 'search_snippet'
    if fetched:
        limitations = [item for item in (ledger.get('limitations') or [])
                       if 'full pages have not been retrieved' not in item]
        limitations.insert(0, f'Full text retrieved for {len(fetched)} of {len(sources)} sources; '
                              'the rest are search snippets only.')
        ledger['limitations'] = limitations
    return ledger



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
    pages = topic.get('pages') or []
    read = [page for page in pages if page.get('status') == 'fetched' and (page.get('text') or '').strip()]
    if read:
        parts.append('\n## مقاطع من نصوص قرأناها بالكامل (ليست كل الصفحة)')
        for page in read[:2]:
            excerpt = ' '.join(str(page.get('text'))[:700].split())
            parts.append(f"- {excerpt} [نص مقروء: {page.get('url')}]")
    blocked = [page for page in pages if page.get('status') in {'blocked', 'error', 'skipped'}]
    if blocked:
        reasons = '، '.join(sorted({str(page.get('error') or page.get('status')) for page in blocked}))
        parts.append(f'\n(لم نقرأ {len(blocked)} صفحة: {reasons}. لا تُنسب إليها معلومات.)')
    verification = topic.get('verification') or {}
    counts = verification.get('counts') or {}
    if counts:
        parts.append(
            '\n### حالة نقل المقتطفات\n'
            f"- مقتطفات طابقت نص الصفحة: {counts.get('confirmed_in_page', 0)}، "
            f"لم نجدها في الصفحة: {counts.get('not_found_in_page', 0)}، "
            f"نفيها مختلف عن الصفحة: {counts.get('negation_differs', 0)}، "
            f"صفحتها لم تُقرأ: {counts.get('page_not_retrieved', 0)}.\n"
            '- «لم نجدها في الصفحة» تعني: لا تنقلها كاقتباس حرفي؛ أعد صياغتها كادعاء منقول '
            'بحذر أو تجاوزها.\n'
            '- «نفيها مختلف» تعني: الكلمات موجودة لكن الصفحة لا تنفي كما ينفي المقتطف؛ '
            'لا تقتبسها كما هي، واذكر الفرق بدل اختيار أحد الصيغتين.'
        )
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
    angles = topic.get('executed_angles') or []
    skipped = topic.get('skipped_angles') or []
    if angles:
        angles_bit = f'{len(angles)} زاوية بحث'
        if skipped:
            angles_bit += f' ({len(skipped)} زاوية لم تنفَّذ لضيق الميزانية)'
        bits.append(angles_bit)
    read_pages = len([page for page in (topic.get('pages') or []) if page.get('status') == 'fetched'])
    if read_pages:
        bits.append(f'قراءة كاملة لـ{read_pages} صفحة')
    stamp = ''
    fetched = topic.get('fetched_at') or pulse.get('fetched_at')
    if fetched:
        try:
            stamped = datetime.fromisoformat(fetched)
            stamp = stamped.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M')
        except Exception:
            stamp = ''
    return 'بحث الويب: ' + '، '.join(bits) + (f' (آخر تحديث {stamp} UTC)' if stamp else '')
