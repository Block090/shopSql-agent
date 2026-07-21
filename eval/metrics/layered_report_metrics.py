"""
电商问数 Agent 分层评测

按召回、上下文、SQL、执行、行为五层评估单条用例，并聚合整体指标。
"""

from collections import Counter

from eval.metrics.behavior_metrics import is_expected_answer, is_expected_rejection
from eval.metrics.context_metrics import has_all_expected_tables
from eval.metrics.performance_metrics import average, percentile
from eval.metrics.result_metrics import evaluate_result
from eval.metrics.retrieval_metrics import recall_at_k
from eval.metrics.sql_metrics import (
    contains_expected_keywords,
    is_sql_compliant,
    normalize_sql,
)


def evaluate_layered_case(case: dict, trace: dict) -> dict:
    """评估单条新版问数用例"""

    should_answer = case.get("should_answer", True)
    base_result = {
        "id": case["id"],
        "query": case.get("query", ""),
        "category": case.get("category", "unknown"),
        "should_answer": should_answer,
        "success": False,
        "final_success": False,
        "failure_layer": None,
        "failure_reason": None,
    }

    if not should_answer:
        return _evaluate_reject_case(case, trace, base_result)
    return _evaluate_answer_case(case, trace, base_result)


def aggregate_layered_results(results: list[dict]) -> dict:
    """汇总新版分层评测结果"""

    total_cases = len(results)
    answer_results = [result for result in results if result.get("should_answer")]
    reject_results = [result for result in results if not result.get("should_answer")]
    generated_sql_results = [
        result for result in answer_results if str(result.get("sql", "")).strip()
    ]
    executed_sql_results = [
        result for result in generated_sql_results if result.get("sql_executable")
    ]
    unsafe_reject_results = [
        result
        for result in reject_results
        if result.get("expected_error_type") == "unsafe_intent"
        or result.get("unsafe_intent_blocked")
    ]
    no_context_reject_results = [
        result
        for result in reject_results
        if result.get("expected_error_type") == "no_recall_context"
        or result.get("no_context_rejected")
    ]

    latencies = [
        result.get("latency_ms", 0)
        for result in results
        if result.get("latency_ms") is not None
    ]

    summary = {
        "total_cases": total_cases,
        "answer_cases": len(answer_results),
        "reject_cases": len(reject_results),
        "end_to_end_success_rate": _rate(
            result.get("final_success") for result in results
        ),
        "column_recall_at_5": average(
            result.get("column_recall_at_5", 0.0) for result in answer_results
        ),
        "metric_recall_at_5": average(
            result.get("metric_recall_at_5", 0.0) for result in answer_results
        ),
        "value_recall_at_5": average(
            result.get("value_recall_at_5", 0.0) for result in answer_results
        ),
        "table_hit_rate": _rate(result.get("table_hit") for result in answer_results),
        "context_pass_rate": _rate(
            result.get("context_pass") for result in answer_results
        ),
        "sql_compliance_rate": _rate(
            result.get("sql_compliant") for result in generated_sql_results
        ),
        "sql_executable_rate": _rate(
            result.get("sql_executable") for result in generated_sql_results
        ),
        "result_correct_rate": _rate(
            result.get("result_pass") for result in executed_sql_results
        ),
        "rejection_accuracy": _rate(
            result.get("rejection_correct") for result in reject_results
        ),
        "unsafe_intent_block_rate": _rate(
            result.get("unsafe_intent_blocked") for result in unsafe_reject_results
        ),
        "no_context_reject_rate": _rate(
            result.get("no_context_rejected") for result in no_context_reject_results
        ),
        "avg_retry_count": average(
            result.get("retry_count", 0) for result in answer_results
        ),
        "avg_latency_ms": average(latencies),
        "p95_latency_ms": percentile(latencies, 0.95),
        "runtime_error_rate": _rate(
            result.get("actual_error_type") == "runtime_error" for result in results
        ),
    }
    summary["denominators"] = {
        "end_to_end_success_rate": total_cases,
        "column_recall_at_5": len(answer_results),
        "metric_recall_at_5": len(answer_results),
        "value_recall_at_5": len(answer_results),
        "table_hit_rate": len(answer_results),
        "context_pass_rate": len(answer_results),
        "sql_compliance_rate": len(generated_sql_results),
        "sql_executable_rate": len(generated_sql_results),
        "result_correct_rate": len(executed_sql_results),
        "rejection_accuracy": len(reject_results),
        "unsafe_intent_block_rate": len(unsafe_reject_results),
        "no_context_reject_rate": len(no_context_reject_results),
    }
    summary["failure_layer_counts"] = dict(
        Counter(
            result.get("failure_layer") or "unknown"
            for result in results
            if not result.get("final_success")
        )
    )
    return summary


def _evaluate_answer_case(case: dict, trace: dict, result: dict) -> dict:
    expected_context = case.get("expected_context", {})
    expected_sql = case.get("expected_sql", {})

    expected_columns = expected_context.get("columns") or case.get("expected_columns", [])
    expected_metrics = expected_context.get("metrics") or case.get("expected_metrics", [])
    expected_values = expected_context.get("values") or case.get("expected_values", [])
    expected_tables = expected_context.get("tables") or case.get("expected_tables", [])

    retrieval = _extract_retrieval(trace)
    context = _extract_context(trace)
    sql_info = _extract_sql(trace)
    execution = _extract_execution(trace)
    result_check = evaluate_result(case.get("expected_result", {}), trace)

    column_recall = recall_at_k(expected_columns, retrieval["columns"], 5)
    metric_recall = recall_at_k(expected_metrics, retrieval["metrics"], 5)
    value_recall = recall_at_k(expected_values, retrieval["values"], 5)
    retrieval_pass = (
        column_recall >= 1.0 and metric_recall >= 1.0 and value_recall >= 1.0
    )

    table_hit = has_all_expected_tables(expected_tables, context["tables"])
    context_column_recall = recall_at_k(
        expected_columns, context["columns"], len(context["columns"]) or 1
    )
    context_pass = table_hit and context_column_recall >= 1.0

    sql_text = sql_info["text"]
    sql_compliant = bool(sql_info.get("compliant", is_sql_compliant(sql_text)))
    sql_keywords_hit = contains_expected_keywords(
        sql_text, expected_sql.get("must_contain") or case.get("expected_sql_keywords", [])
    )
    sql_path_hit = _matches_allowed_sql_path(sql_text, expected_sql)
    sql_path_required = bool(expected_sql.get("allowed_paths")) or bool(
        expected_sql.get("strict_path", False)
    )
    sql_tables_hit = _contains_all(sql_text, expected_sql.get("tables", []))
    sql_columns_hit = _contains_all(sql_text, expected_sql.get("columns", []))
    sql_forbidden_clear = not _contains_any(
        sql_text, expected_sql.get("must_not_contain", [])
    )
    sql_pass = (
        sql_compliant
        and sql_keywords_hit
        and (sql_path_hit or not sql_path_required)
        and sql_forbidden_clear
    )

    execution_pass = execution.get("final_status") == "success"
    result_pass = result_check["result_pass"]
    behavior_pass = is_expected_answer(case, trace)
    final_success = behavior_pass and sql_pass and execution_pass and result_pass

    result.update(
        {
            "column_recall_at_5": column_recall,
            "metric_recall_at_5": metric_recall,
            "value_recall_at_5": value_recall,
            "retrieval_pass": retrieval_pass,
            "table_hit": table_hit,
            "context_pass": context_pass,
            "sql_compliant": sql_compliant,
            "sql_keywords_hit": sql_keywords_hit,
            "sql_table_hit": sql_tables_hit,
            "sql_column_hit": sql_columns_hit,
            "sql_path_hit": sql_path_hit,
            "sql_executable": execution_pass,
            "sql_pass": sql_pass,
            "execution_pass": execution_pass,
            "result_column_hit": result_check["result_column_hit"],
            "result_row_count_hit": result_check["result_row_count_hit"],
            "result_value_hit": result_check["result_value_hit"],
            "result_order_hit": result_check["result_order_hit"],
            "result_pass": result_pass,
            "result_correct": result_pass,
            "result_failure_reason": result_check["result_failure_reason"],
            "behavior_pass": behavior_pass,
            "retry_count": sql_info.get("retry_count", 0),
            "latency_ms": execution.get("latency_ms"),
            "final_status": execution.get("final_status"),
            "sql": sql_text,
            "success": final_success,
            "final_success": final_success,
        }
    )
    _attach_failure(result)
    return result


def _evaluate_reject_case(case: dict, trace: dict, result: dict) -> dict:
    execution = _extract_execution(trace)
    sql_info = _extract_sql(trace)
    expected_behavior = case.get("expected_behavior", {})
    expected_error_type = expected_behavior.get("error_type") or case.get(
        "expected_error_type"
    )

    rejection_correct = is_expected_rejection(case, trace)
    unsafe_blocked = expected_error_type == "unsafe_intent" and rejection_correct
    no_context_rejected = expected_error_type == "no_recall_context" and rejection_correct
    sql_empty = not sql_info["text"].strip()
    sql_should_be_empty = expected_behavior.get("sql_should_be_empty", True)
    sql_requirement_pass = sql_empty if sql_should_be_empty else True
    final_success = rejection_correct and sql_requirement_pass

    result.update(
        {
            "retrieval_pass": True,
            "context_pass": True,
            "sql_pass": sql_requirement_pass,
            "execution_pass": True,
            "behavior_pass": rejection_correct,
            "rejection_correct": rejection_correct,
            "unsafe_intent_blocked": unsafe_blocked,
            "no_context_rejected": no_context_rejected,
            "expected_error_type": expected_error_type,
            "actual_error_type": execution.get("error_type"),
            "final_status": execution.get("final_status"),
            "sql": sql_info["text"],
            "success": final_success,
            "final_success": final_success,
        }
    )
    _attach_failure(result)
    return result


def _extract_retrieval(trace: dict) -> dict:
    retrieval = trace.get("retrieval", {})
    return {
        "columns": retrieval.get("columns", trace.get("retrieved_columns", [])),
        "metrics": retrieval.get("metrics", trace.get("retrieved_metrics", [])),
        "values": retrieval.get("values", trace.get("retrieved_values", [])),
    }


def _extract_context(trace: dict) -> dict:
    context = trace.get("context", {})
    retrieval = _extract_retrieval(trace)
    return {
        "tables": context.get("tables", trace.get("table_infos", [])),
        "columns": context.get("columns", retrieval["columns"]),
        "metrics": context.get("metrics", retrieval["metrics"]),
    }


def _extract_sql(trace: dict) -> dict:
    sql = trace.get("sql", "")
    if isinstance(sql, dict):
        return {
            "text": sql.get("text", "") or "",
            "retry_count": sql.get("retry_count", 0) or 0,
            "compliant": sql.get("compliant", is_sql_compliant(sql.get("text", ""))),
        }
    sql_detail = trace.get("sql_detail", {})
    if isinstance(sql_detail, dict) and sql_detail:
        text = sql_detail.get("text", "") or sql or ""
        return {
            "text": text,
            "retry_count": sql_detail.get("retry_count", 0) or 0,
            "compliant": sql_detail.get("compliant", is_sql_compliant(text)),
        }
    return {
        "text": sql or "",
        "retry_count": trace.get("retry_count", 0) or 0,
        "compliant": is_sql_compliant(sql or ""),
    }


def _extract_execution(trace: dict) -> dict:
    execution = trace.get("execution", {})
    return {
        "final_status": execution.get("final_status", trace.get("final_status")),
        "row_count": execution.get("row_count", trace.get("row_count")),
        "error_type": execution.get("error_type", trace.get("error_type")),
        "latency_ms": execution.get("latency_ms", trace.get("latency_ms")),
    }


def _contains_all(text: str, expected_items: list[str]) -> bool:
    normalized = normalize_sql(text)
    return all(item.lower() in normalized for item in expected_items)


def _contains_any(text: str, expected_items: list[str]) -> bool:
    normalized = normalize_sql(text)
    return any(item.lower() in normalized for item in expected_items)


def _matches_allowed_sql_path(sql_text: str, expected_sql: dict) -> bool:
    """接受任一合法表字段路径，避免把等价 SQL 误判为失败。"""

    allowed_paths = expected_sql.get("allowed_paths") or []
    if not allowed_paths:
        return _contains_all(sql_text, expected_sql.get("tables", [])) and _contains_all(
            sql_text, expected_sql.get("columns", [])
        )

    return any(
        _contains_all(sql_text, path.get("tables", []))
        and _contains_all(sql_text, path.get("columns", []))
        and contains_expected_keywords(sql_text, path.get("must_contain", []))
        for path in allowed_paths
    )


def _attach_failure(result: dict) -> None:
    if result.get("final_success"):
        return

    checks = [
        ("sql", "SQL 未满足安全、结构或表字段命中要求", result.get("sql_pass")),
        ("execution", "SQL 未成功执行或未返回预期结果", result.get("execution_pass")),
        (
            "result",
            result.get("result_failure_reason") or "查询结果不符合预期",
            result.get("result_pass", True),
        ),
        ("behavior", "最终回答或拒答行为不符合预期", result.get("behavior_pass")),
        ("retrieval", "召回结果未命中期望字段、指标或字段值", result.get("retrieval_pass")),
        ("context", "期望表或字段未完整进入上下文", result.get("context_pass")),
    ]
    for layer, reason, passed in checks:
        if not passed:
            result["failure_layer"] = layer
            result["failure_reason"] = reason
            return


def _rate(values) -> float:
    value_list = list(values)
    if not value_list:
        return 0.0
    return sum(1.0 if value else 0.0 for value in value_list) / len(value_list)
