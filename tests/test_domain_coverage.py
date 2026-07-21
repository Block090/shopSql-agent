from app.core.domain_coverage import evaluate_domain_coverage


def test_domain_coverage_rejects_explicit_unsupported_concepts():
    decision = evaluate_domain_coverage(
        query="查询抖音直播间转化率最高的主播",
        table_infos=[{"name": "fact_order", "role": "fact", "columns": []}],
        metric_infos=[],
    )

    assert decision["supported"] is False
    assert decision["reason"] == "unsupported_domain_concept"
    assert "主播" in decision["missing_concepts"]


def test_domain_coverage_allows_deterministic_order_count_when_column_exists():
    decision = evaluate_domain_coverage(
        query="统计第一季度订单数",
        table_infos=[
            {
                "name": "fact_order",
                "role": "fact",
                "columns": [{"name": "order_id"}],
            },
            {
                "name": "dim_date",
                "role": "dim",
                "columns": [{"name": "quarter"}],
            },
        ],
        metric_infos=[],
    )

    assert decision["supported"] is True
    assert decision["reason"] == "covered"
    assert decision["missing_concepts"] == []


def test_domain_coverage_requires_order_count_column_for_deterministic_metric():
    decision = evaluate_domain_coverage(
        query="统计第一季度订单数",
        table_infos=[
            {
                "name": "fact_order",
                "role": "fact",
                "columns": [{"name": "date_id"}],
            },
            {
                "name": "dim_date",
                "role": "dim",
                "columns": [{"name": "quarter"}],
            },
        ],
        metric_infos=[],
    )

    assert decision["supported"] is False
    assert decision["reason"] == "missing_column_context"
    assert decision["missing_concepts"] == ["fact_order.order_id"]


def test_domain_coverage_accepts_supported_metric_and_dimension():
    decision = evaluate_domain_coverage(
        query="按品类统计订单数",
        table_infos=[
            {
                "name": "fact_order",
                "role": "fact",
                "columns": [{"name": "order_id"}],
            },
            {
                "name": "dim_product",
                "role": "dim",
                "columns": [{"name": "category"}],
            },
        ],
        metric_infos=[{"name": "订单数"}],
    )

    assert decision["supported"] is True
    assert decision["missing_concepts"] == []
