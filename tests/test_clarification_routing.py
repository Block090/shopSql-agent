import unittest

from app.agent.graph import (
    route_after_check_clarification,
    route_after_check_query_intent,
)


class ClarificationRoutingTest(unittest.TestCase):
    def test_query_intent_routes_safe_query_to_clarification_check(self):
        route = route_after_check_query_intent({"is_unsafe_intent": False})

        self.assertEqual(route, "check_clarification")

    def test_query_intent_still_routes_unsafe_query_to_reject(self):
        route = route_after_check_query_intent({"is_unsafe_intent": True})

        self.assertEqual(route, "reject_unsafe_intent")

    def test_clarification_routes_ambiguous_query_to_ask_clarification(self):
        route = route_after_check_clarification({"clarification_required": True})

        self.assertEqual(route, "ask_clarification")

    def test_clarification_routes_clear_query_to_extract_keywords(self):
        route = route_after_check_clarification({"clarification_required": False})

        self.assertEqual(route, "check_domain_boundary")


if __name__ == "__main__":
    unittest.main()
