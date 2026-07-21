import unittest

from app.core.clarification_guard import check_clarification_need


class ClarificationGuardTest(unittest.TestCase):
    def test_requires_clarification_for_best_selling_product(self):
        result = check_clarification_need("哪些商品卖得最好")

        self.assertTrue(result["required"])
        self.assertEqual(result["type"], "best_selling_product")
        self.assertEqual(result["options"], ["按销量", "按销售额"])
        self.assertEqual(result["missing_slots"], ["metric"])

    def test_does_not_require_clarification_when_metric_is_explicit(self):
        self.assertFalse(check_clarification_need("哪些商品按销量卖得最好")["required"])
        self.assertFalse(check_clarification_need("哪些商品按销售额卖得最好")["required"])

    def test_requires_clarification_for_recent_time_range(self):
        result = check_clarification_need("最近哪些商品销量最高")

        self.assertTrue(result["required"])
        self.assertEqual(result["type"], "recent_time_range")
        self.assertEqual(result["options"], ["最近7天", "最近30天", "本月"])

    def test_does_not_require_clarification_when_recent_range_is_explicit(self):
        result = check_clarification_need("最近30天哪些商品销量最高")

        self.assertFalse(result["required"])


if __name__ == "__main__":
    unittest.main()
