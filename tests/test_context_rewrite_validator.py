import json
import unittest

from app.core.context_rewrite.llm_rewriter import (
    rewrite_query_with_llm_or_rule,
    validate_llm_rewrite_json,
)


class FakeLLMResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def ainvoke(self, prompt):
        self.calls.append(prompt)
        return FakeLLMResponse(self.content)


class ContextRewriteValidatorTest(unittest.TestCase):
    def test_accepts_valid_rewrite_json(self):
        is_valid, payload, reason = validate_llm_rewrite_json(
            json.dumps(
                {
                    "resolved_query": "统计 2025 年 3 月各大区的 GMV，并按 GMV 从高到低排序",
                    "semantic_slots": {
                        "time_range": "2025 年 3 月",
                        "dimension": "大区",
                        "metrics": ["GMV"],
                        "filters": {},
                        "sort": {"field": "GMV", "direction": "desc"},
                    },
                    "confidence": 0.92,
                },
                ensure_ascii=False,
            )
        )

        self.assertTrue(is_valid)
        self.assertEqual(payload["semantic_slots"]["dimension"], "大区")
        self.assertEqual(reason, "")

    def test_rejects_unknown_dimension(self):
        is_valid, _, reason = validate_llm_rewrite_json(
            json.dumps(
                {
                    "semantic_slots": {
                        "dimension": "主播",
                        "metrics": ["GMV"],
                    },
                    "confidence": 0.92,
                },
                ensure_ascii=False,
            )
        )

        self.assertFalse(is_valid)
        self.assertIn("主播", reason)

    def test_rejects_low_confidence(self):
        is_valid, _, reason = validate_llm_rewrite_json(
            json.dumps(
                {
                    "semantic_slots": {
                        "dimension": "大区",
                        "metrics": ["GMV"],
                    },
                    "confidence": 0.56,
                },
                ensure_ascii=False,
            )
        )

        self.assertFalse(is_valid)
        self.assertIn("置信度", reason)

    def test_rejects_string_sort_without_crashing(self):
        is_valid, _, reason = validate_llm_rewrite_json(
            json.dumps(
                {
                    "semantic_slots": {
                        "dimension": "大区",
                        "metrics": ["GMV"],
                        "sort": "GMV 从高到低",
                    },
                    "confidence": 0.92,
                },
                ensure_ascii=False,
            )
        )

        self.assertFalse(is_valid)
        self.assertIn("排序字段结构", reason)


class LLMRewriteFlowTest(unittest.IsolatedAsyncioTestCase):
    async def test_complete_question_does_not_call_llm(self):
        fake_llm = FakeLLM("{}")

        result = await rewrite_query_with_llm_or_rule(
            "统计 2025 年 3 月各商品品类的销量和销售额",
            [{"query": "统计 2025 年第一季度各大区 GMV"}],
            llm_client=fake_llm,
        )

        self.assertEqual(fake_llm.calls, [])
        self.assertFalse(result.is_follow_up)

    async def test_confirmation_follow_up_reuses_previous_resolved_query_without_llm(self):
        fake_llm = FakeLLM("{}")

        result = await rewrite_query_with_llm_or_rule(
            "那第二季度呢，是，按这个查询",
            [
                {
                    "query": "那第二季度呢",
                    "resolved_query": "统计 2025 年第二季度各大区的 GMV，并按 GMV 从高到低排序",
                    "status": "clarification_required",
                    "semantic_slots": {
                        "time_range": "2025 年第二季度",
                        "dimension": "大区",
                        "metrics": ["GMV"],
                        "filters": {},
                        "sort": {"field": "GMV", "direction": "desc"},
                        "limit": None,
                    },
                    "rewrite_confidence": 0.5,
                }
            ],
            llm_client=fake_llm,
        )

        self.assertEqual(fake_llm.calls, [])
        self.assertEqual(
            result.resolved_query,
            "统计 2025 年第二季度各大区的 GMV，并按 GMV 从高到低排序",
        )
        self.assertEqual(result.rewrite_method, "confirmation")
        self.assertFalse(result.needs_clarification)
        self.assertEqual(result.semantic_slots["time_range"], "2025 年第二季度")

    async def test_valid_llm_json_is_used(self):
        fake_llm = FakeLLM(
            json.dumps(
                {
                    "is_follow_up": True,
                    "resolved_query": "统计 2025 年 3 月各大区的 GMV，并按 GMV 从高到低排序",
                    "semantic_slots": {
                        "time_range": "2025 年 3 月",
                        "dimension": "大区",
                        "metrics": ["GMV"],
                        "filters": {},
                        "sort": {"field": "GMV", "direction": "desc"},
                        "limit": None,
                    },
                    "inherited_context": {"time_range": "2025 年 3 月"},
                    "overwritten_context": {
                        "dimension": "大区",
                        "metrics": ["GMV"],
                        "sort": "GMV 从高到低",
                    },
                    "needs_clarification": False,
                    "clarification_question": "",
                    "confidence": 0.92,
                    "rewrite_method": "llm",
                },
                ensure_ascii=False,
            )
        )

        result = await rewrite_query_with_llm_or_rule(
            "那各大区的GMV排序呢",
            [
                {
                    "query": "统计 2025 年 3 月各商品品类的销量和销售额",
                    "semantic_slots": {
                        "time_range": "2025 年 3 月",
                        "dimension": "商品品类",
                        "metrics": ["销量", "销售额"],
                        "filters": {},
                        "sort": None,
                        "limit": None,
                    },
                }
            ],
            llm_client=fake_llm,
        )

        self.assertEqual(result.rewrite_method, "llm")
        self.assertEqual(result.resolved_query, "统计 2025 年 3 月各大区的 GMV，并按 GMV 从高到低排序")
        self.assertEqual(result.semantic_slots["dimension"], "大区")

    async def test_invalid_llm_json_falls_back_to_rule(self):
        fake_llm = FakeLLM("不是 JSON")

        result = await rewrite_query_with_llm_or_rule(
            "那各大区的GMV排序呢",
            [
                {
                    "query": "统计 2025 年 3 月各商品品类的销量和销售额",
                    "semantic_slots": {
                        "time_range": "2025 年 3 月",
                        "dimension": "商品品类",
                        "metrics": ["销量", "销售额"],
                        "filters": {},
                        "sort": None,
                        "limit": None,
                    },
                }
            ],
            llm_client=fake_llm,
        )

        self.assertEqual(result.rewrite_method, "rule")
        self.assertEqual(result.semantic_slots["dimension"], "大区")

    async def test_deterministic_time_follow_up_does_not_allow_llm_to_drop_slots(self):
        fake_llm = FakeLLM(
            json.dumps(
                {
                    "is_follow_up": True,
                    "resolved_query": "统计 2025 年 4 月的销量",
                    "semantic_slots": {
                        "time_range": "2025 年 4 月",
                        "dimension": None,
                        "metrics": ["销量"],
                        "filters": {},
                        "sort": None,
                        "limit": None,
                    },
                    "needs_clarification": False,
                    "clarification_question": "",
                    "confidence": 0.95,
                    "rewrite_method": "llm",
                },
                ensure_ascii=False,
            )
        )

        result = await rewrite_query_with_llm_or_rule(
            "那4月份的呢",
            [
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
            ],
            llm_client=fake_llm,
        )

        self.assertEqual(result.rewrite_method, "rule")
        self.assertEqual(result.resolved_query, "统计 2025 年 4 月各商品品类的销量和销售额")
        self.assertEqual(result.semantic_slots["metrics"], ["销量", "销售额"])
        self.assertEqual(fake_llm.calls, [])

    async def test_low_confidence_llm_json_returns_clarification(self):
        fake_llm = FakeLLM(
            json.dumps(
                {
                    "is_follow_up": True,
                    "resolved_query": "",
                    "semantic_slots": {
                        "dimension": "大区",
                        "metrics": ["GMV"],
                    },
                    "needs_clarification": True,
                    "clarification_question": "你是想按大区统计 2025 年 3 月 GMV 吗？",
                    "confidence": 0.56,
                    "rewrite_method": "llm",
                },
                ensure_ascii=False,
            )
        )

        result = await rewrite_query_with_llm_or_rule(
            "那各大区呢",
            [{"query": "统计 2025 年 3 月各商品品类的销量和销售额"}],
            llm_client=fake_llm,
        )

        self.assertTrue(result.needs_clarification)
        self.assertEqual(result.clarification_question, "你是想按大区统计 2025 年 3 月 GMV 吗？")


if __name__ == "__main__":
    unittest.main()
