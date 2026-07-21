import unittest
from unittest.mock import patch

from eval.runners.live_agent_trace import consume_graph_stream, run_agent_case


class RAGEvalLiveRunnerTest(unittest.IsolatedAsyncioTestCase):
    async def test_consume_graph_stream_builds_trace_from_custom_and_values_chunks(self):
        async def fake_stream():
            yield (
                "custom",
                {"type": "progress", "step": "检查用户意图", "status": "success"},
            )
            yield (
                "values",
                {
                    "retrieved_column_infos": [{"name": "gmv"}],
                    "retrieved_metric_infos": [{"name": "GMV"}],
                    "table_infos": [{"name": "dws_trade_summary"}],
                    "sql": "select gmv from dws_trade_summary limit 100",
                    "error": None,
                },
            )

        trace = await consume_graph_stream(fake_stream())

        self.assertEqual(trace["retrieved_columns"], ["gmv"])
        self.assertEqual(trace["retrieved_metrics"], ["GMV"])
        self.assertEqual(trace["table_infos"], ["dws_trade_summary"])
        self.assertEqual(trace["final_status"], "success")

    async def test_consume_graph_stream_records_node_and_total_timing(self):
        async def fake_stream():
            yield (
                "custom",
                {"type": "progress", "step": "生成SQL", "status": "running"},
            )
            yield (
                "custom",
                {"type": "progress", "step": "生成SQL", "status": "success"},
            )
            yield ("values", {"sql": "SELECT 1 LIMIT 1", "error": None})

        trace = await consume_graph_stream(fake_stream())

        self.assertGreaterEqual(trace["execution"]["latency_ms"], 0)
        self.assertIn("生成SQL", trace["performance"]["node_latency_ms"])
        self.assertEqual(trace["performance"]["model_call_count"], 1)

    async def test_run_agent_case_returns_timeout_trace_when_case_hangs(self):
        class HangingGraph:
            def astream(self, **kwargs):
                async def stream():
                    while True:
                        yield (
                            "custom",
                            {
                                "type": "progress",
                                "step": "生成SQL",
                                "status": "running",
                            },
                        )

                return stream()

        with patch("eval.runners.live_agent_trace.graph", HangingGraph()):
            trace = await run_agent_case(
                {"id": "case_timeout", "query": "统计 GMV"},
                context={},
                case_timeout_seconds=0.01,
            )

        self.assertEqual(trace["final_status"], "failed")
        self.assertEqual(trace["error_type"], "case_timeout")
        self.assertIn("case_timeout", trace["error_message"])


if __name__ == "__main__":
    unittest.main()
