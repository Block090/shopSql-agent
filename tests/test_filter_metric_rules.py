from app.agent.nodes.filter_metric import (
    apply_required_metric_context,
    should_use_rule_only_metric_filter,
)


def test_apply_required_metric_context_keeps_matched_metrics_after_llm_filter():
    metric_infos = [
        {"name": "GMV", "description": "成交总额", "relevant_columns": [], "alias": []},
        {"name": "订单数", "description": "订单数量", "relevant_columns": [], "alias": []},
    ]

    filtered = apply_required_metric_context(
        query="按会员等级统计 2025 年第一季度的订单数和销售额",
        metric_infos=metric_infos,
        selected_metric_names=["GMV"],
    )

    assert {metric["name"] for metric in filtered} == {"GMV", "订单数"}


def test_apply_required_metric_context_synthesizes_missing_order_count_metric():
    filtered = apply_required_metric_context(
        query="统计 2025 年第一季度各大区订单数，并按订单数从高到低排序",
        metric_infos=[],
        selected_metric_names=[],
    )

    assert filtered == [
        {
            "name": "订单数",
            "description": "订单数，按订单ID去重计数，计算口径为 COUNT(DISTINCT fact_order.order_id)。",
            "relevant_columns": ["fact_order.order_id"],
            "alias": ["订单量", "订单数量", "下单数", "成交订单数"],
        }
    ]


def test_apply_required_metric_context_synthesizes_sales_quantity_and_gmv_metrics():
    filtered = apply_required_metric_context(
        query="统计 2025 年 4 月各商品品类的销量和销售额",
        metric_infos=[],
        selected_metric_names=[],
    )

    assert {metric["name"] for metric in filtered} == {"销量", "GMV"}
    quantity_metric = next(metric for metric in filtered if metric["name"] == "销量")
    assert quantity_metric["relevant_columns"] == ["fact_order.order_quantity"]


def test_should_use_rule_only_metric_filter_for_explicit_business_metric():
    assert should_use_rule_only_metric_filter("统计 2025 年第一季度订单数") is True
    assert should_use_rule_only_metric_filter("哪些商品卖得最好") is False
