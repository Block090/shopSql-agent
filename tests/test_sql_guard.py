import unittest

from app.core.sql_guard import (
    ensure_query_limit,
    sanitize_sql_text,
    validate_readonly_sql,
)


class SQLGuardTest(unittest.TestCase):
    def test_sanitizes_full_width_punctuation_from_model_sql(self):
        sql = "SELECT dr.region_name AS 大区， SUM(fo.order_amount) AS GMV FROM fact_order fo LIMIT 100"

        sanitized = sanitize_sql_text(sql)

        self.assertEqual(
            sanitized,
            "SELECT dr.region_name AS 大区, SUM(fo.order_amount) AS GMV FROM fact_order fo LIMIT 100",
        )

    def test_allows_single_select_with_limit(self):
        validate_readonly_sql("select * from sales_order limit 100")

    def test_rejects_non_select_sql(self):
        with self.assertRaisesRegex(ValueError, "只允许执行 SELECT"):
            validate_readonly_sql("delete from sales_order limit 1")

    def test_rejects_dangerous_keyword(self):
        with self.assertRaisesRegex(ValueError, "危险关键字"):
            validate_readonly_sql("select * from sales_order where name = 'drop' limit 1")

    def test_rejects_multi_statement_sql(self):
        with self.assertRaisesRegex(ValueError, "不允许执行多条 SQL"):
            validate_readonly_sql("select * from sales_order limit 1; select * from dim_user")

    def test_rejects_sql_without_limit(self):
        with self.assertRaisesRegex(ValueError, "必须包含 LIMIT"):
            validate_readonly_sql("select * from sales_order")

    def test_ensure_query_limit_adds_default_limit_before_validation(self):
        sql = ensure_query_limit("SELECT COUNT(*) AS 订单数 FROM fact_order;")

        self.assertEqual(
            sql,
            "SELECT COUNT(*) AS 订单数 FROM fact_order LIMIT 1000",
        )
        validate_readonly_sql(sql)

    def test_ensure_query_limit_caps_excessive_limit(self):
        sql = ensure_query_limit("SELECT * FROM fact_order LIMIT 50000")

        self.assertTrue(sql.endswith("LIMIT 1000"))


if __name__ == "__main__":
    unittest.main()
