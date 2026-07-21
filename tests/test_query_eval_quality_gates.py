from eval.runners.check_quality_gates import evaluate_quality_gates


def test_quality_gate_rejects_critical_security_regression():
    result = evaluate_quality_gates(
        {
            "summary": {
                "end_to_end_success_rate": 1.0,
                "column_recall_at_5": 1.0,
                "metric_recall_at_5": 1.0,
                "table_hit_rate": 1.0,
                "no_context_reject_rate": 1.0,
                "unsafe_intent_block_rate": 1.0,
                "sql_compliance_rate": 1.0,
                "sql_executable_rate": 1.0,
            },
            "results": [{"id": "unsafe", "final_success": False}],
        },
        [{"id": "unsafe", "tags": ["safety"]}],
    )

    assert result["passed"] is False
    assert result["failures"][-1]["type"] == "critical_case"
