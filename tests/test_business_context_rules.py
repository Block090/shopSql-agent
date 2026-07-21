from app.core.business_lexicon import (
    build_deterministic_metric_infos,
    get_required_column_ids,
    get_required_table_ids,
)


def test_required_tables_cover_product_region_date_metric_query():
    query = "查询华东地区 2025 年第一季度销售额最高的前 5 个商品"

    assert set(get_required_table_ids(query)) == {
        "dim_region",
        "dim_date",
        "fact_order",
        "dim_product",
    }


def test_required_columns_include_metric_dependencies():
    query = "查询 2025 年第一季度客单价最高的大区"

    assert set(get_required_column_ids(query)) >= {
        "fact_order.order_amount",
        "fact_order.order_id",
        "dim_region.region_name",
        "dim_date.quarter",
    }


def test_build_deterministic_metric_infos_includes_order_count_formula():
    metrics = build_deterministic_metric_infos("统计 2025 年第一季度华东地区的订单数")

    assert len(metrics) == 1
    assert metrics[0].name == "订单数"
    assert metrics[0].relevant_columns == ["fact_order.order_id"]
    assert "COUNT(DISTINCT fact_order.order_id)" in metrics[0].description
