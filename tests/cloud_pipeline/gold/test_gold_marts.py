import pandas as pd
import pytest

from etl.cloud_pipeline.gold import build_marts, build_rider_mart


def test_city_mart_calculates_delivery_metrics(monkeypatch):
    orders = pd.DataFrame([
        {
            "order_id": "O1", "order_date": "2025-01-01",
            "city": "City A", "delivery_distance_km": 2.0,
            "delivery_time_minutes": 20.0, "customer_rating": 4.0,
            "order_value": 100.0, "delivery_status": "Delivered"
        },
        {
            "order_id": "O2", "order_date": "2025-01-02",
            "city": "City A", "delivery_distance_km": 4.0,
            "delivery_time_minutes": 40.0, "customer_rating": 5.0,
            "order_value": 200.0, "delivery_status": "Delivered"
        },
        {
            "order_id": "O3", "order_date": "2025-01-03",
            "city": "City A", "delivery_distance_km": 3.0,
            "delivery_time_minutes": 30.0, "customer_rating": 4.0,
            "order_value": 150.0, "delivery_status": "Cancelled"
        },
        {
            "order_id": "O4", "order_date": "2025-01-04",
            "city": "City B", "delivery_distance_km": 5.0,
            "delivery_time_minutes": 50.0, "customer_rating": 3.0,
            "order_value": 250.0, "delivery_status": "Failed"
        }
    ])

    monkeypatch.setattr(
        build_marts, "load_silver_orders", lambda: orders.copy()
    )

    mart = build_marts.build_delivery_performance_mart()

    city_a = mart.loc[mart["city"] == "City A"].iloc[0]
    city_b = mart.loc[mart["city"] == "City B"].iloc[0]

    assert city_a["total_orders"] == 3
    assert city_a["delivered_orders"] == 2
    assert city_a["cancelled_orders"] == 1
    assert city_a["failed_orders"] == 0
    assert city_a["avg_delivery_time_minutes"] == 30.0
    assert city_a["avg_delivery_distance_km"] == 3.0
    assert city_a["avg_customer_rating"] == 4.5
    assert city_a["delivered_order_value"] == 300.0
    assert city_a["delivery_success_rate_pct"] == 66.67

    assert city_b["total_orders"] == 1
    assert city_b["delivered_orders"] == 0
    assert city_b["delivery_success_rate_pct"] == 0.0


def test_city_mart_rejects_missing_columns(monkeypatch):
    orders = pd.DataFrame({"order_id": ["O1"]})

    monkeypatch.setattr(
        build_marts, "load_silver_orders", lambda: orders
    )

    with pytest.raises(ValueError, match="Missing columns"):
        build_marts.build_delivery_performance_mart()


def test_city_mart_rejects_unexpected_status(monkeypatch):
    orders = pd.DataFrame([{
        "order_id": "O1",
        "order_date": "2025-01-01",
        "city": "City A",
        "delivery_distance_km": 2.0,
        "delivery_time_minutes": 20.0,
        "customer_rating": 4.0,
        "order_value": 100.0,
        "delivery_status": "Pending"
    }])

    monkeypatch.setattr(
        build_marts, "load_silver_orders", lambda: orders
    )

    with pytest.raises(ValueError, match="Unexpected delivery statuses"):
        build_marts.build_delivery_performance_mart()


def test_rider_mart_calculates_metrics_and_payout(monkeypatch):
    orders = pd.DataFrame([
        {
            "order_id": "O1", "rider_id": "R1",
            "delivery_status": "Delivered",
            "delivery_distance_km": 2.0,
            "delivery_time_minutes": 20.0,
            "customer_rating": 4.0, "order_value": 100.0
        },
        {
            "order_id": "O2", "rider_id": "R1",
            "delivery_status": "Delivered",
            "delivery_distance_km": 4.0,
            "delivery_time_minutes": 40.0,
            "customer_rating": 5.0, "order_value": 200.0
        },
        {
            "order_id": "O3", "rider_id": "R1",
            "delivery_status": "Cancelled",
            "delivery_distance_km": 3.0,
            "delivery_time_minutes": 30.0,
            "customer_rating": None, "order_value": 150.0
        },
        {
            "order_id": "O4", "rider_id": "R2",
            "delivery_status": "Failed",
            "delivery_distance_km": 5.0,
            "delivery_time_minutes": 50.0,
            "customer_rating": None, "order_value": 250.0
        }
    ])

    riders = pd.DataFrame([
        {
            "rider_id": "R1", "rider_name": "Rider One",
            "city": "City A", "vehicle_type": "Bike",
            "employment_type": "Full-time"
        },
        {
            "rider_id": "R2", "rider_name": "Rider Two",
            "city": "City B", "vehicle_type": "Scooter",
            "employment_type": "Part-time"
        }
    ])

    ratecard = pd.DataFrame([
        {
            "vehicle_type": "Bike", "base_payout": 10.0,
            "payout_per_km": 2.0, "payout_per_order": 3.0
        },
        {
            "vehicle_type": "Scooter", "base_payout": 8.0,
            "payout_per_km": 1.5, "payout_per_order": 2.0
        }
    ])

    monkeypatch.setattr(
        build_rider_mart,
        "load_silver_data",
        lambda: (orders.copy(), riders.copy(), ratecard.copy())
    )

    mart = build_rider_mart.build_rider_performance_mart()

    rider_one = mart.loc[mart["rider_id"] == "R1"].iloc[0]
    rider_two = mart.loc[mart["rider_id"] == "R2"].iloc[0]

    assert rider_one["total_orders"] == 3
    assert rider_one["delivered_orders"] == 2
    assert rider_one["cancelled_orders"] == 1
    assert rider_one["failed_orders"] == 0
    assert rider_one["total_distance_km"] == 6.0
    assert rider_one["avg_delivery_time_minutes"] == 30.0
    assert rider_one["avg_customer_rating"] == 4.5
    assert rider_one["estimated_total_payout"] == 38.0
    assert rider_one["delivery_success_rate_pct"] == 66.67

    assert rider_two["total_orders"] == 1
    assert rider_two["delivered_orders"] == 0
    assert rider_two["total_distance_km"] == 0
    assert rider_two["estimated_total_payout"] == 0
    assert rider_two["delivery_success_rate_pct"] == 0


def test_rider_mart_rejects_duplicate_rider_ids(monkeypatch):
    orders = pd.DataFrame(columns=[
        "order_id", "rider_id", "delivery_status",
        "delivery_distance_km", "delivery_time_minutes",
        "customer_rating", "order_value"
    ])

    riders = pd.DataFrame([
        {
            "rider_id": "R1", "rider_name": "One",
            "city": "City A", "vehicle_type": "Bike",
            "employment_type": "Full-time"
        },
        {
            "rider_id": "R1", "rider_name": "Duplicate",
            "city": "City A", "vehicle_type": "Bike",
            "employment_type": "Full-time"
        }
    ])

    ratecard = pd.DataFrame([{
        "vehicle_type": "Bike", "base_payout": 10.0,
        "payout_per_km": 2.0, "payout_per_order": 3.0
    }])

    monkeypatch.setattr(
        build_rider_mart,
        "load_silver_data",
        lambda: (orders, riders, ratecard)
    )

    with pytest.raises(ValueError, match="Duplicate rider_id"):
        build_rider_mart.build_rider_performance_mart()


def test_rider_mart_rejects_unmatched_rider(monkeypatch):
    orders = pd.DataFrame([{
        "order_id": "O1", "rider_id": "UNKNOWN",
        "delivery_status": "Delivered",
        "delivery_distance_km": 2.0,
        "delivery_time_minutes": 20.0,
        "customer_rating": 4.0, "order_value": 100.0
    }])

    riders = pd.DataFrame([{
        "rider_id": "R1", "rider_name": "Rider One",
        "city": "City A", "vehicle_type": "Bike",
        "employment_type": "Full-time"
    }])

    ratecard = pd.DataFrame([{
        "vehicle_type": "Bike", "base_payout": 10.0,
        "payout_per_km": 2.0, "payout_per_order": 3.0
    }])

    monkeypatch.setattr(
        build_rider_mart,
        "load_silver_data",
        lambda: (orders, riders, ratecard)
    )

    with pytest.raises(ValueError, match="no matching rider"):
        build_rider_mart.build_rider_performance_mart()
