"""
数据变更影响范围评估节点

只执行 SELECT COUNT 和 SELECT ... LIMIT 预览 SQL，绝不执行 DML。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState


async def estimate_operation_impact(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    """执行只读影响范围 SQL，得到影响行数和样例数据"""

    writer = runtime.stream_writer
    writer({"type": "progress", "step": "评估影响范围", "status": "running"})

    plan = state.get("operation_plan", {})
    impact_count = 0
    preview_rows = []
    dw_mysql_repository = _get_dw_mysql_repository(runtime.context)

    # INSERT 第一版不执行预览 SQL，只返回待审批方案。
    if plan.get("impact_count_sql"):
        count_rows = await dw_mysql_repository.run(plan["impact_count_sql"])
        if count_rows:
            impact_count = int(count_rows[0].get("impact_count", 0))

    if plan.get("impact_preview_sql"):
        preview_rows = await dw_mysql_repository.run(plan["impact_preview_sql"])

    writer({"type": "progress", "step": "评估影响范围", "status": "success"})
    return {
        "impact_count": impact_count,
        "impact_preview_rows": preview_rows,
    }


def _get_dw_mysql_repository(context):
    """兼容 LangGraph 真实 dict context 和单测对象 context 两种形态"""

    if isinstance(context, dict):
        return context["dw_mysql_repository"]
    return context.dw_mysql_repository
