import json
import unittest
from pathlib import Path

from eval.runners.compare_reports import compare_eval_results, render_compare_report


class QueryEvalCompareTest(unittest.TestCase):
    def test_compare_eval_results_reports_metric_delta(self):
        baseline = {
            "summary": {
                "end_to_end_success_rate": 0.5,
                "result_correct_rate": 0.25,
                "sql_compliance_rate": 0.75,
            }
        }
        current = {
            "summary": {
                "end_to_end_success_rate": 0.75,
                "result_correct_rate": 0.5,
                "sql_compliance_rate": 1.0,
            }
        }

        comparison = compare_eval_results(baseline, current)

        self.assertEqual(
            comparison["metrics"]["end_to_end_success_rate"]["delta"], 0.25
        )
        self.assertEqual(comparison["metrics"]["result_correct_rate"]["delta"], 0.25)

    def test_render_compare_report_writes_readable_markdown(self):
        comparison = {
            "metrics": {
                "end_to_end_success_rate": {
                    "baseline": 0.5,
                    "current": 0.75,
                    "delta": 0.25,
                },
                "result_correct_rate": {
                    "baseline": 0.25,
                    "current": 0.5,
                    "delta": 0.25,
                },
            }
        }

        report = render_compare_report(comparison)

        self.assertIn("# 电商问数 Agent 测评 Baseline 对比报告", report)
        self.assertIn("端到端成功率", report)
        self.assertIn("+25.00%", report)

    def test_compare_cli_helper_writes_report_files(self):
        from eval.runners.compare_reports import write_compare_report

        base_dir = Path(".test_tmp") / "query_eval_compare"
        baseline_path = base_dir / "baseline.json"
        current_path = base_dir / "current.json"
        output_path = base_dir / "compare.md"
        base_dir.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(
            json.dumps({"summary": {"end_to_end_success_rate": 0.5}}),
            encoding="utf-8",
        )
        current_path.write_text(
            json.dumps({"summary": {"end_to_end_success_rate": 0.75}}),
            encoding="utf-8",
        )

        write_compare_report(baseline_path, current_path, output_path)

        self.assertTrue(output_path.exists())
        self.assertIn("+25.00%", output_path.read_text(encoding="utf-8"))

    def test_compare_reports_fixed_regressed_and_new_failures(self):
        baseline = {
            "summary": {},
            "results": [
                {"id": "fixed", "final_success": False},
                {"id": "regressed", "final_success": True},
            ],
        }
        current = {
            "summary": {},
            "results": [
                {"id": "fixed", "final_success": True},
                {"id": "regressed", "final_success": False},
                {"id": "new_failure", "final_success": False},
            ],
        }

        comparison = compare_eval_results(baseline, current)

        self.assertEqual(comparison["fixed_case_ids"], ["fixed"])
        self.assertEqual(comparison["regressed_case_ids"], ["regressed"])
        self.assertEqual(comparison["new_failure_case_ids"], ["new_failure"])


if __name__ == "__main__":
    unittest.main()
