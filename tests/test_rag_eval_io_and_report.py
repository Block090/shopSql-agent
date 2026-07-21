import unittest
from decimal import Decimal
from pathlib import Path

from eval.io import load_jsonl, write_json
from eval.report import render_markdown_report


class RAGEvalIOAndReportTest(unittest.TestCase):
    def test_load_jsonl_ignores_blank_lines(self):
        dataset_path = Path(".test_tmp") / "rag_eval" / "cases.jsonl"
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        dataset_path.write_text(
            '{"id": "case_001", "query": "统计 GMV"}\n\n'
            '{"id": "case_002", "query": "删除订单"}\n',
            encoding="utf-8",
        )

        cases = load_jsonl(dataset_path)

        self.assertEqual([case["id"] for case in cases], ["case_001", "case_002"])

    def test_write_json_creates_parent_directory(self):
        output_path = Path(".test_tmp") / "rag_eval" / "reports" / "result.json"

        write_json(output_path, [{"id": "case_001"}])

        self.assertTrue(output_path.exists())
        self.assertIn("case_001", output_path.read_text(encoding="utf-8"))

    def test_write_json_serializes_decimal_values_from_sql_result(self):
        output_path = Path(".test_tmp") / "rag_eval" / "reports" / "decimal.json"

        write_json(output_path, {"result": {"rows": [{"销量": Decimal("12.50")}]}})

        content = output_path.read_text(encoding="utf-8")
        self.assertIn('"销量": 12.5', content)

    def test_render_markdown_report_contains_summary_and_failed_cases(self):
        summary = {
            "total_cases": 2,
            "answer_cases": 1,
            "reject_cases": 1,
            "end_to_end_success_rate": 0.5,
            "field_recall_at_5": 1.0,
            "metric_recall_at_5": 1.0,
            "table_hit_rate": 1.0,
            "sql_compliance_rate": 1.0,
            "rejection_accuracy": 0.0,
        }
        results = [
            {"id": "case_001", "query": "统计 GMV", "success": True},
            {
                "id": "case_unsafe_001",
                "query": "删除订单",
                "success": False,
                "category": "unsafe_intent",
            },
        ]

        markdown = render_markdown_report(summary, results)

        self.assertIn("# RAG 测评报告", markdown)
        self.assertIn("| 总用例数 | 2 |", markdown)
        self.assertIn("case_unsafe_001", markdown)


if __name__ == "__main__":
    unittest.main()
