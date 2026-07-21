import unittest

from app.core.permission_guard import (
    filter_authorized_context,
    validate_sql_permission,
)


class PermissionGuardTest(unittest.TestCase):
    def test_filters_denied_columns_and_unauthorized_metrics_from_context(self):
        permission_context = {
            "allowed_tables": ["fact_order", "dim_customer"],
            "allowed_metrics": ["GMV"],
            "denied_columns": ["customer_phone"],
        }
        table_infos = [
            {
                "name": "fact_order",
                "role": "fact",
                "description": "order table",
                "columns": [
                    {"name": "order_amount", "type": "decimal", "role": "metric"},
                    {"name": "customer_id", "type": "int", "role": "fk"},
                ],
            },
            {
                "name": "dim_customer",
                "role": "dim",
                "description": "customer table",
                "columns": [
                    {"name": "customer_id", "type": "int", "role": "pk"},
                    {"name": "customer_phone", "type": "varchar", "role": "attr"},
                ],
            },
        ]
        metric_infos = [
            {
                "name": "GMV",
                "description": "total order amount",
                "relevant_columns": ["fact_order.order_amount"],
                "alias": [],
            },
            {
                "name": "利润",
                "description": "profit",
                "relevant_columns": ["fact_order.profit_amount"],
                "alias": [],
            },
        ]

        result = filter_authorized_context(
            table_infos=table_infos,
            metric_infos=metric_infos,
            permission_context=permission_context,
        )

        self.assertEqual(["fact_order", "dim_customer"], [t["name"] for t in result.table_infos])
        customer_columns = result.table_infos[1]["columns"]
        self.assertEqual(["customer_id"], [c["name"] for c in customer_columns])
        self.assertEqual(["GMV"], [m["name"] for m in result.metric_infos])

    def test_validate_sql_permission_rejects_sensitive_column(self):
        permission_context = {
            "allowed_tables": ["dim_customer"],
            "denied_columns": ["customer_phone"],
        }

        with self.assertRaisesRegex(ValueError, "sensitive column"):
            validate_sql_permission(
                "SELECT customer_phone FROM dim_customer LIMIT 10",
                permission_context,
            )

    def test_validate_sql_permission_requires_data_scope_condition(self):
        permission_context = {
            "allowed_tables": ["fact_order", "dim_region"],
            "data_scope": {"region_name": ["华东"]},
        }

        with self.assertRaisesRegex(ValueError, "data scope"):
            validate_sql_permission(
                "SELECT SUM(order_amount) AS GMV FROM fact_order LIMIT 100",
                permission_context,
            )

    def test_validate_sql_permission_allows_authorized_data_scope_condition(self):
        permission_context = {
            "allowed_tables": ["fact_order", "dim_region"],
            "data_scope": {"region_name": ["华东"]},
        }

        validate_sql_permission(
            "SELECT SUM(order_amount) AS GMV "
            "FROM fact_order JOIN dim_region ON fact_order.region_id = dim_region.region_id "
            "WHERE region_name = '华东' LIMIT 100",
            permission_context,
        )


if __name__ == "__main__":
    unittest.main()
