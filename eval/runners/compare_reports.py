"""
测评报告 Baseline 对比

读取 baseline 与 current 的结构化测评结果，输出关键指标变化 Markdown。
"""

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_BASELINE_PATH = Path("eval/reports/baseline_query_eval_result.json")
DEFAULT_CURRENT_PATH = Path("eval/reports/query_eval_result.json")
DEFAULT_OUTPUT_PATH = Path("eval/reports/query_eval_compare.md")

COMPARE_LABELS = {
    "end_to_end_success_rate": "端到端成功率",
    "column_recall_at_5": "字段 Recall@5",
    "metric_recall_at_5": "指标 Recall@5",
    "value_recall_at_5": "字段值 Recall@5",
    "context_pass_rate": "上下文通过率",
    "sql_compliance_rate": "SQL 合规率",
    "sql_executable_rate": "SQL 执行成功率",
    "result_correct_rate": "结果正确率",
    "rejection_accuracy": "拒答准确率",
    "avg_latency_ms": "平均耗时(ms)",
    "p95_latency_ms": "P95 耗时(ms)",
    "runtime_error_rate": "运行时错误率",
}


def compare_eval_results(
    baseline_result: dict[str, Any], current_result: dict[str, Any]
) -> dict[str, Any]:
    """对比两份测评结果中的 summary 指标"""

    baseline_summary = baseline_result.get("summary", {})
    current_summary = current_result.get("summary", {})
    metrics = {}

    for key in COMPARE_LABELS:
        if key not in baseline_summary and key not in current_summary:
            continue
        baseline_value = baseline_summary.get(key, 0)
        current_value = current_summary.get(key, 0)
        metrics[key] = {
            "label": COMPARE_LABELS[key],
            "baseline": baseline_value,
            "current": current_value,
            "delta": current_value - baseline_value,
        }

    baseline_cases = {
        item.get("id"): bool(item.get("final_success"))
        for item in baseline_result.get("results", [])
        if item.get("id")
    }
    current_cases = {
        item.get("id"): bool(item.get("final_success"))
        for item in current_result.get("results", [])
        if item.get("id")
    }
    shared_ids = set(baseline_cases) & set(current_cases)

    return {
        "metrics": metrics,
        "fixed_case_ids": sorted(
            case_id
            for case_id in shared_ids
            if not baseline_cases[case_id] and current_cases[case_id]
        ),
        "regressed_case_ids": sorted(
            case_id
            for case_id in shared_ids
            if baseline_cases[case_id] and not current_cases[case_id]
        ),
        "new_failure_case_ids": sorted(
            case_id
            for case_id in set(current_cases) - set(baseline_cases)
            if not current_cases[case_id]
        ),
    }


def render_compare_report(comparison: dict[str, Any]) -> str:
    """渲染 baseline 对比 Markdown 报告"""

    lines = [
        "# 电商问数 Agent 测评 Baseline 对比报告",
        "",
        "| 指标 | Baseline | Current | 变化 |",
        "| --- | ---: | ---: | ---: |",
    ]

    for key, item in comparison.get("metrics", {}).items():
        lines.append(
            "| {label} | {baseline} | {current} | {delta} |".format(
                label=item.get("label", COMPARE_LABELS.get(key, key)),
                baseline=_format_metric(key, item.get("baseline", 0)),
                current=_format_metric(key, item.get("current", 0)),
                delta=_format_delta(key, item.get("delta", 0)),
            )
        )

    lines.extend(
        [
            "",
            "## 用例变化",
            "",
            f"- 已修复：{_format_case_ids(comparison.get('fixed_case_ids', []))}",
            f"- 新增退化：{_format_case_ids(comparison.get('regressed_case_ids', []))}",
            f"- 新增失败用例：{_format_case_ids(comparison.get('new_failure_case_ids', []))}",
        ]
    )

    return "\n".join(lines) + "\n"


def _format_case_ids(case_ids: list[str]) -> str:
    return "、".join(case_ids) if case_ids else "无"


def write_compare_report(
    baseline_path: str | Path = DEFAULT_BASELINE_PATH,
    current_path: str | Path = DEFAULT_CURRENT_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> dict[str, Any]:
    """读取两份结果并写出 Markdown 对比报告"""

    baseline = _read_json(baseline_path)
    current = _read_json(current_path)
    comparison = compare_eval_results(baseline, current)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_compare_report(comparison), encoding="utf-8")
    return comparison


def main() -> None:
    parser = argparse.ArgumentParser(description="对比两份电商问数 Agent 测评结果")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    parser.add_argument("--current", default=str(DEFAULT_CURRENT_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    args = parser.parse_args()

    comparison = write_compare_report(args.baseline, args.current, args.output)
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _format_metric(key: str, value: Any) -> str:
    if not isinstance(value, int | float):
        return str(value)
    if key.endswith("_ms"):
        return f"{value:.2f}"
    return f"{value * 100:.2f}%"


def _format_delta(key: str, value: Any) -> str:
    if not isinstance(value, int | float):
        return str(value)
    sign = "+" if value > 0 else ""
    if key.endswith("_ms"):
        return f"{sign}{value:.2f}"
    return f"{sign}{value * 100:.2f}%"


if __name__ == "__main__":
    main()
