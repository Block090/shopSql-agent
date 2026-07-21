import unittest

from app.core.value_normalizer import expand_value_terms, normalize_business_value


class ValueNormalizerTest(unittest.TestCase):
    def test_normalizes_quarter_region_and_gender_aliases(self):
        self.assertEqual(normalize_business_value("第一季度"), "q1")
        self.assertEqual(normalize_business_value("华东地区"), "华东")
        self.assertEqual(normalize_business_value("女性"), "女")

    def test_expands_value_terms_with_aliases(self):
        terms = expand_value_terms(["第一季度", "华东地区"])

        self.assertIn("Q1", terms)
        self.assertIn("第一季度", terms)
        self.assertIn("华东", terms)
        self.assertIn("华东地区", terms)


if __name__ == "__main__":
    unittest.main()
