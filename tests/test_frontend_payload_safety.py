from app.core.frontend_payload_safety import (
    sanitize_frontend_payload,
    sanitize_frontend_text,
)


def test_sanitize_frontend_payload_masks_database_columns_and_tables():
    payload = {
        "type": "result",
        "data": [
            {
                "product_name": "Galaxy S24 Ultra",
                "date_id": 20250401,
                "order_amount": 28497,
                "fact_order": "should_not_leak",
            }
        ],
    }

    sanitized = sanitize_frontend_payload(payload)

    assert sanitized["data"] == [
            {
                "商品": "Galaxy S24 Ultra",
                "日期": 20250401,
                "销售额": 28497,
                "业务数据": "业务字段",
            }
        ]
    assert "product_name" not in str(sanitized)
    assert "date_id" not in str(sanitized)
    assert "fact_order" not in str(sanitized)


def test_sanitize_frontend_text_masks_raw_identifiers():
    text = sanitize_frontend_text(
        "返回 5 行，字段：product_name、order_amount，来自 fact_order"
    )

    assert text == "返回 5 行，字段：商品、销售额，来自 业务数据"
