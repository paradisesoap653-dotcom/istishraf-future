import ast
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).parents[1]
SERVICES = ROOT / 'backend/app/services'
spec = importlib.util.spec_from_file_location('integrity', SERVICES / 'research_integrity.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

class EvidenceTests(unittest.TestCase):
    def test_deduplicates_tracking_links_but_does_not_claim_independence(self):
        result = policy.build_evidence_ledger([
            {'url':'https://example.org/a?utm_source=x', 'snippet':'Claim'},
            {'url':'https://example.org/a#part', 'snippet':'Claim repeated'},
            {'url':'https://another.example/a', 'snippet':'Same copied claim'},
        ], retrieved_at='2026-11-18T00:00:00Z')
        self.assertEqual(len(result['sources']), 2)
        self.assertEqual(result['sources'][0]['occurrences'], 2)
        for source in result['sources']:
            self.assertEqual(source['independence'], 'unknown')
            self.assertEqual(source['verification_status'], 'unverified')
            self.assertEqual(source['content_level'], 'search_snippet')
            self.assertIsNone(source['publication_date_raw'])

    def test_rejects_non_web_and_credential_urls(self):
        for url in ['javascript:alert(1)', 'file:///secret', '', 'https://user:password@example.org/a']:
            self.assertEqual(policy.canonical_source_url(url), '')

    def test_keeps_distinct_article_query_parameters(self):
        a = policy.canonical_source_url('https://example.org/article?id=1')
        b = policy.canonical_source_url('https://example.org/article?id=2')
        self.assertNotEqual(a, b)

    def test_no_invented_dates(self):
        source = policy.build_evidence_ledger([{'url':'https://example.org', 'date':'8 months ago'}], retrieved_at='now')['sources'][0]
        self.assertEqual(source['publication_date_raw'], '8 months ago')
        self.assertEqual(source['retrieved_at'], 'now')

    def test_placeholder_detection_is_not_substring_replacement(self):
        self.assertEqual(policy.clean_project_title(' Unnamed Project '), '')
        self.assertEqual(policy.clean_project_title('Unnamed Project analysis'), 'Unnamed Project analysis')

    def test_query_plan_is_domain_independent(self):
        for topic in ['Water policy in Morocco', 'Product launch Japan', 'أثر التقنية في التعليم', 'Healthcare Brazil']:
            plan = policy.plan_queries(topic)
            self.assertEqual(len(plan), 3)
            self.assertEqual(plan[0]['query'], topic)
            self.assertNotIn('السودان', str(plan))
        self.assertEqual(policy.plan_queries(''), [])

class IntegrationContractTests(unittest.TestCase):
    def load_research(self):
        path = SERVICES / 'web_research.py'
        tree = ast.parse(path.read_text())
        tree.body = [n for n in tree.body if not (isinstance(n, ast.ImportFrom) and n.level)]
        ns = {'__name__':'isolated_research', 'serp_lookup':Mock(),
              'page_retrieval':Mock(), 'claim_check':Mock()}
        ns.update({key:getattr(policy, key) for key in dir(policy) if not key.startswith('_')})
        ns['page_retrieval'].resolve_page_budget.return_value = {'max_pages':0,'max_bytes':0,'max_chars':0,'timeout_seconds':0,'max_redirects':0}
        ns['page_retrieval'].retrieve_pages.return_value = {'pages': []}
        ns['claim_check'].verify_snippets.return_value = {}
        exec(compile(tree, str(path), 'exec'), ns)
        return ns

    def test_research_records_only_executed_queries_and_has_ledger(self):
        ns = self.load_research()
        ns['search_topic'] = Mock(return_value=[{'url':'https://example.org/a','snippet':'claim'}])
        ns['search_news'] = Mock(return_value=[])
        ns['_cache_write'] = Mock()
        result = ns['gather_topic']('Water in Morocco', use_cache=False)
        angles = [step['angle'] for step in result['search_report']['angles']]
        # لا تُسجَّل زاوية لم تُنفَّذ: المسجَّل هو ما نُفِّذ فعلًا فقط
        self.assertEqual(result['queries'], ['Water in Morocco',
                                             'Water in Morocco primary data study methodology'])
        self.assertEqual(result['executed_angles'], ['baseline', 'primary'])
        self.assertEqual(angles, ['baseline', 'primary', 'alternatives'])
        self.assertEqual(result['skipped_angles'], ['alternatives'])
        self.assertEqual(result['search_report']['budget']['used'], 2)
        self.assertEqual(ns['search_topic'].call_count, 2)
        self.assertEqual(len(result['query_plan']), 3)
        self.assertEqual(len(result['evidence_ledger']['sources']), 1)

    def test_search_errors_are_not_success(self):
        ns = self.load_research()
        ns['search_topic'] = Mock(side_effect=RuntimeError('offline'))
        result = ns['gather_topic']('topic', with_news=False, use_cache=False)
        self.assertFalse(result['ok'])
        self.assertTrue(result['errors'])
        self.assertEqual(result['evidence_ledger']['sources'], [])

    def test_no_forced_country_in_provider_request(self):
        ns = self.load_research()
        ns['serp_lookup']._get.return_value = {'organic_results':[]}
        ns['search_topic']('Robotics in Japan')
        params = ns['serp_lookup']._get.call_args.args[0]
        self.assertNotIn('gl', params)
        self.assertEqual(params['hl'], 'en')

    def test_policy_present_in_report_generation_paths(self):
        source = (SERVICES / 'report_agent.py').read_text()
        self.assertIn('{PLAN_SYSTEM_PROMPT}\\n\\n{get_language_instruction()}\\n{EVIDENCE_POLICY}', source)
        self.assertGreaterEqual(source.count('{EVIDENCE_POLICY}'), 3)
        self.assertIn('system_prompt += "\\n" + EVIDENCE_POLICY', source)
        self.assertNotIn('غطِّ — بقدر ما يسمح الموضوع — طبقات مختلفة', source)

    def test_persona_default_not_national(self):
        tree = ast.parse((SERVICES / 'oasis_profile_generator.py').read_text())
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_culture_hint')
        self.assertNotIn('sudanese_culture', ast.unparse(fn))
        self.assertIn('research_integrity import EVIDENCE_POLICY', (SERVICES / 'simulation_config_generator.py').read_text())

class GenerationPathTests(unittest.TestCase):
    def test_simulation_and_scenario_use_shared_policy(self):
        for name in ('serverless_sim.py', 'scenario_runner.py'):
            source = (SERVICES / name).read_text()
            self.assertNotIn('sudanese_culture', source)
            tree = ast.parse(source)
            messages = [n for n in ast.walk(tree) if isinstance(n, ast.Dict) and any(
                isinstance(k, ast.Constant) and k.value == 'role' and isinstance(v, ast.Constant) and v.value == 'system'
                for k, v in zip(n.keys, n.values))]
            self.assertTrue(messages)
            for message in messages:
                self.assertIn('EVIDENCE_POLICY', ast.unparse(message))

    def test_placeholder_trends_rejected_before_network(self):
        from typing import Any, Dict
        tree = ast.parse((SERVICES / 'serp_lookup.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'trend_summary')
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        ns = {'Dict':Dict, 'Any':Any, '_TIMEOUT':1, 'clean_project_title':policy.clean_project_title, '_get':Mock()}
        exec(compile(module, 'trend', 'exec'), ns)
        with self.assertRaises(ValueError):
            ns['trend_summary']('Unnamed Project')
        ns['_get'].assert_not_called()

if __name__ == '__main__':
    unittest.main()
