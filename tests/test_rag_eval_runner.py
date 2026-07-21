import unittest
from pathlib import Path
from unittest.mock import patch

from eval.runners.run_rag_eval import run_live_eval, run_offline_eval


class RAGEvalRunnerTest(unittest.TestCase):
    def test_run_offline_eval_writes_result_and_report(self):
        base_dir = Path(".test_tmp") / "rag_eval_runner"
        dataset_path = base_dir / "cases.jsonl"
        trace_path = base_dir / "traces.json"
        result_path = base_dir / "reports" / "rag_eval_result.json"
        report_path = base_dir / "reports" / "rag_eval_report.md"
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        dataset_path.write_text(
            '{"id": "case_001", "query": "统计 GMV", "should_answer": true, '
            '"expected_tables": ["dws_trade_summary"], '
            '"expected_columns": ["gmv"], '
            '"expected_metrics": ["GMV"], '
            '"expected_sql_keywords": ["select", "limit"]}\n',
            encoding="utf-8",
        )
        trace_path.write_text(
            '{"case_001": {'
            '"retrieved_columns": ["gmv"], '
            '"retrieved_metrics": ["GMV"], '
            '"table_infos": ["dws_trade_summary"], '
            '"sql": "select gmv from dws_trade_summary limit 100", '
            '"final_status": "success"'
            "}}",
            encoding="utf-8",
        )

        summary = run_offline_eval(
            dataset_path=dataset_path,
            trace_path=trace_path,
            result_path=result_path,
            report_path=report_path,
        )

        self.assertEqual(summary["total_cases"], 1)
        self.assertTrue(result_path.exists())
        self.assertTrue(report_path.exists())
        self.assertIn("RAG 测评报告", report_path.read_text(encoding="utf-8"))

    def test_run_live_eval_collects_traces_before_evaluating(self):
        base_dir = Path(".test_tmp") / "rag_eval_live_runner"
        dataset_path = base_dir / "cases.jsonl"
        trace_path = base_dir / "reports" / "rag_eval_traces.json"
        result_path = base_dir / "reports" / "rag_eval_result.json"
        report_path = base_dir / "reports" / "rag_eval_report.md"
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        dataset_path.write_text(
            '{"id": "case_001", "query": "统计 GMV", "should_answer": true, '
            '"expected_tables": ["dws_trade_summary"], '
            '"expected_columns": ["gmv"], '
            '"expected_metrics": ["GMV"], '
            '"expected_sql_keywords": ["select", "limit"]}\n',
            encoding="utf-8",
        )

        with patch(
            "eval.runners.run_rag_eval.collect_live_traces",
            return_value={
                "case_001": {
                    "retrieved_columns": ["gmv"],
                    "retrieved_metrics": ["GMV"],
                    "table_infos": ["dws_trade_summary"],
                    "sql": "select gmv from dws_trade_summary limit 100",
                    "final_status": "success",
                }
            },
        ):
            summary = run_live_eval(
                dataset_path=dataset_path,
                trace_path=trace_path,
                result_path=result_path,
                report_path=report_path,
            )

        self.assertEqual(summary["total_cases"], 1)
        self.assertTrue(trace_path.exists())
        self.assertIn("case_001", trace_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
