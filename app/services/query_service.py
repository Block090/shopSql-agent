"""Compatibility wrapper for the history-aware query service.

The active API dependency imports ``app.services.query_history_service`` directly.
This module is kept only for older imports and points to the same implementation.
"""

from app.services.query_history_service import (
    QueryService,
    format_user_error_message,
    limit_history_result_rows,
    summarize_operation_plan,
    summarize_result,
    to_sse,
    unpack_stream_chunk,
)

__all__ = [
    "QueryService",
    "format_user_error_message",
    "limit_history_result_rows",
    "summarize_operation_plan",
    "summarize_result",
    "to_sse",
    "unpack_stream_chunk",
]
