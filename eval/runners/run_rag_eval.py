"""
RAG 评测执行入口

第一版先支持离线 trace 评测：
1. 从 JSONL 读取人工标注用例；
2. 从 JSON 读取每个用例对应的 Agent trace；
3. 计算指标；
4. 输出 JSON 明细和 Markdown 报告。
"""

import argparse
import json
from pathlib import Path

from eval.io import load_jsonl, write_json, write_text
from eval.metrics.report_metrics import aggregate_results, evaluate_case
from eval.report import render_markdown_report
from eval.runners.live_agent_trace import collect_live_traces

DEFAULT_DATASET_PATH = Path("eval/datasets/rag_eval_cases.jsonl")
DEFAULT_TRACE_PATH = Path("eval/reports/rag_eval_traces.json")
DEFAULT_RESULT_PATH = Path("eval/reports/rag_eval_result.json")
DEFAULT_REPORT_PATH = Path("eval/reports/rag_eval_report.md")


def run_offline_eval(
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
    trace_path: str | Path = DEFAULT_TRACE_PATH,
    result_path: str | Path = DEFAULT_RESULT_PATH,
    report_path: str | Path = DEFAULT_REPORT_PATH,
) -> dict:
    """基于离线 trace 执行评测，适合先验证指标和报告链路"""

    cases = load_jsonl(dataset_path)
    traces = _load_trace_map(trace_path)

    results = []
    for case in cases:
        trace = traces.get(case["id"], {})
        results.append(evaluate_case(case, trace))

    summary = aggregate_results(results)
    write_json(result_path, {"summary": summary, "results": results})
    write_text(report_path, render_markdown_report(summary, results))
    return summary


def run_live_eval(
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
    trace_path: str | Path = DEFAULT_TRACE_PATH,
    result_path: str | Path = DEFAULT_RESULT_PATH,
    report_path: str | Path = DEFAULT_REPORT_PATH,
) -> dict:
    """执行真实 Agent 评测：先采集 trace，再生成指标报告"""

    import asyncio

    cases = load_jsonl(dataset_path)
    traces = asyncio.run(collect_live_traces(cases))
    write_json(trace_path, traces)
    return run_offline_eval(
        dataset_path=dataset_path,
        trace_path=trace_path,
        result_path=result_path,
        report_path=report_path,
    )


def main() -> None:
    """命令行入口"""

    parser = argparse.ArgumentParser(description="运行 RAG 离线评测")
    parser.add_argument(
        "--live",
        action="store_true",
        help="调用真实 Agent 采集 trace 后再生成评测报告",
    )
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--trace", default=str(DEFAULT_TRACE_PATH))
    parser.add_argument("--result", default=str(DEFAULT_RESULT_PATH))
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()

    run_eval = run_live_eval if args.live else run_offline_eval
    summary = run_eval(
        dataset_path=args.dataset,
        trace_path=args.trace,
        result_path=args.result,
        report_path=args.report,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _load_trace_map(path: str | Path) -> dict:
    """读取 trace 映射，格式为 {case_id: trace}"""

    trace_path = Path(path)
    if not trace_path.exists():
        return {}
    return json.loads(trace_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
