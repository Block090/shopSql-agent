import unittest

from app.agent.graph import route_after_check_recall_result


class RecallResultRoutingTest(unittest.TestCase):
    def test_routes_to_add_extra_context_when_table_infos_exist(self):
        route = route_after_check_recall_result(
            {"table_infos": [{"name": "fact_order", "role": "fact"}]}
        )

        self.assertEqual(route, "add_extra_context")

    def test_routes_to_unable_to_answer_without_fact_table(self):
        route = route_after_check_recall_result(
            {
                "table_infos": [
                    {
                        "name": "dim_region",
                        "role": "dim",
                        "columns": [{"name": "region_name", "role": "dimension"}],
                    }
                ],
                "metric_infos": [],
            }
        )

        self.assertEqual(route, "unable_to_answer")

    def test_routes_to_unable_to_answer_when_table_infos_empty(self):
        route = route_after_check_recall_result({"table_infos": []})

        self.assertEqual(route, "unable_to_answer")

    def test_routes_to_unable_to_answer_when_domain_coverage_fails(self):
        route = route_after_check_recall_result(
            {
                "table_infos": [{"name": "fact_order", "role": "fact"}],
                "recall_decision": {"supported": False},
            }
        )

        self.assertEqual(route, "unable_to_answer")


if __name__ == "__main__":
    unittest.main()
