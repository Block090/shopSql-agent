import unittest

from app.core.query_rewriter import rewrite_query_with_history, rewrite_query_with_trace


class QueryRewriterTest(unittest.TestCase):
    def test_rewrite_region_follow_up_uses_previous_metric_and_time(self):
        recent_turns = [
            {
                "query": "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
                "resolved_query": "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
            }
        ]

        result = rewrite_query_with_history("那华东地区呢", recent_turns)

        self.assertEqual(result, "统计 2025 年第一季度华东地区的 GMV")

    def test_rewrite_metric_follow_up_uses_previous_subject_and_time(self):
        recent_turns = [
            {
                "query": "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
                "resolved_query": "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
            }
        ]

        result = rewrite_query_with_history("换成订单数呢", recent_turns)

        self.assertEqual(result, "统计 2025 年第一季度各大区的订单数，并按订单数从高到低排序")

    def test_rewrite_quarter_follow_up_keeps_previous_subject_metric_and_sort(self):
        recent_turns = [
            {
                "query": "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
                "resolved_query": "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
                "semantic_slots": {
                    "time_range": "2025 年第一季度",
                    "dimension": "大区",
                    "metrics": ["GMV"],
                    "filters": {},
                    "sort": {"field": "GMV", "direction": "desc"},
                    "limit": None,
                },
            }
        ]

        result = rewrite_query_with_trace("那第二季度", recent_turns)

        self.assertEqual(result.resolved_query, "统计 2025 年第二季度各大区的 GMV，并按 GMV 从高到低排序")
        self.assertEqual(result.semantic_slots["time_range"], "2025 年第二季度")
        self.assertEqual(result.semantic_slots["sort"], {"field": "GMV", "direction": "desc"})

    def test_rewrite_month_follow_up_keeps_previous_dimension_and_all_metrics(self):
        recent_turns = [
            {
                "query": "统计 2025 年 3 月各商品品类的销量和销售额",
                "resolved_query": "统计 2025 年 3 月各商品品类的销量和销售额",
                "semantic_slots": {
                    "time_range": "2025 年 3 月",
                    "dimension": "商品品类",
                    "metrics": ["销量", "销售额"],
                    "filters": {},
                    "sort": None,
                    "limit": None,
                },
            }
        ]

        result = rewrite_query_with_trace("那4月份的呢", recent_turns)

        self.assertEqual(result.resolved_query, "统计 2025 年 4 月各商品品类的销量和销售额")
        self.assertEqual(result.semantic_slots["time_range"], "2025 年 4 月")
        self.assertEqual(result.semantic_slots["dimension"], "商品品类")
        self.assertEqual(result.semantic_slots["metrics"], ["销量", "销售额"])

    def test_complete_question_extracts_semantic_slots_for_later_follow_up(self):
        result = rewrite_query_with_trace(
            "统计 2025 年 3 月各商品品类的销量和销售额",
            [],
        )

        self.assertEqual(
            result.semantic_slots,
            {
                "time_range": "2025 年 3 月",
                "dimension": "商品品类",
                "metrics": ["销量", "销售额"],
                "filters": {},
                "sort": None,
                "limit": None,
            },
        )

    def test_rewrite_keeps_complete_question_unchanged(self):
        result = rewrite_query_with_history(
            "统计 2025 年 3 月各商品品类的销量和销售额",
            [
                {
                    "query": "统计 2025 年第一季度各大区的 GMV",
                    "resolved_query": "统计 2025 年第一季度各大区的 GMV",
                }
            ],
        )

        self.assertEqual(result, "统计 2025 年 3 月各商品品类的销量和销售额")

    def test_rewrite_region_follow_up_returns_context_trace(self):
        recent_turns = [
            {
                "query": "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
                "resolved_query": "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
                "id": 12,
            }
        ]

        result = rewrite_query_with_trace("那华东地区呢", recent_turns)

        self.assertEqual(result.resolved_query, "统计 2025 年第一季度华东地区的 GMV")
        self.assertEqual(
            result.context_trace,
            {
                "original_query": "那华东地区呢",
                "resolved_query": "统计 2025 年第一季度华东地区的 GMV",
                "is_follow_up": True,
                "inherited_context": {
                    "time_range": "2025 年第一季度",
                    "metrics": ["GMV"],
                    "sort": "GMV 从高到低",
                },
                "overwritten_context": {"region": "华东"},
                "source_turn_id": 12,
                "rewrite_method": "rule",
                "confidence": 0.9,
            },
        )

    def test_rewrite_dimension_metric_and_sort_follow_up_from_previous_slots(self):
        recent_turns = [
            {
                "query": "统计 2025 年 3 月各商品品类的销量和销售额",
                "resolved_query": "统计 2025 年 3 月各商品品类的销量和销售额",
                "semantic_slots": {
                    "time_range": "2025 年 3 月",
                    "dimension": "商品品类",
                    "metrics": ["销量", "销售额"],
                    "filters": {},
                    "sort": None,
                    "limit": None,
                },
            }
        ]

        result = rewrite_query_with_trace("那各大区的GMV排序呢", recent_turns)

        self.assertEqual(result.resolved_query, "统计 2025 年 3 月各大区的 GMV，并按 GMV 从高到低排序")
        self.assertEqual(
            result.semantic_slots,
            {
                "time_range": "2025 年 3 月",
                "dimension": "大区",
                "metrics": ["GMV"],
                "filters": {},
                "sort": {"field": "GMV", "direction": "desc"},
                "limit": None,
            },
        )
        self.assertEqual(result.context_trace["inherited_context"], {"time_range": "2025 年 3 月"})
        self.assertEqual(
            result.context_trace["overwritten_context"],
            {"dimension": "大区", "metrics": ["GMV"], "sort": "GMV 从高到低"},
        )
        self.assertGreaterEqual(result.confidence, 0.8)


if __name__ == "__main__":
    unittest.main()
