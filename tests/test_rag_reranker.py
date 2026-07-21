import unittest

from app.core.rag_reranker import build_retrieval_query, rerank_recalled_context


class RagRerankerTest(unittest.TestCase):
    def test_builds_retrieval_query_from_semantic_slots(self):
        retrieval_query = build_retrieval_query(
            "统计 2025 年第一季度华东地区 GMV",
            {
                "time_range": "2025 年第一季度",
                "dimension": "大区",
                "metrics": ["GMV"],
                "filters": {"region": "华东"},
                "sort": {"field": "GMV", "direction": "desc"},
            },
        )

        self.assertIn("统计 2025 年第一季度华东地区 GMV", retrieval_query)
        self.assertIn("指标 GMV", retrieval_query)
        self.assertIn("维度 大区", retrieval_query)
        self.assertIn("过滤条件 region=华东", retrieval_query)
        self.assertIn("排序 GMV desc", retrieval_query)

    def test_reranks_candidates_by_business_slots(self):
        candidates = [
            {
                "name": "product_color",
                "description": "商品颜色",
                "alias": ["颜色"],
                "table": "dim_product",
            },
            {
                "name": "GMV",
                "description": "成交金额，按订单金额汇总",
                "alias": ["销售额"],
                "table": "fact_order",
            },
            {
                "name": "region_name",
                "description": "大区名称",
                "alias": ["大区", "地区"],
                "table": "dim_region",
            },
        ]

        ranked = rerank_recalled_context(
            candidates,
            {
                "dimension": "大区",
                "metrics": ["GMV"],
                "filters": {"region": "华东"},
            },
        )

        self.assertEqual(ranked[0]["name"], "GMV")
        self.assertGreater(ranked[0]["_rerank_score"], ranked[-1]["_rerank_score"])
        self.assertEqual(ranked[-1]["name"], "product_color")

    def test_exact_business_term_is_prioritized_and_top_k_is_enforced(self):
        candidates = [
            {"id": f"other.{index}", "name": f"other_{index}", "alias": []}
            for index in range(8)
        ]
        candidates.append(
            {
                "id": "dim_product.category",
                "name": "category",
                "alias": ["品类", "类目"],
            }
        )

        ranked = rerank_recalled_context(
            candidates,
            semantic_slots={},
            query_text="按品类统计销售额",
            limit=5,
        )

        self.assertEqual(len(ranked), 5)
        self.assertEqual(ranked[0]["id"], "dim_product.category")


if __name__ == "__main__":
    unittest.main()
