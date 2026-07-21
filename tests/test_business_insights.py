import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.business_insights import (
    build_empty_result_diagnosis,
    build_followup_suggestions,
    classify_query_risk,
)


def test_build_empty_result_diagnosis_explains_zero_rows_with_business_suggestions():
    diagnosis = build_empty_result_diagnosis(
        query="查询 2026 年 12 月华东地区 GMV",
        resolved_query="查询 2026 年 12 月华东地区 GMV",
        semantic_slots={
            "time_range": "2026 年 12 月",
            "filters": {"region": "华东"},
            "metrics": ["GMV"],
        },
    )

    assert diagnosis["summary"] == "本次查询没有返回数据。"
    assert any("时间范围" in reason for reason in diagnosis["possible_reasons"])
    assert any("过滤条件" in reason for reason in diagnosis["possible_reasons"])
    assert any("放宽时间范围" in suggestion for suggestion in diagnosis["suggestions"])


def test_build_followup_suggestions_recommends_business_drilldowns():
    suggestions = build_followup_suggestions(
        query="统计 2025 年第一季度各大区 GMV",
        resolved_query="统计 2025 年第一季度各大区 GMV",
        result_analysis={
            "result_facts": {
                "dimension_columns": ["大区"],
                "metric_columns": ["GMV"],
            }
        },
    )

    assert len(suggestions["suggestions"]) >= 3
    assert any("品类" in item for item in suggestions["suggestions"])
    assert any("订单数" in item or "客单价" in item for item in suggestions["suggestions"])


def test_classify_query_risk_marks_aggregate_query_as_low_risk():
    risk = classify_query_risk(
        sql="SELECT region_name AS 大区, SUM(order_amount) AS GMV FROM fact_order GROUP BY region_name LIMIT 100",
        result_data=[{"大区": "华东", "GMV": 100}],
        result_facts={"dimension_columns": ["大区"], "metric_columns": ["GMV"]},
    )

    assert risk["level"] == "low"
    assert risk["label"] == "低风险汇总查询"


def test_classify_query_risk_marks_sensitive_detail_query_as_high_risk():
    risk = classify_query_risk(
        sql="SELECT user_id, phone, address FROM fact_order LIMIT 100",
        result_data=[{"user_id": "u1", "phone": "13812345678", "address": "上海"}],
        result_facts={"dimension_columns": ["user_id", "phone", "address"], "metric_columns": []},
    )

    assert risk["level"] == "high"
    assert any("敏感字段" in reason for reason in risk["reasons"])
    assert any("脱敏" in action for action in risk["actions"])
