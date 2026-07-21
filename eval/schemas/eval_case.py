"""
测评用例结构
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalCase:
    """单条电商问数测评用例"""

    id: str
    query: str
    category: str = "unknown"
    should_answer: bool = True
    expected_context: dict[str, list[str]] = field(default_factory=dict)
    expected_sql: dict[str, Any] = field(default_factory=dict)
    expected_result: dict[str, Any] = field(default_factory=dict)
    expected_behavior: dict[str, Any] = field(default_factory=dict)
    suite: str = "core"
    tags: list[str] = field(default_factory=list)
    user_id: str | None = None
    session_id: str | None = None
    permission_context: dict[str, Any] = field(default_factory=dict)
    conversation: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalCase":
        """从 JSON dict 构造用例，兼容旧版平铺字段"""

        expected_context = data.get("expected_context") or {
            "tables": data.get("expected_tables", []),
            "columns": data.get("expected_columns", []),
            "metrics": data.get("expected_metrics", []),
            "values": data.get("expected_values", []),
        }
        expected_sql = data.get("expected_sql") or {
            "type": "select" if data.get("should_answer", True) else "none",
            "must_contain": data.get("expected_sql_keywords", []),
            "must_not_contain": ["delete", "update", "insert", "drop", "truncate"],
            "tables": data.get("expected_tables", []),
            "columns": data.get("expected_columns", []),
        }
        expected_behavior = data.get("expected_behavior") or {
            "final_status": "success" if data.get("should_answer", True) else "rejected",
            "error_type": data.get("expected_error_type"),
            "sql_should_be_empty": not data.get("should_answer", True),
            "result_required": data.get("should_answer", True),
        }
        return cls(
            id=data["id"],
            query=data.get("query", ""),
            category=data.get("category", "unknown"),
            should_answer=data.get("should_answer", True),
            expected_context=expected_context,
            expected_sql=expected_sql,
            expected_result=data.get("expected_result", {}),
            expected_behavior=expected_behavior,
            suite=data.get("suite", "core"),
            tags=data.get("tags", []),
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            permission_context=data.get("permission_context", {}),
            conversation=data.get("conversation", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为评测函数使用的 dict"""

        return {
            "id": self.id,
            "query": self.query,
            "category": self.category,
            "should_answer": self.should_answer,
            "expected_context": self.expected_context,
            "expected_sql": self.expected_sql,
            "expected_result": self.expected_result,
            "expected_behavior": self.expected_behavior,
            "suite": self.suite,
            "tags": self.tags,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "permission_context": self.permission_context,
            "conversation": self.conversation,
        }
