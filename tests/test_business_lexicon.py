from app.core.business_lexicon import (
    expand_business_terms,
    get_lexicon_version,
    get_matched_column_ids,
    get_matched_metric_ids,
    get_unsupported_concepts,
)


def test_business_lexicon_maps_common_ecommerce_terms():
    query = "按品类统计黄金会员每天的订单量"

    assert "订单数" in expand_business_terms(query)
    assert "fact_order.order_id" in get_matched_column_ids(query)
    assert "dim_product.category" in get_matched_column_ids(query)
    assert "dim_customer.member_level" in get_matched_column_ids(query)
    assert "dim_date.date_id" in get_matched_column_ids(query)
    assert get_matched_metric_ids(query) == ["订单数"]
    assert get_lexicon_version()


def test_business_lexicon_identifies_unsupported_domain_concepts():
    concepts = get_unsupported_concepts("查询抖音直播间转化率最高的主播")

    assert "主播" in concepts
    assert "直播转化率" in concepts
