import unittest

from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.value_info import ValueInfo
from eval.trace import build_trace_from_state


class RAGEvalTraceTest(unittest.TestCase):
    def test_build_trace_from_success_state(self):
        state = {
            "retrieved_column_infos": [
                ColumnInfo(
                    id="c1",
                    name="gmv",
                    type="decimal",
                    role="metric",
                    examples=[],
                    description="成交金额",
                    alias=[],
                    table_id="t1",
                )
            ],
            "retrieved_metric_infos": [
                MetricInfo(
                    id="m1",
                    name="GMV",
                    description="成交金额",
                    relevant_columns=["c1"],
                    alias=[],
                )
            ],
            "retrieved_value_infos": [
                ValueInfo(id="v1", value="华东", column_id="region_name")
            ],
            "table_infos": [{"name": "dws_trade_summary"}],
            "sql": "select gmv from dws_trade_summary limit 100",
            "query_result": [{"GMV": 100}],
            "error": None,
        }

        trace = build_trace_from_state(state, events=[])

        self.assertEqual(trace["retrieved_columns"], ["gmv"])
        self.assertEqual(trace["retrieved_metrics"], ["GMV"])
        self.assertEqual(trace["retrieved_values"], ["华东"])
        self.assertEqual(trace["table_infos"], ["dws_trade_summary"])
        self.assertEqual(trace["final_status"], "success")
        self.assertEqual(trace["result"]["columns"], ["GMV"])
        self.assertEqual(trace["result"]["rows"], [{"GMV": 100}])

    def test_build_trace_prefers_result_event_rows(self):
        state = {
            "sql": "select count(*) as 订单数 from fact_order limit 1",
            "error": None,
        }
        events = [{"type": "result", "data": [{"订单数": 44}]}]

        trace = build_trace_from_state(state, events=events)

        self.assertEqual(trace["execution"]["row_count"], 1)
        self.assertEqual(trace["result"]["columns"], ["订单数"])
        self.assertEqual(trace["result"]["rows"], [{"订单数": 44}])

    def test_build_trace_from_rejected_event(self):
        events = [
            {"type": "progress", "step": "拒绝危险操作", "status": "error"},
            {
                "type": "error",
                "message": "当前系统仅支持只读数据分析，不能执行删除操作。",
            },
        ]

        trace = build_trace_from_state({}, events=events)

        self.assertEqual(trace["final_status"], "rejected")
        self.assertEqual(trace["error_type"], "unsafe_intent")
        self.assertEqual(trace["sql"], "")

    def test_build_trace_from_no_context_event_uses_unable_to_answer_status(self):
        events = [
            {"type": "progress", "step": "无法回答", "status": "error"},
            {
                "type": "error",
                "message": "当前数据知识库中没有找到足够相关的信息。",
            },
        ]

        trace = build_trace_from_state({}, events=events)

        self.assertEqual(trace["final_status"], "unable_to_answer")
        self.assertEqual(trace["execution"]["final_status"], "unable_to_answer")
        self.assertEqual(trace["error_type"], "no_recall_context")


if __name__ == "__main__":
    unittest.main()
