"""
指标召回节点

负责根据用户问题从指标向量知识库中召回候选指标
它帮助 Agent 把“销售额 转化率 客单价”等业务表达映射到已定义指标
实现路径和字段召回类似：关键词扩展 -> Embedding -> Qdrant 相似度检索 -> MetricInfo 去重
"""

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.async_timeout import run_with_timeout
from app.core.business_lexicon import (
    build_deterministic_metric_infos,
    expand_business_terms,
    get_matched_metric_ids,
)
from app.core.log import logger
from app.core.rag_reranker import build_retrieval_query, rerank_recalled_context
from app.entities.metric_info import MetricInfo
from app.prompt.prompt_loader import load_prompt


async def recall_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """召回和用户问题语义相关的业务指标"""

    writer = runtime.stream_writer
    step = "召回指标信息"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # query 用于让 LLM 生成指标层检索词，keywords 来自上游的通用关键词抽取
        query = state["query"]
        semantic_slots = state.get("semantic_slots") or {}
        retrieval_query = build_retrieval_query(query, semantic_slots)
        keywords = state["keywords"]
        # 指标召回使用向量检索，需要 Embedding 客户端和指标 Qdrant 仓储配合
        embedding_client = runtime.context["embedding_client"]
        metric_qdrant_repository = runtime.context["metric_qdrant_repository"]

        matched_metric_ids = get_matched_metric_ids(query)
        result = []
        if not matched_metric_ids:
            prompt = PromptTemplate(
                template=load_prompt("extend_keywords_for_metric_recall"),
                input_variables=["query"],
            )
            output_parser = JsonOutputParser()
            chain = prompt | llm | output_parser
            result = await run_with_timeout(
                chain.ainvoke({"query": retrieval_query}),
                timeout_seconds=8,
                default=[],
                operation_name="指标 LLM 扩展",
            )

        # 通用关键词和指标扩展词都参与召回，提升同义指标的命中率
        keywords = set(expand_business_terms(query, keywords + result + [retrieval_query]))

        # 用指标 id 做唯一键，避免多个关键词命中同一个指标时重复写入 state
        metric_info_map: dict[str, MetricInfo] = {}
        meta_mysql_repository = runtime.context["meta_mysql_repository"]
        exact_metrics = await meta_mysql_repository.get_metric_infos_by_ids(
            matched_metric_ids
        )
        metric_info_map.update({metric.id: metric for metric in exact_metrics})
        for metric in build_deterministic_metric_infos(query):
            metric_info_map.setdefault(metric.id, metric)
        for keyword in keywords:
            # 指标库是向量集合，查询词必须先 Embedding 成 query vector
            embedding = await run_with_timeout(
                embedding_client.aembed_query(keyword),
                timeout_seconds=5,
                default=[],
                operation_name=f"指标 Embedding({keyword})",
            )
            if not embedding:
                continue
            current_metric_infos: list[MetricInfo] = await run_with_timeout(
                metric_qdrant_repository.search(embedding),
                timeout_seconds=5,
                default=[],
                operation_name=f"指标 Qdrant 检索({keyword})",
            )
            for metric_info in current_metric_infos:
                if metric_info.id not in metric_info_map:
                    metric_info_map[metric_info.id] = metric_info

        # 写回 state 的是业务实体列表，后续过滤节点不需要关心 Qdrant 原始 point 结构
        retrieved_metric_infos: list[MetricInfo] = rerank_recalled_context(
            list(metric_info_map.values()), semantic_slots, query_text=query, limit=5
        )
        logger.info(f"检索到指标信息：{list(metric_info_map.keys())}")
        writer({"type": "progress", "step": step, "status": "success"})
        return {"retrieved_metric_infos": retrieved_metric_infos}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
