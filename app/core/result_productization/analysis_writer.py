"""基于事实摘要生成查询结果分析。"""

from __future__ import annotations

import asyncio
import json

from .analysis_validator import parse_result_analysis_json, validate_result_analysis
from .fact_extractor import extract_result_facts


async def analyze_result_with_fallback(
    query: str,
    resolved_query: str,
    result_data,
    llm_client=None,
    timeout_seconds: int = 6,
) -> dict:
    """优先使用 LLM 生成结构化结果分析，失败时回退到规则摘要。"""

    result_facts = extract_result_facts(result_data)
    fallback = build_rule_analysis(query, resolved_query, result_facts)

    try:
        payload = await asyncio.wait_for(
            _call_llm_result_analyzer(
                query=query,
                resolved_query=resolved_query,
                result_data=result_data,
                result_facts=result_facts,
                llm_client=llm_client,
            ),
            timeout=timeout_seconds,
        )
    except Exception:
        return {**fallback, "result_facts": result_facts, "generated_by": "rule_fallback"}

    is_valid, _ = validate_result_analysis(payload, result_facts)
    if not is_valid:
        return {**fallback, "result_facts": result_facts, "generated_by": "rule_fallback"}

    payload["result_facts"] = result_facts
    payload["generated_by"] = "llm"
    return payload


def build_rule_analysis(query: str, resolved_query: str, result_facts: dict) -> dict:
    """使用规则基于事实生成稳定兜底摘要。"""

    row_count = result_facts.get("row_count", 0)
    columns = "、".join(result_facts.get("columns") or [])
    summary = f"本次查询共返回 {row_count} 行结果，字段包括：{columns}。"

    insights: list[str] = []
    for metric, item in (result_facts.get("top_values") or {}).items():
        label = item.get("label")
        value = item.get("value")
        if label is None or value is None:
            continue
        insights.append(f"{metric}最高的是{label}，数值为 {value}。")
        if len(insights) >= 3:
            break

    if not insights:
        insights.append(f"系统已完成“{resolved_query or query}”的结果整理。")

    chart = None
    candidates = result_facts.get("chart_candidates") or []
    if candidates:
        chart = candidates[0]

    return {
        "summary": summary,
        "insights": insights,
        "chart_recommendation": chart,
    }


async def _call_llm_result_analyzer(
    query: str,
    resolved_query: str,
    result_data,
    result_facts: dict,
    llm_client=None,
) -> dict:
    client = llm_client
    if client is None:
        from app.agent.llm import llm as default_llm

        client = default_llm

    response = await client.ainvoke(
        _build_result_analysis_prompt(
            query=query,
            resolved_query=resolved_query,
            result_data=result_data,
            result_facts=result_facts,
        )
    )
    content = getattr(response, "content", response)
    return parse_result_analysis_json(str(content))


def _build_result_analysis_prompt(
    query: str,
    resolved_query: str,
    result_data,
    result_facts: dict,
) -> str:
    sample_rows = result_data[:5] if isinstance(result_data, list) else result_data
    return f"""
你是电商数据分析 Agent 的结果解读模块。
你只能基于给定的事实摘要和样例结果生成结论，不能编造字段、数字或业务结论。
如果数据不足以支撑结论，就不要输出那条洞察。
必须输出 JSON，不要输出 Markdown。

输入：
{json.dumps(
    {
        "query": query,
        "resolved_query": resolved_query,
        "result_facts": result_facts,
        "sample_rows": sample_rows,
    },
    ensure_ascii=False,
    default=str,
)}

输出 JSON 结构：
{{
  "summary": "",
  "insights": ["", ""],
  "chart_recommendation": {{
    "type": "",
    "x": "",
    "y": "",
    "reason": ""
  }}
}}
""".strip()
