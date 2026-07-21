"""
生成数据变更审批方案节点

节点只生成拟定 DML 文本和只读影响范围 SQL，不执行任何写操作。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.operation_plan import build_operation_plan


async def generate_operation_plan(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    """生成结构化变更计划"""

    writer = runtime.stream_writer
    writer({"type": "progress", "step": "生成变更方案", "status": "running"})

    # 这里的 planned_sql 仅用于审批展示，不会进入数据库执行。
    plan = build_operation_plan(
        state.get("query", ""),
        state.get("operation_type", ""),
    )

    writer({"type": "progress", "step": "生成变更方案", "status": "success"})
    return {
        "operation_plan": plan,
        "risk_level": plan.get("risk_level", ""),
        "approval_required": plan.get("requires_approval", True),
    }
