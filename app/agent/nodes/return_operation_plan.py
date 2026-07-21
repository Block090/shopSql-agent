"""
返回数据变更审批卡片节点

把变更计划、影响行数和预览数据返回前端，默认不执行写 SQL。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.operation_plan import enrich_operation_governance


async def return_operation_plan(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    """向前端输出 operation_plan 事件"""

    writer = runtime.stream_writer
    plan = dict(state.get("operation_plan", {}))

    # 审批卡片携带影响范围，但不提供“直接执行”能力。
    plan.update(
        {
            "impact_count": state.get("impact_count", 0),
            "preview_rows": state.get("impact_preview_rows", []),
            "execution_enabled": False,
        }
    )
    plan = enrich_operation_governance(
        plan,
        query=state.get("query", ""),
        impact_count=plan["impact_count"],
        preview_rows=plan["preview_rows"],
    )
    plan["status"] = plan.get("approval_status", "pending")

    writer({"type": "progress", "step": "等待审批确认", "status": "success"})
    writer({"type": "operation_plan", "data": plan})
