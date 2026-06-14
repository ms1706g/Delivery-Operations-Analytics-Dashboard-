PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS monthly_kpis;
DROP TABLE IF EXISTS weekly_kpis;
DROP TABLE IF EXISTS rider_daily_metrics;
DROP TABLE IF EXISTS delivery_metrics;
DROP TABLE IF EXISTS partner_orders;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS payout_ratecard;
DROP TABLE IF EXISTS riders;

CREATE TABLE riders (
    rider_id TEXT PRIMARY KEY,
    rider_name TEXT NOT NULL,
    joining_date TEXT NOT NULL CHECK (joining_date GLOB '????-??-??'),
    city TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    employment_type TEXT NOT NULL CHECK (employment_type IN ('1P', '3P')),
    shift_hours REAL NOT NULL CHECK (shift_hours > 0)
);

CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    order_date TEXT NOT NULL CHECK (order_date GLOB '????-??-??'),
    rider_id TEXT NOT NULL REFERENCES riders(rider_id),
    city TEXT NOT NULL,
    delivery_distance_km REAL NOT NULL CHECK (delivery_distance_km >= 0),
    delivery_time_minutes REAL NOT NULL CHECK (delivery_time_minutes >= 0),
    customer_rating REAL,
    order_value REAL NOT NULL CHECK (order_value >= 0),
    delivery_status TEXT NOT NULL CHECK (delivery_status IN ('Delivered', 'Cancelled', 'Failed'))
);

CREATE TABLE payout_ratecard (
    vehicle_type TEXT PRIMARY KEY,
    base_payout REAL NOT NULL,
    payout_per_km REAL NOT NULL,
    payout_per_order REAL NOT NULL
);

CREATE TABLE partner_orders (
    order_id TEXT PRIMARY KEY REFERENCES orders(order_id),
    partner_name TEXT NOT NULL,
    distance REAL NOT NULL,
    partner_fee REAL NOT NULL,
    delivery_time REAL NOT NULL
);

CREATE TABLE delivery_metrics (
    order_id TEXT PRIMARY KEY REFERENCES orders(order_id),
    order_date TEXT NOT NULL,
    rider_id TEXT NOT NULL,
    city TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    employment_type TEXT NOT NULL,
    delivery_distance_km REAL NOT NULL,
    delivery_time_minutes REAL NOT NULL,
    order_value REAL NOT NULL,
    expected_payout REAL NOT NULL,
    actual_payout REAL NOT NULL,
    payout_variance REAL NOT NULL,
    delivery_cost REAL NOT NULL,
    revenue REAL NOT NULL,
    profit REAL NOT NULL,
    profit_margin_pct REAL NOT NULL,
    is_cost_anomaly INTEGER NOT NULL DEFAULT 0 CHECK (is_cost_anomaly IN (0, 1))
);

CREATE TABLE rider_daily_metrics (
    metric_date TEXT NOT NULL,
    rider_id TEXT NOT NULL,
    city TEXT NOT NULL,
    employment_type TEXT NOT NULL,
    orders_delivered INTEGER NOT NULL,
    distance_km REAL NOT NULL,
    active_delivery_hours REAL NOT NULL,
    shift_hours REAL NOT NULL,
    productivity REAL NOT NULL,
    utilization_rate REAL NOT NULL,
    delivery_cost REAL NOT NULL,
    revenue REAL NOT NULL,
    profit REAL NOT NULL,
    PRIMARY KEY (metric_date, rider_id)
);

CREATE TABLE weekly_kpis (
    week_start TEXT NOT NULL,
    city TEXT NOT NULL,
    orders_delivered INTEGER NOT NULL,
    total_distance_km REAL NOT NULL,
    total_delivery_cost REAL NOT NULL,
    total_revenue REAL NOT NULL,
    cpd REAL NOT NULL,
    avg_productivity REAL NOT NULL,
    avg_utilization_rate REAL NOT NULL,
    PRIMARY KEY (week_start, city)
);

CREATE TABLE monthly_kpis (
    month_start TEXT NOT NULL,
    city TEXT NOT NULL,
    orders_delivered INTEGER NOT NULL,
    total_distance_km REAL NOT NULL,
    total_delivery_cost REAL NOT NULL,
    total_revenue REAL NOT NULL,
    total_profit REAL NOT NULL,
    cpd REAL NOT NULL,
    avg_productivity REAL NOT NULL,
    avg_utilization_rate REAL NOT NULL,
    PRIMARY KEY (month_start, city)
);

CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_orders_rider ON orders(rider_id);
CREATE INDEX idx_orders_city_status ON orders(city, delivery_status);
CREATE INDEX idx_delivery_metrics_date_city ON delivery_metrics(order_date, city);
CREATE INDEX idx_delivery_metrics_anomaly ON delivery_metrics(is_cost_anomaly);
