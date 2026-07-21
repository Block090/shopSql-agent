"""
SQL 校正失败节点

当 SQL 多次校正后仍然无法通过校验时，停止继续重试并向前端返回友好提示。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def fail_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """SQL 校正超过上限后的降级出口"""

    writer = runtime.stream_writer
    step = "SQL校正失败"
    retry_count = state.get("retry_count", 0)
    error = state.get("error")

    # 这里不再继续调用模型，避免在错误上下文中无限修正浪费 token。
    logger.warning(f"SQL校正失败，已重试 {retry_count} 次，最后错误：{error}")
    writer({"type": "progress", "step": step, "status": "error"})
    writer(
        {
            "type": "error",
            "message": "SQL 多次校正后仍未通过校验，请换一种问法或联系管理员。",
        }
    )
