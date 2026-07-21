"""
结果正确性评测指标

用于判断 SQL 执行结果是否符合业务预期，包括返回字段、行数、关键值和排序。
"""

from typing import Any

RESULT_COLUMN_ALIASES = {
    "大区": ["大区", "地区", "区域", "region_name"],
    "省份": ["省份", "province"],
    "商品": ["商品", "商品名称", "product_name"],
    "品类": ["品类", "商品品类", "category"],
    "品牌": ["品牌", "brand"],
    "会员等级": ["会员等级", "member_level"],
    "月份": ["月份", "month"],
    "日期": ["日期", "date_id"],
    "GMV": ["GMV", "销售额", "成交金额"],
    "销售额": ["销售额", "GMV", "成交金额", "消费金额"],
    "订单数": ["订单数", "订单量", "order_count", "count"],
    "客单价": ["客单价", "AOV", "平均订单金额"],
}

_COLUMN_ALIAS_TO_CANONICAL = {
    alias.strip().lower(): canonical
    for canonical, aliases in RESULT_COLUMN_ALIASES.items()
    for alias in aliases
}


def evaluate_result(expected_result: dict[str, Any], trace: dict[str, Any]) -> dict:
    """评估单条 trace 的查询结果是否符合预期"""

    if not expected_result:
        return {
            "result_column_hit": True,
            "result_row_count_hit": True,
            "result_value_hit": True,
            "result_order_hit": True,
            "result_pass": True,
            "result_failure_reason": None,
        }

    actual_result = _extract_result(trace)
    actual_columns = actual_result["columns"]
    actual_rows = actual_result["rows"]

    column_hit = _contains_all_columns(actual_columns, expected_result.get("columns", []))
    row_count_hit = _matches_row_count(actual_rows, expected_result.get("row_count"))
    value_hit = _contains_expected_rows(actual_rows, expected_result.get("contains", []))
    order_hit = _matches_order(actual_rows, expected_result.get("order_by"))
    result_pass = column_hit and row_count_hit and value_hit and order_hit

    return {
        "result_column_hit": column_hit,
        "result_row_count_hit": row_count_hit,
        "result_value_hit": value_hit,
        "result_order_hit": order_hit,
        "result_pass": result_pass,
        "result_failure_reason": _build_failure_reason(
            column_hit, row_count_hit, value_hit, order_hit
        ),
    }


def _extract_result(trace: dict[str, Any]) -> dict[str, Any]:
    result = trace.get("result") or {}
    rows = result.get("rows") or trace.get("result_data") or []
    columns = result.get("columns") or _infer_columns(rows)
    return {"columns": columns, "rows": rows}


def _infer_columns(rows: list[Any]) -> list[str]:
    if rows and isinstance(rows[0], dict):
        return list(rows[0].keys())
    return []


def _contains_all_columns(actual_columns: list[str], expected_columns: list[str]) -> bool:
    if not expected_columns:
        return True
    actual_set = {_normalize_column(column) for column in actual_columns}
    return all(_normalize_column(column) in actual_set for column in expected_columns)


def _matches_row_count(actual_rows: list[Any], expected_row_count: Any) -> bool:
    if expected_row_count is None:
        return True
    if isinstance(expected_row_count, dict):
        mode = expected_row_count.get("mode", "exact")
        value = expected_row_count.get("value")
        if value is None:
            return True
        if mode == "max":
            return len(actual_rows) <= value
        if mode == "min":
            return len(actual_rows) >= value
        return len(actual_rows) == value
    return len(actual_rows) == expected_row_count


def _contains_expected_rows(
    actual_rows: list[Any], expected_rows: list[dict[str, Any]]
) -> bool:
    if not expected_rows:
        return True
    actual_dict_rows = [row for row in actual_rows if isinstance(row, dict)]
    return all(
        any(_row_contains(actual_row, expected_row) for actual_row in actual_dict_rows)
        for expected_row in expected_rows
    )


def _row_contains(actual_row: dict[str, Any], expected_row: dict[str, Any]) -> bool:
    normalized_actual = {
        _normalize_column(key): value for key, value in actual_row.items()
    }
    return all(
        _normalize_column(key) in normalized_actual
        and _same_value(normalized_actual[_normalize_column(key)], expected_value)
        for key, expected_value in expected_row.items()
    )


def _same_value(actual_value: Any, expected_value: Any) -> bool:
    if actual_value == expected_value:
        return True
    return str(actual_value) == str(expected_value)


def _matches_order(actual_rows: list[Any], order_by: dict[str, str] | None) -> bool:
    if not order_by:
        return True
    field = order_by.get("field")
    direction = (order_by.get("direction") or "asc").lower()
    if not field or len(actual_rows) <= 1:
        return True

    values = [
        _get_row_value_by_alias(row, field)
        for row in actual_rows
        if isinstance(row, dict) and _get_row_value_by_alias(row, field) is not None
    ]
    if len(values) <= 1:
        return True
    sorted_values = sorted(values, reverse=direction == "desc")
    return values == sorted_values


def _build_failure_reason(
    column_hit: bool, row_count_hit: bool, value_hit: bool, order_hit: bool
) -> str | None:
    if column_hit and row_count_hit and value_hit and order_hit:
        return None
    reasons = []
    if not column_hit:
        reasons.append("返回字段不符合预期")
    if not row_count_hit:
        reasons.append("返回行数不符合预期")
    if not value_hit:
        reasons.append("查询结果关键值不符合预期")
    if not order_hit:
        reasons.append("查询结果排序不符合预期")
    return "；".join(reasons)


def _normalize_column(column: object) -> str:
    text = str(column).strip()
    return _COLUMN_ALIAS_TO_CANONICAL.get(text.lower(), text)


def _get_row_value_by_alias(row: dict[str, Any], field: str) -> Any:
    normalized_field = _normalize_column(field)
    for key, value in row.items():
        if _normalize_column(key) == normalized_field:
            return value
    return None
