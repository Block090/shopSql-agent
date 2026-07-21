import unittest

from app.agent.nodes.ask_clarification import ask_clarification
from app.agent.nodes.check_clarification import check_clarification


class FakeRuntime:
    def __init__(self):
        self.events = []

    def stream_writer(self, event):
        self.events.append(event)


class ClarificationNodesTest(unittest.IsolatedAsyncioTestCase):
    async def test_check_clarification_marks_ambiguous_query(self):
        runtime = FakeRuntime()

        result = await check_clarification(
            {"query": "哪些商品卖得最好"},
            runtime,
        )

        self.assertTrue(result["clarification_required"])
        self.assertEqual(result["clarification_type"], "best_selling_product")
        self.assertEqual(result["clarification_options"], ["按销量", "按销售额"])
        self.assertEqual(result["clarification_missing_slots"], ["metric"])

    async def test_ask_clarification_streams_event_without_sql(self):
        runtime = FakeRuntime()

        await ask_clarification(
            {
                "clarification_question": "你想按哪个口径判断商品卖得最好？",
                "clarification_options": ["按销量", "按销售额"],
                "clarification_type": "best_selling_product",
                "clarification_missing_slots": ["metric"],
            },
            runtime,
        )

        self.assertEqual(runtime.events[0]["type"], "progress")
        self.assertEqual(runtime.events[1]["type"], "clarification")
        self.assertEqual(runtime.events[1]["options"], ["按销量", "按销售额"])
        self.assertEqual(runtime.events[1]["missing_slots"], ["metric"])


if __name__ == "__main__":
    unittest.main()
