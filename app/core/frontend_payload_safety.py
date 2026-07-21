"""Sanitize data before it is sent to the frontend."""

from __future__ import annotations

import re
from typing import Any

BUSINESS_LABELS = {
    "product_name": "商品",
    "product": "商品",
    "category": "商品品类",
    "category_name": "商品品类",
    "brand": "品牌",
    "region_name": "大区",
    "province": "省份",
    "country": "国家",
    "member_level": "会员等级",
    "gender": "性别",
    "date_id": "日期",
    "order_date": "订单日期",
    "month": "月份",
    "quarter": "季度",
    "year": "年份",
    "day": "日期",
    "order_amount": "销售额",
    "pay_amount": "支付金额",
    "gmv": "GMV",
    "order_quantity": "销量",
    "quantity": "销量",
    "order_count": "订单数",
    "customer_id": "客户",
    "user_id": "用户",
    "member_id": "会员",
    "phone": "敏感信息",
    "mobile": "敏感信息",
    "address": "敏感信息",
    "id_card": "敏感信息",
}

INTERNAL_IDENTIFIER_PATTERN = re.compile(
    r"\b(?:fact|dim|dwd|dws|ads|ods)_[A-Za-z0-9_]+\b|\b[A-Za-z]+_[A-Za-z0-9_]*\b"
)


def sanitize_frontend_payload(payload: Any) -> Any:
    """Return a frontend-safe copy of a payload."""

    if isinstance(payload, list):
        return [sanitize_frontend_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return [sanitize_frontend_payload(item) for item in payload]
    if isinstance(payload, dict):
        return {
            business_label(key): sanitize_frontend_payload(value)
            for key, value in payload.items()
        }
    if isinstance(payload, str):
        return sanitize_frontend_text(payload)
    return payload


def sanitize_frontend_text(text: Any) -> str:
    """Mask internal table and column identifiers in user-facing text."""

    raw_text = str(text or "")
    if not raw_text:
        return ""

    return INTERNAL_IDENTIFIER_PATTERN.sub(
        lambda match: business_label(match.group(0)), raw_text
    )


def business_label(name: Any) -> str:
    """Map a raw database identifier to a business-facing label."""

    text = str(name or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if text in BUSINESS_LABELS:
        return BUSINESS_LABELS[text]
    if lowered in BUSINESS_LABELS:
        return BUSINESS_LABELS[lowered]
    if lowered.startswith(("fact_", "dim_", "dwd_", "dws_", "ads_", "ods_")):
        return "业务数据"
    if re.fullmatch(r"[a-z]+_[a-z0-9_]*", text, flags=re.IGNORECASE):
        return "业务字段"
    return sanitize_frontend_text(text)
