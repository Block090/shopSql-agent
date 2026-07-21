"""上下文改写结果校验。"""

AVAILABLE_DIMENSIONS = {"大区", "商品品类", "商品", "会员等级", "日期"}
AVAILABLE_METRICS = {"GMV", "销售额", "销量", "订单数"}
MIN_EXECUTE_CONFIDENCE = 0.8


def validate_rewrite_payload(payload: dict) -> tuple[bool, str]:
    """校验 LLM/规则输出是否允许进入 SQL 生成。"""

    confidence = payload.get("confidence")
    if isinstance(confidence, (int, float)) and confidence < MIN_EXECUTE_CONFIDENCE:
        return False, "上下文改写置信度较低，需要用户确认。"

    slots = payload.get("semantic_slots") or {}
    if not isinstance(slots, dict):
        return False, "语义槽位结构不合法，需要用户确认。"
    dimension = slots.get("dimension")
    if dimension and dimension not in AVAILABLE_DIMENSIONS:
        return False, f"当前数据知识库中没有找到维度：{dimension}"

    for metric in slots.get("metrics") or []:
        if metric not in AVAILABLE_METRICS:
            return False, f"当前数据知识库中没有找到指标：{metric}"

    sort = slots.get("sort") or {}
    if sort and not isinstance(sort, dict):
        return False, "排序字段结构不合法，需要用户确认。"

    sort_field = sort.get("field")
    if sort_field and sort_field not in AVAILABLE_METRICS:
        return False, f"排序字段不在可用指标范围内：{sort_field}"

    return True, ""
