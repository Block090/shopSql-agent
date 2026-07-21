"""在进入 RAG 前检查显式不支持的数据主题。"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.business_lexicon import get_unsupported_concepts


async def check_domain_boundary(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    writer = runtime.stream_writer
    step = "检查数据领域"
    writer({"type": "progress", "step": step, "status": "running"})

    unsupported = get_unsupported_concepts(state.get("query", ""))
    decision = {
        "supported": False if unsupported else None,
        "reason": "unsupported_domain_concept" if unsupported else "pending_retrieval",
        "missing_concepts": unsupported,
    }

    writer({"type": "progress", "step": step, "status": "success"})
    return {"recall_decision": decision}
