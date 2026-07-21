"""
业务口径追问节点

当问题缺少关键业务口径时，直接把追问问题返回前端。
这个节点不会生成 SQL，也不会访问数据库。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState


async def ask_clarification(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    """向前端返回口径追问事件"""

    writer = runtime.stream_writer
    step = "确认业务口径"

    # 追问阶段明确结束本轮问数链路，避免在口径不清时继续生成 SQL。
    writer({"type": "progress", "step": step, "status": "success"})
    writer(
        {
            "type": "clarification",
            "message": state.get("clarification_question", ""),
            "options": state.get("clarification_options", []),
            "clarification_type": state.get("clarification_type", ""),
            "missing_slots": state.get("clarification_missing_slots", []),
        }
    )
