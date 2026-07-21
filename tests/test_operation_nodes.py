import unittest

from app.agent.nodes.check_query_intent import check_query_intent
from app.agent.nodes.estimate_operation_impact import estimate_operation_impact
from app.agent.nodes.generate_operation_plan import generate_operation_plan
from app.agent.nodes.return_operation_plan import return_operation_plan


class FakeRuntime:
    def __init__(self, repository=None):
        self.events = []
        self.context = type("Context", (), {"dw_mysql_repository": repository})()

    def stream_writer(self, event):
        self.events.append(event)


class FakeDictRuntime:
    def __init__(self, repository=None):
        self.events = []
        self.context = {"dw_mysql_repository": repository}

    def stream_writer(self, event):
        self.events.append(event)


class FakeDWRepository:
    async def run(self, sql):
        if "COUNT" in sql.upper():
            return [{"impact_count": 12}]
        return [{"order_id": "ORD20250301001", "date_id": 20250301}]


class OperationNodesTest(unittest.IsolatedAsyncioTestCase):
    async def test_check_query_intent_routes_delete_to_operation_branch(self):
        result = await check_query_intent(
            {"query": "删除 2025 年 3 月的测试订单"},
            FakeRuntime(),
        )

        self.assertTrue(result["operation_intent"])
        self.assertEqual(result["operation_type"], "DELETE")
        self.assertFalse(result["is_unsafe_intent"])

    async def test_generate_and_return_operation_plan_event(self):
        runtime = FakeRuntime(FakeDWRepository())
        state = {
            "query": "删除 2025 年 3 月的测试订单",
            "operation_type": "DELETE",
        }

        state.update(await generate_operation_plan(state, runtime))
        state.update(await estimate_operation_impact(state, runtime))
        await return_operation_plan(state, runtime)

        event = runtime.events[-1]
        self.assertEqual(event["type"], "operation_plan")
        self.assertEqual(event["data"]["operation_type"], "DELETE")
        self.assertEqual(event["data"]["impact_count"], 12)
        self.assertEqual(event["data"]["status"], "pending")
        self.assertEqual(event["data"]["approval_status"], "pending")
        self.assertEqual(event["data"]["execution_status"], "not_executed")
        self.assertFalse(event["data"]["execution_enabled"])

    async def test_estimate_operation_impact_supports_dict_context(self):
        runtime = FakeDictRuntime(FakeDWRepository())
        state = {
            "operation_plan": {
                "impact_count_sql": "SELECT COUNT(*) AS impact_count FROM fact_order LIMIT 1",
                "impact_preview_sql": "SELECT * FROM fact_order LIMIT 20",
            }
        }

        result = await estimate_operation_impact(state, runtime)

        self.assertEqual(result["impact_count"], 12)
        self.assertEqual(result["impact_preview_rows"][0]["order_id"], "ORD20250301001")


if __name__ == "__main__":
    unittest.main()
