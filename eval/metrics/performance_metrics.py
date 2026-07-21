"""
性能类评测指标
"""


def average(values) -> float:
    """计算平均值，空集合返回 0"""

    value_list = list(values)
    if not value_list:
        return 0.0
    return sum(value_list) / len(value_list)


def percentile(values, percent: float) -> float:
    """计算简单百分位数，空集合返回 0"""

    value_list = sorted(values)
    if not value_list:
        return 0.0
    index = min(len(value_list) - 1, max(0, round((len(value_list) - 1) * percent)))
    return value_list[index]
