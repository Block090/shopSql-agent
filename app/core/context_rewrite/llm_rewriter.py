"""LLM 结构化上下文改写适配层。"""

import json

from app.core.context_rewrite.validator import (
    AVAILABLE_DIMENSIONS,
    AVAILABLE_METRICS,
    MIN_EXECUTE_CONFIDENCE,
    validate_rewrite_payload,
)
from app.core.query_rewriter import QueryRewriteResult, rewrite_query_with_trace


def parse_llm_rewrite_json(content: str) -> dict:
    """解析 LLM 输出，要求必须是 JSON 对象。"""

    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("LLM 上下文改写结果必须是 JSON 对象")
    return payload


def validate_llm_rewrite_json(content: str) -> tuple[bool, dict, str]:
    """解析并校验 LLM 改写 JSON，返回是否可执行。"""

    try:
        payload = parse_llm_rewrite_json(content)
    except (json.JSONDecodeError, ValueError) as exc:
        return False, {}, f"LLM 上下文改写输出不是合法 JSON：{exc}"

    is_valid, reason = validate_rewrite_payload(payload)
    return is_valid, payload, reason


async def rewrite_query_with_llm_or_rule(
    current_query: str,
    recent_turns: list[dict],
    llm_client=None,
) -> QueryRewriteResult:
    """真实主流程入口：追问优先走 LLM 结构化改写，失败时规则兜底。"""

    rule_result = rewrite_query_with_trace(current_query, recent_turns)
    confirmation_result = _confirmed_clarification_result(current_query, recent_turns)
    if confirmation_result:
        return confirmation_result

    if _is_deterministic_rule_rewrite(rule_result):
        return rule_result

    if not recent_turns or not _maybe_follow_up(current_query):
        return rule_result

    try:
        payload = await _call_llm_rewriter(
            current_query=current_query,
            recent_turns=recent_turns,
            llm_client=llm_client,
        )
    except Exception:
        # 中文注释：LLM 改写不可用时不能阻断查询，回到规则版结果。
        return rule_result

    if payload.get("needs_clarification"):
        return _clarification_result(current_query, payload, rule_result)

    is_valid, reason = validate_rewrite_payload(payload)
    if not is_valid:
        if "置信度" in reason or "维度" in reason or "指标" in reason or "排序字段" in reason:
            return _clarification_result(current_query, payload, rule_result, reason)
        return rule_result

    payload = _merge_llm_payload_with_rule_context(payload, rule_result)
    return _payload_to_rewrite_result(current_query, payload, rule_result)


def _maybe_follow_up(query: str) -> bool:
    """规则预判：只判断是否可能是追问，不要求规则版一定能成功改写。"""

    normalized_query = query.strip()
    follow_up_hints = ["那", "呢", "换成", "改成", "再看", "再查", "想查", "按"]
    return bool(normalized_query) and len(normalized_query) <= 24 and any(
        hint in normalized_query for hint in follow_up_hints
    )


def _confirmed_clarification_result(
    current_query: str, recent_turns: list[dict]
) -> QueryRewriteResult | None:
    """用户确认上一轮澄清时，直接执行上一轮已确认的完整查询。"""

    if not recent_turns or not _looks_like_confirmation(current_query):
        return None

    latest_turn = recent_turns[0]
    if latest_turn.get("status") != "clarification_required":
        return None

    resolved_query = (latest_turn.get("resolved_query") or "").strip()
    if not resolved_query:
        return None

    semantic_slots = latest_turn.get("semantic_slots")
    if not isinstance(semantic_slots, dict):
        semantic_slots = {}

    return QueryRewriteResult(
        original_query=current_query.strip(),
        resolved_query=resolved_query,
        is_follow_up=True,
        inherited_context={"confirmed_query": resolved_query},
        overwritten_context={"confirmation": "yes"},
        source_turn_id=latest_turn.get("id") or latest_turn.get("history_id"),
        rewrite_method="confirmation",
        semantic_slots=semantic_slots,
        confidence=1.0,
        needs_clarification=False,
        clarification_question="",
    )


def _looks_like_confirmation(query: str) -> bool:
    """识别“是，按这个查询”这类确认语。"""

    normalized_query = query.strip()
    confirmation_hints = ["是", "对", "确认", "按这个", "就这个", "可以"]
    return any(hint in normalized_query for hint in confirmation_hints)


def _is_deterministic_rule_rewrite(result: QueryRewriteResult) -> bool:
    """高置信规则追问直接执行，避免 LLM 把已继承槽位改丢。"""

    return result.is_follow_up and result.confidence >= 0.88


def _merge_llm_payload_with_rule_context(
    payload: dict, rule_result: QueryRewriteResult
) -> dict:
    """LLM 可以改写表达，但不能丢掉规则已确定的过滤条件和核心槽位。"""

    rule_slots = rule_result.semantic_slots or {}
    llm_slots = payload.get("semantic_slots") or {}
    if not isinstance(llm_slots, dict):
        return payload

    merged_slots = dict(llm_slots)
    for key in ("time_range", "dimension", "metrics", "filters", "sort", "limit"):
        rule_value = rule_slots.get(key)
        llm_value = merged_slots.get(key)
        if rule_value and not llm_value:
            merged_slots[key] = rule_value

    rule_filters = rule_slots.get("filters") or {}
    llm_filters = merged_slots.get("filters") or {}
    if isinstance(rule_filters, dict) and isinstance(llm_filters, dict):
        merged_slots["filters"] = {**rule_filters, **llm_filters}

    return {**payload, "semantic_slots": merged_slots}


async def _call_llm_rewriter(
    current_query: str,
    recent_turns: list[dict],
    llm_client=None,
) -> dict:
    """调用 LLM 并解析 JSON。"""

    client = llm_client
    if client is None:
        from app.agent.llm import llm as default_llm

        client = default_llm

    response = await client.ainvoke(_build_rewrite_prompt(current_query, recent_turns))
    content = getattr(response, "content", response)
    return parse_llm_rewrite_json(str(content))


def _build_rewrite_prompt(current_query: str, recent_turns: list[dict]) -> str:
    """构造要求大模型只输出 JSON 的上下文改写 prompt。"""

    return f"""
你是电商数据分析 Agent 的上下文改写模块。

任务：
1. 判断当前问题是否是对历史问题的追问。
2. 如果是追问，结合最近历史和 semantic_slots 生成完整问题。
3. 只能使用给定的指标和维度。
4. 如果不确定，必须设置 needs_clarification=true。
5. 只能输出 JSON，不能输出解释文字。

可用指标：{json.dumps(sorted(AVAILABLE_METRICS), ensure_ascii=False)}
可用维度：{json.dumps(sorted(AVAILABLE_DIMENSIONS), ensure_ascii=False)}

最近历史：
{json.dumps(recent_turns, ensure_ascii=False, default=str)}

当前用户问题：
{current_query}

请输出 JSON：
{{
  "is_follow_up": true,
  "resolved_query": "",
  "semantic_slots": {{
    "time_range": null,
    "dimension": null,
    "metrics": [],
    "filters": {{}},
    "sort": null,
    "limit": null
  }},
  "inherited_context": {{}},
  "overwritten_context": {{}},
  "needs_clarification": false,
  "clarification_question": "",
  "confidence": 0.0,
  "rewrite_method": "llm"
}}
""".strip()


def _payload_to_rewrite_result(
    current_query: str,
    payload: dict,
    fallback: QueryRewriteResult,
) -> QueryRewriteResult:
    """把 LLM JSON 转成主流程统一使用的 QueryRewriteResult。"""

    return QueryRewriteResult(
        original_query=current_query,
        resolved_query=payload.get("resolved_query") or fallback.resolved_query,
        is_follow_up=bool(payload.get("is_follow_up", True)),
        inherited_context=payload.get("inherited_context") or {},
        overwritten_context=payload.get("overwritten_context") or {},
        source_turn_id=fallback.source_turn_id,
        rewrite_method="llm",
        semantic_slots=payload.get("semantic_slots") or fallback.semantic_slots,
        confidence=float(payload.get("confidence") or fallback.confidence),
        needs_clarification=False,
        clarification_question="",
    )


def _clarification_result(
    current_query: str,
    payload: dict,
    fallback: QueryRewriteResult,
    reason: str = "",
) -> QueryRewriteResult:
    """构造上下文改写澄清结果，不进入 SQL 生成。"""

    question = payload.get("clarification_question") or reason or "当前追问的上下文不够明确，请补充说明后再查询。"
    confidence = float(payload.get("confidence") or fallback.confidence)
    if confidence >= MIN_EXECUTE_CONFIDENCE:
        confidence = 0.5

    return QueryRewriteResult(
        original_query=current_query,
        resolved_query=payload.get("resolved_query") or fallback.resolved_query,
        is_follow_up=True,
        inherited_context=payload.get("inherited_context") or fallback.inherited_context,
        overwritten_context=payload.get("overwritten_context") or fallback.overwritten_context,
        source_turn_id=fallback.source_turn_id,
        rewrite_method="llm",
        semantic_slots=payload.get("semantic_slots") or fallback.semantic_slots,
        confidence=confidence,
        needs_clarification=True,
        clarification_question=question,
    )
