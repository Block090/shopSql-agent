"""
表信息过滤节点

负责在合并后的候选表结构中筛选出当前问题真正需要的表和字段
这里让大模型只返回“保留哪些表和字段”的选择结果，真正的结构裁剪仍由程序完成
"""

import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, TableInfoState
from app.core.business_lexicon import get_required_column_ids, get_required_table_ids
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def filter_table(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """根据用户问题裁剪候选表结构上下文"""

    writer = runtime.stream_writer
    step = "过滤表信息"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        query = state["query"]
        table_infos: list[TableInfoState] = state["table_infos"]
        semantic_slots = state.get("semantic_slots") or {}

        if should_use_rule_only_table_filter(query, semantic_slots):
            filtered_table_infos = apply_required_table_context(
                query=query,
                table_infos=table_infos,
                selected_columns=build_rule_selected_columns(semantic_slots),
            )
            logger.info(
                "规则过滤后的表信息："
                f"{[table_info['name'] for table_info in filtered_table_infos]}"
            )
            writer({"type": "progress", "step": step, "status": "success"})
            return {"table_infos": filtered_table_infos}

        # table_infos 是嵌套结构，转成 YAML 后更适合放进提示词，也保留中文字段说明
        prompt = PromptTemplate(
            template=load_prompt("filter_table_info"),
            input_variables=["query", "table_infos"],
        )
        # filter_table_info prompt 要求模型只输出 JSON 对象：表名 -> 字段名列表
        output_parser = JsonOutputParser()
        # LCEL 管道：填充提示词 -> 调用模型 -> 解析 JSON
        chain = prompt | llm | output_parser

        result = await chain.ainvoke(
            {
                "query": query,
                "table_infos": yaml.dump(
                    table_infos, allow_unicode=True, sort_keys=False
                ),
            }
        )
        # 模型只负责选择，程序根据选择结果从原始 TableInfoState 中裁剪，避免模型重写复杂结构出错
        filtered_table_infos = apply_required_table_context(
            query=query,
            table_infos=table_infos,
            selected_columns=result,
        )

        logger.info(
            f"过滤后的表信息：{[filtered_table_info['name'] for filtered_table_info in filtered_table_infos]}"
        )
        writer({"type": "progress", "step": step, "status": "success"})
        return {"table_infos": filtered_table_infos}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise


def apply_required_table_context(
    query: str,
    table_infos: list[TableInfoState],
    selected_columns: dict[str, list[str]],
) -> list[TableInfoState]:
    """Keep LLM-selected context plus deterministic business-required columns."""

    required_table_ids = set(get_required_table_ids(query))
    required_columns_by_table: dict[str, set[str]] = {}
    for column_id in get_required_column_ids(query):
        if "." not in column_id:
            continue
        table_name, column_name = column_id.split(".", 1)
        required_columns_by_table.setdefault(table_name, set()).add(column_name)

    filtered_table_infos: list[TableInfoState] = []
    for table_info in table_infos:
        table_name = table_info["name"]
        selected = set(selected_columns.get(table_name, []))
        required = required_columns_by_table.get(table_name, set())
        keep_all_key_columns = table_name in required_table_ids
        keep_columns = selected | required

        if table_name not in selected_columns and table_name not in required_table_ids:
            continue

        columns = [
            column_info
            for column_info in table_info["columns"]
            if column_info["name"] in keep_columns
            or (keep_all_key_columns and column_info.get("role") in {"primary_key", "foreign_key"})
        ]
        if columns:
            copied_table = dict(table_info)
            copied_table["columns"] = columns
            filtered_table_infos.append(copied_table)

    return filtered_table_infos


def should_use_rule_only_table_filter(query: str, semantic_slots: dict) -> bool:
    """明确的结构化问数直接走规则筛表，避免大模型筛表拖慢追问。"""

    if not isinstance(semantic_slots, dict):
        return False

    has_time = bool(semantic_slots.get("time_range"))
    has_metric = bool(semantic_slots.get("metrics"))
    has_dimension_or_filter = bool(
        semantic_slots.get("dimension") or semantic_slots.get("filters")
    )
    required_tables = set(get_required_table_ids(query))
    has_fact_table = "fact_order" in required_tables

    return has_time and has_metric and has_dimension_or_filter and has_fact_table


def build_rule_selected_columns(semantic_slots: dict) -> dict[str, list[str]]:
    """根据语义槽位确定必要表字段，覆盖常见电商问数链路。"""

    selected_columns: dict[str, set[str]] = {
        "fact_order": {"date_id"},
    }
    metrics = set(semantic_slots.get("metrics") or [])
    dimension = semantic_slots.get("dimension")
    filters = semantic_slots.get("filters") or {}
    time_range = str(semantic_slots.get("time_range") or "")
    sort = semantic_slots.get("sort") or {}

    metric_names = set(metrics)
    sort_field = sort.get("field") if isinstance(sort, dict) else None
    if sort_field:
        metric_names.add(str(sort_field))

    if metric_names & {"GMV", "销售额", "AOV"}:
        selected_columns["fact_order"].add("order_amount")
    if "销量" in metric_names:
        selected_columns["fact_order"].add("order_quantity")
    if "订单数" in metric_names or "AOV" in metric_names:
        selected_columns["fact_order"].add("order_id")

    if dimension in {"商品", "商品品类"}:
        selected_columns["fact_order"].add("product_id")
        selected_columns.setdefault("dim_product", {"product_id"})
        selected_columns["dim_product"].add(
            "category" if dimension == "商品品类" else "product_name"
        )

    if dimension == "大区" or filters.get("region"):
        selected_columns["fact_order"].add("region_id")
        selected_columns.setdefault("dim_region", {"region_id"}).add("region_name")

    if time_range:
        selected_columns.setdefault("dim_date", {"date_id"})
        if "季度" in time_range:
            selected_columns["dim_date"].update({"year", "quarter"})
        elif "月" in time_range:
            selected_columns["dim_date"].update({"year", "month"})
        else:
            selected_columns["dim_date"].add("date_id")

    return {
        table_name: list(columns)
        for table_name, columns in selected_columns.items()
        if columns
    }
