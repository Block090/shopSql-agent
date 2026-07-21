"""
真实 Agent trace 采集

读取评测用例后逐条调用 LangGraph，并把最终 state 与 stream 事件转换成评测 trace。
"""

import asyncio
from collections.abc import AsyncIterator
from time import perf_counter

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import (
    dw_mysql_client_manager,
    meta_mysql_client_manager,
)
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.core.permission_policy import get_permission_context
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from eval.trace import build_trace_from_state

DEFAULT_CASE_TIMEOUT_SECONDS = 120


async def consume_graph_stream(stream: AsyncIterator) -> dict:
    """消费 LangGraph 多模式 stream，整理成单条评测 trace"""

    events = []
    latest_state = {}
    started_at = perf_counter()
    node_started_at = {}
    node_latency_ms = {}
    model_call_count = 0

    async for chunk in stream:
        mode, payload = _unpack_stream_chunk(chunk)
        if mode == "custom":
            events.append(payload)
            if isinstance(payload, dict) and payload.get("type") == "progress":
                step = str(payload.get("step", ""))
                status = payload.get("status")
                now = perf_counter()
                if status == "running":
                    node_started_at[step] = now
                    if step in MODEL_CALL_STEPS:
                        model_call_count += 1
                elif status in {"success", "error"} and step in node_started_at:
                    elapsed = round((now - node_started_at.pop(step)) * 1000, 3)
                    node_latency_ms[step] = round(
                        node_latency_ms.get(step, 0.0) + elapsed, 3
                    )
        elif mode == "values":
            latest_state = payload

    performance = {
        "latency_ms": round((perf_counter() - started_at) * 1000, 3),
        "node_latency_ms": node_latency_ms,
        "model_call_count": model_call_count,
    }
    return build_trace_from_state(latest_state, events, performance=performance)


MODEL_CALL_STEPS = {
    "抽取关键词",
    "召回字段信息",
    "召回指标信息",
    "召回字段取值",
    "过滤指标信息",
    "过滤表信息",
    "生成SQL",
    "校正SQL",
}


async def run_agent_case(
    case: str | dict,
    context: DataAgentContext,
    case_timeout_seconds: float = DEFAULT_CASE_TIMEOUT_SECONDS,
) -> dict:
    """执行单条真实 Agent 查询并返回 trace"""

    case_data = case if isinstance(case, dict) else {"query": case}
    query = case_data.get("resolved_query") or case_data.get("query", "")
    permission_context = case_data.get("permission_context") or get_permission_context(
        case_data.get("user_id")
    )
    state = DataAgentState(
        query=query,
        semantic_slots=case_data.get("semantic_slots", {}),
        similar_query_cases=[],
        permission_context=permission_context,
    )
    started_at = perf_counter()
    try:
        stream = graph.astream(
            input=state,
            context=context,
            stream_mode=["custom", "values"],
        )
        return await asyncio.wait_for(
            consume_graph_stream(stream),
            timeout=case_timeout_seconds,
        )
    except TimeoutError:
        case_id = case_data.get("id", "unknown")
        return {
            "retrieved_columns": [],
            "retrieved_metrics": [],
            "retrieved_values": [],
            "table_infos": [],
            "sql": "",
            "final_status": "failed",
            "error_type": "case_timeout",
            "error_message": f"case_timeout: {case_id} exceeded {case_timeout_seconds}s",
            "execution": {
                "final_status": "failed",
                "error_type": "case_timeout",
                "latency_ms": round((perf_counter() - started_at) * 1000, 3),
            },
        }
    except Exception as exc:
        # 真实评测不能因为单条失败中断整批，用 failed trace 记录原因。
        return {
            "retrieved_columns": [],
            "retrieved_metrics": [],
            "retrieved_values": [],
            "table_infos": [],
            "sql": "",
            "final_status": "failed",
            "error_type": "runtime_error",
            "error_message": str(exc),
            "execution": {
                "final_status": "failed",
                "error_type": "runtime_error",
                "latency_ms": round((perf_counter() - started_at) * 1000, 3),
            },
        }


async def collect_live_traces(
    cases: list[dict],
    case_timeout_seconds: float = DEFAULT_CASE_TIMEOUT_SECONDS,
) -> dict:
    """初始化外部依赖，逐条执行评测用例并采集真实 trace"""

    _init_clients()
    try:
        async with (
            meta_mysql_client_manager.session_factory() as meta_session,
            dw_mysql_client_manager.session_factory() as dw_session,
        ):
            context = DataAgentContext(
                column_qdrant_repository=ColumnQdrantRepository(
                    qdrant_client_manager.client
                ),
                embedding_client=embedding_client_manager.client,
                metric_qdrant_repository=MetricQdrantRepository(
                    qdrant_client_manager.client
                ),
                value_es_repository=ValueESRepository(es_client_manager.client),
                meta_mysql_repository=MetaMySQLRepository(meta_session),
                dw_mysql_repository=DWMySQLRepository(dw_session),
            )

            traces = {}
            total = len(cases)
            for index, case in enumerate(cases, start=1):
                case_id = case["id"]
                print(f"[eval] running {index}/{total}: {case_id} - {case.get('query', '')}")
                traces[case_id] = await run_agent_case(
                    case,
                    context,
                    case_timeout_seconds=case_timeout_seconds,
                )
                status = traces[case_id].get("execution", {}).get("final_status")
                print(f"[eval] finished {index}/{total}: {case_id} - {status}")
            return traces
    finally:
        await _close_clients()


def _unpack_stream_chunk(chunk) -> tuple[str, dict]:
    """兼容 LangGraph 多 stream 模式和测试中的简化输入"""

    if isinstance(chunk, tuple) and len(chunk) == 2:
        return chunk
    return "custom", chunk


def _init_clients() -> None:
    """按应用启动流程初始化外部客户端"""

    qdrant_client_manager.init()
    embedding_client_manager.init()
    es_client_manager.init()
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()


async def _close_clients() -> None:
    """释放真实评测过程中打开的外部连接"""

    await qdrant_client_manager.close()
    await es_client_manager.close()
    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
