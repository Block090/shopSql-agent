"""Deterministic permission checks for the query agent.

The LLM may generate candidate SQL, but authorization must be enforced by code.
This module keeps the first permission layer small and testable: filter metadata
before prompting, then validate generated SQL before execution.
"""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class AuthorizedContext:
    table_infos: list[dict[str, Any]]
    metric_infos: list[dict[str, Any]]


def filter_authorized_context(
    table_infos: list[dict[str, Any]],
    metric_infos: list[dict[str, Any]],
    permission_context: dict[str, Any] | None,
) -> AuthorizedContext:
    """Remove metadata the current user is not allowed to expose to the LLM."""

    if not permission_context:
        return AuthorizedContext(table_infos=table_infos, metric_infos=metric_infos)

    allowed_tables = _to_set(permission_context.get("allowed_tables"))
    allowed_metrics = _to_set(permission_context.get("allowed_metrics"))
    denied_columns = _to_set(permission_context.get("denied_columns"))

    filtered_tables: list[dict[str, Any]] = []
    for table_info in table_infos:
        table_name = table_info.get("name")
        if allowed_tables and table_name not in allowed_tables:
            continue

        filtered_columns = [
            column
            for column in table_info.get("columns", [])
            if column.get("name") not in denied_columns
            and _column_id(table_name, column.get("name")) not in denied_columns
        ]
        if filtered_columns:
            copied_table = dict(table_info)
            copied_table["columns"] = filtered_columns
            filtered_tables.append(copied_table)

    filtered_metrics = [
        metric_info
        for metric_info in metric_infos
        if not allowed_metrics or metric_info.get("name") in allowed_metrics
    ]

    return AuthorizedContext(
        table_infos=filtered_tables,
        metric_infos=filtered_metrics,
    )


def validate_sql_permission(
    sql: str,
    permission_context: dict[str, Any] | None,
) -> None:
    """Validate generated SQL against deterministic permission rules."""

    if not permission_context:
        return

    normalized = _normalize_sql(sql)
    allowed_tables = _to_set(permission_context.get("allowed_tables"))
    denied_columns = _to_set(permission_context.get("denied_columns"))

    if allowed_tables:
        for table_name in _extract_table_names(normalized):
            if table_name not in {table.lower() for table in allowed_tables}:
                raise ValueError(f"permission denied: table {table_name} is not allowed")

    for column_name in denied_columns:
        short_name = column_name.split(".")[-1].lower()
        if re.search(rf"\b{re.escape(short_name)}\b", normalized):
            raise ValueError(f"permission denied: sensitive column {short_name}")

    data_scope = permission_context.get("data_scope") or {}
    for scope_column, allowed_values in data_scope.items():
        if not allowed_values:
            continue
        if not _sql_contains_scope_condition(
            normalized,
            scope_column=scope_column,
            allowed_values=allowed_values,
        ):
            raise ValueError(
                f"permission denied: missing data scope condition for {scope_column}"
            )


def _to_set(value) -> set[str]:
    if not value:
        return set()
    return {str(item) for item in value}


def _column_id(table_name: str | None, column_name: str | None) -> str:
    if not table_name or not column_name:
        return ""
    return f"{table_name}.{column_name}"


def _normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip().lower()


def _extract_table_names(normalized_sql: str) -> list[str]:
    return re.findall(r"\b(?:from|join)\s+`?([a-zA-Z_][\w]*)`?", normalized_sql)


def _sql_contains_scope_condition(
    normalized_sql: str,
    scope_column: str,
    allowed_values: list[Any],
) -> bool:
    column = scope_column.split(".")[-1].lower()
    for value in allowed_values:
        value_text = str(value).lower()
        equality_pattern = (
            rf"\b{re.escape(column)}\b\s*=\s*['\"]?{re.escape(value_text)}['\"]?"
        )
        if re.search(equality_pattern, normalized_sql):
            return True

        in_pattern = rf"\b{re.escape(column)}\b\s+in\s*\([^)]*{re.escape(value_text)}"
        if re.search(in_pattern, normalized_sql):
            return True

    return False
