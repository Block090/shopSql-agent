"""Return a user-facing message when a query violates data permissions."""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def reject_permission_denied(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    """Stop execution when SQL permission validation fails."""

    writer = runtime.stream_writer
    message = state.get("permission_error") or "当前账号没有权限执行该查询。"
    logger.warning(f"权限校验未通过，已拒绝执行。reason={message}")
    writer(
        {
            "type": "error",
            "message": "权限校验未通过",
            "error_type": "permission_denied",
        }
    )
    return {}
