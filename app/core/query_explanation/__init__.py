"""查询依据说明。

面向业务用户返回指标口径、维度、时间范围和过滤条件；面向技术用户返回脱敏后的
SQL 和字段说明，避免直接暴露底层表结构和敏感字段。
"""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_FIELD_ALIASES = {
    "phone": "敏感信息",
    "mobile": "敏感信息",
    "address": "敏感信息",
    "id_card": "敏感信息",
    "user_id": "用户标识",
    "member_id": "会员标识",
}

BUSINESS_FIELD_ALIASES = {
    "region_name": "大区",
    "region_code": "大区编码",
    "category_name": "商品品类",
    "category_id": "商品品类标识",
    "order_date": "订单日期",
    "order_status": "订单状态",
    "pay_amount": "支付金额",
    "order_amount": "订单金额",
    "gmv": "GMV",
}

INTERNAL_TABLE_PATTERN = re.compile(r"\b(?:fact|dim|dwd|dws|ads)_[a-zA-Z0-9_]+\b")


def mask_sensitive_sql(sql: str | None) -> str:
    """隐藏技术 SQL 中的敏感字段和内部表名。"""

    if not sql:
        return ""

    masked = sql
    for field, alias in {**BUSINESS_FIELD_ALIASES, **SENSITIVE_FIELD_ALIASES}.items():
        masked = re.sub(rf"\b{re.escape(field)}\b", alias, masked, flags=re.IGNORECASE)
    return INTERNAL_TABLE_PATTERN.sub("业务数据表", masked)


def build_query_explanation(
    *,
    query: str,
    resolved_query: str,
    sql: str | None,
    result_summary: str | None,
    result_analysis: dict[str, Any] | None = None,
    semantic_slots: dict[str, Any] | None = None,
    metric_infos: list[dict[str, Any]] | None = None,
    risk: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成分层查询依据说明。"""

    semantic_slots = semantic_slots or {}
    result_facts = (result_analysis or {}).get("result_facts") or {}

    metrics = _list_or_empty(semantic_slots.get("metrics")) or _list_or_empty(
        result_facts.get("metric_columns")
    )
    dimensions = _list_or_empty([semantic_slots.get("dimension")]) or _list_or_empty(
        result_facts.get("dimension_columns")
    )
    time_range = (
        semantic_slots.get("time_range")
        or _extract_date_range_from_sql(sql)
        or _join_business_fields(result_facts.get("time_columns"))
    )

    fields = _unique(
        _list_or_empty(result_facts.get("dimension_columns"))
        + _list_or_empty(result_facts.get("metric_columns"))
        + _list_or_empty(result_facts.get("time_columns"))
    )

    return {
        "business": {
            "question": query,
            "resolved_question": resolved_query,
            "metrics": _format_metric_definitions(metrics, metric_infos),
            "dimensions": [_business_name(item) for item in dimensions],
            "time_range": time_range or "未限定",
            "filters": _format_filters(semantic_slots.get("filters")),
            "result_summary": result_summary,
        },
        "technical": {
            "visibility": "admin_masked",
            "sql_visible_to_user": False,
            "sql": mask_sensitive_sql(sql),
            "fields": [_business_name(field) for field in fields],
        },
        "risk": risk,
    }


def _business_name(value: Any) -> str:
    text = str(value)
    lower = text.lower()
    return SENSITIVE_FIELD_ALIASES.get(lower) or BUSINESS_FIELD_ALIASES.get(lower) or text


def _format_filters(filters: Any) -> list[str]:
    if not isinstance(filters, dict):
        return []

    formatted = []
    for key, value in filters.items():
        if value in (None, "", [], {}):
            continue
        formatted.append(f"{_business_name(key)}：{_business_name(value)}")
    return formatted


def _format_metric_definitions(
    metrics: list[Any], metric_infos: list[dict[str, Any]] | None
) -> list[str]:
    metric_info_map = {
        str(metric_info.get("name")): metric_info
        for metric_info in (metric_infos or [])
        if metric_info.get("name")
    }

    formatted = []
    for metric in metrics:
        name = _business_name(metric)
        metric_info = metric_info_map.get(str(metric)) or metric_info_map.get(name)
        description = (metric_info or {}).get("description")
        if description:
            formatted.append(f"{name}：{description}")
        else:
            formatted.append(name)
    return formatted


def _join_business_fields(values: Any) -> str:
    return "、".join(_business_name(value) for value in _list_or_empty(values))


def _list_or_empty(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]
    return [value] if value != "" else []


def _unique(values: list[Any]) -> list[Any]:
    seen = set()
    result = []
    for value in values:
        key = str(value)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _extract_date_range_from_sql(sql: str | None) -> str | None:
    if not sql:
        return None

    match = re.search(
        r"\bdate_id\b\s+between\s+(\d{8})\s+and\s+(\d{8})",
        sql,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    return f"{_format_yyyymmdd(match.group(1))} 至 {_format_yyyymmdd(match.group(2))}"


def _format_yyyymmdd(value: str) -> str:
    return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
