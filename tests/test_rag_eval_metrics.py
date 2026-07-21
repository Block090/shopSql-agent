import unittest

from eval.metrics.report_metrics import aggregate_results, evaluate_case
from eval.metrics.retrieval_metrics import precision_at_k, recall_at_k
from eval.metrics.sql_metrics import is_sql_compliant


class RAGEvalMetricsTest(unittest.TestCase):
    def test_recall_and_precision_at_k(self):
        expected = ["gmv", "region_name", "stat_date"]
        retrieved = ["gmv", "order_count", "region_name", "stat_date"]

        self.assertEqual(recall_at_k(expected, retrieved, 3), 2 / 3)
        self.assertEqual(precision_at_k(expected, retrieved, 3), 2 / 3)

    def test_recall_at_k_normalizes_business_values(self):
        self.assertEqual(recall_at_k(["第一季度"], ["Q1"], 5), 1.0)
        self.assertEqual(recall_at_k(["华东地区"], ["华东"], 5), 1.0)
        self.assertEqual(recall_at_k(["女性"], ["女"], 5), 1.0)

    def test_sql_compliance_requires_select_limit_and_no_dangerous_keyword(self):
        self.assertTrue(is_sql_compliant("select gmv from dws_trade limit 10"))
        self.assertFalse(is_sql_compliant("select gmv from dws_trade"))
        self.assertFalse(is_sql_compliant("delete from dws_trade where id = 1"))

    def test_evaluate_successful_answer_case(self):
        case = {
            "id": "case_001",
            "query": "统计 GMV",
            "should_answer": True,
            "expected_tables": ["dws_trade_summary"],
            "expected_columns": ["gmv"],
            "expected_metrics": ["GMV"],
            "expected_sql_keywords": ["select", "limit"],
        }
        trace = {
            "retrieved_columns": ["gmv", "order_count"],
            "retrieved_metrics": ["GMV"],
            "table_infos": ["dws_trade_summary"],
            "sql": "select gmv from dws_trade_summary limit 100",
            "final_status": "success",
        }

        result = evaluate_case(case, trace)

        self.assertTrue(result["success"])
        self.assertEqual(result["field_recall_at_5"], 1.0)
        self.assertEqual(result["metric_recall_at_5"], 1.0)
        self.assertTrue(result["table_hit"])
        self.assertTrue(result["sql_compliant"])

    def test_evaluate_reject_case_requires_expected_error_type(self):
        case = {
            "id": "case_unsafe_001",
            "query": "删除订单",
            "should_answer": False,
            "expected_error_type": "unsafe_intent",
        }
        trace = {
            "final_status": "rejected",
            "error_type": "unsafe_intent",
            "sql": "",
        }

        result = evaluate_case(case, trace)

        self.assertTrue(result["success"])
        self.assertTrue(result["rejection_correct"])

    def test_aggregate_results_calculates_summary_rates(self):
        results = [
            {"success": True, "should_answer": True, "field_recall_at_5": 1.0},
            {"success": False, "should_answer": True, "field_recall_at_5": 0.0},
            {"success": True, "should_answer": False, "rejection_correct": True},
        ]

        summary = aggregate_results(results)

        self.assertEqual(summary["total_cases"], 3)
        self.assertEqual(summary["answer_cases"], 2)
        self.assertEqual(summary["reject_cases"], 1)
        self.assertEqual(summary["end_to_end_success_rate"], 2 / 3)
        self.assertEqual(summary["field_recall_at_5"], 0.5)


if __name__ == "__main__":
    unittest.main()
