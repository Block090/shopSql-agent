"""
业务口径澄清规则

第一版采用规则优先的方式处理高频、风险明确的模糊问法。
这些规则不是替代 Agent，而是给企业级关键口径提供稳定兜底。
"""

from typing import Any

BEST_SELLING_TERMS = [
    "卖得最好",
    "卖得好",
    "销售最好",
    "最受欢迎",
    "热门商品",
    "爆款商品",
]

BEST_SELLING_EXPLICIT_TERMS = [
    "按销量",
    "销量最高",
    "总销量",
    "销售数量",
    "按销售额",
    "销售额最高",
    "总销售额",
    "成交额",
    "GMV",
    "gmv",
]

RECENT_TERMS = ["最近", "近期"]

RECENT_EXPLICIT_TERMS = [
    "最近7天",
    "最近 7 天",
    "近7天",
    "近 7 天",
    "最近30天",
    "最近 30 天",
    "近30天",
    "近 30 天",
    "本月",
    "这个月",
]

GROWTH_TERMS = ["增长最快", "增长最高", "涨得最快"]

GROWTH_EXPLICIT_TERMS = ["同比", "环比"]

PERFORMANCE_TERMS = ["销售表现", "经营表现", "表现如何", "表现怎么样"]


def check_clarification_need(query: str) -> dict[str, Any]:
    """判断用户问题是否需要先确认业务口径"""

    normalized_query = _normalize_query(query)

    # “卖得最好”在企业问数里通常有销量和销售额两种口径，未说明时必须追问。
    if _contains_any(normalized_query, BEST_SELLING_TERMS) and not _contains_any(
        normalized_query, BEST_SELLING_EXPLICIT_TERMS
    ):
        return {
            "required": True,
            "type": "best_selling_product",
            "question": "你想按哪个口径判断商品卖得最好？",
            "options": ["按销量", "按销售额"],
            "missing_slots": ["metric"],
        }

    # “最近”没有明确时间窗口时，直接生成 SQL 容易产生隐含假设。
    if _contains_any(normalized_query, RECENT_TERMS) and not _contains_any(
        normalized_query, RECENT_EXPLICIT_TERMS
    ):
        return {
            "required": True,
            "type": "recent_time_range",
            "question": "你说的最近是指哪个时间范围？",
            "options": ["最近7天", "最近30天", "本月"],
            "missing_slots": ["time_range"],
        }

    # “增长最快”需要确认同比或环比，否则业务口径不完整。
    if _contains_any(normalized_query, GROWTH_TERMS) and not _contains_any(
        normalized_query, GROWTH_EXPLICIT_TERMS
    ):
        return {
            "required": True,
            "type": "growth_basis",
            "question": "你想按同比增长还是环比增长判断？",
            "options": ["同比", "环比"],
            "missing_slots": ["comparison_basis"],
        }

    if _contains_any(normalized_query, PERFORMANCE_TERMS) and not _contains_any(
        normalized_query, BEST_SELLING_EXPLICIT_TERMS + ["订单数", "客单价", "AOV"]
    ):
        return {
            "required": True,
            "type": "metric_selection",
            "question": "你想用哪个指标分析销售表现？",
            "options": ["按销量", "按销售额", "按订单数"],
            "missing_slots": ["metric"],
        }

    return {
        "required": False,
        "type": "",
        "question": "",
        "options": [],
        "missing_slots": [],
    }


def _normalize_query(query: str) -> str:
    """去掉空白，降低中英文空格差异对规则判断的影响"""

    return "".join((query or "").split())


def _contains_any(query: str, terms: list[str]) -> bool:
    """判断问题是否包含任意业务表达"""

    normalized_terms = [_normalize_query(term) for term in terms]
    return any(term in query for term in normalized_terms)
