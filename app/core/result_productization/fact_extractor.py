"""从 SQL 结果中提取可校验的结构化事实。"""

from __future__ import annotations

import re
from collections.abc import Iterable
from numbers import Number

DIMENSION_KEYWORDS = ("品类", "商品", "地区", "大区", "会员", "客户", "名称", "类目", "主播")
METRIC_KEYWORDS = ("GMV", "销售额", "销量", "订单数", "金额", "数量", "转化率", "客单价")
TIME_KEYWORDS = ("日期", "时间", "月份", "季度", "年份", "date", "time")


def extract_result_facts(result_data) -> dict:
    """根据查询结果生成事实摘要，供 LLM 和前端共同消费。"""

    rows = _normalize_rows(result_data)
    columns = _collect_columns(rows)
    row_count = len(rows)

    dimension_columns: list[str] = []
    metric_columns: list[str] = []
    time_columns: list[str] = []

    for column in columns:
        values = [row.get(column) for row in rows if row.get(column) is not None]
        if _is_time_column(column, values):
            time_columns.append(column)
            continue
        if _is_metric_column(column, values):
            metric_columns.append(column)
        else:
            dimension_columns.append(column)

    label_column = time_columns[0] if time_columns else (dimension_columns[0] if dimension_columns else None)
    top_values = _build_top_values(rows, metric_columns, label_column)
    chart_candidates = _build_chart_candidates(time_columns, dimension_columns, metric_columns)

    return {
        "row_count": row_count,
        "columns": columns,
        "dimension_columns": dimension_columns,
        "metric_columns": metric_columns,
        "time_columns": time_columns,
        "top_values": top_values,
        "chart_candidates": chart_candidates,
    }


def _normalize_rows(result_data) -> list[dict]:
    if isinstance(result_data, list):
        return [row for row in result_data if isinstance(row, dict)]
    if isinstance(result_data, dict):
        return [result_data]
    return []


def _collect_columns(rows: Iterable[dict]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in columns:
                columns.append(key)
    return columns


def _is_metric_column(column: str, values: list) -> bool:
    if any(keyword.lower() in column.lower() for keyword in METRIC_KEYWORDS):
        return True
    if not values:
        return False
    return all(_is_number(value) for value in values)


def _is_time_column(column: str, values: list) -> bool:
    if any(keyword.lower() in column.lower() for keyword in TIME_KEYWORDS):
        return True
    if not values:
        return False
    return all(_looks_like_date(value) for value in values)


def _is_number(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, Number):
        return True
    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        return bool(normalized) and re.fullmatch(r"-?\d+(\.\d+)?", normalized) is not None
    return False


def _looks_like_date(value) -> bool:
    if isinstance(value, int):
        text = str(value)
        return len(text) == 8 and text.isdigit()
    if isinstance(value, str):
        text = value.strip()
        return bool(
            re.fullmatch(r"\d{4}-\d{2}-\d{2}", text)
            or re.fullmatch(r"\d{8}", text)
            or re.fullmatch(r"\d{4}年\d{1,2}月(\d{1,2}日)?", text)
        )
    return False


def _build_top_values(rows: list[dict], metric_columns: list[str], label_column: str | None) -> dict:
    top_values: dict[str, dict] = {}
    if not rows or not label_column:
        return top_values

    for metric in metric_columns:
        ranked = [row for row in rows if _is_number(row.get(metric))]
        if not ranked:
            continue
        top_row = max(ranked, key=lambda row: float(str(row.get(metric)).replace(",", "")))
        top_values[metric] = {
            "label": top_row.get(label_column),
            "value": top_row.get(metric),
        }
    return top_values


def _build_chart_candidates(
    time_columns: list[str],
    dimension_columns: list[str],
    metric_columns: list[str],
) -> list[dict]:
    candidates: list[dict] = []
    if not metric_columns:
        return candidates

    if time_columns:
        for metric in metric_columns:
            candidates.append(
                {
                    "type": "line",
                    "x": time_columns[0],
                    "y": metric,
                    "reason": "时间维度和数值指标适合趋势折线图。",
                }
            )

    if dimension_columns:
        for metric in metric_columns:
            candidates.append(
                {
                    "type": "bar",
                    "x": dimension_columns[0],
                    "y": metric,
                    "reason": "分类维度和数值指标适合柱状图对比。",
                }
            )
    return candidates
