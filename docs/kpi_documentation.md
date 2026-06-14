# KPI Documentation

## Cost Per Delivery

**Formula:** `SUM(delivery_cost) / COUNT(delivered orders)`

Only completed deliveries are included. Delivery cost contains actual rider or
partner payout plus an operating overhead allocation: INR 5.50 for 1P and
INR 2.50 for 3P.

## Rider Productivity

**Formula:** `orders_delivered / shift_hours`

Calculated at rider-day grain to avoid favoring riders solely because they work
more days. Period comparisons should use the average rider-day productivity or
recalculate as total orders divided by total shift hours.

## Rider Utilization

**Formula:** `active_delivery_hours / shift_hours`

Active delivery hours are the sum of completed delivery duration. Utilization
is capped at 100 percent because overlapping or batched order timestamps are
not modeled in the synthetic source.

## Expected and Actual Payout

**Expected payout:** `base_payout + distance * payout_per_km + payout_per_order`

For partner-feed 3P orders, actual payout is the partner invoice fee. For other
orders, a deterministic synthetic payment variance is applied so the project is
fully reproducible.

## Revenue and Profit

**Allocated revenue:** `MAX(30, order_value * 0.16 + 14)`

This approximates platform commission plus delivery/service revenue.

**Profit:** `revenue - delivery_cost`

**Profit margin:** `profit / revenue * 100`

## Cost Anomaly

**Rule:** `delivery_cost > population mean + 2 * population standard deviation`

The ETL persists the flag for dashboard performance. The SQL query pack also
recomputes the threshold from first and second moments, avoiding reliance on a
non-standard SQLite `STDDEV` function.

## Governance Notes

- Currency: INR
- Time zone assumption: local city operating date
- Null ratings are valid for non-delivered orders and missing feedback
- Cancelled and failed orders remain in the source table but are excluded from
  delivered-order KPIs
- Production implementations should version rate cards by effective date
