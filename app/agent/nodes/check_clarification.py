"""
业务口径澄清检查节点

在关键词抽取和召回前判断问题是否存在关键业务口径不明确的情况。
如果需要追问，本轮流程会提前结束，不生成 SQL。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.clarification_guard import check_clarification_need
from app.core.log import logger


async def check_clarification(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    """检查用户问题是否需要先追问业务口径"""

    writer = runtime.stream_writer
    step = "检查业务口径"
    query = state.get("query", "")
    clarification = check_clarification_need(query)

    logger.info(
        "业务口径检查完成，"
        f"required={clarification['required']}，type={clarification['type']}，query={query}"
    )
    writer({"type": "progress", "step": step, "status": "success"})

    return {
        "clarification_required": clarification["required"],
        "clarification_question": clarification["question"],
        "clarification_options": clarification["options"],
        "clarification_type": clarification["type"],
        "clarification_missing_slots": clarification["missing_slots"],
    }
