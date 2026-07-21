import unittest

from app.agent.graph import (
    MAX_SQL_RETRY_COUNT,
    route_after_validate_sql,
    route_after_validate_sql_permission,
)


class SQLRetryRoutingTest(unittest.TestCase):
    def test_routes_to_permission_validation_when_sql_validation_passes(self):
        route = route_after_validate_sql({"error": None})

        self.assertEqual(route, "validate_sql_permission")

    def test_limit_error_does_not_trigger_llm_correction(self):
        route = route_after_validate_sql(
            {"error": "查询必须包含 LIMIT 限制", "retry_count": 2}
        )

        self.assertEqual(route, "fail_sql")

    def test_database_syntax_error_routes_to_llm_correction(self):
        route = route_after_validate_sql(
            {"error": "You have an error in your SQL syntax", "retry_count": 0}
        )

        self.assertEqual(route, "correct_sql")

    def test_routes_to_fail_sql_after_three_retries(self):
        route = route_after_validate_sql(
            {
                "error": "查询必须包含 LIMIT 限制",
                "retry_count": MAX_SQL_RETRY_COUNT,
            }
        )

        self.assertEqual(route, "fail_sql")

    def test_routes_to_run_sql_when_permission_validation_passes(self):
        route = route_after_validate_sql_permission({"permission_error": None})

        self.assertEqual(route, "run_sql")

    def test_routes_to_permission_denied_when_permission_validation_fails(self):
        route = route_after_validate_sql_permission(
            {"permission_error": "permission denied"}
        )

        self.assertEqual(route, "reject_permission_denied")


if __name__ == "__main__":
    unittest.main()
