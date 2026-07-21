"""
电商问数 Agent 分层评测 Markdown 报告渲染
"""


SUMMARY_LABELS = {
    "total_cases": "总用例数",
    "answer_cases": "应回答用例数",
    "reject_cases": "应拒答用例数",
    "column_recall_at_5": "字段 Recall@5",
    "field_recall_at_5": "字段 Recall@5",
    "metric_recall_at_5": "指标 Recall@5",
    "value_recall_at_5": "字段值 Recall@5",
    "table_hit_rate": "表命中率",
    "context_pass_rate": "上下文通过率",
    "sql_compliance_rate": "SQL 合规率",
    "sql_executable_rate": "SQL 执行成功率",
    "result_correct_rate": "结果正确率",
    "rejection_accuracy": "拒答准确率",
    "unsafe_intent_block_rate": "危险意图拦截率",
    "no_context_reject_rate": "无上下文拒答率",
    "avg_retry_count": "平均 SQL 重试次数",
    "avg_latency_ms": "平均耗时(ms)",
    "p95_latency_ms": "P95 耗时(ms)",
    "runtime_error_rate": "运行时错误率",
    "end_to_end_success_rate": "端到端成功率",
}


def render_markdown_report(summary: dict, results: list[dict]) -> str:
    """把评测汇总和明细渲染成 Markdown 报告"""

    lines = [
        "# 电商问数 Agent 分层测评报告",
        "",
        "> 兼容旧版标题：# RAG 测评报告",
        "",
        "## 一、整体结果",
        "",
        "| 指标 | 结果 |",
        "| --- | ---: |",
    ]

    for key, label in SUMMARY_LABELS.items():
        if key not in summary:
            continue
        value = summary.get(key, 0)
        lines.append(f"| {label} | {_format_value(key, value)} |")

    lines.extend(
        [
            "",
            "## 二、失败层级统计",
            "",
            "| 失败层级 | 数量 |",
            "| --- | ---: |",
            *[
                f"| {layer} | {count} |"
                for layer, count in summary.get("failure_layer_counts", {}).items()
            ],
            "" if summary.get("failure_layer_counts") else "| 无 | 0 |",
            "",
            "## 三、指标分母",
            "",
            "| 指标 | 分母 |",
            "| --- | ---: |",
            *[
                f"| {SUMMARY_LABELS.get(metric, metric)} | {count} |"
                for metric, count in summary.get("denominators", {}).items()
            ],
            "",
            "## 四、失败用例",
            "",
            "| ID | 类别 | 失败层级 | 问题 | 原因 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    failed_results = [result for result in results if not result.get("success")]
    if failed_results:
        for result in failed_results:
            lines.append(
                "| {id} | {category} | {failure_layer} | {query} | {failure_reason} |".format(
                    id=result.get("id", ""),
                    category=result.get("category", "unknown"),
                    failure_layer=result.get("failure_layer", "unknown") or "unknown",
                    query=result.get("query", ""),
                    failure_reason=result.get("failure_reason", "") or "",
                )
            )
    else:
        lines.append("| 无 | 无 | 无 | 本次没有失败用例 | 无 |")

    lines.extend(
        [
            "",
            "## 五、优化建议",
            "",
            *_build_suggestions(summary),
            "",
        ]
    )

    return "\n".join(lines)


def _format_value(key: str, value) -> str:
    """格式化报告中的数字"""

    if isinstance(value, float):
        if key.endswith("_ms") or key == "avg_retry_count":
            return f"{value:.2f}"
        return f"{value * 100:.2f}%"
    return str(value)


def _build_suggestions(summary: dict) -> list[str]:
    """根据汇总指标生成简单优化建议"""

    suggestions = []
    field_recall = summary.get(
        "column_recall_at_5", summary.get("field_recall_at_5", 0.0)
    )
    if field_recall < 0.8:
        suggestions.append("1. 字段 Recall@5 偏低，建议补充字段描述和 alias。")
    if summary.get("metric_recall_at_5", 0.0) < 0.8:
        suggestions.append("2. 指标 Recall@5 偏低，建议补充指标别名和业务口径。")
    if summary.get("table_hit_rate", 0.0) < 0.8:
        suggestions.append("3. 表命中率偏低，建议优化表描述和 `filter_table` prompt。")
    if summary.get("context_pass_rate", 1.0) < 0.8:
        suggestions.append("4. 上下文通过率偏低，建议检查表过滤和字段过滤结果。")
    if summary.get("sql_compliance_rate", 0.0) < 1.0:
        suggestions.append("5. SQL 合规率未达到 100%，建议检查 SQL Guard 和生成约束。")
    if summary.get("result_correct_rate", 1.0) < 0.8:
        suggestions.append("6. 结果正确率偏低，建议检查指标口径、聚合函数和排序逻辑。")
    if summary.get("rejection_accuracy", 0.0) < 1.0:
        suggestions.append("7. 拒答准确率未达到 100%，建议补充负样本和拒答规则。")

    if not suggestions:
        suggestions.append("1. 当前核心指标表现稳定，可以继续扩大评测集覆盖更多复杂问法。")

    return suggestions
