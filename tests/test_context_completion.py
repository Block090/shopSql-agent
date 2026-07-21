import asyncio

from app.agent.nodes.merge_retrieved_info import complete_required_column_context
from app.entities.column_info import ColumnInfo


class FakeMetaRepository:
    async def get_column_infos_by_ids(self, ids):
        fixtures = {
            "dim_product.product_name": ColumnInfo(
                id="dim_product.product_name",
                name="product_name",
                type="varchar",
                role="dimension",
                examples=[],
                description="商品名称",
                alias=["商品"],
                table_id="dim_product",
            ),
            "dim_region.region_name": ColumnInfo(
                id="dim_region.region_name",
                name="region_name",
                type="varchar",
                role="dimension",
                examples=[],
                description="大区",
                alias=["地区"],
                table_id="dim_region",
            ),
            "dim_date.quarter": ColumnInfo(
                id="dim_date.quarter",
                name="quarter",
                type="varchar",
                role="dimension",
                examples=[],
                description="季度",
                alias=["季度"],
                table_id="dim_date",
            ),
        }
        return [fixtures[column_id] for column_id in ids if column_id in fixtures]


def test_complete_required_column_context_adds_business_columns():
    column_map = {
        "fact_order.order_amount": ColumnInfo(
            id="fact_order.order_amount",
            name="order_amount",
            type="decimal",
            role="metric",
            examples=[],
            description="订单金额",
            alias=["销售额"],
            table_id="fact_order",
        )
    }

    asyncio.run(
        complete_required_column_context(
            query="查询华东地区 2025 年第一季度销售额最高的前 5 个商品",
            column_info_map=column_map,
            meta_mysql_repository=FakeMetaRepository(),
        )
    )

    assert "dim_product.product_name" in column_map
    assert "dim_region.region_name" in column_map
    assert "dim_date.quarter" in column_map
