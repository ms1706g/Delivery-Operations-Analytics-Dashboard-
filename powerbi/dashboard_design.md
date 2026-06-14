# Power BI Dashboard Design

## Data Model

Import these SQLite tables:

- `delivery_metrics` as the delivery fact
- `rider_daily_metrics` as the rider-day fact
- `riders` as the rider dimension
- `orders` for status and rating analysis
- `monthly_kpis` and `weekly_kpis` as performance aggregates

Create a calendar table spanning 2024-01-01 through 2025-12-31. Relate
`Calendar[Date]` one-to-many to both fact date fields. Relate
`riders[rider_id]` one-to-many to each fact. Keep cross-filter direction single.

## Core DAX Measures

```DAX
Delivered Orders =
COUNTROWS(delivery_metrics)

Total Riders =
DISTINCTCOUNT(delivery_metrics[rider_id])

Total Delivery Cost =
SUM(delivery_metrics[delivery_cost])

Average CPD =
DIVIDE([Total Delivery Cost], [Delivered Orders])

Average Distance =
AVERAGE(delivery_metrics[delivery_distance_km])

Expected Payout =
SUM(delivery_metrics[expected_payout])

Actual Payout =
SUM(delivery_metrics[actual_payout])

Payout Variance =
[Actual Payout] - [Expected Payout]

Average Productivity =
AVERAGE(rider_daily_metrics[productivity])

Average Utilization % =
AVERAGE(rider_daily_metrics[utilization_rate])

Cost Anomalies =
CALCULATE(
    COUNTROWS(delivery_metrics),
    delivery_metrics[is_cost_anomaly] = 1
)

Anomaly Rate =
DIVIDE([Cost Anomalies], [Delivered Orders])

Total Profit =
SUM(delivery_metrics[profit])

Profit Margin % =
DIVIDE([Total Profit], SUM(delivery_metrics[revenue]))
```

## Visual Theme

- Canvas: 16:10, dark navy `#09111F`
- Visual surface: `#13233A`
- Primary accent: teal `#43D9AD`
- Secondary accent: blue `#5BA8FF`
- Warning: amber `#F7B955`
- Exception: red `#E96B78`
- Font: Segoe UI
- Currency display: INR with two decimals for CPD, compact units for totals

## Page 1: Executive Summary

Top KPI row:

- Delivered Orders
- Active Riders
- Average CPD
- Average Productivity
- Average Distance

Main visuals:

- Monthly CPD line chart with month drill-down
- Monthly delivered-orders area chart
- Orders by city horizontal bar chart
- Profit margin by city matrix with conditional formatting

Slicers: date, city, employment type. Tooltip includes revenue, cost, margin,
distance, and utilization. Mockup: `mockups/01_executive_summary.svg`.

## Page 2: Rider Analytics

- Top 10 rider bar chart by productivity
- Bottom 10 rider table with active-day minimum
- Productivity distribution histogram
- Rider weekday heatmap: rider or city on rows, weekday on columns
- Scatter plot: utilization versus productivity, sized by delivered orders

Slicers: city, vehicle type, employment type, active-day threshold.
Drill-through target: rider detail with daily trend, distance, rating, and CPD.
Mockup: `mockups/02_rider_analytics.svg`.

## Page 3: 1P vs 3P Performance

- KPI cards for orders, CPD, productivity, utilization, and payout variance
- Clustered columns comparing delivered orders and average CPD
- Small multiples for monthly CPD by employment type
- Distribution plot for delivery distance
- Decomposition tree: CPD by employment type, city, vehicle, and rider

Use consistent teal for 1P and amber for 3P. Mockup:
`mockups/03_1p_vs_3p.svg`.

## Page 4: Cost Control

- KPI cards for payout variance, anomaly count, anomaly rate, and profit margin
- Monthly payout-variance line chart
- Anomalies by city bar chart
- Outlier delivery table with order, rider, expected payout, actual payout,
  variance, and cost
- Scatter plot: distance versus cost, colored by anomaly flag

Add conditional formatting when absolute payout variance exceeds 10 percent of
expected payout. Configure an order-level drill-through page for audit evidence.
Mockup: `mockups/04_cost_control.svg`.

## Interaction Design

- City and date slicers synchronize across all pages.
- Selecting a city cross-filters every visual.
- Top/bottom rider visuals do not filter one another.
- Anomaly cards navigate to the Cost Control page.
- Reset Filters bookmark restores the default two-year view.
- Dynamic titles display selected city and date range.

## Refresh

For Desktop, connect to `delivery_operations.db` through an SQLite ODBC driver.
For Power BI Service, publish through an on-premises data gateway or migrate the
SQLite model to a supported cloud warehouse for scheduled refresh.
