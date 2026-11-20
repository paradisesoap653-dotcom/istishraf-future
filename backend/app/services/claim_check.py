"""فحص الدعم اللفظي للادعاءات مقابل ما سحبناه فعلًا.

هذا ليس «تحققًا من الحقيقة»، ولا نموذج استنتاج (entailment)، ولا بديلًا عن
قارئ بشري. هو فحص آلي محافظ يجيب سؤالًا واحدًا فقط:

    هل توجد في نص المصدر كلمات وأرقام كافية تطابق الادعاء لفظيًا؟

ولذلك:
- «مطابقة» تعني: تطابق لفظي كافٍ — لا تعني أن الادعاء صحيح.
- «لا مطابقة» تعني: لم نجد التطابق — لا تعني أن الادعاء كاذب؛ قد يكون
  المصدر نقل الرقم بصيغة أخرى، أو الصفحة لم تُقرأ كاملة، أو لم تُسحب أصلًا.
- كل ادعاء يحمل عدّاد ما فُحص وما لم يُفحص، حتى لا يُقرأ الجواب أكثر مما يحتمل.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

NOTE = ('مطابقة لفظية آلية فقط: لا تثبت صحة الادعاء، ولا تنفي الخطأ أو الاقتطاع من السياق. '
        'الغياب لا يُعدّ تكذيبًا.')

MIN_WORDS = 3
MATCH_COVERAGE = 0.7
# الكلمات المتطابقة يجب أن تقع قريبة من بعضها، لا متفرقة في صفحة كاملة.
WINDOW_CHARS = 240
MAX_OCCURRENCES = 60
# أدوات نفي/استثناء: إن وُجدت في الادعاء ولم نجدها في المقطع المطابق، ننبّه ولا نحكم.
NEGATIONS = frozenset({'لم', 'لن', 'ليس', 'ليست', 'غير', 'دون', 'بلا', 'لا', 'عدا', 'سوى', 'انتفى'})

_AR_DIACRITICS = re.compile(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]')
_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
_WORD = re.compile(r'[\w\u0600-\u06ff]+', re.UNICODE)
_NUMBER = re.compile(r'\d+(?:[.,]\d+)?')
_SENTENCE = re.compile(r'[^.!?؟؛\n]+[.!?؟؛\n]?')


def _normalise(text: Any) -> str:
    value = str(text or '').translate(_DIGITS)
    value = _AR_DIACRITICS.sub('', value)
    for source, target in (('أ', 'ا'), ('إ', 'ا'), ('آ', 'ا'), ('ى', 'ي'), ('ة', 'ه'), ('ؤ', 'و'), ('ئ', 'ي')):
        value = value.replace(source, target)
    return value.casefold()


def significant_words(text: Any) -> List[str]:
    """كلمات ذات معنى للمطابقة: بلا تشكيل، بلا أرقام، بلا كلمات قصيرة."""
    words: List[str] = []
    for token in _WORD.findall(_normalise(text)):
        if token.isdigit() or len(token) < 4:
            continue
        if token not in words:
            words.append(token)
    return words


def claim_numbers(text: Any) -> List[str]:
    numbers: List[str] = []
    for number in _NUMBER.findall(_normalise(text)):
        if number not in numbers:
            numbers.append(number)
    return numbers


def _word_pattern(word: str) -> str:
    return r'(?<!\w)' + re.escape(word) + r'(?!\w)'


def _number_present(number: str, haystack: str) -> bool:
    """الرقم يُطابق كرقم كامل: «30» لا تُطابق داخل «1300» ولا «2015»."""
    return re.search(r'(?<![\d.,])' + re.escape(number) + r'(?![\d])', haystack) is not None


def _has_negation(text: Any) -> bool:
    return any(token in NEGATIONS for token in _WORD.findall(_normalise(text)))


def _window_match(words: List[str], haystack: str) -> Dict[str, Any]:
    """أفضل مقطع: أكبر عدد من كلمات الادعاء داخل نافذة واحدة من النص.

    يعيد تغطية المقطع وتغطية الصفحة كلها ونص المقطع نفسه، حتى يرى القارئ
    على أي أساس قيلت المطابقة.
    """
    events: List[tuple] = []
    for word in words:
        seen_here = 0
        for match in re.finditer(_word_pattern(word), haystack):
            events.append((match.start(), match.end(), word))
            seen_here += 1
            if seen_here >= MAX_OCCURRENCES:
                break
    present_page = len({event[2] for event in events})
    page_coverage = present_page / len(words) if words else 0.0
    if not events:
        return {'coverage': 0.0, 'page_coverage': page_coverage, 'excerpt': ''}
    events.sort()
    counts: Dict[str, int] = {}
    left = 0
    best_count = 0
    best_span = (events[0][0], events[0][1])
    for right, (start, end, word) in enumerate(events):
        counts[word] = counts.get(word, 0) + 1
        while start - events[left][0] > WINDOW_CHARS:
            old = events[left][2]
            counts[old] -= 1
            if counts[old] <= 0:
                counts.pop(old, None)
            left += 1
        if len(counts) > best_count:
            best_count = len(counts)
            best_span = (events[left][0], end)
    coverage = best_count / len(words) if words else 0.0
    excerpt = ' '.join(haystack[max(0, best_span[0] - 20): best_span[1] + 60].split())
    return {'coverage': coverage, 'page_coverage': page_coverage, 'excerpt': excerpt[:300]}


def _source_record(source: Dict[str, Any]) -> Dict[str, Any]:
    """توحيد شكل المصدر: سجلّ السجلّ (مقتطف) أو نتيجة سحب صفحة (نص كامل)."""
    content_level = str(source.get('content_level') or '')
    text = source.get('text') if content_level == 'full_page' else (source.get('snippet') or source.get('text'))
    return {
        'source_id': str(source.get('source_id') or source.get('url') or ''),
        'url': source.get('url') or source.get('final_url') or '',
        'title': str(source.get('title') or '')[:200],
        'content_level': 'full_page' if content_level == 'full_page' else 'search_snippet',
        'text': str(text or ''),
    }


def check_claim(claim: str, sources: Optional[Iterable[Dict[str, Any]]]) -> Dict[str, Any]:
    """فحص ادعاء واحد. الحالات الممكنة صريحة، ولا واحدة منها تعني «صحيح»."""
    words = significant_words(claim)
    numbers = claim_numbers(claim)
    prepared = [_source_record(s) for s in (sources or [])]
    prepared = [s for s in prepared if s['text'].strip()]
    record: Dict[str, Any] = {
        'claim': ' '.join(str(claim or '').split())[:400],
        'status': 'unverifiable_no_source',
        'coverage': 0.0,
        'page_coverage': 0.0,
        'content_level': '',
        'matched_source_ids': [],
        'matched_urls': [],
        'words_checked': len(words),
        'numbers_checked': numbers,
        'sources_checked': len(prepared),
        'note': NOTE,
    }
    if not record['claim']:
        record['status'] = 'not_checkable'
        record['error'] = 'empty_claim'
        return record
    if len(words) < MIN_WORDS:
        record['status'] = 'not_checkable'
        record['error'] = 'too_short'
        return record
    if not prepared:
        return record

    best: Optional[Dict[str, Any]] = None
    best_key = (-1.0, -1)
    missing_numbers: List[str] = []
    for source in prepared:
        haystack = _normalise(source['text'])
        absent = [number for number in numbers if not _number_present(number, haystack)]
        if absent:
            missing_numbers = absent
            continue
        matched_window = _window_match(words, haystack)
        key = (round(matched_window['coverage'], 4),
               1 if source['content_level'] == 'full_page' else 0)
        if key > best_key:
            best_key = key
            best = {**source, **matched_window}

    if best is None:
        # الأرقام لم تُطابق في أي مصدر: نقول ذلك صراحة، ولا نسمّيه تكذيبًا.
        record['status'] = 'number_not_found' if numbers else 'no_match'
        if numbers:
            record['missing_numbers'] = missing_numbers
        return record
    record['coverage'] = round(float(best['coverage']), 3)
    record['page_coverage'] = round(float(best.get('page_coverage') or 0.0), 3)
    record['content_level'] = best['content_level']
    record['evidence_excerpt'] = best.get('excerpt') or ''
    record['matched_source_ids'] = [best['source_id']]
    record['matched_urls'] = [best['url']]
    if best['coverage'] >= MATCH_COVERAGE:
        base_status = ('matched_in_retrieved_page'
                       if best['content_level'] == 'full_page' else 'matched_in_search_snippet')
        record['matched_status'] = base_status
        if _has_negation(record['claim']) and not _has_negation(best.get('excerpt') or ''):
            # المطابقة اللفظية لا تفهم النفي: ننبّه بدل أن نسمّيها مطابقة تامة
            record['status'] = 'possible_negation_mismatch'
            record['reason'] = 'الادعاء يحمل نفيًا والمقطع المطابق لا يحمل نفيًا'
        else:
            record['status'] = base_status
    else:
        record['status'] = 'weak_match'
        # الكلمات موجودة في الصفحة لكن متفرقة: أشهر أسباب «المطابقة» الكاذبة
        record['reason'] = ('words_scattered'
                            if (best.get('page_coverage') or 0.0) >= MATCH_COVERAGE
                            else 'low_coverage')
    return record


def verify_snippets(sources: Optional[Iterable[Dict[str, Any]]],
                    pages: Optional[Iterable[Dict[str, Any]]]) -> Dict[str, Any]:
    """هل المقتطف الذي سنحقنه موجود فعلًا في الصفحة التي سحبناها؟

    لا يفحص صحة المقتطف، بل يفحص أمانة النقل بين الصفحة والمقتطف.
    """
    texts: Dict[str, str] = {}
    for page in pages or []:
        if page.get('status') == 'fetched' and (page.get('text') or '').strip():
            texts[str(page.get('url'))] = str(page.get('text'))
    records: List[Dict[str, Any]] = []
    counts = {'confirmed_in_page': 0, 'not_found_in_page': 0, 'page_not_retrieved': 0, 'not_checkable': 0}
    for source in sources or []:
        url = str(source.get('url') or '')
        snippet = str(source.get('snippet') or '')
        if url in texts:
            check = check_claim(snippet, [{'source_id': source.get('source_id'), 'url': url,
                                           'content_level': 'full_page', 'text': texts[url]}])
            status = check['status']
            if status == 'matched_in_retrieved_page':
                outcome = 'confirmed_in_page'
            elif status == 'not_checkable':
                outcome = 'not_checkable'
            else:
                outcome = 'not_found_in_page'
            counts[outcome] += 1
            records.append({
                'source_id': source.get('source_id'), 'url': url, 'outcome': outcome,
                'coverage': check['coverage'], 'status': status,
            })
        else:
            counts['page_not_retrieved'] += 1
            records.append({'source_id': source.get('source_id'), 'url': url,
                            'outcome': 'page_not_retrieved', 'coverage': 0.0,
                            'status': 'unverifiable_no_source'})
    return {
        'pages_fetched': len(texts),
        'counts': counts,
        'records': records,
        'note': ('«مطابق في الصفحة» = المقتطف موجود في النص الذي سحبناه. '
                 '«غير موجود» قد يعني اقتطاعًا أو إعادة صياغة أو حجبًا، وليس تكذيبًا.'),
    }


def extract_sentences(text: str, *, max_claims: int = 8, min_chars: int = 40) -> List[str]:
    """جُمل قابلة للفحص: نتجاهل العناوين والقوائم القصيرة والتنسيق."""
    sentences: List[str] = []
    for raw in _SENTENCE.findall(str(text or '')):
        sentence = ' '.join(raw.split())
        if len(sentence) < min_chars:
            continue
        if sentence.lstrip().startswith(('#', '-', '*', '>', '|', '```')):
            continue
        if sentence.count('http') and len(sentence) < min_chars * 2:
            continue
        sentences.append(sentence)
        if len(sentences) >= max_claims:
            break
    return sentences


def check_report(text: str, sources: Optional[Iterable[Dict[str, Any]]],
                 *, max_claims: int = 8) -> Dict[str, Any]:
    """فحص عيّنة من جُمل التقرير ضد ما سُحب من المصادر. لا يعدّل النص."""
    prepared = [_source_record(s) for s in (sources or [])]
    claims = [check_claim(sentence, prepared) for sentence in extract_sentences(text, max_claims=max_claims)]
    counts: Dict[str, int] = {}
    for claim in claims:
        counts[claim['status']] = counts.get(claim['status'], 0) + 1
    return {
        'claims': claims,
        'counts': counts,
        'claims_checked': len(claims),
        'sources_considered': len(prepared),
        'note': NOTE,
        'limitations': [
            'عيّنة محدودة من الجُمل، وليست كل التقرير.',
            'المطابقة لفظية: تشترط تقارب الكلمات في مقطع واحد، وترفض الأرقام الجزئية.',
            'لا تفهم النفي أو القلب أو الشرط؛ النفي يُنبَّه عليه ولا يُحكم فيه.',
            'غياب المطابقة ليس دليل خطأ، ووجودها ليس دليل صحة.',
        ],
    }
