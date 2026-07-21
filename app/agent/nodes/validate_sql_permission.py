"""Validate generated SQL against user data permissions."""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.core.permission_guard import validate_sql_permission as validate_permission


async def validate_sql_permission(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    """Check whether the generated SQL is allowed for the current user."""

    writer = runtime.stream_writer
    step = "校验查询权限"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        validate_permission(
            sql=state.get("sql", ""),
            permission_context=state.get("permission_context"),
        )
        logger.info("SQL 权限校验通过")
        writer({"type": "progress", "step": step, "status": "success"})
        return {"permission_error": None}
    except Exception as exc:
        logger.info(f"SQL 权限校验失败：{exc}")
        writer({"type": "progress", "step": step, "status": "error"})
        return {"permission_error": str(exc)}
