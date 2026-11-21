"""اختبارات مراجع الأرقام (الطبقة ١ من خطة دقة المعلومات).

لا تحتاج Flask ولا شبكة: facts.py مستقل بذاته.
"""

import importlib.util
import os
import sys
import unittest

_SERVICES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "services")


def _load_module(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(_SERVICES, "facts.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[name] = module
    return module


facts = _load_module("_facts_under_test")

BUNDLE = {
    "topic": {
        "facts": [
            {"title": "Uber early bet", "snippet": "A-Grade invested $500,000 in Uber in 2011.",
             "url": "https://example.com/uber", "source": "Forbes", "date": "2016-03-01"},
            {"title": "بلا رابط", "snippet": "رقم بلا مصدر", "url": "", "source": "", "date": ""},
            {"title": "GiveDirectly", "snippet": "Sound Ventures put $35 million into Anthropic.",
             "url": "https://example.com/anthropic", "source": "Bloomberg", "date": "2026-11-15"},
        ],
        "news": [
            {"title": "خبر", "snippet": "Anthropic started trading on Nasdaq.",
             "url": "https://example.com/ipo", "source": "Reuters", "date": "2026-11-20"},
        ],
    }
}


class BuildTests(unittest.TestCase):
    def test_keys_are_stable_and_skip_url_less_items(self):
        built = facts.build_from_bundle(BUNDLE)
        self.assertEqual(list(built), ["f01", "f02", "f03"])
        self.assertEqual(built["f01"]["publisher"], "Forbes")
        # العنصر بلا رابط لا يصبح مفتاحًا، وإلا لدفع النموذج للكتابة من ذاكرته
        self.assertNotIn("رقم بلا مصدر", [f["value"] for f in built.values()])

    def test_empty_bundle_yields_nothing(self):
        self.assertEqual(facts.build_from_bundle(None), {})
        self.assertEqual(facts.build_from_bundle({}), {})

    def test_limit_respected(self):
        built = facts.build_from_bundle(BUNDLE, limit=1)
        self.assertEqual(len(built), 1)


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.built = facts.build_from_bundle(BUNDLE)

    def test_reference_is_replaced_with_quote(self):
        text, used, missing = facts.render("استثمرت {{fact:f01}} في أوبر.", self.built)
        self.assertIn("A-Grade invested $500,000 in Uber in 2011.", text)
        self.assertNotIn("{{fact:", text)
        self.assertEqual(used, ["f01"])
        self.assertEqual(missing, [])

    def test_spaces_inside_reference_are_tolerated(self):
        text, used, _ = facts.render("{{ fact : f02 }}", self.built)
        self.assertIn("$35 million", text)
        self.assertEqual(used, ["f02"])

    def test_unknown_reference_is_kept_visible(self):
        text, used, missing = facts.render("رقم {{fact:nope}}", self.built)
        self.assertEqual(text, "رقم {{fact:nope}}")
        self.assertEqual(missing, ["nope"])
        self.assertEqual(used, [])

    def test_repeated_reference_listed_once(self):
        text, used, _ = facts.render("{{fact:f01}} و{{fact:f01}}", self.built)
        self.assertEqual(used, ["f01"])
        self.assertEqual(text.count("$500,000"), 2)

    def test_unresolved_keys_detects_leftovers(self):
        self.assertEqual(facts.unresolved_keys("{{fact:a}} {{fact:b}}"), ["a", "b"])
        self.assertEqual(facts.unresolved_keys("لا شيء"), [])


class SourcesBlockTests(unittest.TestCase):
    def test_sources_listed_only_for_used_keys(self):
        built = facts.build_from_bundle(BUNDLE)
        block = facts.sources_block(built, ["f01"])
        self.assertIn("https://example.com/uber", block)
        self.assertNotIn("example.com/anthropic", block)

    def test_no_used_keys_means_no_block(self):
        self.assertEqual(facts.sources_block(facts.build_from_bundle(BUNDLE), []), "")


class PromptBlockTests(unittest.TestCase):
    def test_prompt_lists_keys_and_forbids_writing_numbers(self):
        built = facts.build_from_bundle(BUNDLE)
        block = facts.prompt_block(built)
        self.assertIn("{{f01}}", block)
        self.assertIn("لا تكتب أي رقم واقعي بنفسك", block)
        self.assertEqual(facts.prompt_block({}), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
