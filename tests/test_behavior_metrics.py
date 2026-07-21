from eval.metrics.behavior_metrics import is_expected_rejection


def test_clarification_options_pass_when_expected_options_are_contained():
    case = {
        "expected_behavior": {
            "final_status": "clarification_required",
            "clarification_type": "best_selling_product",
            "options": ["按销量", "按销售额"],
            "sql_should_be_empty": True,
        }
    }
    trace = {
        "execution": {"final_status": "clarification_required"},
        "clarification": {
            "clarification_type": "best_selling_product",
            "options": ["按销量", "按销售额", "按订单数"],
        },
        "sql": "",
    }

    assert is_expected_rejection(case, trace) is True
