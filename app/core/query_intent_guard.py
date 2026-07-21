"""
用户意图安全检查

当前项目是只读电商问数系统，用户主动提出删除 修改 写入等操作时，
不应该继续进入 SQL 生成链路。
"""

UNSAFE_WRITE_INTENT_KEYWORDS = {
    "删除",
    "删掉",
    "清空",
    "修改",
    "更新",
    "插入",
    "新增",
    "写入",
    "delete",
    "update",
    "insert",
    "drop",
    "truncate",
    "alter",
}


def is_unsafe_write_intent(query: str) -> bool:
    """判断用户问题是否包含危险写操作意图"""

    normalized_query = query.lower()
    return any(keyword in normalized_query for keyword in UNSAFE_WRITE_INTENT_KEYWORDS)
