import unittest

from app.agent.graph import route_after_check_domain_boundary
from app.agent.nodes.check_domain_boundary import check_domain_boundary


class _Runtime:
    def __init__(self):
        self.events = []

    def stream_writer(self, event):
        self.events.append(event)


class DomainBoundaryNodeTest(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_domain_is_rejected_before_rag(self):
        result = await check_domain_boundary(
            {"query": "查询直播间转化率最高的主播"}, _Runtime()
        )

        self.assertFalse(result["recall_decision"]["supported"])
        self.assertEqual(
            route_after_check_domain_boundary(result), "unable_to_answer"
        )

    async def test_supported_domain_continues_to_retrieval(self):
        result = await check_domain_boundary(
            {"query": "统计第一季度GMV"}, _Runtime()
        )

        self.assertEqual(route_after_check_domain_boundary(result), "extract_keywords")
