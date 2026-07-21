import unittest
from types import SimpleNamespace

from app.agent.nodes.check_query_intent import check_query_intent
from app.agent.nodes.reject_unsafe_intent import reject_unsafe_intent


class QueryIntentNodesTest(unittest.IsolatedAsyncioTestCase):
    async def test_check_query_intent_marks_delete_request_as_operation(self):
        events = []
        runtime = SimpleNamespace(stream_writer=events.append)

        result = await check_query_intent(
            {"query": "删除 2025 年 3 月的订单"},
            runtime,
        )

        self.assertEqual(
            result,
            {
                "is_unsafe_intent": False,
                "operation_intent": True,
                "operation_type": "DELETE",
            },
        )
        self.assertIn(
            {"type": "progress", "step": "检查用户意图", "status": "success"},
            events,
        )

    async def test_check_query_intent_marks_truncate_request_as_unsafe(self):
        events = []
        runtime = SimpleNamespace(stream_writer=events.append)

        result = await check_query_intent({"query": "清空订单表"}, runtime)

        self.assertEqual(
            result,
            {
                "is_unsafe_intent": True,
                "operation_intent": False,
                "operation_type": "TRUNCATE",
            },
        )

    async def test_reject_unsafe_intent_emits_readonly_error_message(self):
        events = []
        runtime = SimpleNamespace(stream_writer=events.append)

        await reject_unsafe_intent({"query": "修改商品价格"}, runtime)

        self.assertIn(
            {"type": "progress", "step": "拒绝危险操作", "status": "error"},
            events,
        )
        self.assertTrue(
            any(
                event.get("type") == "error"
                and "仅支持只读数据分析" in event.get("message", "")
                for event in events
            )
        )


if __name__ == "__main__":
    unittest.main()
