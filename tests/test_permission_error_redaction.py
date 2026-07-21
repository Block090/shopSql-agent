import unittest
from types import SimpleNamespace

from app.agent.nodes.reject_permission_denied import reject_permission_denied
from app.services.query_history_service import format_user_error_message


class PermissionErrorRedactionTest(unittest.IsolatedAsyncioTestCase):
    async def test_reject_permission_denied_hides_raw_permission_detail(self):
        events = []
        runtime = SimpleNamespace(context={}, stream_writer=events.append)

        await reject_permission_denied(
            {
                "permission_error": "permission denied: missing data scope condition for region_name"
            },
            runtime,
        )

        error_event = events[-1]
        self.assertEqual(error_event["type"], "error")
        self.assertEqual(error_event["error_type"], "permission_denied")
        self.assertEqual(error_event["message"], "权限校验未通过")
        self.assertNotIn("permission denied", error_event["message"])
        self.assertNotIn("region_name", error_event["message"])

    async def test_format_user_error_message_hides_permission_detail(self):
        message = format_user_error_message(
            RuntimeError("permission denied: sensitive column customer_phone")
        )

        self.assertEqual(message, "权限校验未通过")
        self.assertNotIn("customer_phone", message)


if __name__ == "__main__":
    unittest.main()
