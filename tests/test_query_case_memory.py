import unittest

from app.core.query_case_memory import (
    build_query_case,
    build_query_case_text,
    compress_similar_cases,
)


class QueryCaseMemoryTest(unittest.TestCase):
    def test_builds_query_case_from_successful_sql(self):
        query_case = build_query_case(
            query="各大区 GMV",
            resolved_query="统计 2025 年第一季度各大区 GMV，并按 GMV 从高到低排序",
            sql=(
                "SELECT dim_region.region_name AS 大区, SUM(fact_order.order_amount) AS GMV "
                "FROM fact_order JOIN dim_region ON fact_order.region_id = dim_region.region_id "
                "JOIN dim_date ON fact_order.date_id = dim_date.date_id "
                "WHERE fact_order.date_id BETWEEN 20250101 AND 20250331 "
                "GROUP BY dim_region.region_name ORDER BY GMV DESC"
            ),
            semantic_slots={
                "time_range": "2025 年第一季度",
                "dimension": "大区",
                "metrics": ["GMV"],
                "filters": {},
                "sort": {"field": "GMV", "direction": "desc"},
            },
            result_summary="返回 5 行，字段：大区、GMV",
        )

        self.assertEqual(query_case["question"], "各大区 GMV")
        self.assertEqual(query_case["resolved_query"], "统计 2025 年第一季度各大区 GMV，并按 GMV 从高到低排序")
        self.assertEqual(query_case["used_tables"], ["dim_date", "dim_region", "fact_order"])
        self.assertIn("order_amount", query_case["used_fields"])
        self.assertIn("按大区维度分组", query_case["sql_pattern"])
        self.assertIn("按 GMV 降序", query_case["sql_pattern"])

    def test_build_query_case_text_contains_business_slots(self):
        text = build_query_case_text(
            {
                "question": "各大区 GMV",
                "resolved_query": "统计 2025 年第一季度各大区 GMV",
                "semantic_slots": {
                    "time_range": "2025 年第一季度",
                    "dimension": "大区",
                    "metrics": ["GMV"],
                    "filters": {"region": "华东"},
                },
                "used_tables": ["fact_order", "dim_region"],
                "used_fields": ["order_amount", "region_name"],
                "sql_pattern": "按大区维度分组，汇总 GMV",
            }
        )

        self.assertIn("指标：GMV", text)
        self.assertIn("维度：大区", text)
        self.assertIn("过滤条件：region=华东", text)
        self.assertIn("使用表：fact_order, dim_region", text)

    def test_compresses_similar_cases_without_raw_sql(self):
        compressed = compress_similar_cases(
            [
                {
                    "question": "统计各大区 GMV",
                    "resolved_query": "统计 2025 年第一季度各大区 GMV",
                    "sql": "SELECT secret FROM fact_order",
                    "used_tables": ["fact_order", "dim_region"],
                    "used_fields": ["order_amount", "region_name"],
                    "sql_pattern": "按大区维度分组，汇总 GMV",
                }
            ]
        )

        self.assertEqual(compressed[0]["question"], "统计各大区 GMV")
        self.assertNotIn("sql", compressed[0])
        self.assertEqual(compressed[0]["used_tables"], ["fact_order", "dim_region"])


if __name__ == "__main__":
    unittest.main()
