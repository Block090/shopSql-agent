import unittest

from app.core.operation_plan import build_operation_plan


class OperationPlanTest(unittest.TestCase):
    def test_builds_delete_plan_with_readonly_impact_sql(self):
        plan = build_operation_plan("删除 2025 年 3 月的测试订单", "DELETE")

        self.assertEqual(plan["operation_type"], "DELETE")
        self.assertEqual(plan["target_table"], "fact_order")
        self.assertIn("DELETE FROM fact_order", plan["planned_sql"])
        self.assertTrue(plan["impact_count_sql"].lower().startswith("select count"))
        self.assertTrue(plan["impact_preview_sql"].lower().startswith("select"))
        self.assertIn("LIMIT 20", plan["impact_preview_sql"])
        self.assertTrue(plan["requires_approval"])
        self.assertEqual(plan["risk_level"], "high")

    def test_builds_update_plan_for_product_category_change(self):
        plan = build_operation_plan("把 iPhone 15 Pro 的品类改成手机数码", "UPDATE")

        self.assertEqual(plan["operation_type"], "UPDATE")
        self.assertEqual(plan["target_table"], "dim_product")
        self.assertEqual(plan["target_columns"], ["category"])
        self.assertIn("UPDATE dim_product", plan["planned_sql"])
        self.assertIn("product_name = 'iPhone 15 Pro'", plan["planned_sql"])

    def test_rejects_unknown_operation_plan(self):
        plan = build_operation_plan("随便改一下数据", "UPDATE")

        self.assertEqual(plan["risk_level"], "critical")
        self.assertFalse(plan["impact_count_sql"])


if __name__ == "__main__":
    unittest.main()
