"""
召回类评测指标

用于衡量字段 指标 字段值等候选信息是否在 TopK 结果中命中。
"""

from app.core.value_normalizer import normalize_business_value


def _normalize_items(items: list[str]) -> list[str]:
    """统一大小写，避免 GMV 和 gmv 这类差异影响评测"""

    return [normalize_business_value(item) for item in items if item and item.strip()]


def recall_at_k(expected: list[str], retrieved: list[str], k: int) -> float:
    """计算 Recall@K：期望项中有多少出现在前 K 个召回结果里"""

    expected_set = set(_normalize_items(expected))
    if not expected_set:
        return 1.0

    retrieved_set = set(_normalize_items(retrieved[:k]))
    return len(expected_set & retrieved_set) / len(expected_set)


def precision_at_k(expected: list[str], retrieved: list[str], k: int) -> float:
    """计算 Precision@K：前 K 个召回结果中有多少是期望项"""

    if k <= 0:
        return 0.0

    expected_set = set(_normalize_items(expected))
    retrieved_items = _normalize_items(retrieved[:k])
    if not retrieved_items:
        return 0.0

    return len(expected_set & set(retrieved_items)) / min(k, len(retrieved_items))


def contains_any_expected(expected: list[str], actual: list[str]) -> bool:
    """判断实际结果是否命中任意一个期望项"""

    expected_set = set(_normalize_items(expected))
    actual_set = set(_normalize_items(actual))
    return bool(expected_set & actual_set)
