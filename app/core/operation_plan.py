"""
数据变更计划构造

第一版用规则构造常见电商数据变更方案。
注意：这里生成的 DELETE / UPDATE / INSERT 只用于审批展示，不会直接执行。
"""

from datetime import datetime
from typing import Any
from uuid import uuid4


def build_operation_plan(query: str, operation_type: str) -> dict[str, Any]:
    """根据用户问题和操作类型生成审批用变更计划"""

    if operation_type == "DELETE":
        return _build_delete_plan(query)
    if operation_type == "UPDATE":
        return _build_update_plan(query)
    if operation_type == "INSERT":
        return _build_insert_plan(query)
    return _unsupported_plan(query, operation_type)


def enrich_operation_governance(
    plan: dict[str, Any],
    query: str = "",
    impact_count: int = 0,
    preview_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """补全数据变更治理字段，用于前端审批卡片展示。"""

    enriched = dict(plan)
    operation_type = enriched.get("operation_type", "")
    target_table = enriched.get("target_table", "")
    condition_description = enriched.get("condition_description") or query or "未明确"

    enriched.setdefault("target_object", _infer_target_object(target_table))
    enriched.setdefault(
        "business_purpose",
        _infer_business_purpose(query, operation_type, enriched["target_object"]),
    )
    enriched.setdefault(
        "rollback_suggestion",
        _build_rollback_suggestion(operation_type, enriched["target_object"]),
    )
    enriched.setdefault("execution_policy", "plan_only")
    enriched.setdefault(
        "impact_summary",
        _build_impact_summary(
            operation_type,
            enriched["target_object"],
            condition_description,
            impact_count,
        ),
    )
    enriched.setdefault(
        "impact_dimensions",
        _infer_impact_dimensions(condition_description, target_table, preview_rows or []),
    )
    enriched.setdefault(
        "threshold_level",
        _calculate_threshold_level(operation_type, impact_count, enriched.get("risk_level", "")),
    )
    enriched.setdefault("approval_id", _build_approval_id())
    if _is_rejected_plan(enriched):
        enriched.setdefault("approval_status", "rejected")
        enriched.setdefault("execution_status", "blocked")
        enriched.setdefault("status_description", "变更条件不明确，方案已拒绝，系统不会执行写操作。")
    else:
        enriched.setdefault("approval_status", "pending")
        enriched.setdefault("execution_status", "not_executed")
        enriched.setdefault(
            "status_description",
            "当前仅生成变更方案，系统不会直接执行写操作。",
        )
    enriched.setdefault("execution_enabled", False)
    enriched.setdefault("submitter", "当前用户")
    enriched.setdefault("approver", "数据负责人")
    enriched.setdefault("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    return enriched


def _build_delete_plan(query: str) -> dict[str, Any]:
    """构造订单删除计划，第一版只支持 2025 年 3 月订单场景"""

    if "3 月" in query or "3月" in query or "2025" in query:
        where_clause = "date_id BETWEEN 20250301 AND 20250331"
        return {
            "operation_type": "DELETE",
            "target_table": "fact_order",
            "target_columns": [],
            "condition_description": "2025 年 3 月订单数据",
            "planned_sql": f"DELETE FROM fact_order WHERE {where_clause};",
            "impact_count_sql": (
                f"SELECT COUNT(*) AS impact_count FROM fact_order WHERE {where_clause} LIMIT 1"
            ),
            "impact_preview_sql": (
                "SELECT order_id, customer_id, product_id, date_id, region_id, "
                f"order_quantity, order_amount FROM fact_order WHERE {where_clause} LIMIT 20"
            ),
            "risk_level": "high",
            "requires_approval": True,
            "status": "draft",
            "warning": "第一版仅生成删除方案和影响范围预览，不会执行 DELETE。",
        }
    return _unsupported_plan(query, "DELETE")


def _build_update_plan(query: str) -> dict[str, Any]:
    """构造商品品类修改计划，第一版支持商品名称 + 品类改成某值"""

    if "iphone 15 pro" in query.lower() and "品类" in query:
        where_clause = "product_name = 'iPhone 15 Pro'"
        return {
            "operation_type": "UPDATE",
            "target_table": "dim_product",
            "target_columns": ["category"],
            "condition_description": "商品名称为 iPhone 15 Pro",
            "planned_sql": (
                "UPDATE dim_product SET category = '手机数码' "
                f"WHERE {where_clause};"
            ),
            "impact_count_sql": (
                f"SELECT COUNT(*) AS impact_count FROM dim_product WHERE {where_clause} LIMIT 1"
            ),
            "impact_preview_sql": (
                f"SELECT product_id, product_name, category, brand FROM dim_product WHERE {where_clause} LIMIT 20"
            ),
            "risk_level": "medium",
            "requires_approval": True,
            "status": "draft",
            "warning": "第一版仅生成修改方案和影响范围预览，不会执行 UPDATE。",
        }
    return _unsupported_plan(query, "UPDATE")


def _build_insert_plan(query: str) -> dict[str, Any]:
    """构造商品新增计划，第一版只生成审批方案，不生成真实主键"""

    if "商品" in query:
        return {
            "operation_type": "INSERT",
            "target_table": "dim_product",
            "target_columns": ["product_name", "category", "brand"],
            "condition_description": "新增商品数据",
            "planned_sql": (
                "INSERT INTO dim_product (product_id, product_name, category, brand) "
                "VALUES ('待生成', '小米 14 Pro', '手机数码', '小米');"
            ),
            "impact_count_sql": "",
            "impact_preview_sql": "",
            "risk_level": "medium",
            "requires_approval": True,
            "status": "draft",
            "warning": "第一版仅生成新增方案，不会执行 INSERT。",
        }
    return _unsupported_plan(query, "INSERT")


def _unsupported_plan(query: str, operation_type: str) -> dict[str, Any]:
    """无法安全解析条件时返回高风险计划，避免误生成可审批 SQL"""

    return {
        "operation_type": operation_type,
        "target_table": "",
        "target_columns": [],
        "condition_description": query,
        "planned_sql": "",
        "impact_count_sql": "",
        "impact_preview_sql": "",
        "risk_level": "critical",
        "requires_approval": False,
        "status": "rejected",
        "warning": "无法从问题中提取明确变更条件，已拒绝生成变更方案。",
    }


def _infer_target_object(target_table: str) -> str:
    if "order" in target_table:
        return "订单数据"
    if "product" in target_table:
        return "商品数据"
    if "customer" in target_table or "member" in target_table or "user" in target_table:
        return "会员数据"
    if target_table:
        return "业务数据"
    return "未识别业务对象"


def _infer_business_purpose(query: str, operation_type: str, target_object: str) -> str:
    normalized_query = query.strip()
    if operation_type == "DELETE" and "测试" in normalized_query:
        return f"清理测试{target_object}，避免测试数据影响业务分析。"
    if operation_type == "DELETE":
        return f"根据用户诉求清理{target_object}。"
    if operation_type == "UPDATE":
        return f"根据用户诉求修正{target_object}字段信息。"
    if operation_type == "INSERT":
        return f"根据用户诉求新增{target_object}。"
    return normalized_query or "根据用户诉求生成数据变更方案。"


def _build_rollback_suggestion(operation_type: str, target_object: str) -> str:
    if operation_type == "DELETE":
        return f"执行前导出命中订单 ID 和完整{target_object}备份，回滚时按备份重新导入。"
    if operation_type == "UPDATE":
        return "执行前备份命中记录的修改前记录和字段旧值，回滚时按主键恢复原值。"
    if operation_type == "INSERT":
        return f"执行前确认新增记录唯一键，回滚时按新增主键删除对应{target_object}。"
    return "暂不支持生成可靠回滚方案，需人工复核后处理。"


def _build_impact_summary(
    operation_type: str,
    target_object: str,
    condition_description: str,
    impact_count: int,
) -> str:
    if impact_count <= 0:
        return f"按条件“{condition_description}”未命中需要变更的{target_object}。"
    return (
        f"{operation_type} 操作预计影响 {impact_count} 行{target_object}，"
        f"命中条件为“{condition_description}”。"
    )


def _infer_impact_dimensions(
    condition_description: str,
    target_table: str,
    preview_rows: list[dict[str, Any]],
) -> list[str]:
    dimensions: list[str] = []
    if any(token in condition_description for token in ("年", "月", "date", "日期")):
        dimensions.append("时间")
    if any(token in condition_description for token in ("地区", "大区", "region")):
        dimensions.append("地区")
    if "product" in target_table or any(token in condition_description for token in ("商品", "品类")):
        dimensions.append("商品")
    if "order" in target_table or "订单" in condition_description:
        dimensions.append("订单")

    if preview_rows:
        sample_columns = set(preview_rows[0].keys())
        if "date_id" in sample_columns and "时间" not in dimensions:
            dimensions.append("时间")
        if "region_id" in sample_columns and "地区" not in dimensions:
            dimensions.append("地区")
        if "product_id" in sample_columns and "商品" not in dimensions:
            dimensions.append("商品")

    return dimensions or ["变更条件"]


def _calculate_threshold_level(
    operation_type: str,
    impact_count: int,
    risk_level: str,
) -> str:
    if impact_count <= 0:
        return "none"
    if operation_type == "DELETE" or impact_count > 100 or risk_level in {"high", "critical"}:
        return "high"
    return "medium"


def _is_rejected_plan(plan: dict[str, Any]) -> bool:
    return plan.get("status") == "rejected" or plan.get("requires_approval") is False


def _build_approval_id() -> str:
    today = datetime.now().strftime("%Y%m%d")
    suffix = uuid4().hex[:4].upper()
    return f"CHG-{today}-{suffix}"
