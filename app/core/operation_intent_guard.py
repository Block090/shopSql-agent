"""
数据变更意图识别

这里把写操作分成两类：
1. DELETE / UPDATE / INSERT：进入变更审批链路，只生成方案，不直接执行。
2. DROP / TRUNCATE / ALTER：属于结构级高危操作，仍然直接拒绝。
"""


DELETE_KEYWORDS = ["删除", "删掉", "移除", "delete"]
UPDATE_KEYWORDS = ["修改", "更新", "调整", "改成", "update"]
INSERT_KEYWORDS = ["新增", "添加", "插入", "写入", "insert"]
DANGEROUS_KEYWORDS = ["清空", "drop", "truncate", "alter", "删表"]


def classify_operation_intent(query: str) -> dict[str, str]:
    """识别用户问题是只读查询、可审批变更，还是结构级危险操作"""

    normalized_query = (query or "").lower()

    if _contains_any(normalized_query, DANGEROUS_KEYWORDS):
        return {"intent_type": "dangerous", "operation_type": "TRUNCATE"}
    if _contains_any(normalized_query, DELETE_KEYWORDS):
        return {"intent_type": "operation", "operation_type": "DELETE"}
    if _contains_any(normalized_query, UPDATE_KEYWORDS):
        return {"intent_type": "operation", "operation_type": "UPDATE"}
    if _contains_any(normalized_query, INSERT_KEYWORDS):
        return {"intent_type": "operation", "operation_type": "INSERT"}

    return {"intent_type": "readonly", "operation_type": ""}


def _contains_any(query: str, keywords: list[str]) -> bool:
    """判断问题是否命中任意操作关键词"""

    return any(keyword.lower() in query for keyword in keywords)
