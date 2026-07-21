"""Filter retrieved context by deterministic user permissions."""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.core.permission_guard import filter_authorized_context


async def filter_permission_context(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    """Remove unauthorized metadata before it is exposed to SQL generation."""

    writer = runtime.stream_writer
    step = "过滤权限上下文"
    writer({"type": "progress", "step": step, "status": "running"})

    permission_context = state.get("permission_context")
    result = filter_authorized_context(
        table_infos=state.get("table_infos", []),
        metric_infos=state.get("metric_infos", []),
        permission_context=permission_context,
    )

    logger.info(
        f"权限过滤后的表信息：{[table_info['name'] for table_info in result.table_infos]}"
    )
    logger.info(
        f"权限过滤后的指标信息：{[metric_info['name'] for metric_info in result.metric_infos]}"
    )
    writer({"type": "progress", "step": step, "status": "success"})
    return {
        "table_infos": result.table_infos,
        "metric_infos": result.metric_infos,
    }
