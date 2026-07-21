import unittest

from app.core.operation_plan import enrich_operation_governance


class OperationPlanGovernanceTest(unittest.TestCase):
    def test_enriches_delete_plan_with_business_approval_and_impact_fields(self):
        plan = {
            "operation_type": "DELETE",
            "target_table": "fact_order",
            "target_columns": [],
            "condition_description": "2025 年 3 月订单数据",
            "risk_level": "high",
            "requires_approval": True,
            "warning": "第一版仅生成删除方案和影响范围预览，不会执行 DELETE。",
        }

        enriched = enrich_operation_governance(
            plan,
            query="删除 2025 年 3 月的测试订单",
            impact_count=128,
            preview_rows=[{"order_id": "ORD20250301001", "date_id": 20250301}],
        )

        self.assertEqual(enriched["target_object"], "订单数据")
        self.assertIn("清理测试订单数据", enriched["business_purpose"])
        self.assertIn("导出命中订单 ID", enriched["rollback_suggestion"])
        self.assertEqual(enriched["execution_policy"], "plan_only")
        self.assertIn("预计影响 128 行", enriched["impact_summary"])
        self.assertIn("时间", enriched["impact_dimensions"])
        self.assertEqual(enriched["threshold_level"], "high")
        self.assertRegex(enriched["approval_id"], r"^CHG-\d{8}-[A-Z0-9]{4}$")
        self.assertEqual(enriched["approval_status"], "pending")
        self.assertEqual(enriched["execution_status"], "not_executed")
        self.assertFalse(enriched["execution_enabled"])
        self.assertEqual(enriched["approver"], "数据负责人")
        self.assertIn("不会直接执行写操作", enriched["status_description"])

    def test_marks_zero_impact_as_none_threshold(self):
        enriched = enrich_operation_governance(
            {
                "operation_type": "UPDATE",
                "target_table": "dim_product",
                "target_columns": ["category"],
                "condition_description": "商品名称为 iPhone 15 Pro",
                "risk_level": "medium",
                "requires_approval": True,
            },
            query="把 iPhone 15 Pro 的品类改成手机数码",
            impact_count=0,
            preview_rows=[],
        )

        self.assertEqual(enriched["target_object"], "商品数据")
        self.assertEqual(enriched["threshold_level"], "none")
        self.assertIn("未命中", enriched["impact_summary"])
        self.assertIn("修改前记录", enriched["rollback_suggestion"])

    def test_rejected_plan_stays_rejected_and_blocks_execution(self):
        enriched = enrich_operation_governance(
            {
                "operation_type": "UPDATE",
                "target_table": "",
                "target_columns": [],
                "condition_description": "随便改一下数据",
                "risk_level": "critical",
                "requires_approval": False,
                "status": "rejected",
            },
            query="随便改一下数据",
            impact_count=0,
            preview_rows=[],
        )

        self.assertEqual(enriched["approval_status"], "rejected")
        self.assertEqual(enriched["execution_status"], "blocked")
        self.assertIn("已拒绝", enriched["status_description"])


if __name__ == "__main__":
    unittest.main()
