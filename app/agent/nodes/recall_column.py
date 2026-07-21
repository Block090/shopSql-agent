"""
字段召回节点

负责根据关键词从字段向量知识库中召回候选字段
它解决的是“用户问题可能对应哪些数据库字段”的问题
本章的主线是：关键词扩展 -> Embedding -> Qdrant 相似度检索 -> ColumnInfo 去重
"""

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.async_timeout import run_with_timeout
from app.core.business_lexicon import expand_business_terms, get_matched_column_ids
from app.core.log import logger
from app.core.rag_reranker import build_retrieval_query, rerank_recalled_context
from app.entities.column_info import ColumnInfo
from app.prompt.prompt_loader import load_prompt


async def recall_column(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """召回和用户问题语义相关的字段元数据"""

    writer = runtime.stream_writer
    step = "召回字段信息"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # state 保存图内业务中间结果：原始问题和上游抽取出的关键词
        keywords = state["keywords"]
        query = state["query"]
        semantic_slots = state.get("semantic_slots") or {}
        retrieval_query = build_retrieval_query(query, semantic_slots)
        # context 保存外部运行时工具：向量仓储和 Embedding 客户端
        column_qdrant_repository = runtime.context["column_qdrant_repository"]
        embedding_client = runtime.context["embedding_client"]

        matched_column_ids = get_matched_column_ids(query)
        result = []
        if not matched_column_ids:
            prompt = PromptTemplate(
                template=load_prompt("extend_keywords_for_column_recall"),
                input_variables=["query"],
            )
            output_parser = JsonOutputParser()
            chain = prompt | llm | output_parser
            result = await run_with_timeout(
                chain.ainvoke({"query": retrieval_query}),
                timeout_seconds=8,
                default=[],
                operation_name="字段 LLM 扩展",
            )

        # 原始关键词和 LLM 扩展词一起参与召回；set 去重，避免重复请求同一关键词
        keywords = set(expand_business_terms(query, keywords + result + [retrieval_query]))

        # 用字段 id 做唯一键，因为多个关键词、同一字段的多个向量点都可能命中同一个字段
        column_info_map: dict[str, ColumnInfo] = {}
        meta_mysql_repository = runtime.context["meta_mysql_repository"]
        exact_columns = await meta_mysql_repository.get_column_infos_by_ids(
            matched_column_ids
        )
        column_info_map.update({column.id: column for column in exact_columns})
        for keyword in keywords:
            # 查询词必须先转成向量，才能和第 9 章写入 Qdrant 的字段向量做相似度检索
            embedding = await run_with_timeout(
                embedding_client.aembed_query(keyword),
                timeout_seconds=5,
                default=[],
                operation_name=f"字段 Embedding({keyword})",
            )
            if not embedding:
                continue
            current_column_infos: list[ColumnInfo] = await run_with_timeout(
                column_qdrant_repository.search(embedding),
                timeout_seconds=5,
                default=[],
                operation_name=f"字段 Qdrant 检索({keyword})",
            )
            for column_info in current_column_infos:
                if column_info.id not in column_info_map:
                    column_info_map[column_info.id] = column_info

        # 写回 state 的是去重后的 ColumnInfo 列表，不暴露 Qdrant 原始 point 结构
        retrieved_column_infos: list[ColumnInfo] = rerank_recalled_context(
            list(column_info_map.values()), semantic_slots, query_text=query, limit=5
        )

        writer({"type": "progress", "step": step, "status": "success"})
        return {"retrieved_column_infos": retrieved_column_infos}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
