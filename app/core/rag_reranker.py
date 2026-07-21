"""RAG 检索 query 增强与业务相关性重排。"""

from dataclasses import asdict, is_dataclass
from typing import Any


def build_retrieval_query(resolved_query: str, semantic_slots: dict[str, Any] | None) -> str:
    """用 resolved_query 和 semantic_slots 构造更稳定的召回文本。"""

    slots = semantic_slots or {}
    parts = [resolved_query.strip()]

    metrics = slots.get("metrics") or []
    if metrics:
        parts.append(f"指标 {' '.join(str(metric) for metric in metrics)}")

    dimension = slots.get("dimension")
    if dimension:
        parts.append(f"维度 {dimension}")

    filters = slots.get("filters") or {}
    if filters:
        filter_text = " ".join(f"{key}={value}" for key, value in filters.items())
        parts.append(f"过滤条件 {filter_text}")

    time_range = slots.get("time_range")
    if time_range:
        parts.append(f"时间 {time_range}")

    sort = slots.get("sort") or {}
    if sort:
        parts.append(f"排序 {sort.get('field')} {sort.get('direction')}")

    return " ".join(part for part in parts if part)


def rerank_recalled_context(
    candidates: list[Any],
    semantic_slots: dict[str, Any] | None,
    query_text: str = "",
    limit: int | None = None,
) -> list[Any]:
    """结合业务槽位对召回候选重排。"""

    slots = semantic_slots or {}
    scored = []
    for index, candidate in enumerate(candidates):
        score = _score_candidate(candidate, slots, query_text)
        if isinstance(candidate, dict):
            item = dict(candidate)
            item["_rerank_score"] = score
        else:
            item = candidate
        scored.append((score, -index, item))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    ranked = [item for _, _, item in scored]
    if limit is not None:
        return ranked[:limit]
    return ranked


def _score_candidate(
    candidate: Any, semantic_slots: dict[str, Any], query_text: str = ""
) -> int:
    candidate_text = _candidate_text(candidate).lower()
    score = 0

    normalized_query = "".join(query_text.lower().split())
    for term in _candidate_terms(candidate):
        normalized_term = "".join(term.lower().split())
        if normalized_term and normalized_term in normalized_query:
            score += 6

    for metric in semantic_slots.get("metrics") or []:
        if str(metric).lower() in candidate_text:
            score += 3

    dimension = semantic_slots.get("dimension")
    if dimension and str(dimension).lower() in candidate_text:
        score += 2

    filters = semantic_slots.get("filters") or {}
    for key, value in filters.items():
        if str(key).lower() in candidate_text or str(value).lower() in candidate_text:
            score += 2

    if semantic_slots.get("time_range") and any(
        token in candidate_text for token in ("date", "日期", "时间")
    ):
        score += 1

    if any(token in candidate_text for token in ("fact_order", "订单", "order_amount")):
        score += 1

    if score == 0:
        score -= 1
    return score


def _candidate_terms(candidate: Any) -> list[str]:
    if is_dataclass(candidate):
        candidate = asdict(candidate)
    if isinstance(candidate, dict):
        terms = [str(candidate.get("name", "")), str(candidate.get("id", ""))]
        terms.extend(str(term) for term in candidate.get("alias", []) or [])
        return terms
    terms = [str(getattr(candidate, "name", "")), str(getattr(candidate, "id", ""))]
    terms.extend(str(term) for term in getattr(candidate, "alias", []) or [])
    return terms


def _candidate_text(candidate: Any) -> str:
    if is_dataclass(candidate):
        candidate = asdict(candidate)

    if isinstance(candidate, dict):
        values = []
        for value in candidate.values():
            if isinstance(value, list):
                values.extend(str(item) for item in value)
            elif isinstance(value, dict):
                values.extend(f"{key}={inner}" for key, inner in value.items())
            else:
                values.append(str(value))
        return " ".join(values)

    attrs = []
    for attr in ("name", "description", "alias", "role", "table_id"):
        if hasattr(candidate, attr):
            value = getattr(candidate, attr)
            if isinstance(value, list):
                attrs.extend(str(item) for item in value)
            else:
                attrs.append(str(value))
    return " ".join(attrs)
