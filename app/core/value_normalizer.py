"""
业务字段值归一化

把用户自然语言里的字段值表达映射到更接近数据库真实值的标准表达，
用于字段值召回和测评指标计算。
"""

from collections.abc import Iterable

VALUE_ALIASES = {
    "q1": ["第一季度", "一季度", "1季度", "Q1", "q1"],
    "q2": ["第二季度", "二季度", "2季度", "Q2", "q2"],
    "q3": ["第三季度", "三季度", "3季度", "Q3", "q3"],
    "q4": ["第四季度", "四季度", "4季度", "Q4", "q4"],
    "华东": ["华东", "华东地区", "华东大区"],
    "华北": ["华北", "华北地区", "华北大区"],
    "华南": ["华南", "华南地区", "华南大区"],
    "华中": ["华中", "华中地区", "华中大区"],
    "西南": ["西南", "西南地区", "西南大区"],
    "黄金会员": ["黄金会员", "黄金"],
    "白银会员": ["白银会员", "白银"],
    "普通会员": ["普通会员", "普通"],
    "女": ["女性", "女"],
    "男": ["男性", "男"],
}

_ALIAS_TO_CANONICAL = {
    alias.strip().lower(): canonical
    for canonical, aliases in VALUE_ALIASES.items()
    for alias in aliases
}


def normalize_business_value(value: object) -> str:
    """把业务值表达归一化，未命中别名时返回清洗后的原值"""

    text = str(value).strip()
    if not text:
        return ""
    return _ALIAS_TO_CANONICAL.get(text.lower(), text.lower())


def expand_value_terms(values: Iterable[object]) -> list[str]:
    """为字段值检索补充标准值和别名"""

    expanded: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        canonical = normalize_business_value(text)
        terms = [text]
        terms.extend(VALUE_ALIASES.get(canonical, []))
        terms.append(canonical)
        for term in terms:
            normalized = str(term).strip()
            key = normalized.lower()
            if normalized and key not in seen:
                expanded.append(normalized)
                seen.add(key)
    return expanded
