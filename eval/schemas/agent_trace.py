"""
Agent 执行轨迹结构
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentTrace:
    """新版分层测评使用的 Agent trace"""

    query: str = ""
    resolved_query: str = ""
    intent: dict[str, Any] = field(default_factory=dict)
    retrieval: dict[str, list[str]] = field(default_factory=dict)
    context: dict[str, list[str]] = field(default_factory=dict)
    sql: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    operation_plan: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentTrace":
        """从新版或旧版 trace 构造统一结构"""

        sql = data.get("sql", "")
        if not isinstance(sql, dict):
            sql = data.get("sql_detail") or {"text": sql or ""}
        return cls(
            query=data.get("query", ""),
            resolved_query=data.get("resolved_query", ""),
            intent=data.get("intent", {}),
            retrieval=data.get("retrieval")
            or {
                "columns": data.get("retrieved_columns", []),
                "metrics": data.get("retrieved_metrics", []),
                "values": data.get("retrieved_values", []),
            },
            context=data.get("context")
            or {
                "tables": data.get("table_infos", []),
                "columns": data.get("retrieved_columns", []),
                "metrics": data.get("retrieved_metrics", []),
            },
            sql=sql,
            execution=data.get("execution")
            or {
                "final_status": data.get("final_status"),
                "error_type": data.get("error_type"),
                "row_count": data.get("row_count"),
            },
            result=data.get("result")
            or {
                "columns": _infer_result_columns(data.get("result_data", [])),
                "rows": data.get("result_data", []),
            },
            operation_plan=data.get("operation_plan", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为评测函数使用的 dict"""

        return {
            "query": self.query,
            "resolved_query": self.resolved_query,
            "intent": self.intent,
            "retrieval": self.retrieval,
            "context": self.context,
            "sql": self.sql,
            "execution": self.execution,
            "result": self.result,
            "operation_plan": self.operation_plan,
        }


def _infer_result_columns(rows: list[Any]) -> list[str]:
    if rows and isinstance(rows[0], dict):
        return list(rows[0].keys())
    return []
