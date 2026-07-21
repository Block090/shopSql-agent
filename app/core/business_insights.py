"""真实业务场景下的问数辅助洞察。

包含空结果诊断、后续分析建议和查询风险分级。全部先使用规则实现，保证在
LLM 不可用时也能稳定输出可解释结果。
"""

from __future__ import annotations

from typing import Any

SENSITIVE_KEYWORDS = ("phone", "mobile", "address", "id_card", "user_id", "member_id", "手机号", "地址")


def build_empty_result_diagnosis(
    *,
    query: str,
    resolved_query: str,
    semantic_slots: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """为 0 行结果生成业务可读诊断。"""

    semantic_slots = semantic_slots or {}
    filters = semantic_slots.get("filters") or {}

    possible_reasons = [
        "时间范围内可能没有符合条件的数据。",
        "过滤条件可能过窄，导致没有命中记录。",
        "字段取值可能与数据库中的标准取值不一致。",
    ]

    if not filters:
        possible_reasons.append("当前问题可能缺少必要的业务限定条件。")

    suggestions = [
        "放宽时间范围后重试，例如改查相邻月份或季度。",
        "减少地区、品类、会员等级等过滤条件后重新查询。",
        "先查询该时间段是否存在订单数据，再逐步增加过滤条件。",
    ]

    return {
        "summary": "本次查询没有返回数据。",
        "query": query,
        "resolved_query": resolved_query,
        "possible_reasons": possible_reasons,
        "suggestions": suggestions,
    }


def build_followup_suggestions(
    *,
    query: str,
    resolved_query: str,
    result_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """基于结果事实生成下一步分析建议。"""

    facts = (result_analysis or {}).get("result_facts") or {}
    dimensions = facts.get("dimension_columns") or []
    metrics = facts.get("metric_columns") or []
    primary_metric = metrics[0] if metrics else "核心指标"
    primary_dimension = dimensions[0] if dimensions else "当前维度"

    suggestions = [
        f"按商品品类拆分{primary_dimension}的{primary_metric}，定位主要贡献来源。",
        f"对比各{primary_dimension}的订单数和客单价，判断差异来自流量还是客单。",
        f"查看{primary_metric}排名靠前和靠后的对象，进一步分析 TOP 与尾部差异。",
    ]

    if "大区" in "".join(map(str, dimensions)) or "地区" in "".join(map(str, dimensions)):
        suggestions.append("对重点大区继续按商品品类、会员等级拆分，定位区域差异原因。")
    else:
        suggestions.append("增加大区或会员等级维度，观察结果是否存在明显结构差异。")

    return {
        "summary": "可以继续从维度拆分、指标拆解和 TOP 对比三个方向分析。",
        "query": query,
        "resolved_query": resolved_query,
        "suggestions": suggestions,
    }


def classify_query_risk(
    *,
    sql: str | None,
    result_data,
    result_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """根据 SQL、字段和结果规模给查询打业务风险标签。"""

    result_facts = result_facts or {}
    columns = _collect_columns(result_data) or result_facts.get("columns") or []
    sql_text = sql or ""
    haystack = " ".join([sql_text, *map(str, columns)]).lower()

    sensitive_hits = [
        keyword for keyword in SENSITIVE_KEYWORDS if keyword.lower() in haystack
    ]
    row_count = len(result_data) if isinstance(result_data, list) else 1 if result_data else 0
    has_metrics = bool(result_facts.get("metric_columns"))

    if sensitive_hits:
        return {
            "level": "high",
            "label": "高风险敏感数据查询",
            "reasons": ["查询涉及敏感字段或用户明细。"],
            "actions": ["普通视图应隐藏或脱敏敏感字段，导出前需要二次确认。"],
        }

    if row_count > 100 or not has_metrics:
        return {
            "level": "medium",
            "label": "中风险明细查询",
            "reasons": ["查询结果可能偏明细或返回行数较多。"],
            "actions": ["建议限制返回行数，并优先使用汇总指标展示。"],
        }

    return {
        "level": "low",
        "label": "低风险汇总查询",
        "reasons": ["查询以汇总指标为主，未命中明显敏感字段。"],
        "actions": ["可直接展示业务结果。"],
    }


def _collect_columns(result_data) -> list[str]:
    if isinstance(result_data, list):
        columns: list[str] = []
        for row in result_data:
            if not isinstance(row, dict):
                continue
            for column in row.keys():
                if column not in columns:
                    columns.append(column)
        return columns
    if isinstance(result_data, dict):
        return list(result_data.keys())
    return []
