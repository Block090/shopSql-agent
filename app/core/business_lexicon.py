"""确定性业务词典，用于补充向量召回并声明数据域边界。"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.entities.metric_info import MetricInfo

DEFAULT_LEXICON_PATH = Path(__file__).parents[2] / "conf" / "business_lexicon.yaml"

DETERMINISTIC_METRIC_INFOS = {
    "订单数": MetricInfo(
        id="订单数",
        name="订单数",
        description="订单数，按订单ID去重计数，计算口径为 COUNT(DISTINCT fact_order.order_id)。",
        relevant_columns=["fact_order.order_id"],
        alias=["订单量", "订单数量", "下单数", "成交订单数"],
    ),
    "GMV": MetricInfo(
        id="GMV",
        name="GMV",
        description="GMV，成交总额，计算口径为 SUM(fact_order.order_amount)。",
        relevant_columns=["fact_order.order_amount"],
        alias=["成交总额", "订单总额", "销售额", "消费金额"],
    ),
    "销量": MetricInfo(
        id="销量",
        name="销量",
        description="销量，按订单商品数量汇总，计算口径为 SUM(fact_order.order_quantity)。",
        relevant_columns=["fact_order.order_quantity"],
        alias=["销售数量", "购买数量", "件数", "总销量"],
    ),
    "AOV": MetricInfo(
        id="AOV",
        name="AOV",
        description="客单价，平均订单金额，计算口径为 SUM(fact_order.order_amount) / COUNT(DISTINCT fact_order.order_id)。",
        relevant_columns=["fact_order.order_amount", "fact_order.order_id"],
        alias=["客单价", "平均订单金额", "平均客单价"],
    ),
}


@lru_cache(maxsize=1)
def load_business_lexicon() -> dict[str, Any]:
    return yaml.safe_load(DEFAULT_LEXICON_PATH.read_text(encoding="utf-8")) or {}


def get_lexicon_version() -> str:
    return str(load_business_lexicon().get("version", "unknown"))


def expand_business_terms(query: str, keywords: list[str] | None = None) -> list[str]:
    """把用户命中的业务表达扩展为标准名、字段 id 和同义词。"""

    expanded = list(keywords or [])
    lexicon = load_business_lexicon()
    for section in ("metrics", "columns"):
        for canonical, config in lexicon.get(section, {}).items():
            terms = [str(term) for term in config.get("terms", [])]
            if _matches(query, terms):
                expanded.extend([canonical, *terms])
    return _deduplicate(expanded)


def get_matched_column_ids(query: str) -> list[str]:
    return _matched_keys(query, "columns")


def get_matched_metric_ids(query: str) -> list[str]:
    return _matched_keys(query, "metrics")


def build_deterministic_metric_infos(query: str) -> list[MetricInfo]:
    """Return built-in metric definitions for high-frequency deterministic metrics."""

    return [
        DETERMINISTIC_METRIC_INFOS[metric_id]
        for metric_id in get_matched_metric_ids(query)
        if metric_id in DETERMINISTIC_METRIC_INFOS
    ]


def build_deterministic_metric_states(query: str) -> list[dict[str, Any]]:
    """Return SQL-prompt-ready metric context for deterministic metrics."""

    return [
        {
            "name": metric.name,
            "description": metric.description,
            "relevant_columns": metric.relevant_columns,
            "alias": metric.alias,
        }
        for metric in build_deterministic_metric_infos(query)
    ]


def get_required_table_ids(query: str) -> list[str]:
    """Infer required physical tables from deterministic business terms."""

    table_ids = [_table_id(column_id) for column_id in get_required_column_ids(query)]
    normalized_query = _normalize(query)
    if any(term in normalized_query for term in ("gmv", "销售额", "成交总额", "订单数", "客单价", "销量")):
        table_ids.append("fact_order")
    if any(term in normalized_query for term in ("商品", "品类", "品牌", "产品")):
        table_ids.append("dim_product")
    if any(term in normalized_query for term in ("地区", "大区", "省份", "华东", "华北", "华南")):
        table_ids.append("dim_region")
    if any(term in normalized_query for term in ("年", "月", "季度", "第一季度", "每天", "每日", "趋势")):
        table_ids.append("dim_date")
    if any(term in normalized_query for term in ("会员", "客户", "性别", "女性", "男性")):
        table_ids.append("dim_customer")
    return _deduplicate([table_id for table_id in table_ids if table_id])


def get_required_column_ids(query: str) -> list[str]:
    """Infer required physical columns from business terms and metric formulas."""

    column_ids = list(get_matched_column_ids(query))
    for metric_id in get_matched_metric_ids(query):
        normalized_metric = _normalize(metric_id)
        if metric_id == "GMV":
            column_ids.append("fact_order.order_amount")
        elif metric_id == "AOV":
            column_ids.extend(["fact_order.order_amount", "fact_order.order_id"])
        elif metric_id == "销量":
            column_ids.append("fact_order.order_quantity")
        elif "订单" in normalized_metric:
            column_ids.append("fact_order.order_id")
    return _deduplicate(column_ids)


def get_unsupported_concepts(query: str) -> list[str]:
    return _matched_keys(query, "unsupported_concepts")


def _matched_keys(query: str, section: str) -> list[str]:
    matched = []
    for canonical, config in load_business_lexicon().get(section, {}).items():
        if _matches(query, config.get("terms", [])):
            matched.append(str(canonical))
    return matched


def _matches(query: str, terms: list[str]) -> bool:
    normalized_query = _normalize(query)
    return any(_normalize(term) in normalized_query for term in terms)


def _normalize(value: object) -> str:
    return "".join(str(value or "").lower().split())


def _table_id(column_id: str) -> str:
    return column_id.split(".", 1)[0] if "." in column_id else ""


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value).strip()))
