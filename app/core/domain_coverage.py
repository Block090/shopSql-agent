"""在生成 SQL 前确定性检查问题是否被当前元数据覆盖。"""

from typing import Any

from app.core.business_lexicon import (
    build_deterministic_metric_infos,
    get_matched_column_ids,
    get_matched_metric_ids,
    get_unsupported_concepts,
)


def evaluate_domain_coverage(
    query: str,
    table_infos: list[dict[str, Any]],
    metric_infos: list[dict[str, Any]],
) -> dict[str, Any]:
    unsupported = get_unsupported_concepts(query)
    if unsupported:
        return _decision(False, "unsupported_domain_concept", unsupported)

    available_columns = {
        f"{table.get('name')}.{column.get('name')}"
        for table in table_infos
        for column in table.get("columns", [])
    }
    missing_columns = [
        column_id
        for column_id in get_matched_column_ids(query)
        if column_id not in available_columns
    ]
    if missing_columns:
        return _decision(False, "missing_column_context", missing_columns)

    available_metrics = {str(item.get("name")) for item in metric_infos}
    deterministic_metrics = {
        metric.name: metric for metric in build_deterministic_metric_infos(query)
    }
    missing_metrics = [
        metric
        for metric in get_matched_metric_ids(query)
        if not _metric_context_available(
            metric,
            available_metrics=available_metrics,
            available_columns=available_columns,
            deterministic_metrics=deterministic_metrics,
        )
    ]
    if missing_metrics:
        return _decision(False, "missing_metric_context", missing_metrics)

    if not table_infos:
        return _decision(False, "missing_table_context", ["业务数据"])

    return _decision(True, "covered", [])


def _decision(supported: bool, reason: str, missing: list[str]) -> dict[str, Any]:
    return {
        "supported": supported,
        "reason": reason,
        "missing_concepts": missing,
    }


def _metric_context_available(
    metric_name: str,
    available_metrics: set[str],
    available_columns: set[str],
    deterministic_metrics: dict[str, Any],
) -> bool:
    if metric_name in available_metrics:
        return True

    deterministic_metric = deterministic_metrics.get(metric_name)
    if not deterministic_metric:
        return False

    return all(
        column_id in available_columns
        for column_id in deterministic_metric.relevant_columns
    )
