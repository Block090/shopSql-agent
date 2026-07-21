"""
上下文类评测指标

用于判断最终进入 SQL 生成上下文的表、字段、指标是否完整。
"""

from eval.metrics.retrieval_metrics import recall_at_k


def table_hit_rate(expected_tables: list[str], actual_tables: list[str]) -> float:
    """计算期望表命中率，空期望表视为命中"""

    return recall_at_k(expected_tables, actual_tables, len(actual_tables) or 1)


def has_all_expected_tables(expected_tables: list[str], actual_tables: list[str]) -> bool:
    """判断最终上下文是否包含所有期望表"""

    return table_hit_rate(expected_tables, actual_tables) >= 1.0


def context_completeness(
    expected_tables: list[str],
    actual_tables: list[str],
    expected_columns: list[str],
    actual_columns: list[str],
) -> float:
    """综合表和字段的上下文完整性"""

    table_score = table_hit_rate(expected_tables, actual_tables)
    column_score = recall_at_k(expected_columns, actual_columns, len(actual_columns) or 1)
    return (table_score + column_score) / 2


def context_noise_rate(expected_items: list[str], actual_items: list[str]) -> float:
    """计算无关上下文占比"""

    if not actual_items:
        return 0.0

    expected = {item.strip().lower() for item in expected_items if item and item.strip()}
    actual = [item.strip().lower() for item in actual_items if item and item.strip()]
    if not actual:
        return 0.0

    noisy_count = sum(1 for item in actual if item not in expected)
    return noisy_count / len(actual)
