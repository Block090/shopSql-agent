"""
电商问数 Agent 图编排

使用 LangGraph 把问数智能体的各个节点串成一条可观测的执行链路
当前链路已经落地关键词抽取和多路召回，字段和指标走 Qdrant 向量检索，字段取值走 ES 全文检索
整体流程先抽取用户问题关键词，再并行召回字段 字段取值和指标信息，
随后合并召回结果 过滤候选表和指标 补充额外上下文，最后生成 校验 修正并执行 SQL
"""

import asyncio

from langgraph.constants import END, START
from langgraph.graph import StateGraph

from app.agent.context import DataAgentContext
from app.agent.nodes.add_extra_context import add_extra_context
from app.agent.nodes.ask_clarification import ask_clarification
from app.agent.nodes.check_clarification import check_clarification
from app.agent.nodes.check_domain_boundary import check_domain_boundary
from app.agent.nodes.check_query_intent import check_query_intent
from app.agent.nodes.check_recall_result import check_recall_result
from app.agent.nodes.correct_sql import correct_sql
from app.agent.nodes.estimate_operation_impact import estimate_operation_impact
from app.agent.nodes.extract_keywords import extract_keywords
from app.agent.nodes.fail_sql import fail_sql
from app.agent.nodes.filter_metric import filter_metric
from app.agent.nodes.filter_permission_context import filter_permission_context
from app.agent.nodes.filter_table import filter_table
from app.agent.nodes.generate_operation_plan import generate_operation_plan
from app.agent.nodes.generate_sql import generate_sql
from app.agent.nodes.merge_retrieved_info import merge_retrieved_info
from app.agent.nodes.recall_column import recall_column
from app.agent.nodes.recall_metric import recall_metric
from app.agent.nodes.recall_value import recall_value
from app.agent.nodes.reject_permission_denied import reject_permission_denied
from app.agent.nodes.reject_unsafe_intent import reject_unsafe_intent
from app.agent.nodes.return_operation_plan import return_operation_plan
from app.agent.nodes.run_sql import run_sql
from app.agent.nodes.unable_to_answer import unable_to_answer
from app.agent.nodes.validate_sql import validate_sql
from app.agent.nodes.validate_sql_permission import validate_sql_permission
from app.agent.state import DataAgentState
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import (
    dw_mysql_client_manager,
    meta_mysql_client_manager,
)
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.core.sql_guard import is_correctable_sql_error
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

MAX_SQL_RETRY_COUNT = 3


def route_after_check_query_intent(state: DataAgentState):
    """根据用户意图判断是否允许进入只读问数链路"""

    if state.get("is_unsafe_intent", False):
        return "reject_unsafe_intent"
    if state.get("operation_intent", False):
        return "generate_operation_plan"

    return "check_clarification"


def route_after_check_clarification(state: DataAgentState):
    """根据业务口径是否明确决定继续问数或先追问用户"""

    if state.get("clarification_required", False):
        return "ask_clarification"

    return "check_domain_boundary"


def route_after_check_domain_boundary(state: DataAgentState):
    decision = state.get("recall_decision") or {}
    if decision.get("supported") is False:
        return "unable_to_answer"
    return "extract_keywords"


def route_after_validate_sql(state: DataAgentState):
    """根据 SQL 校验结果和重试次数决定下一步走向"""

    if state["error"] is None:
        return "validate_sql_permission"

    # 校正次数达到上限后进入失败节点，避免模型反复生成错误 SQL。
    retry_count = state.get("retry_count", 0)
    if retry_count >= MAX_SQL_RETRY_COUNT:
        return "fail_sql"

    if not is_correctable_sql_error(state.get("error")):
        return "fail_sql"

    return "correct_sql"


def route_after_validate_sql_permission(state: DataAgentState):
    """Route SQL to execution only after deterministic permission validation."""

    if state.get("permission_error") is None:
        return "run_sql"

    return "reject_permission_denied"


def route_after_check_recall_result(state: DataAgentState):
    """根据过滤后的候选表判断是否具备继续生成 SQL 的上下文"""

    table_infos = state.get("table_infos", [])
    recall_decision = state.get("recall_decision") or {}
    if recall_decision.get("supported") is False:
        return "unable_to_answer"
    if recall_decision.get("supported") is True:
        return "add_extra_context"
    if not table_infos:
        return "unable_to_answer"
    if not any(table_info.get("role") == "fact" for table_info in table_infos):
        return "unable_to_answer"

    return "add_extra_context"


# StateGraph 声明整张图使用的状态结构和运行时上下文结构
graph_builder = StateGraph(state_schema=DataAgentState, context_schema=DataAgentContext)

# 注册节点：每个节点负责问数链路中的一个清晰步骤
graph_builder.add_node("check_query_intent", check_query_intent)
graph_builder.add_node("check_clarification", check_clarification)
graph_builder.add_node("check_domain_boundary", check_domain_boundary)
graph_builder.add_node("ask_clarification", ask_clarification)
graph_builder.add_node("generate_operation_plan", generate_operation_plan)
graph_builder.add_node("estimate_operation_impact", estimate_operation_impact)
graph_builder.add_node("return_operation_plan", return_operation_plan)
graph_builder.add_node("extract_keywords", extract_keywords)
graph_builder.add_node("recall_column", recall_column)
graph_builder.add_node("recall_value", recall_value)
graph_builder.add_node("recall_metric", recall_metric)
graph_builder.add_node("merge_retrieved_info", merge_retrieved_info)
graph_builder.add_node("filter_permission_context", filter_permission_context)
graph_builder.add_node("filter_metric", filter_metric)
graph_builder.add_node("filter_table", filter_table)
graph_builder.add_node("check_recall_result", check_recall_result)
graph_builder.add_node("add_extra_context", add_extra_context)
graph_builder.add_node("generate_sql", generate_sql)
graph_builder.add_node("validate_sql", validate_sql)
graph_builder.add_node("validate_sql_permission", validate_sql_permission)
graph_builder.add_node("correct_sql", correct_sql)
graph_builder.add_node("run_sql", run_sql)
graph_builder.add_node("fail_sql", fail_sql)
graph_builder.add_node("unable_to_answer", unable_to_answer)
graph_builder.add_node("reject_unsafe_intent", reject_unsafe_intent)
graph_builder.add_node("reject_permission_denied", reject_permission_denied)

# 从用户问题开始，先检查是否包含删除 修改 写入等危险操作意图
graph_builder.add_edge(START, "check_query_intent")
graph_builder.add_conditional_edges(
    source="check_query_intent",
    path=route_after_check_query_intent,
    path_map={
        "check_clarification": "check_clarification",
        "generate_operation_plan": "generate_operation_plan",
        "reject_unsafe_intent": "reject_unsafe_intent",
    },
)
graph_builder.add_conditional_edges(
    source="check_clarification",
    path=route_after_check_clarification,
    path_map={
        "check_domain_boundary": "check_domain_boundary",
        "ask_clarification": "ask_clarification",
    },
)
graph_builder.add_conditional_edges(
    source="check_domain_boundary",
    path=route_after_check_domain_boundary,
    path_map={
        "extract_keywords": "extract_keywords",
        "unable_to_answer": "unable_to_answer",
    },
)

# 关键词抽取后并行进入三类召回，分别面向字段 字段值和业务指标
graph_builder.add_edge("extract_keywords", "recall_column")
graph_builder.add_edge("extract_keywords", "recall_value")
graph_builder.add_edge("extract_keywords", "recall_metric")

# 三路召回都完成后，再进入统一的信息合并节点
graph_builder.add_edge("recall_column", "merge_retrieved_info")
graph_builder.add_edge("recall_value", "merge_retrieved_info")
graph_builder.add_edge("recall_metric", "merge_retrieved_info")

# 合并后的候选信息继续拆成表过滤和指标过滤两条线
graph_builder.add_edge("merge_retrieved_info", "filter_permission_context")
graph_builder.add_edge("filter_permission_context", "filter_table")
graph_builder.add_edge("filter_permission_context", "filter_metric")

# 表和指标都过滤完成后，统一补充生成 SQL 所需的上下文
# 过滤后先检查是否有可靠候选表，避免无上下文时继续硬凑 SQL。
graph_builder.add_edge("filter_table", "check_recall_result")
graph_builder.add_edge("filter_metric", "check_recall_result")
graph_builder.add_conditional_edges(
    source="check_recall_result",
    path=route_after_check_recall_result,
    path_map={
        "add_extra_context": "add_extra_context",
        "unable_to_answer": "unable_to_answer",
    },
)
graph_builder.add_edge("add_extra_context", "generate_sql")
graph_builder.add_edge("generate_sql", "validate_sql")

# SQL 校验通过就直接执行，校验失败则先进入修正节点
graph_builder.add_conditional_edges(
    source="validate_sql",
    path=route_after_validate_sql,
    path_map={
        "validate_sql_permission": "validate_sql_permission",
        "correct_sql": "correct_sql",
        "fail_sql": "fail_sql",
    },
)
graph_builder.add_conditional_edges(
    source="validate_sql_permission",
    path=route_after_validate_sql_permission,
    path_map={
        "run_sql": "run_sql",
        "reject_permission_denied": "reject_permission_denied",
    },
)
# 修正后的 SQL 必须重新进入校验节点，形成「校验 -> 修正 -> 再校验」闭环。
graph_builder.add_edge("correct_sql", "validate_sql")
graph_builder.add_edge("run_sql", END)
graph_builder.add_edge("fail_sql", END)
graph_builder.add_edge("unable_to_answer", END)
graph_builder.add_edge("reject_unsafe_intent", END)
graph_builder.add_edge("reject_permission_denied", END)
graph_builder.add_edge("ask_clarification", END)
graph_builder.add_edge("generate_operation_plan", "estimate_operation_impact")
graph_builder.add_edge("estimate_operation_impact", "return_operation_plan")
graph_builder.add_edge("return_operation_plan", END)

# 编译后的 graph 是对外使用的 Agent 执行入口
graph = graph_builder.compile()

# print(graph.get_graph().draw_mermaid())

if __name__ == "__main__":

    async def test():
        """本地调试关键词抽取和字段 指标 取值三路召回链路"""

        # 多路召回和上下文补全会访问 Qdrant、Embedding、ES、Meta MySQL 和 DW MySQL
        qdrant_client_manager.init()
        embedding_client_manager.init()
        es_client_manager.init()
        meta_mysql_client_manager.init()
        dw_mysql_client_manager.init()

        # Meta MySQL 用来补齐元数据，DW MySQL 用来读取数据库方言和版本
        async with (
            meta_mysql_client_manager.session_factory() as meta_session,
            dw_mysql_client_manager.session_factory() as dw_session,
        ):
            meta_mysql_repository = MetaMySQLRepository(meta_session)
            dw_mysql_repository = DWMySQLRepository(dw_session)

            # 字段和指标分别使用不同 Qdrant collection，取值检索使用 ES index
            column_qdrant_repository = ColumnQdrantRepository(
                qdrant_client_manager.client
            )
            metric_qdrant_repository = MetricQdrantRepository(
                qdrant_client_manager.client
            )
            value_es_repository = ValueESRepository(es_client_manager.client)

            # 当前只需要传入原始问题，后续节点会逐步写回召回、过滤和额外上下文结果
            state = DataAgentState(query="统计华北地区的销售总额")
            context = DataAgentContext(
                column_qdrant_repository=column_qdrant_repository,
                embedding_client=embedding_client_manager.client,
                metric_qdrant_repository=metric_qdrant_repository,
                value_es_repository=value_es_repository,
                meta_mysql_repository=meta_mysql_repository,
                dw_mysql_repository=dw_mysql_repository,
            )

            # stream_mode="custom" 会接收各节点通过 runtime.stream_writer 写出的进度信息
            async for chunk in graph.astream(
                input=state, context=context, stream_mode="custom"
            ):
                print(chunk)

        # 关闭显式创建的异步客户端，避免本地调试时连接资源悬挂
        await qdrant_client_manager.close()
        await es_client_manager.close()
        await meta_mysql_client_manager.close()
        await dw_mysql_client_manager.close()

    asyncio.run(test())
