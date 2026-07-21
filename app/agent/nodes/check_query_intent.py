"""
用户意图安全检查节点

在生成 SQL 前识别删除 修改 写入等危险操作意图，避免把写操作请求改写成 SELECT。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.core.operation_intent_guard import classify_operation_intent


async def check_query_intent(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    """检查用户问题是否属于只读问数范围"""

    writer = runtime.stream_writer
    step = "检查用户意图"
    query = state.get("query", "")
    operation_intent = classify_operation_intent(query)
    is_unsafe_intent = operation_intent["intent_type"] == "dangerous"

    # 结构级高危操作仍然拒绝；普通 DML 进入审批方案链路，不直接执行。
    logger.info(
        "用户意图检查完成，"
        f"intent_type={operation_intent['intent_type']}，"
        f"operation_type={operation_intent['operation_type']}，query={query}"
    )
    writer({"type": "progress", "step": step, "status": "success"})

    return {
        "is_unsafe_intent": is_unsafe_intent,
        "operation_intent": operation_intent["intent_type"] == "operation",
        "operation_type": operation_intent["operation_type"],
    }
