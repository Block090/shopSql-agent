import unittest

from eval.metrics.layered_report_metrics import (
    aggregate_layered_results,
    evaluate_layered_case,
)
from eval.metrics.result_metrics import evaluate_result
from eval.schemas.eval_case import EvalCase


class QueryEvalResultMetricsTest(unittest.TestCase):
    def test_eval_case_preserves_expected_result(self):
        case = EvalCase.from_dict(
            {
                "id": "case_order_count_001",
                "query": "统计 2025 年第一季度华东地区的订单数",
                "expected_result": {
                    "columns": ["订单数"],
                    "row_count": 1,
                    "contains": [{"订单数": 44}],
                },
            }
        ).to_dict()

        self.assertEqual(case["expected_result"]["columns"], ["订单数"])
        self.assertEqual(case["expected_result"]["contains"], [{"订单数": 44}])

    def test_evaluate_result_checks_columns_row_count_and_values(self):
        result = evaluate_result(
            {
                "columns": ["订单数"],
                "row_count": 1,
                "contains": [{"订单数": 44}],
            },
            {"result": {"columns": ["订单数"], "rows": [{"订单数": 44}]}},
        )

        self.assertTrue(result["result_pass"])

    def test_evaluate_result_accepts_business_column_aliases(self):
        result = evaluate_result(
            {"columns": ["商品", "GMV"]},
            {
                "result": {
                    "columns": ["商品名称", "销售额"],
                    "rows": [{"商品名称": "手机", "销售额": 100}],
                }
            },
        )

        self.assertTrue(result["result_column_hit"])
        self.assertTrue(result["result_pass"])

    def test_evaluate_result_supports_max_row_count_for_top_n(self):
        result = evaluate_result(
            {"row_count": {"mode": "max", "value": 5}},
            {
                "result": {
                    "columns": ["商品", "销售额"],
                    "rows": [
                        {"商品": "A", "销售额": 100},
                        {"商品": "B", "销售额": 80},
                    ],
                }
            },
        )

        self.assertTrue(result["result_row_count_hit"])
        self.assertTrue(result["result_pass"])

    def test_layered_case_fails_at_result_layer_when_value_is_wrong(self):
        case = {
            "id": "case_order_count_001",
            "query": "统计 2025 年第一季度华东地区的订单数",
            "category": "simple_metric",
            "should_answer": True,
            "expected_context": {
                "tables": [],
                "columns": [],
                "metrics": [],
                "values": [],
            },
            "expected_sql": {
                "must_contain": ["select", "limit"],
                "must_not_contain": ["delete", "update", "insert", "drop", "truncate"],
                "tables": [],
                "columns": [],
            },
            "expected_result": {
                "columns": ["订单数"],
                "row_count": 1,
                "contains": [{"订单数": 44}],
            },
            "expected_behavior": {"final_status": "success", "result_required": True},
        }
        trace = {
            "sql": {"text": "SELECT COUNT(order_id) AS 订单数 FROM fact_order LIMIT 1"},
            "execution": {"final_status": "success", "row_count": 1},
            "result": {"columns": ["订单数"], "rows": [{"订单数": 40}]},
        }

        result = evaluate_layered_case(case, trace)

        self.assertFalse(result["result_pass"])
        self.assertEqual(result["failure_layer"], "result")
        self.assertIn("查询结果", result["failure_reason"])

    def test_aggregate_reports_result_correct_rate(self):
        summary = aggregate_layered_results(
            [
                {
                    "should_answer": True,
                    "final_success": True,
                    "result_pass": True,
                    "sql": "SELECT 1 LIMIT 1",
                    "sql_executable": True,
                },
                {
                    "should_answer": True,
                    "final_success": False,
                    "result_pass": False,
                    "sql": "SELECT 2 LIMIT 1",
                    "sql_executable": True,
                },
            ]
        )

        self.assertEqual(summary["result_correct_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
