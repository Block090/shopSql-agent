"""
SQL 安全防护工具

大模型生成的 SQL 不能直接进入数仓执行，这里先提供一版轻量级只读校验：
只允许单条 SELECT 查询，拦截危险关键字，并要求 LIMIT 限制查询规模。
"""

import re

DANGEROUS_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "replace",
    "grant",
    "revoke",
}

SQL_PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "，": ",",
        "；": ";",
        "（": "(",
        "）": ")",
    }
)

DEFAULT_QUERY_LIMIT = 1000
MAX_QUERY_LIMIT = 1000
NON_CORRECTABLE_ERROR_MARKERS = (
    "只允许执行 SELECT",
    "不允许执行多条 SQL",
    "SQL 包含危险关键字",
    "SQL 不能为空",
    "查询必须包含 LIMIT",
    "permission denied",
)


def sanitize_sql_text(sql: str) -> str:
    """Replace common full-width punctuation that LLMs may emit in SQL text."""
    return sql.strip().translate(SQL_PUNCTUATION_TRANSLATION)


def normalize_sql(sql: str) -> str:
    """统一清理 SQL 文本，方便后续做大小写无关的安全判断"""
    return sanitize_sql_text(sql).lower()


def ensure_query_limit(sql: str, default_limit: int = DEFAULT_QUERY_LIMIT) -> str:
    """为单条查询确定性补充或收紧 LIMIT，避免为格式问题调用大模型。"""

    sanitized = sanitize_sql_text(sql).rstrip(";").strip()
    limit_match = re.search(r"\blimit\s+(\d+)\s*$", sanitized, flags=re.IGNORECASE)
    if limit_match:
        current_limit = int(limit_match.group(1))
        if current_limit <= MAX_QUERY_LIMIT:
            return sanitized
        return f"{sanitized[:limit_match.start()].rstrip()} LIMIT {MAX_QUERY_LIMIT}"

    if re.search(r"\blimit\b", sanitized, flags=re.IGNORECASE):
        return sanitized
    return f"{sanitized} LIMIT {min(default_limit, MAX_QUERY_LIMIT)}"


def is_correctable_sql_error(error: str | None) -> bool:
    """只有数据库语法、表字段和关联错误允许进入模型修正。"""

    if not error:
        return False
    return not any(marker.lower() in error.lower() for marker in NON_CORRECTABLE_ERROR_MARKERS)


def validate_readonly_sql(sql: str) -> None:
    """校验 SQL 是否满足当前项目的只读查询安全边界"""
    normalized = normalize_sql(sql)

    if not normalized:
        raise ValueError("SQL 不能为空")

    # 第一层防护：问数场景只允许查询语句，禁止写入或 DDL 操作。
    if not normalized.startswith("select"):
        raise ValueError("只允许执行 SELECT 查询语句")

    # 第二层防护：禁止通过分号拼接多条 SQL，避免一次请求执行多段语句。
    if ";" in normalized.rstrip(";"):
        raise ValueError("不允许执行多条 SQL")

    # 第三层防护：即使 SQL 以 SELECT 开头，也不能夹带高风险关键字。
    for keyword in DANGEROUS_KEYWORDS:
        if re.search(rf"\b{keyword}\b", normalized):
            raise ValueError(f"SQL 包含危险关键字: {keyword}")

    # 第四层防护：第一版先要求模型生成 LIMIT，避免无限制大查询拖垮数仓。
    if not re.search(r"\blimit\b", normalized):
        raise ValueError("查询必须包含 LIMIT 限制")
