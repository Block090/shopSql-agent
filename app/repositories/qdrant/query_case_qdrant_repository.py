"""历史成功 Query Case 向量仓储。"""

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.conf.app_config import app_config


class QueryCaseQdrantRepository:
    """保存和召回历史成功查询案例。"""

    collection_name = "query_case_collection"

    def __init__(self, client: AsyncQdrantClient):
        self.client = client

    async def ensure_collection(self):
        """确保 Query Case 向量集合存在。"""

        if not await self.client.collection_exists(self.collection_name):
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=app_config.qdrant.embedding_size,
                    distance=Distance.COSINE,
                ),
            )

    async def upsert_query_case(
        self,
        query_case: dict,
        vector: list[float],
    ) -> None:
        """写入一个成功查询案例。"""

        await self.ensure_collection()
        await self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=query_case["case_id"],
                    vector=vector,
                    payload=query_case,
                )
            ],
        )

    async def search_query_cases(
        self,
        vector: list[float],
        limit: int = 3,
        score_threshold: float = 0.55,
    ) -> list[dict]:
        """召回相似历史成功查询案例。"""

        await self.ensure_collection()
        result = await self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=limit,
            score_threshold=score_threshold,
        )
        return [dict(point.payload or {}) for point in result.points]
