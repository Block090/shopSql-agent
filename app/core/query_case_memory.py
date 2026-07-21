"""历史成功查询案例记忆。

把成功问数沉淀成可召回的 Query Case，供后续 SQL 生成参考结构模式。
"""

import re
import uuid
from datetime import datetime
from typing import Any

SQL_KEYWORDS = {
    "select",
    "from",
    "join",
    "on",
    "where",
    "group",
    "by",
    "order",
    "limit",
    "as",
    "and",
    "or",
    "sum",
    "count",
    "avg",
    "min",
    "max",
    "between",
    "desc",
    "asc",
}


def build_query_case(
    query: str,
    resolved_query: str,
    sql: str,
    semantic_slots: dict[str, Any] | None = None,
    result_summary: str | None = None,
) -> dict[str, Any]:
    """从一次成功查询中构造可向量化的 Query Case。"""

    slots = _normalize_slots(semantic_slots or {})
    used_tables = _extract_tables(sql)
    used_fields = _extract_fields(sql)
    return {
        "case_id": f"qc_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}",
        "question": query,
        "resolved_query": resolved_query,
        "semantic_slots": slots,
        "sql": sql,
        "used_tables": used_tables,
        "used_fields": used_fields,
        "sql_pattern": _build_sql_pattern(sql, slots),
        "result_summary": result_summary or "",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def build_query_case_text(query_case: dict[str, Any]) -> str:
    """构造 Query Case 的向量化文本。"""

    slots = _normalize_slots(query_case.get("semantic_slots") or {})
    filters = slots.get("filters") or {}
    filter_text = (
        "、".join(f"{key}={value}" for key, value in filters.items())
        if filters
        else "无"
    )
    return "\n".join(
        [
            f"问题：{query_case.get('question', '')}",
            f"完整问题：{query_case.get('resolved_query', '')}",
            f"指标：{', '.join(slots.get('metrics') or []) or '无'}",
            f"维度：{slots.get('dimension') or '无'}",
            f"过滤条件：{filter_text}",
            f"时间范围：{slots.get('time_range') or '无'}",
            f"使用表：{', '.join(query_case.get('used_tables') or []) or '无'}",
            f"使用字段：{', '.join(query_case.get('used_fields') or []) or '无'}",
            f"SQL模式：{query_case.get('sql_pattern', '')}",
        ]
    )


def compress_similar_cases(cases: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    """压缩相似案例，只保留 SQL 生成需要的结构化参考。"""

    compressed = []
    for case in cases[:limit]:
        compressed.append(
            {
                "question": case.get("question") or "",
                "resolved_query": case.get("resolved_query") or "",
                "used_tables": case.get("used_tables") or [],
                "used_fields": case.get("used_fields") or [],
                "sql_pattern": case.get("sql_pattern") or "",
            }
        )
    return compressed


def _extract_tables(sql: str) -> list[str]:
    table_names = set()
    for match in re.finditer(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][\w.]*)", sql, re.IGNORECASE):
        table_names.add(match.group(1).split(".")[-1])
    return sorted(table_names)


def _extract_fields(sql: str) -> list[str]:
    field_names = set()
    for _, field_name in re.findall(r"\b([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)\b", sql):
        if field_name.lower() not in SQL_KEYWORDS:
            field_names.add(field_name)
    for function_arg in re.findall(
        r"\b(?:SUM|COUNT|AVG|MIN|MAX)\s*\(\s*([a-zA-Z_][\w.]*)",
        sql,
        re.IGNORECASE,
    ):
        field_name = function_arg.split(".")[-1]
        if field_name != "*" and field_name.lower() not in SQL_KEYWORDS:
            field_names.add(field_name)
    return sorted(field_names)


def _build_sql_pattern(sql: str, semantic_slots: dict[str, Any]) -> str:
    parts = []
    dimension = semantic_slots.get("dimension")
    metrics = semantic_slots.get("metrics") or []
    sort = semantic_slots.get("sort") or {}

    if dimension and "group by" in sql.lower():
        parts.append(f"按{dimension}维度分组")
    elif "group by" in sql.lower():
        parts.append("按指定维度分组")

    if metrics:
        parts.append(f"汇总{','.join(metrics)}")
    elif re.search(r"\b(sum|count|avg|min|max)\s*\(", sql, re.IGNORECASE):
        parts.append("使用聚合函数计算指标")

    sort_field = sort.get("field")
    direction = sort.get("direction")
    if sort_field and direction == "desc":
        parts.append(f"按 {sort_field} 降序")
    elif sort_field and direction:
        parts.append(f"按 {sort_field} {direction} 排序")
    elif "order by" in sql.lower():
        parts.append("按结果排序")

    if "join" in sql.lower():
        parts.append("通过维表 Join 补充分析维度")

    return "，".join(parts) or "根据过滤条件查询明细数据"


def _normalize_slots(slots: dict[str, Any]) -> dict[str, Any]:
    return {
        "time_range": slots.get("time_range"),
        "dimension": slots.get("dimension"),
        "metrics": slots.get("metrics") or [],
        "filters": slots.get("filters") or {},
        "sort": slots.get("sort"),
        "limit": slots.get("limit"),
    }
