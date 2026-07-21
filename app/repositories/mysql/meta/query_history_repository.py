"""查询历史仓库，负责保存会话和每轮问数记录。"""

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class QueryHistoryRepository:
    """把问数会话历史持久化到 meta MySQL。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_tables(self) -> None:
        """确保会话表和查询历史表存在，兼容已有本地数据库。"""

        await self.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS chat_session (
                  session_id VARCHAR(64) PRIMARY KEY COMMENT '会话 ID',
                  title VARCHAR(255) NULL COMMENT '会话标题',
                  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
                ) COMMENT='问数会话表'
                """
            )
        )
        await self.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS query_history (
                  id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '历史记录 ID',
                  session_id VARCHAR(64) NOT NULL COMMENT '会话 ID',
                  query TEXT NOT NULL COMMENT '用户原始问题',
                  resolved_query TEXT NULL COMMENT '结合上下文后的完整问题',
                  sql_text TEXT NULL COMMENT '本次生成或预览用 SQL',
                  result_summary TEXT NULL COMMENT '结果摘要',
                  result_data JSON NULL COMMENT '查询结果数据，用于历史回看表格',
                  context_trace JSON NULL COMMENT '上下文改写轨迹，用于解释系统如何理解多轮追问',
                  semantic_slots JSON NULL COMMENT '结构化语义槽位，用于多轮上下文继承',
                  rewrite_confidence DECIMAL(5,4) NULL COMMENT '上下文改写置信度',
                  status VARCHAR(32) NOT NULL COMMENT '查询状态',
                  error_message TEXT NULL COMMENT '错误信息',
                  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                  INDEX idx_query_history_session_time (session_id, created_at),
                  CONSTRAINT fk_query_history_session
                    FOREIGN KEY (session_id) REFERENCES chat_session(session_id)
                ) COMMENT='问数查询历史表'
                """
            )
        )
        await self._ensure_result_data_column()
        await self._ensure_context_trace_column()
        await self._ensure_result_productization_columns()
        await self._ensure_semantic_slots_columns()
        await self.session.commit()

    async def _ensure_result_data_column(self) -> None:
        """兼容已有数据库：旧 query_history 表没有 result_data 时自动补字段。"""

        result = await self.session.execute(
            text("SHOW COLUMNS FROM query_history LIKE 'result_data'")
        )
        if result.mappings().first() is None:
            await self.session.execute(
                text(
                    """
                    ALTER TABLE query_history
                    ADD COLUMN result_data JSON NULL COMMENT '查询结果数据，用于历史回看表格'
                    """
                )
            )

    async def _ensure_context_trace_column(self) -> None:
        """兼容已有数据库：旧 query_history 表没有 context_trace 时自动补字段。"""

        result = await self.session.execute(
            text("SHOW COLUMNS FROM query_history LIKE 'context_trace'")
        )
        if result.mappings().first() is None:
            await self.session.execute(
                text(
                    """
                    ALTER TABLE query_history
                    ADD COLUMN context_trace JSON NULL COMMENT '上下文改写轨迹，用于解释系统如何理解多轮追问'
                    """
                )
            )

    async def _ensure_result_productization_columns(self) -> None:
        """兼容旧 query_history 表缺少查询结果产品化字段的情况。"""

        facts_result = await self.session.execute(
            text("SHOW COLUMNS FROM query_history LIKE 'result_facts'")
        )
        if facts_result.mappings().first() is None:
            await self.session.execute(
                text(
                    """
                    ALTER TABLE query_history
                    ADD COLUMN result_facts JSON NULL COMMENT '查询结果事实摘要'
                    """
                )
            )

        analysis_result = await self.session.execute(
            text("SHOW COLUMNS FROM query_history LIKE 'result_analysis'")
        )
        if analysis_result.mappings().first() is None:
            await self.session.execute(
                text(
                    """
                    ALTER TABLE query_history
                    ADD COLUMN result_analysis JSON NULL COMMENT '查询结果智能分析摘要'
                    """
                )
            )

    async def _ensure_semantic_slots_columns(self) -> None:
        """兼容已有数据库：为旧 query_history 表补充语义槽位和置信度字段。"""

        slots_result = await self.session.execute(
            text("SHOW COLUMNS FROM query_history LIKE 'semantic_slots'")
        )
        if slots_result.mappings().first() is None:
            await self.session.execute(
                text(
                    """
                    ALTER TABLE query_history
                    ADD COLUMN semantic_slots JSON NULL COMMENT '结构化语义槽位，用于多轮上下文继承'
                    """
                )
            )

        confidence_result = await self.session.execute(
            text("SHOW COLUMNS FROM query_history LIKE 'rewrite_confidence'")
        )
        if confidence_result.mappings().first() is None:
            await self.session.execute(
                text(
                    """
                    ALTER TABLE query_history
                    ADD COLUMN rewrite_confidence DECIMAL(5,4) NULL COMMENT '上下文改写置信度'
                    """
                )
            )

    async def create_or_touch_session(self, session_id: str, title: str | None) -> None:
        """创建会话；如果会话已存在，只更新时间。"""

        await self.session.execute(
            text(
                """
                INSERT INTO chat_session (session_id, title)
                VALUES (:session_id, :title)
                ON DUPLICATE KEY UPDATE
                  updated_at = CURRENT_TIMESTAMP,
                  title = COALESCE(chat_session.title, VALUES(title))
                """
            ),
            {"session_id": session_id, "title": title},
        )
        await self.session.commit()

    async def save_history(
        self,
        session_id: str,
        query: str,
        resolved_query: str,
        sql: str | None,
        result_summary: str | None,
        status: str,
        error_message: str | None = None,
        result_data=None,
        context_trace=None,
        result_facts=None,
        result_analysis=None,
        semantic_slots=None,
        rewrite_confidence: float | None = None,
    ) -> None:
        """保存一轮问数历史。"""

        await self.session.execute(
            text(
                """
                INSERT INTO query_history
                  (session_id, query, resolved_query, sql_text, result_summary, result_data, context_trace, result_facts, result_analysis, semantic_slots, rewrite_confidence, status, error_message)
                VALUES
                  (:session_id, :query, :resolved_query, :sql_text, :result_summary, :result_data, :context_trace, :result_facts, :result_analysis, :semantic_slots, :rewrite_confidence, :status, :error_message)
                """
            ),
            {
                "session_id": session_id,
                "query": query,
                "resolved_query": resolved_query,
                "sql_text": sql,
                "result_summary": result_summary,
                "result_data": _dump_result_data(result_data),
                "context_trace": _dump_result_data(context_trace),
                "result_facts": _dump_result_data(result_facts),
                "result_analysis": _dump_result_data(result_analysis),
                "semantic_slots": _dump_result_data(semantic_slots),
                "rewrite_confidence": rewrite_confidence,
                "status": status,
                "error_message": error_message,
            },
        )
        await self.session.commit()

    async def list_sessions(self, limit: int = 20) -> list[dict]:
        """查询最近会话列表。"""

        result = await self.session.execute(
            text(
                """
                SELECT session_id, title, created_at, updated_at
                FROM chat_session
                ORDER BY updated_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [dict(row) for row in result.mappings().fetchall()]

    async def get_session_history(self, session_id: str, limit: int = 50) -> list[dict]:
        """查询某个会话的历史，按时间正序返回给前端展示。"""

        result = await self.session.execute(
            text(
                """
                SELECT query, resolved_query, sql_text AS `sql`, result_summary, result_data, context_trace, result_facts, result_analysis, semantic_slots, rewrite_confidence, status, error_message, created_at
                FROM query_history
                WHERE session_id = :session_id
                ORDER BY created_at ASC, id ASC
                LIMIT :limit
                """
            ),
            {"session_id": session_id, "limit": limit},
        )
        return [_parse_history_row(dict(row)) for row in result.mappings().fetchall()]

    async def get_recent_turns(self, session_id: str, limit: int = 3) -> list[dict]:
        """查询最近 N 轮，按新到旧返回，用于上下文改写。"""

        result = await self.session.execute(
            text(
                """
                SELECT query, resolved_query, sql_text AS `sql`, result_summary, result_data, context_trace, result_facts, result_analysis, semantic_slots, rewrite_confidence, status, created_at
                FROM query_history
                WHERE session_id = :session_id
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"session_id": session_id, "limit": limit},
        )
        return [_parse_history_row(dict(row)) for row in result.mappings().fetchall()]

    async def delete_session(self, session_id: str) -> None:
        """删除一个会话及其全部查询历史。"""

        await self.session.execute(
            text("DELETE FROM query_history WHERE session_id = :session_id"),
            {"session_id": session_id},
        )
        await self.session.execute(
            text("DELETE FROM chat_session WHERE session_id = :session_id"),
            {"session_id": session_id},
        )
        await self.session.commit()


def _dump_result_data(result_data) -> str | None:
    """把查询结果转成 MySQL JSON 字符串，Decimal 等类型用字符串兜底。"""

    if result_data is None:
        return None
    return json.dumps(result_data, ensure_ascii=False, default=str)


def _parse_history_row(row: dict) -> dict:
    """把 MySQL JSON 字段恢复成前端可直接消费的数据结构。"""

    raw_result_data = row.get("result_data")
    if isinstance(raw_result_data, str):
        try:
            row["result_data"] = json.loads(raw_result_data)
        except json.JSONDecodeError:
            row["result_data"] = None
    raw_context_trace = row.get("context_trace")
    if isinstance(raw_context_trace, str):
        try:
            row["context_trace"] = json.loads(raw_context_trace)
        except json.JSONDecodeError:
            row["context_trace"] = None
    raw_result_facts = row.get("result_facts")
    if isinstance(raw_result_facts, str):
        try:
            row["result_facts"] = json.loads(raw_result_facts)
        except json.JSONDecodeError:
            row["result_facts"] = None
    raw_result_analysis = row.get("result_analysis")
    if isinstance(raw_result_analysis, str):
        try:
            row["result_analysis"] = json.loads(raw_result_analysis)
        except json.JSONDecodeError:
            row["result_analysis"] = None
    raw_semantic_slots = row.get("semantic_slots")
    if isinstance(raw_semantic_slots, str):
        try:
            row["semantic_slots"] = json.loads(raw_semantic_slots)
        except json.JSONDecodeError:
            row["semantic_slots"] = None
    return row
