import unittest

from app.core.query_intent_guard import is_unsafe_write_intent


class QueryIntentGuardTest(unittest.TestCase):
    def test_detects_chinese_delete_update_and_insert_intents(self):
        self.assertTrue(is_unsafe_write_intent("删除 2025 年 3 月的测试订单"))
        self.assertTrue(is_unsafe_write_intent("帮我修改商品价格"))
        self.assertTrue(is_unsafe_write_intent("新增一条会员记录"))

    def test_allows_readonly_analysis_question(self):
        self.assertFalse(is_unsafe_write_intent("统计 2025 年第一季度各大区 GMV"))


if __name__ == "__main__":
    unittest.main()
