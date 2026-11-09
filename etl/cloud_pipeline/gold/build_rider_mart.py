
"""
Gold Layer - Rider Performance & Payout Analytics Mart

Combines Silver orders, riders and payout rate card
to generate rider-level operational and payout metrics.
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]

SILVER_DIR = PROJECT_ROOT / "data" / "silver"
GOLD_DIR = PROJECT_ROOT / "data" / "gold"


def load_silver_data():
    """Load validated Silver datasets."""

    orders_path = SILVER_DIR / "orders" / "orders.parquet"
    riders_path = SILVER_DIR / "riders" / "riders.parquet"
    ratecard_path = (
        SILVER_DIR / "payout_ratecard" / "payout_ratecard.parquet"
    )

    for file_path in [orders_path, riders_path, ratecard_path]:
        if not file_path.exists():
            raise FileNotFoundError(file_path)

    orders = pd.read_parquet(orders_path)
    riders = pd.read_parquet(riders_path)
    ratecard = pd.read_parquet(ratecard_path)

    return orders, riders, ratecard


def build_rider_performance_mart():
    """Build rider-level performance and payout metrics."""

    orders, riders, ratecard = load_silver_data()

    # Validate required columns.
    required_order_columns = {
        "order_id",
        "rider_id",
        "delivery_status",
        "delivery_distance_km",
        "delivery_time_minutes",
        "customer_rating",
        "order_value",
    }

    required_rider_columns = {
        "rider_id",
        "rider_name",
        "city",
        "vehicle_type",
        "employment_type",
    }

    required_ratecard_columns = {
        "vehicle_type",
        "base_payout",
        "payout_per_km",
        "payout_per_order",
    }

    if not required_order_columns.issubset(orders.columns):
        raise ValueError("Missing required columns in orders dataset.")

    if not required_rider_columns.issubset(riders.columns):
        raise ValueError("Missing required columns in riders dataset.")

    if not required_ratecard_columns.issubset(ratecard.columns):
        raise ValueError("Missing required columns in rate card.")

    # Check join-key integrity.
    if riders["rider_id"].duplicated().any():
        raise ValueError("Duplicate rider_id found in riders dataset.")

    if ratecard["vehicle_type"].duplicated().any():
        raise ValueError("Duplicate vehicle_type found in rate card.")

    # Join orders with rider details.
    rider_orders = orders.merge(
        riders,
        on="rider_id",
        how="left",
        validate="many_to_one",
        indicator=True,
    )

    unmatched_orders = (
        rider_orders["_merge"] != "both"
    ).sum()

    if unmatched_orders:
        raise ValueError(
            f"{unmatched_orders} orders have no matching rider."
        )

    rider_orders = rider_orders.drop(columns=["_merge"])

    # Join payout rules using vehicle type.
    rider_orders = rider_orders.merge(
        ratecard,
        on="vehicle_type",
        how="left",
        validate="many_to_one",
        indicator=True,
    )

    unmatched_ratecards = (
        rider_orders["_merge"] != "both"
    ).sum()

    if unmatched_ratecards:
        raise ValueError(
            f"{unmatched_ratecards} records have no matching rate card."
        )

    rider_orders = rider_orders.drop(columns=["_merge"])

    # Only delivered orders contribute to completed delivery metrics.
    delivered = rider_orders[
        rider_orders["delivery_status"] == "Delivered"
    ].copy()

    # Payout calculation based on the actual rate card.
    delivered["estimated_payout"] = (
        delivered["base_payout"]
        + (
            delivered["delivery_distance_km"]
            * delivered["payout_per_km"]
        )
        + delivered["payout_per_order"]
    )

    # Aggregate all-order counts.
    total_orders = (
        rider_orders.groupby("rider_id")
        .size()
        .rename("total_orders")
    )

    status_counts = pd.crosstab(
        rider_orders["rider_id"],
        rider_orders["delivery_status"],
    )

    expected_statuses = [
        "Delivered",
        "Cancelled",
        "Failed",
    ]

    for status in expected_statuses:
        if status not in status_counts.columns:
            status_counts[status] = 0

    # Aggregate delivered-order metrics.
    delivery_metrics = (
        delivered.groupby("rider_id")
        .agg(
            total_distance_km=(
                "delivery_distance_km", "sum"
            ),
            avg_delivery_time_minutes=(
                "delivery_time_minutes", "mean"
            ),
            avg_customer_rating=(
                "customer_rating", "mean"
            ),
            estimated_total_payout=(
                "estimated_payout", "sum"
            ),
        )
    )

    # Combine the metrics.
    mart = pd.concat(
        [
            total_orders,
            status_counts[expected_statuses],
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

    # Add rider details.
    rider_details = riders.set_index("rider_id")[
        [
            "rider_name",
            "city",
            "vehicle_type",
            "employment_type",
        ]
    ]

    mart = rider_details.join(mart, how="left")

    count_columns = [
        "total_orders",
        "delivered_orders",
        "cancelled_orders",
        "failed_orders",
    ]

    mart[count_columns] = (
        mart[count_columns].fillna(0).astype("int64")
    )

    # Riders without delivered orders get zero distance and payout.
    zero_fill_columns = [
        "total_distance_km",
        "estimated_total_payout",
    ]

    mart[zero_fill_columns] = (
        mart[zero_fill_columns].fillna(0)
    )

    # Calculate delivery success rate.
    mart["delivery_success_rate_pct"] = (
        mart["delivered_orders"]
        / mart["total_orders"].replace(0, pd.NA)
        * 100
    )

    mart = mart.reset_index()

    # Round analytical metrics.
    metric_columns = [
        "total_distance_km",
        "avg_delivery_time_minutes",
        "avg_customer_rating",
        "estimated_total_payout",
        "delivery_success_rate_pct",
    ]

    mart[metric_columns] = mart[metric_columns].round(2)

    # Sort by completed deliveries.
    mart = mart.sort_values(
        ["delivered_orders", "total_orders"],
        ascending=[False, False],
    ).reset_index(drop=True)

    return mart


def run_gold_pipeline():
    """Build and save the rider performance mart."""

    GOLD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    mart = build_rider_performance_mart()

    output_file = (
        GOLD_DIR / "rider_performance_and_payout.parquet"
    )

    mart.to_parquet(
        output_file,
        engine="pyarrow",
        index=False,
    )

    print("\nRIDER PERFORMANCE & PAYOUT MART")
    print("=" * 90)

    print(mart.head(10).to_string(index=False))

    print("\nTotal riders:", len(mart))
    print("Total orders:", mart["total_orders"].sum())
    print("Delivered:", mart["delivered_orders"].sum())
    print("Cancelled:", mart["cancelled_orders"].sum())
    print("Failed:", mart["failed_orders"].sum())

    print(
        "\nTotal estimated payout:",
        round(mart["estimated_total_payout"].sum(), 2),
    )

    print("\nSaved:", output_file)


if __name__ == "__main__":
    run_gold_pipeline()
