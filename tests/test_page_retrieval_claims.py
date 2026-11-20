import ast
import socket
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).parents[1]
SERVICES = ROOT / 'backend/app/services'


def load(name, extra=None):
    """تحميل وحدة معزولة: تُحذف الاستيرادات النسبية وتُحقن أسماؤها صراحة."""
    path = SERVICES / f'{name}.py'
    tree = ast.parse(path.read_text())
    tree.body = [node for node in tree.body
                 if not (isinstance(node, ast.ImportFrom) and node.level)]
    namespace = {'__name__': name, **(extra or {})}
    exec(compile(tree, str(path), 'exec'), namespace)
    return namespace


class FakeResponse:
    def __init__(self, status=200, content_type='text/html; charset=utf-8', body=b'',
                 url='https://example.org/a', location=None):
        self.status_code = status
        self.headers = {'content-type': content_type, 'location': location}
        self.url = url
        self._body = body

    def iter_bytes(self):
        if self._body:
            yield self._body


class FakeStream:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self.response

    def __exit__(self, *exc_info):
        return False


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def stream(self, method, url, **kwargs):
        self.calls.append(url)
        if self.error:
            raise self.error
        return FakeStream(self.response)


class RoutingClient:
    """عميل وهمي يعيد استجابة مختلفة لكل عنوان، ويسجّل كل عنوان طُلب فعلًا."""

    def __init__(self, routes, follow_redirects=None):
        self.routes = routes
        self.calls = []
        self.follow_flags = []

    def stream(self, method, url, **kwargs):
        self.calls.append(url)
        self.follow_flags.append(kwargs.get('follow_redirects'))
        key = str(url)
        if key not in self.routes:
            raise AssertionError(f'طلب غير متوقّع: {key}')
        return FakeStream(self.routes[key])


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.canonical = load('research_integrity')['canonical_source_url']
        self.pr = load('page_retrieval', {'canonical_source_url': self.canonical})

    def test_internal_and_credential_urls_never_reach_the_network(self):
        client = FakeClient(FakeResponse())
        for url in ['http://localhost/admin', 'http://127.0.0.1/', 'http://169.254.169.254/latest/meta-data',
                    'http://10.0.0.5/x', 'http://192.168.1.1/', 'https://user:pass@example.org/a',
                    'file:///etc/passwd', 'ftp://example.org/a', '']:
            with self.subTest(url=url):
                result = self.pr['fetch_page'](url, client=client, resolve_dns=False)
                self.assertEqual(result['status'], 'blocked')
                self.assertEqual(result['text'], '')
                self.assertEqual(result['content_level'], 'none')
        self.assertEqual(client.calls, [])

    def test_hostname_resolving_to_private_address_is_blocked(self):
        client = FakeClient(FakeResponse())
        with patch.object(socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('10.1.2.3', 0))]):
            result = self.pr['fetch_page']('https://internal.example.com/a', client=client)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['error'], 'resolves_to_internal_address')
        self.assertEqual(client.calls, [])

    def test_html_is_converted_and_scripts_are_dropped(self):
        body = ('<html><head><script>var secret="لا يُقرأ";</script><style>.a{}</style></head>'
                '<body><p>ارتفعت أسعار الشحن في الميناء.</p><div>بيانات 2026</div></body></html>').encode()
        result = self.pr['fetch_page']('https://example.org/a', client=FakeClient(FakeResponse(body=body)))
        self.assertEqual(result['status'], 'fetched')
        self.assertEqual(result['content_level'], 'full_page')
        self.assertIn('ارتفعت أسعار الشحن', result['text'])
        self.assertIn('بيانات 2026', result['text'])
        self.assertNotIn('secret', result['text'])
        self.assertNotIn('<p>', result['text'])

    def test_body_is_truncated_at_the_byte_limit(self):
        body = ('<p>' + ('كلمة ' * 40000) + '</p>').encode()
        budget = {'max_bytes': 50_000, 'max_chars': 1_000}
        result = self.pr['fetch_page']('https://example.org/a', budget=budget, client=FakeClient(FakeResponse(body=body)))
        self.assertEqual(result['status'], 'fetched')
        self.assertTrue(result['truncated'])
        self.assertLessEqual(result['chars'], 1_000)

    def test_budget_floors_protect_against_absurd_limits(self):
        resolve = self.pr['resolve_page_budget']
        self.assertEqual(resolve({'max_bytes': 1000})['max_bytes'], 50_000)
        self.assertEqual(resolve({'max_pages': 999})['max_pages'], 4)
        self.assertEqual(resolve({'timeout_seconds': 0})['timeout_seconds'], 4.0)
        self.assertEqual(resolve({'max_chars': 10})['max_chars'], 1_000)

    def test_pdf_is_not_faked_as_text(self):
        result = self.pr['fetch_page']('https://example.org/a.pdf', client=FakeClient(
            FakeResponse(content_type='application/pdf', body=b'%PDF-1.7 ...')))
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['text'], '')
        self.assertTrue(result['error'].startswith('unsupported_content_type'))

    def test_http_error_is_an_error_not_a_fetch(self):
        result = self.pr['fetch_page']('https://example.org/a', client=FakeClient(FakeResponse(status=404)))
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error'], 'http_404')
        self.assertEqual(result['content_level'], 'none')

    def test_network_failure_is_recorded_not_hidden(self):
        result = self.pr['fetch_page']('https://example.org/a', client=FakeClient(error=TimeoutError('timed out')))
        self.assertEqual(result['status'], 'error')
        self.assertIn('TimeoutError', result['error'])
        self.assertEqual(result['text'], '')

    def test_empty_page_is_skipped(self):
        result = self.pr['fetch_page']('https://example.org/a', client=FakeClient(FakeResponse(body=b'<body>   </body>')))
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['error'], 'empty_text')

    def test_retrieval_respects_page_budget_and_deduplicates(self):
        calls = []

        def fetcher(url):
            calls.append(url)
            return {'url': url, 'status': 'fetched', 'text': 'نص', 'chars': 3, 'truncated': False}

        urls = ['https://example.org/a?utm_source=x', 'https://example.org/a', 'https://example.org/b',
                'https://example.org/c', 'https://example.org/d']
        result = self.pr['retrieve_pages'](urls, budget={'max_pages': 2}, fetcher=fetcher)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(result['fetched'], 2)
        self.assertEqual(sorted(result['skipped_for_budget']), ['https://example.org/c', 'https://example.org/d'])
        self.assertTrue(result['budget']['exhausted'])

    def test_zero_page_budget_makes_no_request(self):
        calls = []
        result = self.pr['retrieve_pages'](['https://example.org/a'], budget={'max_pages': 0},
                                           fetcher=lambda url: calls.append(url) or {'status': 'fetched'})
        self.assertEqual(calls, [])
        self.assertEqual(result['fetched'], 0)

    def test_fetcher_crash_is_recorded_per_url(self):
        def fetcher(url):
            raise RuntimeError('boom')

        result = self.pr['retrieve_pages'](['https://example.org/a'], fetcher=fetcher)
        self.assertEqual(result['pages'][0]['status'], 'error')
        self.assertIn('boom', result['pages'][0]['error'])


class RedirectSafetyTests(unittest.TestCase):
    def setUp(self):
        self.canonical = load('research_integrity')['canonical_source_url']
        self.pr = load('page_retrieval', {'canonical_source_url': self.canonical})

    def test_redirect_to_internal_address_is_blocked_and_never_requested(self):
        client = RoutingClient({
            'https://example.org/start': FakeResponse(
                status=302, location='http://169.254.169.254/latest/meta-data/'),
            'http://169.254.169.254/latest/meta-data/': FakeResponse(
                body=b'secret', content_type='text/plain'),
        })
        record = self.pr['fetch_page']('https://example.org/start', budget={'max_pages': 1},
                                       client=client, resolve_dns=False)
        self.assertEqual(record['status'], 'blocked')
        self.assertTrue(record['error'].startswith('redirect_blocked'))
        self.assertEqual(record['text'], '')
        self.assertEqual(client.calls, ['https://example.org/start'])
        self.assertEqual(record['redirects'], 1)

    def test_redirect_to_public_url_is_followed_and_counted(self):
        client = RoutingClient({
            'https://example.org/start': FakeResponse(
                status=301, location='https://news.example/final'),
            'https://news.example/final': FakeResponse(
                body='نص الصفحة العامة'.encode('utf-8'), content_type='text/plain; charset=utf-8'),
        })
        record = self.pr['fetch_page']('https://example.org/start', budget={'max_pages': 1},
                                       client=client, resolve_dns=False)
        self.assertEqual(record['status'], 'fetched')
        self.assertEqual(record['redirects'], 1)
        self.assertEqual(client.calls, ['https://example.org/start', 'https://news.example/final'])
        # كل طلب يجب أن يمنع httpx من تتبّع التحويل نيابةً عنّا
        self.assertEqual(client.follow_flags, [False, False])

    def test_redirect_loop_stops_as_an_error_not_a_fetch(self):
        client = RoutingClient({
            'https://example.org/loop': FakeResponse(
                status=302, location='https://example.org/loop'),
        })
        record = self.pr['fetch_page']('https://example.org/loop',
                                       budget={'max_pages': 1, 'max_redirects': 2},
                                       client=client, resolve_dns=False)
        self.assertEqual(record['status'], 'error')
        self.assertEqual(record['error'], 'too_many_redirects')
        self.assertEqual(record['text'], '')

    def test_redirect_without_location_is_an_error(self):
        client = RoutingClient({'https://example.org/x': FakeResponse(status=302)})
        record = self.pr['fetch_page']('https://example.org/x', budget={'max_pages': 1},
                                       client=client, resolve_dns=False)
        self.assertEqual(record['status'], 'error')
        self.assertIn('without_location', record['error'])

    def test_public_pages_drops_text_and_keeps_the_rest(self):
        pages = [{'url': 'https://example.org/a', 'status': 'fetched', 'chars': 120,
                  'truncated': False, 'text': 'نص كامل لا يجب أن يُنشر'}]
        published = self.pr['public_pages'](pages)
        self.assertNotIn('text', published[0])
        self.assertEqual(published[0]['url'], 'https://example.org/a')
        self.assertEqual(published[0]['chars'], 120)
        self.assertEqual(self.pr['public_pages'](None), [])
        # الدالة لا تُعدّل الأصل
        self.assertIn('text', pages[0])


class ClaimTests(unittest.TestCase):
    def setUp(self):
        self.cc = load('claim_check')

    def test_claim_matching_a_retrieved_page_is_lexical_only(self):
        record = self.cc['check_claim'](
            'ارتفعت أسعار الشحن في ميناء بورتسودان بنسبة 20% خلال 2026',
            [{'source_id': 'src_1', 'url': 'https://example.org/a', 'content_level': 'full_page',
              'text': 'قال التقرير إن أسعار الشحن في ميناء بورتسودان ارتفعت بنسبة 20% خلال 2026.'}])
        self.assertEqual(record['status'], 'matched_in_retrieved_page')
        self.assertEqual(record['matched_source_ids'], ['src_1'])
        self.assertNotIn('true', record['status'])
        self.assertIn('لا تثبت صحة الادعاء', record['note'])

    def test_number_absent_from_source_is_flagged(self):
        record = self.cc['check_claim'](
            'ارتفعت أسعار الشحن في ميناء بورتسودان بنسبة 45% خلال 2026',
            [{'source_id': 'src_1', 'url': 'https://example.org/a', 'content_level': 'full_page',
              'text': 'ارتفعت أسعار الشحن في ميناء بورتسودان بنسبة 20% خلال 2026.'}])
        self.assertEqual(record['status'], 'number_not_found')
        self.assertIn('45', record['missing_numbers'])

    def test_snippet_level_match_is_weaker_than_page_match(self):
        record = self.cc['check_claim'](
            'ارتفعت أسعار الشحن في ميناء بورتسودان خلال 2026',
            [{'source_id': 'src_2', 'url': 'https://example.org/b', 'content_level': 'search_snippet',
              'snippet': 'ارتفعت أسعار الشحن في ميناء بورتسودان خلال 2026 بعد إغلاق الطريق.'}])
        self.assertEqual(record['status'], 'matched_in_search_snippet')

    def test_no_source_means_unverifiable_not_false(self):
        record = self.cc['check_claim']('ادعاء طويل بما يكفي للفحص ولا يوجد له مصدر', [])
        self.assertEqual(record['status'], 'unverifiable_no_source')
        self.assertEqual(record['matched_source_ids'], [])

    def test_short_claim_is_not_checkable(self):
        record = self.cc['check_claim']('سعر مرتفع', [{'content_level': 'full_page', 'text': 'سعر مرتفع'}])
        self.assertEqual(record['status'], 'not_checkable')

    def test_arabic_normalisation_matches_with_and_without_diacritics(self):
        record = self.cc['check_claim'](
            'أعلنت الحكومة عن برنامج دعم جديد للفلاحين',
            [{'source_id': 'src_3', 'url': 'https://example.org/c', 'content_level': 'full_page',
              'text': 'اعلنت الحكومه عن برنامج دعم جديد للفلاحين في الولايات'}])
        self.assertIn(record['status'], {'matched_in_retrieved_page', 'weak_match'})

    def test_verify_snippets_distinguishes_not_retrieved_pages(self):
        sources = [
            {'source_id': 'src_1', 'url': 'https://example.org/a', 'snippet': 'ارتفعت أسعار الشحن في الميناء خلال 2026'},
            {'source_id': 'src_2', 'url': 'https://example.org/b', 'snippet': 'خبر آخر غير مقروء صفحته'},
        ]
        pages = [{'url': 'https://example.org/a', 'status': 'fetched',
                  'text': 'ارتفعت أسعار الشحن في الميناء خلال 2026 بنسبة كبيرة.'}]
        result = self.cc['verify_snippets'](sources, pages)
        outcomes = {record['source_id']: record['outcome'] for record in result['records']}
        self.assertEqual(outcomes['src_1'], 'confirmed_in_page')
        self.assertEqual(outcomes['src_2'], 'page_not_retrieved')
        self.assertEqual(result['pages_fetched'], 1)

    def test_report_check_limits_sample_and_keeps_text_untouched(self):
        text = ('# عنوان\n\n' + 'ارتفعت أسعار الشحن في ميناء بورتسودان بنسبة 20% خلال 2026. ' * 3 +
                '\n- نقطة قصيرة\n' + 'وهذا ادعاء آخر طويل بما يكفي ليدخل العيّنة ويُفحص مقابل المصادر.')
        sources = [{'source_id': 'src_1', 'url': 'https://example.org/a', 'content_level': 'full_page',
                    'text': 'ارتفعت أسعار الشحن في ميناء بورتسودان بنسبة 20% خلال 2026.'}]
        result = self.cc['check_report'](text, sources, max_claims=2)
        self.assertEqual(result['claims_checked'], 2)
        self.assertNotIn('# عنوان', str([claim['claim'] for claim in result['claims']]))
        self.assertIn('note', result)

    def test_no_status_implies_truth(self):
        for status in ['matched_in_retrieved_page', 'matched_in_search_snippet', 'no_match',
                       'number_not_found', 'weak_match', 'not_checkable', 'unverifiable_no_source']:
            self.assertNotIn('true', status)
            self.assertNotIn('verified', status)


class ClaimHardeningTests(unittest.TestCase):
    def setUp(self):
        self.cc = load('claim_check')

    def _page(self, text, source_id='src_1'):
        return {'source_id': source_id, 'url': 'https://example.org/a',
                'content_level': 'full_page', 'text': text}

    def test_number_is_matched_as_a_whole_not_inside_a_bigger_number(self):
        record = self.cc['check_claim'](
            'ارتفعت أسعار الخبز في الخرطوم بنسبة 30 بالمئة خلال مارس',
            [self._page('ارتفعت أسعار الخبز في الخرطوم بنسبة 1300 بالمئة خلال مارس')])
        self.assertEqual(record['status'], 'number_not_found')
        self.assertIn('30', record['missing_numbers'])

    def test_negated_claim_is_flagged_not_called_a_match(self):
        record = self.cc['check_claim'](
            'لم ترتفع أسعار الخبز في الخرطوم خلال مارس حسب تجار السوق',
            [self._page('ارتفعت أسعار الخبز في الخرطوم بنسبة كبيرة خلال مارس حسب تجار السوق')])
        self.assertEqual(record['status'], 'possible_negation_mismatch')
        self.assertEqual(record['matched_status'], 'matched_in_retrieved_page')
        self.assertIn('نفي', record['reason'])

    def test_negated_claim_with_negated_source_is_not_flagged(self):
        record = self.cc['check_claim'](
            'لم ترتفع أسعار الخبز في الخرطوم خلال مارس حسب تجار السوق',
            [self._page('قال تجار السوق إن أسعار الخبز لم ترتفع في الخرطوم خلال مارس')])
        self.assertEqual(record['status'], 'matched_in_retrieved_page')

    def test_words_scattered_across_a_long_page_are_not_a_match(self):
        filler = ('واصلت الورشة أعمالها في الجلسة الصباحية بحضور عدد من المشاركين '
                  'وناقش الحاضرون جدول الأعمال ثم انتقلوا إلى استراحة قصيرة. ') * 3
        text = ('تناول التقرير أوضاع الريف. ' + filler
                + 'وقال المسؤول إن أسعار المعدات ارتفعت عالميًا. ' + filler
                + 'وتشير تقارير السوق إلى أن الطلب على القمح زاد. ' + filler
                + 'وأضاف أن الخرطوم تحتاج إلى مزيد من الصوامع. ' + filler
                + 'وفي سياق آخر ناقش الاجتماع تمويل البنك الزراعي.')
        record = self.cc['check_claim'](
            'ارتفعت أسعار القمح في الخرطوم بعد زيادة الطلب بحسب البنك الزراعي',
            [self._page(text)])
        self.assertEqual(record['status'], 'weak_match')
        self.assertEqual(record['reason'], 'words_scattered')
        # الكلمات موجودة فعلًا في الصفحة كلها — وهذا سبب الخطأ القديم
        self.assertGreaterEqual(record['page_coverage'], 0.7)
        self.assertLess(record['coverage'], 0.7)

    def test_negation_difference_is_not_reported_as_absent_from_page(self):
        # الكلمات موجودة في الصفحة، لكن الصفحة تقول «ما ارتفعت» لا «لم ترتفع»
        pages = [{'url': 'https://example.org/p', 'status': 'fetched',
                  'text': 'وقال مسؤول محلي إن أسعار الخبز ما ارتفعت في الخرطوم خلال مارس حسب بياناته.'}]
        sources = [{'source_id': 's1', 'url': 'https://example.org/p',
                    'snippet': 'أسعار الخبز لم ترتفع في الخرطوم خلال مارس'}]
        result = self.cc['verify_snippets'](sources, pages)
        self.assertEqual(result['records'][0]['outcome'], 'negation_differs')
        self.assertEqual(result['counts']['negation_differs'], 1)
        self.assertEqual(result['counts']['not_found_in_page'], 0)

    def test_match_carries_the_excerpt_it_was_based_on(self):
        record = self.cc['check_claim'](
            'ارتفعت أسعار الشحن في ميناء بورتسودان خلال 2026',
            [self._page('قال التقرير إن أسعار الشحن في ميناء بورتسودان ارتفعت خلال 2026.')])
        self.assertEqual(record['status'], 'matched_in_retrieved_page')
        self.assertIn('بورتسودان', record['evidence_excerpt'])


class WiringTests(unittest.TestCase):
    def test_research_bundle_carries_pages_and_verification(self):
        source = (SERVICES / 'web_research.py').read_text()
        tree = ast.parse(source)
        names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        self.assertIn('_retrieve_source_pages', names)
        self.assertIn('_apply_pages', names)
        self.assertIn('claim_check.verify_snippets', source)
        self.assertIn("'content_level'] = 'full_page'", source)
        self.assertIn('CACHE_VERSION', source)
        self.assertNotIn("topic::evidence-v1", source)

    def test_api_exposes_what_was_executed_and_fetched(self):
        api = (ROOT / 'backend/app/api/simulation.py').read_text()
        self.assertIn("@simulation_bp.route('/research/verify'", api)
        self.assertIn('claim_check.check_report', api)
        for key in ('"search_report"', '"skipped_angles"', '"pages"', '"verification"'):
            self.assertIn(key, api)

    def test_prompt_warns_about_negation_difference(self):
        source = (ROOT / 'backend/app/services/web_research.py').read_text()
        self.assertIn('negation_differs', source)
        self.assertIn('نفيها مختلف', source)

    def test_every_pages_response_goes_through_public_pages(self):
        """كل مسار يعيد «pages» يجب أن يمرّ بالدالة التي تحذف النص.

        الفحص بالنص القديم كان ينجح لأن السلسلة موجودة في مسار آخر فقط.
        هنا نفحص كل دالة في الملف، فلا يمرّ مسار ينسى الحذف.
        """
        source = (ROOT / 'backend/app/api/simulation.py').read_text()
        tree = ast.parse(source)
        offenders = []
        for func in [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]:
            segment = ast.get_source_segment(source, func) or ''
            if '"pages"' not in segment:
                continue
            if 'public_pages' not in segment:
                offenders.append(func.name)
        self.assertEqual(offenders, [], f'مسارات تعيد نص الصفحات: {offenders}')


if __name__ == '__main__':
    unittest.main()
