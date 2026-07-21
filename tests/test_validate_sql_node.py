import unittest
from types import SimpleNamespace

from app.agent.nodes.validate_sql import validate_sql


class _Repository:
    def __init__(self):
        self.validated_sql = None

    async def validate(self, sql):
        self.validated_sql = sql


class ValidateSQLNodeTest(unittest.IsolatedAsyncioTestCase):
    async def test_node_deterministically_adds_limit_without_llm_retry(self):
        repository = _Repository()
        runtime = SimpleNamespace(
            context={"dw_mysql_repository": repository},
            stream_writer=lambda event: None,
        )

        result = await validate_sql(
            {"sql": "SELECT COUNT(*) AS 订单数 FROM fact_order"}, runtime
        )

        self.assertIsNone(result["error"])
        self.assertEqual(result["sql"], repository.validated_sql)
        self.assertTrue(result["sql"].endswith("LIMIT 1000"))
