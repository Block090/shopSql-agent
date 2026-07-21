import unittest

from app.agent.graph import route_after_check_query_intent


class QueryIntentRoutingTest(unittest.TestCase):
    def test_routes_to_reject_unsafe_intent_for_delete_request(self):
        route = route_after_check_query_intent({"is_unsafe_intent": True})

        self.assertEqual(route, "reject_unsafe_intent")

    def test_routes_to_clarification_check_for_readonly_question(self):
        route = route_after_check_query_intent({"is_unsafe_intent": False})

        self.assertEqual(route, "check_clarification")


if __name__ == "__main__":
    unittest.main()
