"""
Agent 执行 trace 提取

把 LangGraph 最终 state 和 stream 事件整理成 RAG 测评需要的轻量 JSON。
"""

from typing import Any


def build_trace_from_state(
    state: dict, events: list[dict], performance: dict | None = None
) -> dict:
    """从最终 state 和事件列表构造评测 trace"""

    error_type = _infer_error_type(events)
    final_status = _infer_final_status(state, error_type)
    retrieved_columns = _extract_names(state.get("retrieved_column_infos", []))
    retrieved_metrics = _extract_names(state.get("retrieved_metric_infos", []))
    retrieved_values = _extract_values(state.get("retrieved_value_infos", []))
    table_infos = _extract_names(state.get("table_infos", []))
    sql = state.get("sql", "") or ""
    result_rows = _extract_result_rows(state, events)

    performance = performance or {}
    latency_ms = performance.get("latency_ms")

    return {
        "query": state.get("query", ""),
        "resolved_query": state.get("resolved_query", state.get("query", "")),
        # 兼容旧版 RAG 测评字段
        "retrieved_columns": retrieved_columns,
        "retrieved_metrics": retrieved_metrics,
        "retrieved_values": retrieved_values,
        "table_infos": table_infos,
        "sql": sql,
        "final_status": final_status,
        "error_type": error_type,
        # 新版电商问数 Agent 分层测评字段
        "intent": {
            "is_unsafe_intent": error_type == "unsafe_intent",
            "reject_reason": error_type,
        },
        "retrieval": {
            "keywords": _extract_keywords(events),
            "columns": retrieved_columns,
            "metrics": retrieved_metrics,
            "values": retrieved_values,
        },
        "context": {
            "tables": table_infos,
            "columns": retrieved_columns,
            "metrics": retrieved_metrics,
        },
        "sql_detail": {
            "text": sql,
            "validate_error": state.get("sql_error") or state.get("error"),
            "retry_count": state.get("retry_count", 0) or 0,
            "compliant": not state.get("sql_error"),
        },
        "execution": {
            "final_status": _infer_execution_status(events, final_status),
            "row_count": len(result_rows) if isinstance(result_rows, list) else None,
            "error_type": error_type,
            "latency_ms": latency_ms,
        },
        "result": {
            "columns": _infer_result_columns(result_rows),
            "rows": result_rows,
        },
        "result_data": result_rows,
        "clarification": _extract_clarification(events),
        "operation_plan": _extract_operation_plan(events),
        "performance": {
            "latency_ms": latency_ms,
            "node_latency_ms": performance.get("node_latency_ms", {}),
            "model_call_count": performance.get("model_call_count", 0),
        },
    }


def _extract_names(items: list[Any]) -> list[str]:
    """从 dataclass 或 dict 列表中提取 name 字段"""

    names = []
    for item in items:
        value = _get_attr_or_key(item, "name")
        if value:
            names.append(value)
    return names


def _extract_values(items: list[Any]) -> list[str]:
    """从 dataclass 或 dict 列表中提取 value 字段"""

    values = []
    for item in items:
        value = _get_attr_or_key(item, "value")
        if value:
            values.append(value)
    return values


def _get_attr_or_key(item: Any, key: str):
    """兼容 dict 和 dataclass/object 两类结构"""

    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _infer_final_status(state: dict, error_type: str | None) -> str:
    """根据 state 和错误类型推断最终状态"""

    if error_type == "no_recall_context":
        return "unable_to_answer"
    if error_type:
        return "rejected"
    if state.get("error"):
        return "failed"
    if state.get("sql"):
        return "success"
    return "failed"


def _infer_error_type(events: list[dict]) -> str | None:
    """根据 stream 事件推断拒答类型"""

    for event in events:
        step = event.get("step", "")
        message = event.get("message", "")
        if step == "拒绝危险操作" or "仅支持只读数据分析" in message:
            return "unsafe_intent"
        if step == "无法回答" or "没有找到足够相关的信息" in message:
            return "no_recall_context"
        if event.get("error_type") == "permission_denied" or "权限校验未通过" in message:
            return "permission_denied"
    return None


def _infer_execution_status(events: list[dict], fallback_status: str) -> str:
    """识别追问类事件，避免把业务口径澄清误判成普通失败"""

    if _extract_clarification(events):
        return "clarification_required"
    if _extract_operation_plan(events):
        return "operation_plan"
    return fallback_status


def _extract_keywords(events: list[dict]) -> list[str]:
    """从日志事件中尽量提取关键词信息"""

    for event in events:
        keywords = event.get("keywords")
        if isinstance(keywords, list):
            return [str(keyword) for keyword in keywords]
    return []


def _infer_row_count(state: dict) -> int | None:
    """从执行结果中推断返回行数"""

    query_result = state.get("query_result") or state.get("result")
    if isinstance(query_result, list):
        return len(query_result)
    return None


def _extract_result_rows(state: dict, events: list[dict] | None = None) -> list[dict]:
    """从最终 state 中提取 SQL 执行结果行"""

    for event in events or []:
        if event.get("type") == "result" and isinstance(event.get("data"), list):
            return [row for row in event["data"] if isinstance(row, dict)]

    query_result = state.get("query_result") or state.get("result") or []
    if isinstance(query_result, list):
        return [row for row in query_result if isinstance(row, dict)]
    return []


def _infer_result_columns(rows: list[dict]) -> list[str]:
    """根据结果行推断返回字段"""

    if rows:
        return list(rows[0].keys())
    return []


def _extract_clarification(events: list[dict]) -> dict:
    """提取业务口径澄清事件，供测评模块判断追问是否触发"""

    for event in events:
        if event.get("type") == "clarification":
            return {
                "message": event.get("message", ""),
                "options": event.get("options", []),
                "clarification_type": event.get("clarification_type", ""),
                "missing_slots": event.get("missing_slots", []),
            }
    return {}


def _extract_operation_plan(events: list[dict]) -> dict:
    """提取数据变更审批方案事件，供测评判断 DML 是否被默认拦住"""

    for event in events:
        if event.get("type") == "operation_plan":
            return event.get("data", {})
    return {}
