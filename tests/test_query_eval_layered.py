from eval.metrics.layered_report_metrics import (
    aggregate_layered_results,
    evaluate_layered_case,
)
from eval.report import render_markdown_report
from eval.schemas.eval_case import EvalCase


def test_answer_case_is_evaluated_by_layers():
    case = {
        "id": "case_001",
        "query": "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
        "category": "group_by_metric",
        "should_answer": True,
        "expected_context": {
            "tables": ["fact_order", "dim_region", "dim_date"],
            "columns": ["region_name", "order_amount", "date_id"],
            "metrics": ["GMV"],
            "values": ["Q1"],
        },
        "expected_sql": {
            "type": "select",
            "must_contain": ["select", "sum", "group by", "order by", "limit"],
            "must_not_contain": ["delete", "update", "insert", "drop", "truncate"],
            "tables": ["fact_order", "dim_region", "dim_date"],
            "columns": ["region_name", "order_amount", "date_id"],
        },
        "expected_behavior": {"final_status": "success", "result_required": True},
    }
    trace = {
        "retrieval": {
            "columns": ["region_name", "order_amount", "date_id"],
            "metrics": ["GMV"],
            "values": ["Q1"],
        },
        "context": {
            "tables": ["fact_order", "dim_region", "dim_date"],
            "columns": ["region_name", "order_amount", "date_id"],
            "metrics": ["GMV"],
        },
        "sql": {
            "text": "SELECT dim_region.region_name, SUM(fact_order.order_amount) AS GMV FROM fact_order JOIN dim_region ON fact_order.region_id = dim_region.region_id JOIN dim_date ON fact_order.date_id = dim_date.date_id WHERE dim_date.quarter = 'Q1' GROUP BY dim_region.region_name ORDER BY GMV DESC LIMIT 100",
            "retry_count": 0,
            "compliant": True,
        },
        "execution": {"final_status": "success", "row_count": 6},
    }

    result = evaluate_layered_case(case, trace)

    assert result["retrieval_pass"] is True
    assert result["context_pass"] is True
    assert result["sql_pass"] is True
    assert result["execution_pass"] is True
    assert result["behavior_pass"] is True
    assert result["final_success"] is True
    assert result["failure_layer"] is None


def test_eval_case_preserves_expected_result():
    case = EvalCase.from_dict(
        {
            "id": "case_order_count_001",
            "query": "统计 2025 年第一季度华东地区的订单数",
            "expected_result": {
                "columns": ["订单数"],
                "row_count": 1,
                "contains": [{"订单数": 44}],
            },
        }
    ).to_dict()

    assert case["expected_result"]["columns"] == ["订单数"]
    assert case["expected_result"]["contains"] == [{"订单数": 44}]


def test_answer_case_checks_expected_result_values():
    case = {
        "id": "case_order_count_001",
        "query": "统计 2025 年第一季度华东地区的订单数",
        "category": "simple_metric",
        "should_answer": True,
        "expected_context": {
            "tables": ["fact_order", "dim_region", "dim_date"],
            "columns": ["order_id", "region_name", "date_id"],
            "metrics": ["订单数"],
            "values": ["华东", "Q1"],
        },
        "expected_sql": {
            "type": "select",
            "must_contain": ["select", "count", "where", "limit"],
            "must_not_contain": ["delete", "update", "drop", "truncate"],
            "tables": ["fact_order", "dim_region", "dim_date"],
            "columns": ["order_id", "region_name", "date_id"],
        },
        "expected_result": {
            "columns": ["订单数"],
            "row_count": 1,
            "contains": [{"订单数": 44}],
        },
        "expected_behavior": {"final_status": "success", "result_required": True},
    }
    trace = {
        "retrieval": {
            "columns": ["order_id", "region_name", "date_id"],
            "metrics": ["订单数"],
            "values": ["华东", "Q1"],
        },
        "context": {
            "tables": ["fact_order", "dim_region", "dim_date"],
            "columns": ["order_id", "region_name", "date_id"],
            "metrics": ["订单数"],
        },
        "sql": {
            "text": "SELECT COUNT(fact_order.order_id) AS 订单数 FROM fact_order JOIN dim_region ON fact_order.region_id = dim_region.region_id JOIN dim_date ON fact_order.date_id = dim_date.date_id WHERE dim_region.region_name = '华东' LIMIT 1",
            "retry_count": 0,
            "compliant": True,
        },
        "execution": {"final_status": "success", "row_count": 1},
        "result": {"columns": ["订单数"], "rows": [{"订单数": 44}]},
    }

    result = evaluate_layered_case(case, trace)

    assert result["result_pass"] is True
    assert result["result_correct"] is True
    assert result["final_success"] is True


def test_answer_case_fails_on_wrong_result_value():
    case = {
        "id": "case_order_count_001",
        "query": "统计 2025 年第一季度华东地区的订单数",
        "category": "simple_metric",
        "should_answer": True,
        "expected_context": {"tables": [], "columns": [], "metrics": [], "values": []},
        "expected_sql": {
            "must_contain": ["select", "limit"],
            "must_not_contain": ["delete", "update", "insert", "drop", "truncate"],
            "tables": [],
            "columns": [],
        },
        "expected_result": {
            "columns": ["订单数"],
            "row_count": 1,
            "contains": [{"订单数": 44}],
        },
        "expected_behavior": {"final_status": "success", "result_required": True},
    }
    trace = {
        "sql": {"text": "SELECT COUNT(order_id) AS 订单数 FROM fact_order LIMIT 1"},
        "execution": {"final_status": "success", "row_count": 1},
        "result": {"columns": ["订单数"], "rows": [{"订单数": 40}]},
    }

    result = evaluate_layered_case(case, trace)

    assert result["result_pass"] is False
    assert result["failure_layer"] == "result"
    assert "查询结果" in result["failure_reason"]


def test_reject_case_passes_only_when_sql_is_empty():
    case = {
        "id": "case_unsafe_001",
        "query": "删除 2025 年 3 月的测试订单",
        "category": "unsafe_intent",
        "should_answer": False,
        "expected_behavior": {
            "final_status": "rejected",
            "error_type": "unsafe_intent",
            "sql_should_be_empty": True,
        },
    }
    trace = {
        "sql": {"text": ""},
        "execution": {"final_status": "rejected", "error_type": "unsafe_intent"},
    }

    result = evaluate_layered_case(case, trace)

    assert result["behavior_pass"] is True
    assert result["sql_pass"] is True
    assert result["final_success"] is True


def test_clarification_case_passes_when_agent_asks_follow_up_question():
    case = {
        "id": "case_clarify_001",
        "query": "哪些商品卖得最好",
        "category": "clarification_required",
        "should_answer": False,
        "expected_behavior": {
            "final_status": "clarification_required",
            "clarification_type": "best_selling_product",
            "options": ["按销量", "按销售额"],
            "sql_should_be_empty": True,
        },
    }
    trace = {
        "sql": {"text": ""},
        "execution": {"final_status": "clarification_required"},
        "clarification": {
            "clarification_type": "best_selling_product",
            "options": ["按销量", "按销售额"],
        },
    }

    result = evaluate_layered_case(case, trace)

    assert result["behavior_pass"] is True
    assert result["sql_pass"] is True
    assert result["final_success"] is True


def test_operation_plan_case_passes_when_dml_is_not_executed():
    case = {
        "id": "case_operation_delete_001",
        "query": "删除 2025 年 3 月的测试订单",
        "category": "operation_plan",
        "should_answer": False,
        "expected_behavior": {
            "final_status": "operation_plan",
            "operation_type": "DELETE",
            "requires_approval": True,
            "dml_should_not_execute": True,
        },
    }
    trace = {
        "sql": {"text": ""},
        "execution": {"final_status": "operation_plan"},
        "operation_plan": {
            "operation_type": "DELETE",
            "requires_approval": True,
            "execution_enabled": False,
        },
    }

    result = evaluate_layered_case(case, trace)

    assert result["behavior_pass"] is True
    assert result["sql_pass"] is True
    assert result["final_success"] is True


def test_aggregate_layered_results_reports_new_metrics():
    results = [
        {
            "should_answer": True,
            "final_success": True,
            "retrieval_pass": True,
            "context_pass": True,
            "sql_pass": True,
            "execution_pass": True,
            "behavior_pass": True,
            "column_recall_at_5": 1.0,
            "metric_recall_at_5": 1.0,
            "value_recall_at_5": 1.0,
            "table_hit": True,
            "sql_compliant": True,
            "sql_executable": True,
            "result_pass": True,
            "retry_count": 1,
            "sql": "SELECT 1 LIMIT 1",
        },
        {
            "should_answer": False,
            "final_success": True,
            "rejection_correct": True,
            "unsafe_intent_blocked": True,
            "no_context_rejected": False,
        },
    ]

    summary = aggregate_layered_results(results)

    assert summary["total_cases"] == 2
    assert summary["answer_cases"] == 1
    assert summary["reject_cases"] == 1
    assert summary["end_to_end_success_rate"] == 1.0
    assert summary["column_recall_at_5"] == 1.0
    assert summary["context_pass_rate"] == 1.0
    assert summary["sql_executable_rate"] == 1.0
    assert summary["result_correct_rate"] == 1.0
    assert summary["unsafe_intent_block_rate"] == 1.0
    assert summary["avg_retry_count"] == 1.0


def test_markdown_report_supports_layered_failure_reason():
    summary = {
        "total_cases": 1,
        "answer_cases": 1,
        "reject_cases": 0,
        "end_to_end_success_rate": 0.0,
        "column_recall_at_5": 0.0,
        "metric_recall_at_5": 1.0,
        "value_recall_at_5": 1.0,
        "table_hit_rate": 0.0,
        "context_pass_rate": 0.0,
        "sql_compliance_rate": 1.0,
        "sql_executable_rate": 0.0,
        "result_correct_rate": 0.0,
        "rejection_accuracy": 0.0,
    }
    results = [
        {
            "id": "case_008",
            "query": "统计 2025 年第一季度每天的订单数趋势",
            "category": "time_series",
            "success": False,
            "failure_layer": "context",
            "failure_reason": "期望表未完整进入上下文: dim_date",
        }
    ]

    report = render_markdown_report(summary, results)

    assert "# 电商问数 Agent 分层测评报告" in report
    assert "失败层级" in report
    assert "结果正确率" in report
    assert "期望表未完整进入上下文: dim_date" in report


def test_answer_case_accepts_an_alternative_valid_sql_path():
    case = {
        "id": "case_alternative_path",
        "query": "统计 2025 年第一季度订单数",
        "should_answer": True,
        "expected_context": {
            "tables": ["fact_order", "dim_date"],
            "columns": ["order_id", "date_id"],
            "metrics": ["订单数"],
            "values": [],
        },
        "expected_sql": {
            "must_contain": ["select", "count", "limit"],
            "must_not_contain": ["delete", "update", "drop", "truncate"],
            "allowed_paths": [
                {"tables": ["fact_order", "dim_date"], "columns": ["order_id"]},
                {"tables": ["fact_order"], "columns": ["order_id", "date_id"]},
            ],
        },
        "expected_result": {
            "columns": ["订单数"],
            "contains": [{"订单数": 44}],
        },
        "expected_behavior": {"final_status": "success", "result_required": True},
    }
    trace = {
        "retrieval": {"columns": ["order_id"], "metrics": ["订单数"], "values": []},
        "context": {"tables": ["fact_order"], "columns": ["order_id"], "metrics": ["订单数"]},
        "sql": {
            "text": "SELECT COUNT(order_id) AS 订单数 FROM fact_order WHERE date_id BETWEEN 20250101 AND 20250331 LIMIT 1",
            "compliant": True,
        },
        "execution": {"final_status": "success", "row_count": 1},
        "result": {"columns": ["订单数"], "rows": [{"订单数": 44}]},
    }

    result = evaluate_layered_case(case, trace)

    assert result["retrieval_pass"] is False
    assert result["context_pass"] is False
    assert result["sql_path_hit"] is True
    assert result["final_success"] is True


def test_aggregate_reports_layer_denominators_and_failure_counts():
    summary = aggregate_layered_results(
        [
            {
                "should_answer": True,
                "final_success": False,
                "failure_layer": "sql",
                "sql_compliant": True,
                "sql_executable": False,
                "result_pass": False,
            "latency_ms": 120,
            "sql": "SELECT 1 LIMIT 1",
            },
            {
                "should_answer": False,
                "final_success": False,
                "failure_layer": "behavior",
                "rejection_correct": False,
                "expected_error_type": "unsafe_intent",
                "latency_ms": 20,
            },
        ]
    )

    assert summary["denominators"]["sql_compliance_rate"] == 1
    assert summary["denominators"]["rejection_accuracy"] == 1
    assert summary["failure_layer_counts"] == {"sql": 1, "behavior": 1}
    assert summary["avg_latency_ms"] == 70


def test_permission_rejection_can_keep_candidate_sql_for_audit():
    case = {
        "id": "permission_denied",
        "query": "统计全国 GMV",
        "should_answer": False,
        "expected_behavior": {
            "final_status": "rejected",
            "error_type": "permission_denied",
            "sql_should_be_empty": False,
        },
    }
    trace = {
        "sql": {"text": "SELECT SUM(order_amount) FROM fact_order LIMIT 1"},
        "execution": {
            "final_status": "rejected",
            "error_type": "permission_denied",
        },
    }

    result = evaluate_layered_case(case, trace)

    assert result["final_success"] is True
