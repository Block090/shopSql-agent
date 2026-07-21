"""
召回结果检查节点

在表和指标过滤完成后检查候选上下文是否足够支撑 SQL 生成。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.domain_coverage import evaluate_domain_coverage
from app.core.log import logger


async def check_recall_result(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    """记录过滤后的召回结果，具体路由由 graph.py 的条件边决定"""

    writer = runtime.stream_writer
    step = "检查召回结果"
    writer({"type": "progress", "step": step, "status": "running"})

    table_infos = state.get("table_infos", [])
    metric_infos = state.get("metric_infos", [])
    decision = evaluate_domain_coverage(
        query=state.get("query", ""),
        table_infos=table_infos,
        metric_infos=metric_infos,
    )

    # 这里不直接返回拒答结果，只记录信息；是否拒答交给图路由统一控制。
    logger.info(
        f"召回结果检查：候选表数量={len(table_infos)}，候选指标数量={len(metric_infos)}，"
        f"supported={decision['supported']}，reason={decision['reason']}"
    )
    writer({"type": "progress", "step": step, "status": "success"})
    return {"recall_decision": decision}
