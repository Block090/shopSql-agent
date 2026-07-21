import unittest

from app.core.result_productization import (
    analyze_result_with_fallback,
    extract_result_facts,
)


class ResultProductizationTest(unittest.IsolatedAsyncioTestCase):
    def test_extract_result_facts_identifies_dimensions_metrics_and_chart(self):
        data = [
            {"商品品类": "手机数码", "销量": 10, "销售额": 62190},
            {"商品品类": "食品饮料", "销量": 139, "销售额": 1115},
            {"商品品类": "休闲零食", "销量": 156, "销售额": 630},
        ]

        facts = extract_result_facts(data)

        assert facts["row_count"] == 3
        assert facts["dimension_columns"] == ["商品品类"]
        assert facts["metric_columns"] == ["销量", "销售额"]
        assert facts["top_values"]["销量"] == {"label": "休闲零食", "value": 156}
        assert facts["top_values"]["销售额"] == {"label": "手机数码", "value": 62190}
        assert facts["chart_candidates"][0]["type"] == "bar"
        assert facts["chart_candidates"][0]["x"] == "商品品类"
        assert facts["chart_candidates"][0]["y"] == "销量"

    async def test_analyze_result_with_fallback_returns_rule_analysis_when_llm_is_unavailable(self):
        data = [
            {"商品品类": "手机数码", "销量": 10, "销售额": 62190},
            {"商品品类": "食品饮料", "销量": 139, "销售额": 1115},
            {"商品品类": "休闲零食", "销量": 156, "销售额": 630},
        ]

        analysis = await analyze_result_with_fallback(
            query="统计 2025 年 3 月各商品品类的销量和销售额",
            resolved_query="统计 2025 年 3 月各商品品类的销量和销售额",
            result_data=data,
            llm_client=object(),
        )

        assert analysis["generated_by"] == "rule_fallback"
        assert analysis["summary"]
        assert len(analysis["insights"]) >= 2
        assert analysis["chart_recommendation"]["type"] == "bar"
        assert analysis["result_facts"]["top_values"]["销售额"]["label"] == "手机数码"


if __name__ == "__main__":
    unittest.main()
