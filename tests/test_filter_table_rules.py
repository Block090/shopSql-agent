from app.agent.nodes.filter_table import apply_required_table_context


def test_apply_required_table_context_keeps_required_columns_after_llm_filter():
    table_infos = [
        {
            "name": "fact_order",
            "role": "fact",
            "description": "订单事实表",
            "columns": [
                {"name": "order_amount"},
                {"name": "product_id"},
                {"name": "region_id"},
                {"name": "date_id"},
            ],
        },
        {
            "name": "dim_product",
            "role": "dim",
            "description": "商品维表",
            "columns": [{"name": "product_name"}, {"name": "category"}],
        },
        {
            "name": "dim_region",
            "role": "dim",
            "description": "地区维表",
            "columns": [{"name": "region_name"}],
        },
        {
            "name": "dim_date",
            "role": "dim",
            "description": "日期维表",
            "columns": [{"name": "quarter"}],
        },
    ]

    filtered = apply_required_table_context(
        query="查询华东地区 2025 年第一季度销售额最高的前 5 个商品",
        table_infos=table_infos,
        selected_columns={"fact_order": ["order_amount"]},
    )

    table_names = {table["name"] for table in filtered}
    assert {"fact_order", "dim_product", "dim_region", "dim_date"} <= table_names
    assert _column_names(filtered, "dim_product") == {"product_name"}
    assert _column_names(filtered, "dim_region") == {"region_name"}
    assert _column_names(filtered, "dim_date") == {"quarter"}


def _column_names(table_infos, table_name):
    for table_info in table_infos:
        if table_info["name"] == table_name:
            return {column["name"] for column in table_info["columns"]}
    return set()
