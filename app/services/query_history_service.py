"""带查询历史和多轮上下文的问数服务。"""

import json
import re
import uuid

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.agent.context import DataAgentContext
from app.agent.graph import graph as default_graph
from app.agent.state import DataAgentState
from app.core.business_insights import (
    build_empty_result_diagnosis,
    build_followup_suggestions,
    classify_query_risk,
)
from app.core.context_rewrite.llm_rewriter import rewrite_query_with_llm_or_rule
from app.core.frontend_payload_safety import (
    business_label,
    sanitize_frontend_payload,
    sanitize_frontend_text,
)
from app.core.permission_policy import get_permission_context
from app.core.query_case_memory import build_query_case, build_query_case_text
from app.core.query_explanation import build_query_explanation
from app.core.result_productization import analyze_result_with_fallback
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.mysql.meta.query_history_repository import QueryHistoryRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

MAX_HISTORY_RESULT_ROWS = 100


class QueryService:
    """封装一次问数查询所需的业务编排逻辑。"""

    def __init__(
        self,
        meta_mysql_repository: MetaMySQLRepository,
        query_history_repository: QueryHistoryRepository,
        embedding_client: HuggingFaceEndpointEmbeddings,
        dw_mysql_repository: DWMySQLRepository,
        column_qdrant_repository: ColumnQdrantRepository,
        metric_qdrant_repository: MetricQdrantRepository,
        value_es_repository: ValueESRepository,
        graph=default_graph,
        context_rewriter=rewrite_query_with_llm_or_rule,
        result_analyzer=analyze_result_with_fallback,
        query_case_repository=None,
    ):
        self.meta_mysql_repository = meta_mysql_repository
        self.query_history_repository = query_history_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_es_repository = value_es_repository
        self.graph = graph
        self.context_rewriter = context_rewriter
        self.result_analyzer = result_analyzer
        self.query_case_repository = query_case_repository

    async def list_sessions(self) -> list[dict]:
        """查询最近会话列表。"""

        await self.query_history_repository.ensure_tables()
        return await self.query_history_repository.list_sessions()

    async def get_session_history(self, session_id: str) -> list[dict]:
        """查询指定会话的历史记录。"""

        await self.query_history_repository.ensure_tables()
        return await self.query_history_repository.get_session_history(session_id)

    async def delete_session(self, session_id: str) -> dict:
        """删除一个历史会话及其全部查询记录。"""

        await self.query_history_repository.ensure_tables()
        await self.query_history_repository.delete_session(session_id)
        return {"deleted": True, "session_id": session_id}

    async def query(
        self, query: str, session_id: str | None = None, user_id: str | None = None
    ):
        """执行一次问数工作流，并逐段产出 SSE 消息。"""

        current_session_id = session_id or uuid.uuid4().hex
        try:
            await self.query_history_repository.ensure_tables()
            await self.query_history_repository.create_or_touch_session(
                current_session_id, title=query[:80]
            )
            recent_turns = await self.query_history_repository.get_recent_turns(
                current_session_id, limit=3
            )
        except Exception as exc:
            # 中文注释：历史模块异常不能再变成 200 空响应，必须让前端看到错误。
            error_message = sanitize_frontend_text(format_user_error_message(exc))
            yield to_sse({"type": "error", "message": error_message})
            return

        # 中文注释：Agent 内部使用补全后的问题，同时保留上下文轨迹给前端解释展示。
        rewrite_result = await self.context_rewriter(query, recent_turns)
        resolved_query = rewrite_result.resolved_query
        context_trace = rewrite_result.context_trace

        state = DataAgentState(
            query=resolved_query,
            semantic_slots=rewrite_result.semantic_slots,
            similar_query_cases=[],
            permission_context=get_permission_context(user_id),
        )
        context = DataAgentContext(
            column_qdrant_repository=self.column_qdrant_repository,
            embedding_client=self.embedding_client,
            metric_qdrant_repository=self.metric_qdrant_repository,
            value_es_repository=self.value_es_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository,
            query_case_repository=self.query_case_repository,
        )

        final_status = "failed"
        result_summary = None
        result_data = None
        result_facts = None
        result_analysis = None
        query_explanation = None
        metric_infos = None
        error_message = None
        sql = None

        yield to_sse({"type": "session", "session_id": current_session_id})
        if rewrite_result.is_follow_up:
            yield to_sse({"type": "context_trace", "data": context_trace})

        if rewrite_result.needs_clarification:
            final_status = "clarification_required"
            result_summary = rewrite_result.clarification_question
            yield to_sse(
                {
                    "type": "clarification",
                    "message": rewrite_result.clarification_question,
                    "options": ["是，按这个查询", "不是，我重新描述"],
                    "clarification_type": "context_rewrite",
                }
            )
            await self.query_history_repository.save_history(
                session_id=current_session_id,
                query=query,
                resolved_query=resolved_query,
                sql=sql,
                result_summary=result_summary,
                status=final_status,
                error_message=error_message,
                result_data=result_data,
                context_trace=context_trace,
                result_facts=result_facts,
                result_analysis=result_analysis,
                semantic_slots=rewrite_result.semantic_slots,
                rewrite_confidence=rewrite_result.confidence,
            )
            return

        try:
            # 中文注释：custom 继续给前端展示，values 只用于记录最终 SQL。
            async for chunk in self.graph.astream(
                input=state,
                context=context,
                stream_mode=["custom", "values"],
            ):
                mode, payload = unpack_stream_chunk(chunk)
                if mode == "values":
                    if isinstance(payload, dict):
                        sql = payload.get("sql") or sql
                        metric_infos = payload.get("metric_infos") or metric_infos
                    continue

                if not isinstance(payload, dict):
                    continue

                event = payload
                if event.get("type") == "result":
                    safe_result = sanitize_frontend_payload(event.get("data"))
                    event = {**event, "data": safe_result}
                    final_status = "success"
                    result_summary = summarize_result(safe_result)
                    result_data = limit_history_result_rows(safe_result)
                elif event.get("type") == "clarification":
                    final_status = "clarification_required"
                    result_summary = sanitize_frontend_text(event.get("message"))
                    event = {**event, "message": result_summary}
                elif event.get("type") == "operation_plan":
                    final_status = "operation_plan"
                    operation_data = event.get("data") or {}
                    result_summary = summarize_operation_plan(operation_data)
                    sql = operation_data.get("impact_preview_sql") or sql
                elif event.get("type") == "error":
                    final_status = "failed"
                    error_message = sanitize_frontend_text(event.get("message"))
                    result_summary = error_message
                    event = {**event, "message": error_message}

                yield to_sse(event)
                if event.get("type") == "result":
                    try:
                        result_analysis = await self.result_analyzer(
                            query=query,
                            resolved_query=resolved_query,
                            result_data=result_data,
                        )
                        result_facts = result_analysis.get("result_facts")
                    except Exception:
                        # 中文注释：结果分析是增强能力，不能影响原始查询结果返回。
                        result_analysis = None
                        result_facts = None

                    if result_analysis:
                        yield to_sse({"type": "result_analysis", "data": result_analysis})

                    risk = classify_query_risk(
                        sql=sql,
                        result_data=result_data,
                        result_facts=result_facts,
                    )
                    query_explanation = build_query_explanation(
                        query=query,
                        resolved_query=resolved_query,
                        sql=sql,
                        result_summary=result_summary,
                        result_analysis=result_analysis,
                        semantic_slots=rewrite_result.semantic_slots,
                        metric_infos=metric_infos,
                        risk=risk,
                    )
                    yield to_sse(
                        {"type": "query_explanation", "data": query_explanation}
                    )
                    if result_data == []:
                        yield to_sse(
                            {
                                "type": "empty_result_diagnosis",
                                "data": build_empty_result_diagnosis(
                                    query=query,
                                    resolved_query=resolved_query,
                                    semantic_slots=rewrite_result.semantic_slots,
                                ),
                            }
                        )
                    elif result_analysis:
                        yield to_sse(
                            {
                                "type": "followup_suggestions",
                                "data": build_followup_suggestions(
                                    query=query,
                                    resolved_query=resolved_query,
                                    result_analysis=result_analysis,
                                ),
                            }
                        )
            if final_status == "failed" and result_summary is None and error_message is None:
                error_message = "流程执行结束，但没有生成可展示的查询结果，请查看后端日志定位具体节点。"
                result_summary = error_message
                yield to_sse({"type": "error", "message": error_message})
        except Exception as exc:
            error_message = sanitize_frontend_text(format_user_error_message(exc))
            result_summary = error_message
            yield to_sse({"type": "error", "message": error_message})
        finally:
            if (
                final_status == "success"
                and sql
                and result_data
                and self.query_case_repository
            ):
                try:
                    query_case = build_query_case(
                        query=query,
                        resolved_query=resolved_query,
                        sql=sql,
                        semantic_slots=rewrite_result.semantic_slots,
                        result_summary=result_summary,
                    )
                    query_case_text = build_query_case_text(query_case)
                    query_case_embedding = await self.embedding_client.aembed_query(
                        query_case_text
                    )
                    await self.query_case_repository.upsert_query_case(
                        query_case, query_case_embedding
                    )
                except Exception:
                    # Query Case 是增强记忆能力，失败不能影响主查询和历史保存。
                    pass

            await self.query_history_repository.save_history(
                session_id=current_session_id,
                query=query,
                resolved_query=resolved_query,
                sql=sql,
                result_summary=result_summary,
                status=final_status,
                error_message=error_message,
                result_data=result_data,
                context_trace=context_trace,
                result_facts=result_facts,
                result_analysis=result_analysis,
                semantic_slots=rewrite_result.semantic_slots,
                rewrite_confidence=rewrite_result.confidence,
            )


def to_sse(event: dict) -> str:
    """把后端事件包装成 SSE 文本。"""

    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


def format_user_error_message(exc: Exception) -> str:
    """把底层异常转换成用户能理解的错误原因，避免直接暴露英文堆栈或文档链接。"""

    raw_message = str(exc)
    if "permission denied" in raw_message.lower():
        return "权限校验未通过"
    if "502 Bad Gateway" in raw_message:
        target = _extract_error_target(raw_message)
        if target:
            return (
                f"后端调用下游服务失败：本次查询依赖的本地服务 {target} 返回 502。"
                "请检查对应服务是否已启动、端口是否正确，或稍后重试。"
            )
        return "后端调用下游服务失败：下游服务返回 502，请检查相关服务是否已启动后重试。"
    if "Connection refused" in raw_message or "WinError 10061" in raw_message:
        return "后端连接下游服务失败：目标服务未启动或端口不可用，请检查本地依赖服务。"
    if not raw_message:
        return "流程执行失败：后端没有返回明确错误原因，请查看后端日志。"
    return raw_message


def _extract_error_target(message: str) -> str | None:
    """从 httpx 等异常文本中提取 host:port，避免把完整 URL 和外部链接展示给用户。"""

    match = re.search(r"https?://([^/'\"\s]+)", message)
    if not match:
        return None
    return match.group(1)


def unpack_stream_chunk(chunk) -> tuple[str, dict]:
    """兼容 LangGraph 多 stream_mode 的二元组和三元组返回格式。"""

    if (
        isinstance(chunk, tuple)
        and len(chunk) == 2
        and chunk[0] in {"custom", "values"}
    ):
        return chunk
    if (
        isinstance(chunk, tuple)
        and len(chunk) == 3
        and chunk[1] in {"custom", "values"}
    ):
        return chunk[1], chunk[2]
    return "custom", chunk


def summarize_result(data) -> str:
    """生成轻量结果摘要，避免把完整大结果写入历史表。"""

    if isinstance(data, list):
        if not data:
            return "返回 0 行"
        first_row = data[0]
        if isinstance(first_row, dict):
            columns = [business_label(key) for key in first_row]
            return f"返回 {len(data)} 行，字段：{'、'.join(columns)}"
        return f"返回 {len(data)} 行"
    if isinstance(data, dict):
        columns = [business_label(key) for key in data]
        return f"返回对象，字段：{'、'.join(columns)}"
    return "查询已返回结果"


def limit_history_result_rows(data):
    """历史表只保存前 100 行表格结果，避免结果过大。"""

    if isinstance(data, list):
        return data[:MAX_HISTORY_RESULT_ROWS]
    return data


def summarize_operation_plan(data: dict) -> str:
    """生成数据变更审批计划摘要。"""

    operation_type = data.get("operation_type") or "数据变更"
    impact_count = data.get("impact_count")
    if impact_count is None:
        return f"生成{operation_type}操作计划，需要审批后才能执行"
    return f"生成{operation_type}操作计划，预计影响 {impact_count} 行，需要审批后才能执行"
