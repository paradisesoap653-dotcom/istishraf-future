"""سحب نصّ الصفحات المذكورة في سجلّ المصادر — بحدود صارمة وصدق كامل.

ما يفعله: يطلب الصفحة مرة واحدة، بلا كوكيز وبلا تسجيل دخول وبلا تنفيذ
جافاسكربت، ويحوّل HTML إلى نص عادي، ثم يتوقف عند أول حدّ يبلغه.

ما لا يفعله ولن يدّعيه:
- لا يثبت أن ما في الصفحة صحيح.
- لا يجعل الناشر مستقلًا أو موثوقًا.
- لا يقرأ صفحات تدفع حائطًا أو تتطلب تسجيل دخول (ونقول ذلك صراحة).
- لا يفتح ملفات PDF ولا الصور ولا الفيديو: يعلن أنها لم تُقرأ.
- لا يلمس الشبكة الداخلية ولا عناوين الخدمات السحابية الوصفية (حماية SSRF).

كل نتيجة سحب تحمل حالتها: fetched / blocked / skipped / error. والحالة
الوحيدة التي تعني «قرأنا نصًا» هي fetched، وما عداها لا يُحتسب مصدرًا مقروءًا.
"""

from __future__ import annotations

import html as html_lib
import ipaddress
import re
import socket
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlsplit

import httpx

from .research_integrity import canonical_source_url

DEFAULT_PAGE_BUDGET = {
    'max_pages': 2,
    'max_bytes': 800_000,
    'max_chars': 12_000,
    'timeout_seconds': 12.0,
    'max_redirects': 3,
}

_BUDGET_LIMITS = {
    'max_pages': (0, 4),
    'max_bytes': (50_000, 2_000_000),
    'max_chars': (1_000, 40_000),
    'timeout_seconds': (4.0, 30.0),
    'max_redirects': (0, 5),
}

TEXTUAL_CONTENT_TYPES = ('text/html', 'application/xhtml+xml', 'text/plain')
BLOCKED_HOSTS = {
    'localhost', 'metadata', 'metadata.google.internal', 'instance-data',
    '169.254.169.254', '::1', '0.0.0.0',
}
BLOCKED_HOST_SUFFIXES = ('.localhost', '.local', '.internal', '.home.arpa', '.lan')
# الوصف هنا يجب أن يطابق السلوك: لا فحص robots.txt في هذا المسار.
USER_AGENT = 'IstishrafResearch/1.0 (+analysis retrieval; no indexing)'

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

_SKIP_TAGS = re.compile(r'(?is)<(script|style|noscript|template|svg|iframe|canvas)[^>]*>.*?</\1>')
_COMMENTS = re.compile(r'(?s)<!--.*?-->')
_BLOCK_BREAKS = re.compile(r'(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr|section|article|header|footer|blockquote)>')
_ANY_TAG = re.compile(r'(?s)<[^>]+>')
_SPACES = re.compile(r'[ \t\f\v\u00a0]+')
_BLANKS = re.compile(r'\n\s*\n+')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_page_budget(overrides=None) -> Dict[str, Any]:
    budget: Dict[str, Any] = dict(DEFAULT_PAGE_BUDGET)
    for key, (low, high) in _BUDGET_LIMITS.items():
        raw = (overrides or {}).get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value != value:
            continue
        budget[key] = int(min(max(value, low), high)) if isinstance(low, int) else float(min(max(value, low), high))
    return budget


def _ip_blocked(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    return bool(
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
        or ip.is_reserved or ip.is_unspecified
    )


def url_blocked_reason(url: str, *, resolve_dns: bool = True) -> str:
    """سبب رفض العنوان، أو نص فارغ إن كان مقبولًا."""
    parsed = urlsplit(str(url or '').strip())
    if parsed.scheme.lower() not in {'http', 'https'}:
        return 'scheme_not_http'
    host = (parsed.hostname or '').strip().lower()
    if not host:
        return 'missing_host'
    if parsed.username or parsed.password:
        return 'credentials_in_url'
    if host in BLOCKED_HOSTS or host.endswith(BLOCKED_HOST_SUFFIXES):
        return 'internal_host'
    try:
        ipaddress.ip_address(host)
        return 'internal_host' if _ip_blocked(host) else ''
    except ValueError:
        pass
    if not resolve_dns:
        return ''
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:  # noqa: BLE001 - فشل التحليل ليس تصريحًا بالمرور
        return 'dns_unresolved'
    for info in infos:
        address = str((info[4] or ('',))[0])
        if _ip_blocked(address):
            return 'resolves_to_internal_address'
    return ''


def html_to_text(markup: str) -> str:
    text = _SKIP_TAGS.sub(' ', str(markup or ''))
    text = _COMMENTS.sub(' ', text)
    text = _BLOCK_BREAKS.sub('\n', text)
    text = _ANY_TAG.sub(' ', text)
    text = html_lib.unescape(text)
    text = _SPACES.sub(' ', text)
    text = _BLANKS.sub('\n', text)
    return text.strip()


def _decode(body: bytes, charset: str) -> str:
    for candidate in (charset, 'utf-8', 'windows-1256', 'latin-1'):
        if not candidate:
            continue
        try:
            return body.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode('utf-8', 'replace')


def _charset_of(content_type: str) -> str:
    match = re.search(r'charset=([\w-]+)', str(content_type or ''), re.IGNORECASE)
    return match.group(1) if match else ''


def _read_limited(response, max_bytes: int):
    """يقرأ حتى الحدّ فقط، ويعيد (البايتات، هل قُصّت)."""
    chunks: List[bytes] = []
    remaining = max_bytes
    truncated = False
    try:
        iterator: Iterable[bytes] = response.iter_bytes()
    except Exception:  # noqa: BLE001
        iterator = [response.content or b'']
    for chunk in iterator:
        if not chunk:
            continue
        if remaining <= 0:
            truncated = True
            break
        piece = chunk[:remaining]
        chunks.append(piece)
        remaining -= len(piece)
        if len(piece) < len(chunk):
            truncated = True
            break
    return b''.join(chunks), truncated


def fetch_page(url: str, *, budget=None, client=None, resolve_dns: bool = True) -> Dict[str, Any]:
    """سحب صفحة واحدة. لا يرفع استثناءً: كل نتيجة تحمل حالتها."""
    budget = resolve_page_budget(budget)
    requested = str(url or '').strip()
    record: Dict[str, Any] = {
        'requested_url': requested[:500],
        'url': canonical_source_url(requested),
        'final_url': '',
        'status': 'error',
        'http_status': None,
        'content_type': '',
        'chars': 0,
        'truncated': False,
        'text': '',
        'error': '',
        'retrieved_at': _now(),
        'content_level': 'none',
        'redirects': 0,
        'blocked_redirect': '',
    }
    if not record['url']:
        record['status'] = 'blocked'
        record['error'] = 'invalid_url'
        return record
    reason = url_blocked_reason(record['url'], resolve_dns=resolve_dns)
    if reason:
        record['status'] = 'blocked'
        record['error'] = reason
        return record

    own_client = client is None
    http = client or httpx.Client(
        follow_redirects=False,
        timeout=float(budget['timeout_seconds']),
        headers={'User-Agent': USER_AGENT,
                 'Accept': 'text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1'},
        trust_env=False,
    )
    try:
        # التحويلات تُتبع يدويًا خطوة بخطوة: كل عنوان تحويل يُفحص بنفس حراسة
        # العنوان الأول قبل أن يُطلب، فلا تُلتفّ الحراسة بتحويل إلى الشبكة الداخلية.
        current = record['url']
        max_redirects = int(budget['max_redirects'])
        hops = 0
        body = b''
        while True:
            with http.stream('GET', current, follow_redirects=False) as response:
                status = int(getattr(response, 'status_code', 0) or 0)
                headers = response.headers or {}
                if status in REDIRECT_STATUSES:
                    location = str(headers.get('location') or '').strip()
                    if not location:
                        record['status'] = 'error'
                        record['error'] = f'http_{status}_without_location'
                        return record
                    target = canonical_source_url(urljoin(current, location))
                    if not target:
                        record['status'] = 'blocked'
                        record['error'] = 'redirect_to_invalid_url'
                        return record
                    if hops >= max_redirects:
                        record['status'] = 'error'
                        record['error'] = 'too_many_redirects'
                        record['final_url'] = target
                        return record
                    reason = url_blocked_reason(target, resolve_dns=resolve_dns)
                    if reason:
                        # التحويل مرفوض قبل أي اتصال به: لا نص ولا محتوى من الشبكة الداخلية
                        record['status'] = 'blocked'
                        record['error'] = f'redirect_blocked:{reason}'
                        record['blocked_redirect'] = target
                        record['final_url'] = target
                        record['redirects'] = hops + 1
                        return record
                    hops += 1
                    current = target
                    continue
                record['http_status'] = status
                record['redirects'] = hops
                record['content_type'] = str(headers.get('content-type') or '')[:120]
                final_url = str(getattr(response, 'url', '') or '')
                record['final_url'] = canonical_source_url(final_url) or current
                if status >= 400:
                    record['status'] = 'error'
                    record['error'] = f'http_{status}'
                    return record
                base_type = record['content_type'].split(';')[0].strip().lower()
                if base_type and not any(base_type.startswith(t) for t in TEXTUAL_CONTENT_TYPES):
                    record['status'] = 'skipped'
                    record['error'] = f'unsupported_content_type:{base_type[:40]}'
                    return record
                body, truncated = _read_limited(response, int(budget['max_bytes']))
                record['truncated'] = truncated
                break
    except Exception as exc:  # noqa: BLE001
        record['status'] = 'error'
        record['error'] = f'{type(exc).__name__}: {str(exc)[:160]}'
        return record
    finally:
        if own_client:
            try:
                http.close()
            except Exception:  # noqa: BLE001
                pass

    text = _decode(body, _charset_of(record['content_type']))
    if 'html' in record['content_type'].lower() or re.search(r'(?i)<(html|body|div|p)[\s>]', text[:2000]):
        text = html_to_text(text)
    text = text[: int(budget['max_chars'])]
    record['chars'] = len(text)
    record['text'] = text
    if not text.strip():
        record['status'] = 'skipped'
        record['error'] = 'empty_text'
        return record
    record['status'] = 'fetched'
    record['content_level'] = 'full_page'
    return record


def public_pages(pages: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """نسخة آمنة للنشر: بلا نص الصفحة، وببقية الحقول كما هي.

    مسارات الـAPI جميعها تستخدم هذه الدالة، حتى لا يعرض مسار ما يخفيه آخر.
    """
    return [
        {key: value for key, value in page.items() if key != 'text'}
        for page in (pages or []) if isinstance(page, dict)
    ]


def retrieve_pages(urls: Iterable[str], *, budget=None, fetcher=None,
                   resolve_dns: bool = True) -> Dict[str, Any]:
    """سحب حتى الميزانية فقط: لا محاولات إضافية، ولا عنوان يُسحب مرتين."""
    budget = resolve_page_budget(budget)
    fetch = fetcher or (lambda target: fetch_page(target, budget=budget, resolve_dns=resolve_dns))
    seen = set()
    records: List[Dict[str, Any]] = []
    attempts = 0
    skipped_for_budget: List[str] = []
    for raw in urls:
        url = canonical_source_url(raw)
        if not url or url in seen:
            continue
        seen.add(url)
        if attempts >= int(budget['max_pages']):
            skipped_for_budget.append(url)
            if len(skipped_for_budget) >= 20:
                break
            continue
        attempts += 1
        try:
            records.append(fetch(url))
        except Exception as exc:  # noqa: BLE001 - الفشل يسجَّل ولا يُخفي
            records.append({
                'requested_url': url, 'url': url, 'final_url': '', 'status': 'error',
                'http_status': None, 'content_type': '', 'chars': 0, 'truncated': False,
                'text': '', 'error': f'{type(exc).__name__}: {str(exc)[:160]}',
                'retrieved_at': _now(), 'content_level': 'none',
            })
    fetched = [r for r in records if r.get('status') == 'fetched']
    return {
        'pages': records,
        'attempts': attempts,
        'fetched': len(fetched),
        'failed': len(records) - len(fetched),
        'skipped_for_budget': skipped_for_budget,
        'budget': {
            'max_pages': budget['max_pages'],
            'max_bytes': budget['max_bytes'],
            'max_chars': budget['max_chars'],
            'timeout_seconds': budget['timeout_seconds'],
            'exhausted': bool(skipped_for_budget),
        },
    }


def page_texts(pages: Optional[Iterable[Dict[str, Any]]]) -> Dict[str, str]:
    """url ← النص المقروء فعلًا فقط (لا شيء للنصوص الفارغة)."""
    texts: Dict[str, str] = {}
    for page in pages or []:
        if page.get('status') == 'fetched' and (page.get('text') or '').strip():
            texts[str(page.get('url'))] = str(page.get('text'))
    return texts
