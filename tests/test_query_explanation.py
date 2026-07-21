import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.query_explanation import (
    build_query_explanation,
    mask_sensitive_sql,
)


def test_mask_sensitive_sql_hides_internal_and_sensitive_identifiers():
    sql = (
        "SELECT user_id, phone, address, SUM(pay_amount) AS GMV "
        "FROM fact_order WHERE region_name = '华东' LIMIT 10"
    )

    masked = mask_sensitive_sql(sql)

    assert "phone" not in masked.lower()
    assert "address" not in masked.lower()
    assert "user_id" not in masked.lower()
    assert "fact_order" not in masked
    assert "支付金额" in masked
    assert "用户标识" in masked
    assert "敏感信息" in masked


def test_build_query_explanation_returns_business_and_masked_technical_layers():
    explanation = build_query_explanation(
        query="统计 2025 年第一季度各大区 GMV",
        resolved_query="统计 2025 年第一季度各大区 GMV",
        sql=(
            "SELECT region_name, SUM(pay_amount) AS GMV "
            "FROM fact_order WHERE order_date >= '2025-01-01' LIMIT 100"
        ),
        result_summary="返回 3 行，字段：region_name、GMV",
        result_analysis={
            "result_facts": {
                "dimension_columns": ["region_name"],
                "metric_columns": ["GMV"],
                "time_columns": ["order_date"],
            }
        },
        semantic_slots={
            "time_range": "2025 年第一季度",
            "dimension": "大区",
            "metrics": ["GMV"],
            "filters": {"order_status": "已支付"},
        },
    )

    assert explanation["business"]["metrics"] == ["GMV"]
    assert explanation["business"]["dimensions"] == ["大区"]
    assert explanation["business"]["time_range"] == "2025 年第一季度"
    assert explanation["business"]["filters"] == ["订单状态：已支付"]
    assert explanation["business"]["result_summary"] == "返回 3 行，字段：region_name、GMV"
    assert explanation["technical"]["sql"]
    assert "fact_order" not in explanation["technical"]["sql"]
    assert "region_name" not in explanation["technical"]["fields"]
    assert "大区" in explanation["technical"]["fields"]
    assert explanation["technical"]["visibility"] == "admin_masked"
    assert explanation["technical"]["sql_visible_to_user"] is False


def test_build_query_explanation_derives_time_range_from_date_id_sql_for_business_user():
    explanation = build_query_explanation(
        query="统计 2025 年第一季度各大区 GMV",
        resolved_query="统计 2025 年第一季度各大区 GMV",
        sql=(
            "SELECT region_name, SUM(order_amount) AS GMV FROM fact_order "
            "WHERE date_id BETWEEN 20250101 AND 20250331 "
            "GROUP BY region_name LIMIT 100"
        ),
        result_summary="返回 5 行，字段：大区、GMV",
        result_analysis={"result_facts": {"metric_columns": ["GMV"]}},
        semantic_slots={},
    )

    assert explanation["business"]["time_range"] == "2025-01-01 至 2025-03-31"
    assert explanation["business"]["filters"] == []
    assert explanation["technical"]["sql_visible_to_user"] is False


def test_build_query_explanation_uses_metric_description_as_business_definition():
    explanation = build_query_explanation(
        query="统计各大区 GMV",
        resolved_query="统计各大区 GMV",
        sql="SELECT region_name AS 大区, SUM(order_amount) AS GMV FROM fact_order LIMIT 100",
        result_summary="返回 5 行，字段：大区、GMV",
        result_analysis={"result_facts": {"metric_columns": ["GMV"]}},
        semantic_slots={},
        metric_infos=[
            {
                "name": "GMV",
                "description": "成交总额，按订单金额汇总",
                "relevant_columns": ["fact_order.order_amount"],
                "alias": ["成交额", "销售总额"],
            }
        ],
    )

    assert explanation["business"]["metrics"] == [
        "GMV：成交总额，按订单金额汇总"
    ]
