USE dw;

INSERT IGNORE INTO dim_date (date_id, year, quarter, month, day)
WITH RECURSIVE calendar_days AS (
    SELECT DATE('2025-04-01') AS dt
    UNION ALL
    SELECT DATE_ADD(dt, INTERVAL 1 DAY)
    FROM calendar_days
    WHERE dt < DATE('2025-06-30')
)
SELECT
    CAST(DATE_FORMAT(dt, '%Y%m%d') AS UNSIGNED) AS date_id,
    YEAR(dt) AS year,
    'Q2' AS quarter,
    MONTH(dt) AS month,
    DAY(dt) AS day
FROM calendar_days;

INSERT IGNORE INTO fact_order (
    order_id,
    customer_id,
    product_id,
    date_id,
    region_id,
    order_quantity,
    order_amount
)
WITH RECURSIVE calendar_days AS (
    SELECT DATE('2025-04-01') AS dt
    UNION ALL
    SELECT DATE_ADD(dt, INTERVAL 1 DAY)
    FROM calendar_days
    WHERE dt < DATE('2025-06-30')
),
order_slots AS (
    SELECT 1 AS slot_no
    UNION ALL
    SELECT 2
    UNION ALL
    SELECT 3
),
base_orders AS (
    SELECT
        dt,
        slot_no,
        ((DAYOFYEAR(dt) + slot_no * 3 - 1) MOD 20) + 1 AS customer_no,
        ((DAYOFYEAR(dt) + slot_no * 5 - 1) MOD 15) + 1 AS product_no,
        ((DAYOFYEAR(dt) + slot_no * 2 - 1) MOD 6) + 1 AS region_no,
        CASE
            WHEN ((DAYOFYEAR(dt) + slot_no * 5 - 1) MOD 15) + 1 IN (10, 11, 12, 13) THEN 4 + ((DAYOFYEAR(dt) + slot_no) MOD 18)
            WHEN ((DAYOFYEAR(dt) + slot_no * 5 - 1) MOD 15) + 1 IN (8, 9) THEN 1 + ((DAYOFYEAR(dt) + slot_no) MOD 3)
            ELSE 1
        END AS quantity
    FROM calendar_days
    CROSS JOIN order_slots
),
priced_orders AS (
    SELECT
        dt,
        slot_no,
        customer_no,
        product_no,
        region_no,
        quantity,
        CASE product_no
            WHEN 1 THEN 8999.00
            WHEN 2 THEN 9499.00
            WHEN 3 THEN 6999.00
            WHEN 4 THEN 5499.00
            WHEN 5 THEN 3200.00
            WHEN 6 THEN 899.00
            WHEN 7 THEN 1299.00
            WHEN 8 THEN 199.00
            WHEN 9 THEN 599.00
            WHEN 10 THEN 25.00
            WHEN 11 THEN 5.00
            WHEN 12 THEN 5.00
            WHEN 13 THEN 3.50
            WHEN 14 THEN 1399.00
            WHEN 15 THEN 899.00
        END AS unit_price
    FROM base_orders
)
SELECT
    CONCAT('ORD', DATE_FORMAT(dt, '%Y%m%d'), LPAD(slot_no + 100, 3, '0')) AS order_id,
    CONCAT('C', LPAD(customer_no, 3, '0')) AS customer_id,
    CONCAT('P', LPAD(product_no, 3, '0')) AS product_id,
    CAST(DATE_FORMAT(dt, '%Y%m%d') AS UNSIGNED) AS date_id,
    CONCAT('R', LPAD(region_no, 3, '0')) AS region_id,
    quantity AS order_quantity,
    ROUND(quantity * unit_price, 2) AS order_amount
FROM priced_orders;
