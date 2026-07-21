"""
电商问数 Agent 分层测评执行入口
"""

import argparse
import json
from pathlib import Path

from eval.io import load_jsonl, write_json, write_text
from eval.metrics.layered_report_metrics import (
    aggregate_layered_results,
    evaluate_layered_case,
)
from eval.report import render_markdown_report
from eval.runners.live_agent_trace import (
    DEFAULT_CASE_TIMEOUT_SECONDS,
    collect_live_traces,
)
from eval.schemas.agent_trace import AgentTrace
from eval.schemas.eval_case import EvalCase

DEFAULT_DATASET_PATH = Path("eval/datasets/query_eval_cases.jsonl")
DEFAULT_TRACE_PATH = Path("eval/reports/query_eval_traces.json")
DEFAULT_RESULT_PATH = Path("eval/reports/query_eval_result.json")
DEFAULT_REPORT_PATH = Path("eval/reports/query_eval_report.md")


def run_offline_eval(
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
    trace_path: str | Path = DEFAULT_TRACE_PATH,
    result_path: str | Path = DEFAULT_RESULT_PATH,
    report_path: str | Path = DEFAULT_REPORT_PATH,
    suite: str = "all",
) -> dict:
    """基于离线 trace 执行新版分层测评"""

    cases = _select_cases(
        [EvalCase.from_dict(case).to_dict() for case in load_jsonl(dataset_path)],
        suite,
    )
    traces = _load_trace_map(trace_path)

    results = []
    for case in cases:
        trace = AgentTrace.from_dict(traces.get(case["id"], {})).to_dict()
        results.append(evaluate_layered_case(case, trace))

    summary = aggregate_layered_results(results)
    write_json(result_path, {"summary": summary, "results": results})
    write_text(report_path, render_markdown_report(summary, results))
    return summary


def run_live_eval(
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
    trace_path: str | Path = DEFAULT_TRACE_PATH,
    result_path: str | Path = DEFAULT_RESULT_PATH,
    report_path: str | Path = DEFAULT_REPORT_PATH,
    suite: str = "all",
    case_timeout_seconds: float = DEFAULT_CASE_TIMEOUT_SECONDS,
) -> dict:
    """执行真实 Agent 分层测评：先采集 trace，再生成指标报告"""

    import asyncio

    cases = _select_cases(load_jsonl(dataset_path), suite)
    traces = asyncio.run(
        collect_live_traces(cases, case_timeout_seconds=case_timeout_seconds)
    )
    write_json(trace_path, traces)
    return run_offline_eval(
        dataset_path=dataset_path,
        trace_path=trace_path,
        result_path=result_path,
        report_path=report_path,
        suite=suite,
    )


def main() -> None:
    """命令行入口"""

    parser = argparse.ArgumentParser(description="运行电商问数 Agent 分层测评")
    parser.add_argument(
        "--live",
        action="store_true",
        help="调用真实 Agent 采集 trace 后再生成评测报告",
    )
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--trace", default=str(DEFAULT_TRACE_PATH))
    parser.add_argument("--result", default=str(DEFAULT_RESULT_PATH))
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument(
        "--suite",
        default="all",
        help="运行 all、core 或用例中声明的其他 suite",
    )
    parser.add_argument(
        "--case-timeout",
        type=float,
        default=DEFAULT_CASE_TIMEOUT_SECONDS,
        help="live 测评单条用例最大等待秒数，超时后记录 case_timeout 并继续下一条",
    )
    args = parser.parse_args()

    if args.live:
        summary = run_live_eval(
            dataset_path=args.dataset,
            trace_path=args.trace,
            result_path=args.result,
            report_path=args.report,
            suite=args.suite,
            case_timeout_seconds=args.case_timeout,
        )
    else:
        summary = run_offline_eval(
            dataset_path=args.dataset,
            trace_path=args.trace,
            result_path=args.result,
            report_path=args.report,
            suite=args.suite,
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _load_trace_map(path: str | Path) -> dict:
    """读取 trace 映射，格式为 {case_id: trace}"""

    trace_path = Path(path)
    if not trace_path.exists():
        return {}
    return json.loads(trace_path.read_text(encoding="utf-8"))


def _select_cases(cases: list[dict], suite: str) -> list[dict]:
    if not suite or suite == "all":
        return cases
    return [
        case
        for case in cases
        if case.get("suite", "core") == suite or suite in case.get("tags", [])
    ]


if __name__ == "__main__":
    main()
