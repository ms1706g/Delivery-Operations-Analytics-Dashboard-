-- Delivery Operations Analytics Dashboard
-- All currency values are INR.

-- 1. CPD by city
SELECT
    city,
    COUNT(*) AS orders_delivered,
    ROUND(SUM(delivery_cost), 2) AS total_delivery_cost,
    ROUND(SUM(delivery_cost) / COUNT(*), 2) AS cpd
FROM delivery_metrics
GROUP BY city
ORDER BY cpd DESC;

-- 2. CPD by month
SELECT
    SUBSTR(order_date, 1, 7) AS order_month,
    COUNT(*) AS orders_delivered,
    ROUND(SUM(delivery_cost) / COUNT(*), 2) AS cpd
FROM delivery_metrics
GROUP BY SUBSTR(order_date, 1, 7)
ORDER BY order_month;

-- 3. CPD by rider (minimum 20 completed deliveries)
SELECT
    dm.rider_id,
    r.rider_name,
    r.city,
    COUNT(*) AS orders_delivered,
    ROUND(AVG(dm.delivery_cost), 2) AS cpd
FROM delivery_metrics dm
JOIN riders r ON r.rider_id = dm.rider_id
GROUP BY dm.rider_id, r.rider_name, r.city
HAVING COUNT(*) >= 20
ORDER BY cpd DESC;

-- 4. Top 10 riders by productivity
SELECT
    rdm.rider_id,
    r.rider_name,
    r.city,
    SUM(rdm.orders_delivered) AS orders_delivered,
    ROUND(SUM(rdm.orders_delivered) / SUM(rdm.shift_hours), 3) AS productivity
FROM rider_daily_metrics rdm
JOIN riders r ON r.rider_id = rdm.rider_id
GROUP BY rdm.rider_id, r.rider_name, r.city
ORDER BY productivity DESC
LIMIT 10;

-- 5. Bottom 10 riders by productivity (minimum 20 active days)
SELECT
    rdm.rider_id,
    r.rider_name,
    r.city,
    COUNT(*) AS active_days,
    SUM(rdm.orders_delivered) AS orders_delivered,
    ROUND(SUM(rdm.orders_delivered) / SUM(rdm.shift_hours), 3) AS productivity
FROM rider_daily_metrics rdm
JOIN riders r ON r.rider_id = rdm.rider_id
GROUP BY rdm.rider_id, r.rider_name, r.city
HAVING COUNT(*) >= 20
ORDER BY productivity ASC
LIMIT 10;

-- 6. 1P vs 3P comparison
WITH delivery_summary AS (
    SELECT
        employment_type,
        COUNT(*) AS orders_delivered,
        AVG(delivery_cost) AS avg_cpd,
        AVG(delivery_distance_km) AS avg_distance_km
    FROM delivery_metrics
    GROUP BY employment_type
),
rider_summary AS (
    SELECT
        employment_type,
        AVG(productivity) AS avg_daily_productivity,
        AVG(utilization_rate) AS avg_utilization_rate
    FROM rider_daily_metrics
    GROUP BY employment_type
)
SELECT
    d.employment_type,
    d.orders_delivered,
    ROUND(d.avg_cpd, 2) AS avg_cpd,
    ROUND(d.avg_distance_km, 2) AS avg_distance_km,
    ROUND(r.avg_daily_productivity, 3) AS avg_daily_productivity,
    ROUND(r.avg_utilization_rate * 100, 2) AS avg_utilization_pct
FROM delivery_summary d
JOIN rider_summary r USING (employment_type);

-- 7. Rate card reconciliation summary
SELECT
    employment_type,
    COUNT(*) AS deliveries,
    ROUND(SUM(expected_payout), 2) AS expected_payout,
    ROUND(SUM(actual_payout), 2) AS actual_payout,
    ROUND(SUM(payout_variance), 2) AS variance,
    ROUND(100.0 * SUM(payout_variance) / NULLIF(SUM(expected_payout), 0), 2) AS variance_pct
FROM delivery_metrics
GROUP BY employment_type;

-- 8. Largest payout variances for investigation
SELECT
    order_id,
    order_date,
    rider_id,
    city,
    employment_type,
    expected_payout,
    actual_payout,
    payout_variance
FROM delivery_metrics
ORDER BY ABS(payout_variance) DESC
LIMIT 50;

-- 9. Cost anomalies using the project definition:
-- delivery cost > population mean + two population standard deviations.
WITH moments AS (
    SELECT
        AVG(delivery_cost) AS mean_cost,
        AVG(delivery_cost * delivery_cost) AS mean_square_cost
    FROM delivery_metrics
),
threshold AS (
    SELECT
        mean_cost,
        SQRT(mean_square_cost - mean_cost * mean_cost) AS stddev_cost
    FROM moments
)
SELECT
    dm.order_id,
    dm.order_date,
    dm.city,
    dm.rider_id,
    dm.delivery_cost,
    ROUND(t.mean_cost, 2) AS mean_cost,
    ROUND(t.stddev_cost, 2) AS stddev_cost,
    ROUND(t.mean_cost + 2 * t.stddev_cost, 2) AS anomaly_threshold
FROM delivery_metrics dm
CROSS JOIN threshold t
WHERE dm.delivery_cost > t.mean_cost + 2 * t.stddev_cost
ORDER BY dm.delivery_cost DESC;

-- 10. Weekly trend
SELECT *
FROM weekly_kpis
ORDER BY week_start, city;

-- 11. Monthly trend
SELECT *
FROM monthly_kpis
ORDER BY month_start, city;
