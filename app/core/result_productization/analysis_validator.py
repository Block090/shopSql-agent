"""校验查询结果分析 JSON。"""

from __future__ import annotations

import json
import re


def validate_result_analysis(payload: dict, result_facts: dict) -> tuple[bool, str]:
    """校验结果分析是否满足结构要求和字段边界。"""

    if not isinstance(payload, dict):
        return False, "结果分析必须是 JSON 对象"

    summary = payload.get("summary")
    insights = payload.get("insights")
    chart = payload.get("chart_recommendation")
    columns = set(result_facts.get("columns") or [])

    if not isinstance(summary, str) or not summary.strip():
        return False, "summary 不能为空"
    if not isinstance(insights, list) or any(not isinstance(item, str) for item in insights):
        return False, "insights 必须是字符串数组"
    if len(insights) > 3:
        return False, "insights 不能超过 3 条"

    if chart is not None:
        if not isinstance(chart, dict):
            return False, "chart_recommendation 必须是对象"
        x_axis = chart.get("x")
        y_axis = chart.get("y")
        if x_axis and x_axis not in columns:
            return False, "图表 x 字段不存在于结果中"
        if y_axis and y_axis not in columns:
            return False, "图表 y 字段不存在于结果中"

    if not _numbers_are_grounded(payload, result_facts):
        return False, "分析中包含未在事实摘要中出现的关键数字"

    return True, ""


def parse_result_analysis_json(content: str) -> dict:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("结果分析必须是 JSON 对象")
    return payload


def _numbers_are_grounded(payload: dict, result_facts: dict) -> bool:
    available_numbers = _collect_available_numbers(result_facts)
    text_blocks = [payload.get("summary", ""), *payload.get("insights", [])]
    for block in text_blocks:
        for number in re.findall(r"\d+(?:\.\d+)?", str(block)):
            if number not in available_numbers:
                return False
    return True


def _collect_available_numbers(result_facts: dict) -> set[str]:
    numbers = {str(result_facts.get("row_count"))}
    for metric in (result_facts.get("top_values") or {}).values():
        value = metric.get("value")
        if value is not None:
            numbers.add(str(value))
            numbers.add(_normalize_number_string(value))
    return numbers


def _normalize_number_string(value) -> str:
    return str(value).replace(",", "")
