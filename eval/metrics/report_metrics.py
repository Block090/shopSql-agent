"""
评测结果计算和报告聚合

把单条评测用例和 Agent trace 转换为可统计的结果明细。
"""

from eval.metrics.retrieval_metrics import contains_any_expected, recall_at_k
from eval.metrics.sql_metrics import contains_expected_keywords, is_sql_compliant


def evaluate_case(case: dict, trace: dict) -> dict:
    """评估单条用例，返回结构化明细"""

    should_answer = case.get("should_answer", True)
    result = {
        "id": case["id"],
        "query": case.get("query", ""),
        "category": case.get("category", "unknown"),
        "should_answer": should_answer,
        "success": False,
    }

    if not should_answer:
        expected_error_type = case.get("expected_error_type")
        actual_error_type = trace.get("error_type")
        rejection_correct = (
            trace.get("final_status") == "rejected"
            and actual_error_type == expected_error_type
            and not trace.get("sql")
        )
        result.update(
            {
                "expected_error_type": expected_error_type,
                "actual_error_type": actual_error_type,
                "rejection_correct": rejection_correct,
                "success": rejection_correct,
            }
        )
        return result

    expected_columns = case.get("expected_columns", [])
    expected_metrics = case.get("expected_metrics", [])
    expected_tables = case.get("expected_tables", [])
    expected_sql_keywords = case.get("expected_sql_keywords", [])

    retrieved_columns = trace.get("retrieved_columns", [])
    retrieved_metrics = trace.get("retrieved_metrics", [])
    table_infos = trace.get("table_infos", [])
    sql = trace.get("sql", "")

    field_recall = recall_at_k(expected_columns, retrieved_columns, 5)
    metric_recall = recall_at_k(expected_metrics, retrieved_metrics, 5)
    table_hit = contains_any_expected(expected_tables, table_infos)
    sql_compliant = is_sql_compliant(sql)
    sql_keywords_hit = contains_expected_keywords(sql, expected_sql_keywords)
    final_success = trace.get("final_status") == "success"

    success = (
        field_recall >= 1.0
        and metric_recall >= 1.0
        and table_hit
        and sql_compliant
        and sql_keywords_hit
        and final_success
    )

    result.update(
        {
            "field_recall_at_5": field_recall,
            "metric_recall_at_5": metric_recall,
            "table_hit": table_hit,
            "sql_compliant": sql_compliant,
            "sql_keywords_hit": sql_keywords_hit,
            "final_status": trace.get("final_status"),
            "sql": sql,
            "success": success,
        }
    )
    return result


def aggregate_results(results: list[dict]) -> dict:
    """汇总多条评测结果，生成报告所需的整体指标"""

    total_cases = len(results)
    answer_results = [result for result in results if result.get("should_answer")]
    reject_results = [result for result in results if not result.get("should_answer")]

    return {
        "total_cases": total_cases,
        "answer_cases": len(answer_results),
        "reject_cases": len(reject_results),
        "end_to_end_success_rate": _avg(
            1.0 if result.get("success") else 0.0 for result in results
        ),
        "field_recall_at_5": _avg(
            result.get("field_recall_at_5", 0.0) for result in answer_results
        ),
        "metric_recall_at_5": _avg(
            result.get("metric_recall_at_5", 0.0) for result in answer_results
        ),
        "table_hit_rate": _avg(
            1.0 if result.get("table_hit") else 0.0 for result in answer_results
        ),
        "sql_compliance_rate": _avg(
            1.0 if result.get("sql_compliant") else 0.0
            for result in answer_results
        ),
        "rejection_accuracy": _avg(
            1.0 if result.get("rejection_correct") else 0.0
            for result in reject_results
        ),
    }


def _avg(values) -> float:
    """计算平均值，空集合返回 0"""

    value_list = list(values)
    if not value_list:
        return 0.0
    return sum(value_list) / len(value_list)
