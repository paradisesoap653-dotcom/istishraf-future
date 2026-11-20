import ast
from pathlib import Path
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).parents[1]
SERVICES = ROOT / 'backend/app/services'


def load_policy():
    namespace = {}
    exec(compile((SERVICES / 'research_integrity.py').read_text(), 'policy', 'exec'), namespace)
    return namespace


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()

    def test_defaults_are_small_and_explicit(self):
        budget = self.policy['resolve_search_budget']()
        self.assertEqual(budget['max_query_calls'], 2)
        self.assertEqual(budget['max_news_calls'], 1)
        self.assertLessEqual(budget['max_results_per_call'], 10)

    def test_overrides_are_clamped_not_trusted(self):
        resolve = self.policy['resolve_search_budget']
        self.assertEqual(resolve({'max_query_calls': 99})['max_query_calls'], 4)
        self.assertEqual(resolve({'max_query_calls': -3})['max_query_calls'], 1)
        self.assertEqual(resolve({'max_news_calls': -1})['max_news_calls'], 0)
        self.assertEqual(resolve({'max_query_calls': 'abc'})['max_query_calls'], 2)
        self.assertEqual(resolve({'unknown_key': 5}), self.policy['DEFAULT_SEARCH_BUDGET'])
        self.assertEqual(resolve({'per_call_timeout_seconds': float('nan')})['per_call_timeout_seconds'], 20.0)

    def test_plan_is_ordered_and_domain_independent(self):
        plan = self.policy['plan_search_queries']('Solar power in Chile')
        self.assertEqual([step['angle'] for step in plan], ['baseline', 'primary', 'alternatives'])
        self.assertEqual([step['priority'] for step in plan], [0, 1, 2])
        self.assertNotIn('السودان', str(plan))


class MultiAngleTests(unittest.TestCase):
    def setUp(self):
        path = SERVICES / 'web_research.py'
        tree = ast.parse(path.read_text())
        tree.body = [n for n in tree.body if not (isinstance(n, ast.ImportFrom) and n.level)]
        policy = load_policy()
        self.ns = {'__name__': 'multi_angle_test', 'serp_lookup': Mock(),
                   'page_retrieval': Mock(), 'claim_check': Mock(),
                   **{key: value for key, value in policy.items() if not key.startswith('_')}}
        self.ns['page_retrieval'].resolve_page_budget.return_value = {
            'max_pages': 0, 'max_bytes': 0, 'max_chars': 0, 'timeout_seconds': 0, 'max_redirects': 0}
        self.ns['page_retrieval'].retrieve_pages.return_value = {'pages': []}
        self.ns['claim_check'].verify_snippets.return_value = {}
        exec(compile(tree, str(path), 'exec'), self.ns)
        self.ns['_cache_write'] = Mock()

    def run_angles(self, searcher, **budget):
        return self.ns['search_multi_angle'](
            'Water policy in Morocco', budget=self.ns['resolve_search_budget'](budget), searcher=searcher)

    def test_budget_is_never_exceeded(self):
        searcher = Mock(return_value=[{'url': 'https://example.org/a', 'snippet': 'x'}])
        result = self.run_angles(searcher, max_query_calls=2)
        self.assertEqual(searcher.call_count, 2)
        self.assertEqual(result['budget']['used'], 2)
        self.assertTrue(result['budget']['exhausted'])

    def test_single_call_budget_leaves_rest_skipped_not_hidden(self):
        searcher = Mock(return_value=[{'url': 'https://example.org/a', 'snippet': 'x'}])
        result = self.run_angles(searcher, max_query_calls=1)
        self.assertEqual(searcher.call_count, 1)
        self.assertEqual(result['executed_angles'], ['baseline'])
        self.assertEqual(result['skipped_angles'], ['primary', 'alternatives'])
        statuses = {step['angle']: step['status'] for step in result['angles']}
        self.assertEqual(statuses, {'baseline': 'executed', 'primary': 'skipped_budget',
                                    'alternatives': 'skipped_budget'})
        self.assertEqual(result['status'], 'partial_budget')

    def test_error_is_not_success_and_does_not_stop_the_run(self):
        def searcher(query, **kwargs):
            if query == 'Water policy in Morocco':
                raise RuntimeError('provider down')
            return [{'url': 'https://example.org/b', 'snippet': 'y'}]

        result = self.run_angles(searcher, max_query_calls=2)
        statuses = {step['angle']: step['status'] for step in result['angles']}
        self.assertEqual(statuses['baseline'], 'error')
        self.assertEqual(statuses['primary'], 'executed')
        self.assertEqual(result['status'], 'partial_errors')
        self.assertEqual(result['executed_angles'], ['primary'])
        self.assertTrue(result['errors'])
        self.assertEqual(len(result['facts']), 1)

    def test_all_errors_means_failed(self):
        searcher = Mock(side_effect=RuntimeError('offline'))
        result = self.run_angles(searcher, max_query_calls=2)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['facts'], [])
        self.assertEqual(len(result['errors']), 2)

    def test_empty_results_are_reported_as_empty(self):
        # ميزانية تكفي الزوايا الثلاث، حتى لا يختلط «لا نتائج» بـ«لم تُنفَّذ»
        result = self.run_angles(Mock(return_value=[]), max_query_calls=3)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['facts'], [])
        statuses = {step['angle']: step['status'] for step in result['angles']}
        self.assertEqual(statuses['baseline'], 'empty')
        self.assertEqual(statuses['primary'], 'empty')
        self.assertEqual(result['skipped_angles'], [])

    def test_results_per_call_comes_from_budget(self):
        searcher = Mock(return_value=[])
        self.run_angles(searcher, max_query_calls=1, max_results_per_call=3)
        self.assertEqual(searcher.call_args.kwargs['max_results'], 3)
        self.assertIn('timeout', searcher.call_args.kwargs)

    def test_gather_topic_keeps_provider_calls_within_budget(self):
        self.ns['search_topic'] = Mock(return_value=[{'url': 'https://example.org/a', 'snippet': 'c'}])
        self.ns['search_news'] = Mock(return_value=[])
        result = self.ns['gather_topic']('Water policy in Morocco', use_cache=False)
        self.assertEqual(self.ns['search_topic'].call_count, 2)
        self.assertEqual(self.ns['search_news'].call_count, 1)
        self.assertEqual(result['executed_angles'], ['baseline', 'primary'])
        self.assertEqual(result['skipped_angles'], ['alternatives'])
        self.assertEqual(len(result['evidence_ledger']['sources']), 1)

    def test_zero_news_budget_makes_no_news_call(self):
        self.ns['search_topic'] = Mock(return_value=[{'url': 'https://example.org/a', 'snippet': 'c'}])
        self.ns['search_news'] = Mock(return_value=[])
        budget = self.ns['resolve_search_budget']({'max_news_calls': 0})
        self.ns['gather_topic']('Water policy in Morocco', use_cache=False, budget=budget)
        self.ns['search_news'].assert_not_called()

    def test_failed_search_is_not_cached(self):
        self.ns['search_topic'] = Mock(side_effect=RuntimeError('offline'))
        self.ns['search_news'] = Mock(side_effect=RuntimeError('offline'))
        result = self.ns['gather_topic']('topic', use_cache=False)
        self.assertFalse(result['ok'])
        self.ns['_cache_write'].assert_not_called()


if __name__ == '__main__':
    unittest.main()
