
"""
Gold Layer - Business Analytics Data Marts

Mart 1: Delivery Performance by City
"""

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]

SILVER_DIR = PROJECT_ROOT / "data" / "silver"
GOLD_DIR = PROJECT_ROOT / "data" / "gold"


def load_silver_orders() -> pd.DataFrame:
    """Load validated Silver orders."""

    file_path = SILVER_DIR / "orders" / "orders.parquet"

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    return pd.read_parquet(file_path)


def build_delivery_performance_mart() -> pd.DataFrame:
    """Build city-level delivery performance metrics."""

    orders = load_silver_orders()

    required_columns = [
        "order_id",
        "order_date",
        "city",
        "delivery_distance_km",
        "delivery_time_minutes",
        "customer_rating",
        "order_value",
        "delivery_status",
    ]

    missing = set(required_columns) - set(orders.columns)

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    allowed_statuses = {
        "Delivered",
        "Cancelled",
        "Failed",
    }

    unexpected_statuses = (
        set(orders["delivery_status"].dropna().unique())
        - allowed_statuses
    )

    if unexpected_statuses:
        raise ValueError(
            f"Unexpected delivery statuses: {unexpected_statuses}"
        )

    delivered = orders[
        orders["delivery_status"] == "Delivered"
    ].copy()

    # All-order counts by city.
    total_orders = (
        orders.groupby("city")
        .size()
        .rename("total_orders")
    )

    status_counts = pd.crosstab(
        orders["city"],
        orders["delivery_status"],
    )

    # Ensure all expected status columns exist.
    for status in allowed_statuses:
        if status not in status_counts.columns:
            status_counts[status] = 0

    # Metrics calculated only on delivered orders.
    delivery_metrics = (
        delivered.groupby("city")
        .agg(
            avg_delivery_time_minutes=(
                "delivery_time_minutes", "mean"
            ),
            avg_delivery_distance_km=(
                "delivery_distance_km", "mean"
            ),
            avg_customer_rating=(
                "customer_rating", "mean"
            ),
            delivered_order_value=(
                "order_value", "sum"
            ),
        )
    )

    mart = pd.concat(
        [
            total_orders,
            status_counts[
                ["Delivered", "Cancelled", "Failed"]
            ],
            delivery_metrics,
        ],
        axis=1,
    )

    mart = mart.rename(
        columns={
            "Delivered": "delivered_orders",
            "Cancelled": "cancelled_orders",
            "Failed": "failed_orders",
        }
    )

    mart = mart.fillna(
        {
            "delivered_orders": 0,
            "cancelled_orders": 0,
            "failed_orders": 0,
        }
    )

    mart["delivery_success_rate_pct"] = (
        mart["delivered_orders"]
        / mart["total_orders"]
        * 100
    )

    mart = mart.reset_index()

    # Round analytical metrics.
    metric_columns = [
        "avg_delivery_time_minutes",
        "avg_delivery_distance_km",
        "avg_customer_rating",
        "delivered_order_value",
        "delivery_success_rate_pct",
    ]

    mart[metric_columns] = mart[metric_columns].round(2)

    # Sort by total order volume.
    mart = mart.sort_values(
        "total_orders",
        ascending=False,
    ).reset_index(drop=True)

    return mart


def run_gold_pipeline() -> None:
    """Build and save the Delivery Performance Mart."""

    GOLD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    mart = build_delivery_performance_mart()

    output_file = (
        GOLD_DIR / "delivery_performance_by_city.parquet"
    )

    mart.to_parquet(
        output_file,
        engine="pyarrow",
        index=False,
    )

    print("\nDELIVERY PERFORMANCE MART")
    print("=" * 65)

    print(mart.to_string(index=False))

    print("\nTotal orders:", mart["total_orders"].sum())
    print("Delivered:", mart["delivered_orders"].sum())
    print("Cancelled:", mart["cancelled_orders"].sum())
    print("Failed:", mart["failed_orders"].sum())

    print("\nSaved:", output_file)


if __name__ == "__main__":
    run_gold_pipeline()
