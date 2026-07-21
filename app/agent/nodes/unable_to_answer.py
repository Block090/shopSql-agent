"""
无法回答节点

当召回和过滤后没有可靠候选表时，提前结束流程，避免硬凑 SQL。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def unable_to_answer(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    """召回结果不足时的友好拒答出口"""

    writer = runtime.stream_writer
    step = "无法回答"

    # 没有候选表时继续生成 SQL 容易答非所问，因此直接给出明确提示。
    logger.info(f"召回结果不足，拒答。query={state.get('query')}")
    decision = state.get("recall_decision") or {}
    missing_concepts = decision.get("missing_concepts", [])
    writer({"type": "progress", "step": step, "status": "error"})
    writer(
        {
            "type": "unable_to_answer",
            "status": "unable_to_answer",
            "reason": decision.get("reason", "no_recall_context"),
            "missing_concepts": missing_concepts,
            "suggestion": "请补充对应数据源或改用当前电商数仓已支持的指标和维度。",
        }
    )
    writer(
        {
            "type": "error",
            "message": (
                "当前数据知识库中没有找到足够相关的信息，"
                "无法可靠回答该问题。请换一种问法，或确认该问题是否属于当前电商数据范围。"
            ),
        }
    )
