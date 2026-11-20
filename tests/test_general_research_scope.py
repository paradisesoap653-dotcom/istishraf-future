import ast
from pathlib import Path
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).parents[1]

class ScopeTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'backend/app/services/web_research.py'
        tree = ast.parse(path.read_text())
        tree.body = [n for n in tree.body if not (isinstance(n, ast.ImportFrom) and n.level)]
        policy = {}
        exec(compile((ROOT / 'backend/app/services/research_integrity.py').read_text(), 'policy', 'exec'), policy)
        self.ns = {'__name__': 'scope_test', 'serp_lookup': Mock(), **{
            key: policy[key] for key in ('clean_project_title', 'build_evidence_ledger', 'plan_queries', 'EVIDENCE_POLICY')
        }}
        exec(compile(tree, str(path), 'exec'), self.ns)
        self.ns['gather_topic'] = Mock(return_value={'ok': True})
        self.ns['sudan_pulse'] = Mock(return_value={'ok': True})

    def test_no_sudan_injection_for_other_countries_and_domains(self):
        for text in ['إطلاق منتج في اليابان', 'Water policy in Morocco', 'Hospital staffing in Brazil', 'Cloud storage pricing in Germany', 'أثر قناة الجزيرة على النقاش في فرنسا']:
            with self.subTest(text=text):
                result = self.ns['gather_for_simulation'](text)
                self.assertIsNone(result['pulse'])
        self.ns['sudan_pulse'].assert_not_called()

    def test_explicit_sudan_context_retains_local_enrichment(self):
        for text in ['التعليم في السودان', 'Transport in Sudan', 'Sudanese agriculture']:
            self.assertIsNotNone(self.ns['gather_for_simulation'](text)['pulse'])

    def test_placeholder_title_not_searched(self):
        result = self.ns['gather_for_simulation']('', title='Unnamed Project')
        self.ns['gather_topic'].assert_not_called()
        self.assertEqual(result['title'], '')
        self.assertFalse(result['ok'])

    def test_source_links_survive_prompt_rendering(self):
        result = self.ns['prompt_block']({'topic': {'facts': [{'title':'Example', 'snippet':'A claim', 'url':'https://example.org/source', 'date':'2026-01-01'}]}})
        self.assertIn('https://example.org/source', result)
        self.assertIn('مقتطفات', result)

if __name__ == '__main__':
    unittest.main()
