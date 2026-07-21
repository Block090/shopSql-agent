import asyncio
import unittest

from app.core.async_timeout import run_with_timeout


class AsyncTimeoutTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_with_timeout_returns_default_when_awaitable_is_too_slow(self):
        async def never_finishes():
            await asyncio.sleep(60)
            return ["late"]

        result = await run_with_timeout(
            never_finishes(),
            timeout_seconds=0.01,
            default=["fallback"],
            operation_name="slow-test",
        )

        self.assertEqual(["fallback"], result)

    async def test_run_with_timeout_returns_result_when_awaitable_finishes(self):
        async def finishes():
            return ["ok"]

        result = await run_with_timeout(
            finishes(),
            timeout_seconds=1,
            default=["fallback"],
            operation_name="fast-test",
        )

        self.assertEqual(["ok"], result)
