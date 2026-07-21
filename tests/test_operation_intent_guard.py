import unittest

from app.core.operation_intent_guard import classify_operation_intent


class OperationIntentGuardTest(unittest.TestCase):
    def test_classifies_delete_update_insert_intents(self):
        self.assertEqual(
            classify_operation_intent("删除 2025 年 3 月的测试订单")["intent_type"],
            "operation",
        )
        self.assertEqual(
            classify_operation_intent("把 iPhone 15 Pro 的品类改成手机数码")[
                "operation_type"
            ],
            "UPDATE",
        )
        self.assertEqual(
            classify_operation_intent("新增一个商品：小米 14 Pro")["operation_type"],
            "INSERT",
        )

    def test_classifies_structural_database_changes_as_dangerous(self):
        result = classify_operation_intent("清空订单表")

        self.assertEqual(result["intent_type"], "dangerous")
        self.assertEqual(result["operation_type"], "TRUNCATE")

    def test_classifies_readonly_question(self):
        result = classify_operation_intent("统计 2025 年第一季度各大区 GMV")

        self.assertEqual(result["intent_type"], "readonly")
        self.assertEqual(result["operation_type"], "")


if __name__ == "__main__":
    unittest.main()
