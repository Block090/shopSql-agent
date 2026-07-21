import unittest

from app.agent.graph import route_after_check_query_intent


class OperationRoutingTest(unittest.TestCase):
    def test_routes_operation_intent_to_operation_plan(self):
        route = route_after_check_query_intent(
            {"is_unsafe_intent": False, "operation_intent": True}
        )

        self.assertEqual(route, "generate_operation_plan")

    def test_routes_dangerous_intent_to_reject(self):
        route = route_after_check_query_intent(
            {"is_unsafe_intent": True, "operation_intent": False}
        )

        self.assertEqual(route, "reject_unsafe_intent")


if __name__ == "__main__":
    unittest.main()
