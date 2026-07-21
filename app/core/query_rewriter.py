"""
多轮问数上下文改写。

第一版只处理非常明确的追问，不把完整问题交给规则强行重写。
同时返回 context_trace，方便前端解释“系统理解为……”。
"""

import re
from dataclasses import dataclass

REGIONS = ["华东", "华北", "华南", "华中", "西南", "西北", "东北"]
FOLLOW_UP_HINTS = ["那", "呢", "换成", "改成", "再看", "再查", "想查"]
METRIC_REPLACEMENTS = {
    "订单数": ["GMV", "销售额", "销量", "总销量"],
    "销售额": ["GMV", "订单数", "销量", "总销量"],
    "GMV": ["销售额", "订单数", "销量", "总销量"],
    "销量": ["GMV", "销售额", "订单数"],
}
DIMENSION_KEYWORDS = {
    "商品品类": ["商品品类", "品类"],
    "商品": ["商品"],
    "会员等级": ["会员等级"],
    "日期": ["日期", "每天", "每日"],
    "大区": ["各大区", "大区", "各地区", "按地区", "分地区"],
}


@dataclass(frozen=True)
class QueryRewriteResult:
    """上下文改写结果，兼顾 Agent 执行和前端解释展示。"""

    original_query: str
    resolved_query: str
    is_follow_up: bool
    inherited_context: dict
    overwritten_context: dict
    source_turn_id: int | str | None
    rewrite_method: str
    semantic_slots: dict | None = None
    confidence: float = 1.0
    needs_clarification: bool = False
    clarification_question: str = ""

    @property
    def context_trace(self) -> dict:
        """转成可 JSON 序列化的上下文轨迹。"""

        return {
            "original_query": self.original_query,
            "resolved_query": self.resolved_query,
            "is_follow_up": self.is_follow_up,
            "inherited_context": self.inherited_context,
            "overwritten_context": self.overwritten_context,
            "source_turn_id": self.source_turn_id,
            "rewrite_method": self.rewrite_method,
            "confidence": self.confidence,
        }


def rewrite_query_with_history(query: str, recent_turns: list[dict]) -> str:
    """兼容旧调用：只返回改写后的完整问题字符串。"""

    return rewrite_query_with_trace(query, recent_turns).resolved_query


def rewrite_query_with_trace(query: str, recent_turns: list[dict]) -> QueryRewriteResult:
    """根据最近历史把省略式追问补全，并返回可解释的上下文轨迹。"""

    normalized_query = query.strip()
    if not normalized_query or not recent_turns:
        return _no_rewrite_result(normalized_query)

    latest_turn = _select_context_turn(recent_turns)
    last_query = _get_resolved_query_from_turn(latest_turn)
    if not last_query or not _looks_like_follow_up(normalized_query):
        return _no_rewrite_result(normalized_query)

    inherited_context = _extract_inherited_context(last_query)
    previous_slots = _get_previous_semantic_slots(latest_turn, last_query)
    source_turn_id = latest_turn.get("id") or latest_turn.get("history_id")

    dimension = _extract_dimension(normalized_query)
    metric = _extract_metric(normalized_query)
    sort = _extract_sort(normalized_query, metric)
    time_range = _extract_time_follow_up(
        normalized_query,
        previous_slots.get("time_range") or _extract_time_range(last_query),
    )
    if time_range:
        semantic_slots = _merge_semantic_slots(previous_slots, time_range=time_range)
        resolved_query = _build_query_from_slots(semantic_slots)
        return QueryRewriteResult(
            original_query=normalized_query,
            resolved_query=resolved_query,
            is_follow_up=True,
            inherited_context=_context_from_slots(
                previous_slots, keep=["dimension", "metrics", "filters", "sort"]
            ),
            overwritten_context={"time_range": time_range},
            source_turn_id=source_turn_id,
            rewrite_method="rule",
            semantic_slots=semantic_slots,
            confidence=0.88,
        )

    if dimension and metric:
        semantic_slots = _merge_semantic_slots(
            previous_slots,
            dimension=dimension,
            metrics=[metric],
            sort=sort,
        )
        resolved_query = _build_query_from_slots(semantic_slots)
        overwritten_context = {"dimension": dimension, "metrics": [metric]}
        if sort:
            overwritten_context["sort"] = f"{sort['field']} 从高到低"
        return QueryRewriteResult(
            original_query=normalized_query,
            resolved_query=resolved_query,
            is_follow_up=True,
            inherited_context=_context_from_slots(previous_slots, keep=["time_range", "filters"]),
            overwritten_context=overwritten_context,
            source_turn_id=source_turn_id,
            rewrite_method="rule",
            semantic_slots=semantic_slots,
            confidence=0.86,
        )

    region = _extract_region(normalized_query)
    if region:
        resolved_query = _rewrite_region_follow_up(last_query, region)
        semantic_slots = _merge_semantic_slots(
            previous_slots,
            filters={**(previous_slots.get("filters") or {}), "region": region},
        )
        return QueryRewriteResult(
            original_query=normalized_query,
            resolved_query=resolved_query,
            is_follow_up=True,
            inherited_context=inherited_context,
            overwritten_context={"region": region},
            source_turn_id=source_turn_id,
            rewrite_method="rule",
            semantic_slots=semantic_slots,
            confidence=0.9,
        )

    if metric:
        resolved_query = _rewrite_metric_follow_up(last_query, metric)
        semantic_slots = _merge_semantic_slots(previous_slots, metrics=[metric])
        return QueryRewriteResult(
            original_query=normalized_query,
            resolved_query=resolved_query,
            is_follow_up=True,
            inherited_context=inherited_context,
            overwritten_context={"metrics": [metric]},
            source_turn_id=source_turn_id,
            rewrite_method="rule",
            semantic_slots=semantic_slots,
            confidence=0.82,
        )

    return _no_rewrite_result(normalized_query)


def _no_rewrite_result(query: str) -> QueryRewriteResult:
    """普通完整问题或无法确定的追问不强行改写。"""

    return QueryRewriteResult(
        original_query=query,
        resolved_query=query,
        is_follow_up=False,
        inherited_context={},
        overwritten_context={},
        source_turn_id=None,
        rewrite_method="none",
        semantic_slots=_extract_semantic_slots(query),
        confidence=1.0,
    )


def _select_context_turn(recent_turns: list[dict]) -> dict:
    """从历史中选择最适合继承的完整分析上下文。"""

    for turn in recent_turns:
        last_query = _get_resolved_query_from_turn(turn)
        slots = _get_previous_semantic_slots(turn, last_query)
        if _is_complete_analysis_slots(slots):
            return turn
    return recent_turns[0]


def _get_resolved_query_from_turn(latest_turn: dict) -> str:
    """读取一轮完整问题，优先使用已改写后的 resolved_query。"""

    return (
        latest_turn.get("resolved_query")
        or latest_turn.get("query")
        or latest_turn.get("user_query")
        or ""
    ).strip()


def _is_complete_analysis_slots(slots: dict) -> bool:
    """可继承上下文必须至少包含维度和指标，避免坏追问污染后续追问。"""

    normalized = _normalize_semantic_slots(slots)
    return bool(normalized.get("dimension") and normalized.get("metrics"))


def _looks_like_follow_up(query: str) -> bool:
    """判断当前问题是否像追问，完整问题不进入改写。"""

    return any(hint in query for hint in FOLLOW_UP_HINTS) and len(query) <= 18


def _extract_region(query: str) -> str | None:
    """提取追问里的地区词。"""

    for region in REGIONS:
        if region in query:
            return region
    return None


def _extract_metric(query: str) -> str | None:
    """提取追问里的指标词。"""

    metrics = _extract_metrics(query)
    return metrics[0] if metrics else None


def _extract_metrics(query: str) -> list[str]:
    """按用户表达顺序提取指标，避免多指标追问只保留一个。"""

    matches = []
    for metric in METRIC_REPLACEMENTS:
        index = query.find(metric)
        if index >= 0:
            matches.append((index, metric))
    matches.sort(key=lambda item: item[0])
    return list(dict.fromkeys(metric for _, metric in matches))


def _extract_dimension(query: str) -> str | None:
    """提取追问里的分析维度。"""

    for dimension, keywords in DIMENSION_KEYWORDS.items():
        if any(keyword in query for keyword in keywords):
            return dimension
    return None


def _extract_sort(query: str, metric: str | None) -> dict | None:
    """提取排序意图，第一版默认“排序”表示从高到低。"""

    if not metric:
        return None
    if "排序" in query or "排行" in query or "最高" in query:
        return {"field": metric, "direction": "desc"}
    return None


def _extract_limit(query: str) -> int | None:
    """提取 TopN 限制，用于追问继承。"""

    match = re.search(r"前\s*(\d+)\s*个?", query)
    if not match:
        match = re.search(r"top\s*(\d+)", query, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _get_previous_semantic_slots(latest_turn: dict, last_query: str) -> dict:
    """优先使用历史里的 semantic_slots；旧记录没有时从自然语言问题中抽取基础槽位。"""

    slots = latest_turn.get("semantic_slots")
    if isinstance(slots, dict) and slots:
        return _normalize_semantic_slots(slots)

    return _normalize_semantic_slots(
        {
            "time_range": _extract_time_range(last_query),
            "dimension": _extract_dimension(last_query),
            "metrics": _extract_metrics(last_query),
            "filters": _extract_filters(last_query),
            "sort": _extract_sort(last_query, _extract_metric(last_query)),
            "limit": _extract_limit(last_query),
        }
    )


def _merge_semantic_slots(
    previous_slots: dict,
    *,
    time_range: str | None = None,
    dimension: str | None = None,
    metrics: list[str] | None = None,
    filters: dict | None = None,
    sort: dict | None = None,
) -> dict:
    """在上一轮槽位基础上覆盖当前追问明确提到的槽位。"""

    slots = _normalize_semantic_slots(previous_slots)
    if time_range is not None:
        slots["time_range"] = time_range
    if dimension is not None:
        slots["dimension"] = dimension
    if metrics is not None:
        slots["metrics"] = metrics
    if filters is not None:
        slots["filters"] = filters
    if sort is not None:
        slots["sort"] = sort
    return slots


def _normalize_semantic_slots(slots: dict) -> dict:
    """统一语义槽位结构，避免旧历史缺字段导致前端和测评处理分叉。"""

    return {
        "time_range": slots.get("time_range"),
        "dimension": slots.get("dimension"),
        "metrics": slots.get("metrics") or [],
        "filters": slots.get("filters") or {},
        "sort": slots.get("sort"),
        "limit": slots.get("limit"),
    }


def _empty_semantic_slots() -> dict:
    """返回空槽位。"""

    return _normalize_semantic_slots({})


def _extract_semantic_slots(query: str) -> dict:
    """从完整自然语言问题中抽取可继承的基础槽位。"""

    return _normalize_semantic_slots(
        {
            "time_range": _extract_time_range(query),
            "dimension": _extract_dimension(query),
            "metrics": _extract_metrics(query),
            "filters": _extract_filters(query),
            "sort": _extract_sort(query, _extract_metric(query)),
            "limit": _extract_limit(query),
        }
    )


def _context_from_slots(slots: dict, keep: list[str]) -> dict:
    """从槽位生成可展示的继承上下文。"""

    context = {}
    normalized = _normalize_semantic_slots(slots)
    for key in keep:
        value = normalized.get(key)
        if value:
            context[key] = value
    return context


def _build_query_from_slots(slots: dict) -> str:
    """把结构化槽位转成给后续 Agent 使用的完整自然语言问题。"""

    time_range = slots.get("time_range") or ""
    dimension = slots.get("dimension") or "对象"
    filters = slots.get("filters") or {}
    metrics = slots.get("metrics") or ["指标"]
    metric_text = "和".join(metrics)
    query = (
        f"统计 {time_range}{_filter_phrase(filters)}"
        f"{_dimension_phrase(dimension)}{_metric_phrase(metric_text)}"
    ).strip()

    sort = slots.get("sort")
    if sort and sort.get("field"):
        direction_text = "从高到低" if sort.get("direction") == "desc" else "从低到高"
        query = f"{query}，并按 {sort['field']} {direction_text}排序"
    if slots.get("limit"):
        query = f"{query}，返回前 {slots['limit']} 个"
    return query


def _dimension_phrase(dimension: str) -> str:
    """维度转自然语言片段。"""

    if dimension == "大区":
        return "各大区"
    if dimension == "商品品类":
        return "各商品品类"
    if dimension == "商品":
        return "各商品"
    if dimension == "会员等级":
        return "各会员等级"
    if dimension == "日期":
        return "每天"
    return dimension


def _filter_phrase(filters: dict) -> str:
    """过滤条件转自然语言片段，确保权限范围类条件不会在追问中丢失。"""

    region = filters.get("region")
    if region:
        return f"{region}地区"
    return ""


def _extract_filters(query: str) -> dict:
    """从完整问题中抽取可继承过滤条件。"""

    filters = {}
    region = _extract_region(query)
    if region:
        filters["region"] = region
    return filters


def _metric_phrase(metric_text: str) -> str:
    """中文指标不额外加空格，英文指标保留分隔。"""

    if re.match(r"^[A-Za-z]", metric_text):
        return f"的 {metric_text}"
    return f"的{metric_text}"


def _extract_inherited_context(last_query: str) -> dict:
    """从上一轮问题中抽取可解释的继承条件。"""

    context = {}
    time_range = _extract_time_range(last_query)
    if time_range:
        context["time_range"] = time_range

    metrics = _extract_metrics(last_query)
    if metrics:
        # 中文注释：保持出现顺序去重，避免“GMV”在排序和指标里重复展示。
        context["metrics"] = list(dict.fromkeys(metrics))

    if "从高到低" in last_query:
        sort_metric = context.get("metrics", ["指标"])[0]
        context["sort"] = f"{sort_metric} 从高到低"
    elif "从低到高" in last_query:
        sort_metric = context.get("metrics", ["指标"])[0]
        context["sort"] = f"{sort_metric} 从低到高"

    return context


def _extract_time_range(query: str) -> str | None:
    """提取第一版支持的高频时间范围。"""

    query = _normalize_chinese_month(query)
    if "2025 年第一季度" in query:
        return "2025 年第一季度"
    if "2025 年第二季度" in query:
        return "2025 年第二季度"
    month_match = re.search(r"(20\d{2})\s*年\s*(1[0-2]|[1-9])\s*月份?", query)
    if month_match:
        return f"{month_match.group(1)} 年 {int(month_match.group(2))} 月"
    return None


def _extract_time_follow_up(query: str, previous_time_range: str | None) -> str | None:
    """从“那第二季度”这类追问中提取新时间，并继承上一轮年份。"""

    query = _normalize_chinese_month(query)
    year = "2025"
    if previous_time_range:
        for candidate in ["2025", "2026"]:
            if candidate in previous_time_range:
                year = candidate
                break

    quarter_aliases = {
        "第一季度": "第一季度",
        "一季度": "第一季度",
        "第二季度": "第二季度",
        "二季度": "第二季度",
        "第三季度": "第三季度",
        "三季度": "第三季度",
        "第四季度": "第四季度",
        "四季度": "第四季度",
    }
    for alias, quarter in quarter_aliases.items():
        if alias in query:
            return f"{year} 年{quarter}"
    month_match = re.search(r"(1[0-2]|[1-9])\s*月份?", query)
    if month_match:
        return f"{year} 年 {int(month_match.group(1))} 月"
    return None


def _normalize_chinese_month(query: str) -> str:
    """把“四月份”这类中文月份先转成数字月份，避免被当成指标前缀。"""

    month_aliases = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
        "十一": 11,
        "十二": 12,
    }
    for alias, month in sorted(
        month_aliases.items(), key=lambda item: len(item[0]), reverse=True
    ):
        query = re.sub(fr"{alias}\s*月份?", f"{month}月份", query)
    return query


def _rewrite_region_follow_up(last_query: str, region: str) -> str:
    """继承上一轮时间和指标，将“大区”范围收窄为指定地区。"""

    if "2025 年第一季度" in last_query and ("GMV" in last_query or "销售额" in last_query):
        metric = "GMV" if "GMV" in last_query else "销售额"
        return f"统计 2025 年第一季度{region}地区的 {metric}"

    # 中文注释：兜底替换只处理已有地区或“大区”，避免凭空扩写过多内容。
    for old_region in REGIONS:
        if old_region in last_query:
            return last_query.replace(old_region, region, 1)
    if "各大区" in last_query:
        return last_query.replace("各大区", f"{region}地区", 1)
    return f"{last_query}，限定{region}地区"


def _rewrite_metric_follow_up(last_query: str, metric: str) -> str:
    """继承上一轮对象和时间，只替换指标口径。"""

    rewritten = last_query
    for old_metric in METRIC_REPLACEMENTS[metric]:
        rewritten = rewritten.replace(old_metric, metric)
    return _normalize_chinese_spaces(rewritten)


def _normalize_chinese_spaces(query: str) -> str:
    """清理替换指标后产生的中文语句多余空格。"""

    for metric in METRIC_REPLACEMENTS:
        query = query.replace(f" {metric}", metric).replace(f"{metric} ", metric)
    return query
