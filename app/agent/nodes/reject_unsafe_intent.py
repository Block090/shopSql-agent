"""
危险操作意图拒答节点

当前系统只支持只读数据分析，命中删除 修改 写入等意图时直接结束流程。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def reject_unsafe_intent(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    """危险写操作意图的统一拒答出口"""

    writer = runtime.stream_writer
    step = "拒绝危险操作"

    # 这里不做二次生成，也不把危险意图改写成 SELECT，避免语义被静默改变。
    logger.warning(f"检测到危险操作意图，已拒绝。query={state.get('query')}")
    writer({"type": "progress", "step": step, "status": "error"})
    writer(
        {
            "type": "error",
            "message": (
                "当前系统仅支持只读数据分析，不能执行删除、修改、插入、"
                "清空等写操作。请改为查询或统计类问题。"
            ),
        }
    )
