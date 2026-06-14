# Data Dictionary

All currency fields are Indian rupees (INR). Dates use ISO `YYYY-MM-DD`.

## riders

| Column | Type | Description |
|---|---|---|
| rider_id | TEXT | Unique rider identifier |
| rider_name | TEXT | Synthetic rider name |
| joining_date | DATE | Rider onboarding date |
| city | TEXT | Operating city |
| vehicle_type | TEXT | Bicycle, Motorcycle, or Electric Scooter |
| employment_type | TEXT | First-party (`1P`) or third-party (`3P`) |
| shift_hours | REAL | Planned hours per active shift |

## orders

| Column | Type | Description |
|---|---|---|
| order_id | TEXT | Unique order identifier |
| order_date | DATE | Operational date |
| rider_id | TEXT | Rider foreign key |
| city | TEXT | Delivery city |
| delivery_distance_km | REAL | Route distance in kilometers |
| delivery_time_minutes | REAL | Active delivery duration |
| customer_rating | REAL | Rating from 1 to 5; null when unavailable |
| order_value | REAL | Customer basket value |
| delivery_status | TEXT | Delivered, Cancelled, or Failed |

## payout_ratecard

| Column | Type | Description |
|---|---|---|
| vehicle_type | TEXT | Rate-card key |
| base_payout | REAL | Fixed payout component |
| payout_per_km | REAL | Variable distance component |
| payout_per_order | REAL | Completed-order incentive |

## partner_orders

| Column | Type | Description |
|---|---|---|
| order_id | TEXT | Matching order foreign key |
| partner_name | TEXT | Logistics partner |
| distance | REAL | Partner-reported distance |
| partner_fee | REAL | Partner invoice amount |
| delivery_time | REAL | Partner-reported duration |

## delivery_metrics

| Column | Type | Description |
|---|---|---|
| order_id | TEXT | Delivered order key |
| order_date | DATE | Delivery date |
| rider_id | TEXT | Rider key |
| city | TEXT | Delivery city |
| vehicle_type | TEXT | Rider vehicle |
| employment_type | TEXT | 1P or 3P |
| delivery_distance_km | REAL | Clean source distance |
| delivery_time_minutes | REAL | Clean source duration |
| order_value | REAL | Clean source basket value |
| expected_payout | REAL | Rate-card payout |
| actual_payout | REAL | Paid or invoiced amount |
| payout_variance | REAL | Actual minus expected |
| delivery_cost | REAL | Actual payout plus operating overhead |
| revenue | REAL | Revenue allocated to delivery |
| profit | REAL | Revenue minus delivery cost |
| profit_margin_pct | REAL | Profit divided by revenue, percentage |
| is_cost_anomaly | INTEGER | 1 when cost exceeds statistical threshold |

## rider_daily_metrics

| Column | Type | Description |
|---|---|---|
| metric_date | DATE | Activity date |
| rider_id | TEXT | Rider key |
| city | TEXT | Rider city |
| employment_type | TEXT | 1P or 3P |
| orders_delivered | INTEGER | Completed orders |
| distance_km | REAL | Total daily distance |
| active_delivery_hours | REAL | Sum of delivery durations |
| shift_hours | REAL | Planned shift hours |
| productivity | REAL | Orders per shift hour |
| utilization_rate | REAL | Active hours divided by shift hours, capped at 1 |
| delivery_cost | REAL | Total daily delivery cost |
| revenue | REAL | Total allocated daily revenue |
| profit | REAL | Total daily profit |

## weekly_kpis and monthly_kpis

These marts contain period start, city, delivered orders, distance, cost,
revenue, CPD, average productivity, and average utilization. `monthly_kpis`
also contains total profit.
