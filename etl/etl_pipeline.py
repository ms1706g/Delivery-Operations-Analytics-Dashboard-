"""Clean, transform, and load delivery operations data into SQLite."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = ROOT / "delivery_operations.db"
SCHEMA_PATH = ROOT / "sql" / "schema.sql"


def parse_date(value: str) -> str | None:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date().isoformat()
    except (AttributeError, TypeError, ValueError):
        return None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def clean_riders(rows: list[dict[str, str]]) -> tuple[list[dict], dict[str, int]]:
    clean, seen = [], set()
    stats = defaultdict(int)
    for row in rows:
        rider_id = row.get("rider_id", "").strip()
        joining_date = parse_date(row.get("joining_date", ""))
        if not rider_id or rider_id in seen:
            stats["duplicate_or_missing_id"] += 1
            continue
        if not joining_date:
            stats["invalid_date"] += 1
            continue
        try:
            shift_hours = float(row["shift_hours"])
        except (KeyError, TypeError, ValueError):
            stats["invalid_numeric"] += 1
            continue
        if shift_hours <= 0 or row.get("employment_type") not in {"1P", "3P"}:
            stats["invalid_business_value"] += 1
            continue
        seen.add(rider_id)
        clean.append(
            {
                "rider_id": rider_id,
                "rider_name": row.get("rider_name", "").strip() or "Unknown Rider",
                "joining_date": joining_date,
                "city": row.get("city", "").strip() or "Unknown",
                "vehicle_type": row.get("vehicle_type", "").strip(),
                "employment_type": row["employment_type"],
                "shift_hours": shift_hours,
            }
        )
    return clean, dict(stats)


def clean_orders(rows: list[dict[str, str]], valid_riders: set[str]) -> tuple[list[dict], dict[str, int]]:
    clean, seen = [], set()
    stats = defaultdict(int)
    for row in rows:
        order_id = row.get("order_id", "").strip()
        order_date = parse_date(row.get("order_date", ""))
        rider_id = row.get("rider_id", "").strip()
        if not order_id or order_id in seen:
            stats["duplicate_or_missing_id"] += 1
            continue
        if not order_date:
            stats["invalid_date"] += 1
            continue
        if rider_id not in valid_riders:
            stats["invalid_rider"] += 1
            continue
        try:
            distance = float(row["delivery_distance_km"])
            minutes = float(row["delivery_time_minutes"])
            order_value = float(row["order_value"])
            rating = float(row["customer_rating"]) if row.get("customer_rating", "").strip() else None
        except (KeyError, TypeError, ValueError):
            stats["invalid_numeric"] += 1
            continue
        status = row.get("delivery_status", "").strip()
        if distance < 0 or minutes < 0 or order_value < 0 or status not in {"Delivered", "Cancelled", "Failed"}:
            stats["invalid_business_value"] += 1
            continue
        seen.add(order_id)
        clean.append(
            {
                "order_id": order_id,
                "order_date": order_date,
                "rider_id": rider_id,
                "city": row.get("city", "").strip(),
                "delivery_distance_km": distance,
                "delivery_time_minutes": minutes,
                "customer_rating": rating,
                "order_value": order_value,
                "delivery_status": status,
            }
        )
    return clean, dict(stats)


def clean_ratecard(rows: list[dict[str, str]]) -> list[dict]:
    result = []
    for row in rows:
        result.append(
            {
                "vehicle_type": row["vehicle_type"].strip(),
                "base_payout": float(row["base_payout"]),
                "payout_per_km": float(row["payout_per_km"]),
                "payout_per_order": float(row["payout_per_order"]),
            }
        )
    return result


def clean_partner_feed(path: Path, valid_order_ids: set[str]) -> tuple[list[dict], dict[str, int]]:
    with path.open(encoding="utf-8") as handle:
        feed = json.load(handle)
    clean, seen = [], set()
    stats = defaultdict(int)
    partner_name = str(feed.get("partner_name", "Unknown Partner")).strip()
    for row in feed.get("partner_orders", []):
        order_id = str(row.get("order_id", "")).strip()
        if not order_id or order_id in seen:
            stats["duplicate_or_missing_id"] += 1
            continue
        if order_id not in valid_order_ids:
            stats["unmatched_order"] += 1
            continue
        try:
            distance = float(row["distance"])
            fee = float(row["partner_fee"])
            minutes = float(row["delivery_time"])
        except (KeyError, TypeError, ValueError):
            stats["invalid_numeric"] += 1
            continue
        if min(distance, fee, minutes) < 0:
            stats["invalid_business_value"] += 1
            continue
        seen.add(order_id)
        clean.append(
            {
                "order_id": order_id,
                "partner_name": partner_name,
                "distance": distance,
                "partner_fee": fee,
                "delivery_time": minutes,
            }
        )
    return clean, dict(stats)


def deterministic_factor(order_id: str) -> float:
    value = int(hashlib.sha256(order_id.encode()).hexdigest()[:8], 16)
    centered = ((value % 1001) / 1000) - 0.5
    factor = 1 + centered * 0.08
    if value % 137 == 0:
        factor += 0.35
    return factor


def build_metrics(orders: list[dict], riders: list[dict], ratecard: list[dict], partner: list[dict]):
    rider_map = {r["rider_id"]: r for r in riders}
    rate_map = {r["vehicle_type"]: r for r in ratecard}
    partner_map = {p["order_id"]: p for p in partner}
    metrics = []
    for order in orders:
        if order["delivery_status"] != "Delivered":
            continue
        rider = rider_map[order["rider_id"]]
        rate = rate_map[rider["vehicle_type"]]
        expected = (
            rate["base_payout"]
            + rate["payout_per_km"] * order["delivery_distance_km"]
            + rate["payout_per_order"]
        )
        if rider["employment_type"] == "3P" and order["order_id"] in partner_map:
            actual = partner_map[order["order_id"]]["partner_fee"]
        else:
            actual = expected * deterministic_factor(order["order_id"])
        overhead = 5.5 if rider["employment_type"] == "1P" else 2.5
        delivery_cost = actual + overhead
        # Allocated delivery revenue combines platform commission and service fees.
        revenue = max(30.0, order["order_value"] * 0.16 + 14.0)
        profit = revenue - delivery_cost
        margin = profit / revenue * 100 if revenue else 0
        metrics.append(
            {
                "order_id": order["order_id"],
                "order_date": order["order_date"],
                "rider_id": order["rider_id"],
                "city": order["city"],
                "vehicle_type": rider["vehicle_type"],
                "employment_type": rider["employment_type"],
                "delivery_distance_km": order["delivery_distance_km"],
                "delivery_time_minutes": order["delivery_time_minutes"],
                "order_value": order["order_value"],
                "expected_payout": round(expected, 2),
                "actual_payout": round(actual, 2),
                "payout_variance": round(actual - expected, 2),
                "delivery_cost": round(delivery_cost, 2),
                "revenue": round(revenue, 2),
                "profit": round(profit, 2),
                "profit_margin_pct": round(margin, 2),
                "is_cost_anomaly": 0,
            }
        )
    costs = [m["delivery_cost"] for m in metrics]
    threshold = statistics.mean(costs) + 2 * statistics.pstdev(costs)
    for metric in metrics:
        metric["is_cost_anomaly"] = int(metric["delivery_cost"] > threshold)
    return metrics, threshold


def build_rider_daily(metrics: list[dict], riders: list[dict]) -> list[dict]:
    rider_map = {r["rider_id"]: r for r in riders}
    grouped = defaultdict(list)
    for metric in metrics:
        grouped[(metric["order_date"], metric["rider_id"])].append(metric)
    output = []
    for (metric_date, rider_id), rows in sorted(grouped.items()):
        rider = rider_map[rider_id]
        active_hours = sum(r["delivery_time_minutes"] for r in rows) / 60
        shift_hours = rider["shift_hours"]
        output.append(
            {
                "metric_date": metric_date,
                "rider_id": rider_id,
                "city": rider["city"],
                "employment_type": rider["employment_type"],
                "orders_delivered": len(rows),
                "distance_km": round(sum(r["delivery_distance_km"] for r in rows), 2),
                "active_delivery_hours": round(active_hours, 2),
                "shift_hours": shift_hours,
                "productivity": round(len(rows) / shift_hours, 4),
                "utilization_rate": round(min(active_hours / shift_hours, 1.0), 4),
                "delivery_cost": round(sum(r["delivery_cost"] for r in rows), 2),
                "revenue": round(sum(r["revenue"] for r in rows), 2),
                "profit": round(sum(r["profit"] for r in rows), 2),
            }
        )
    return output


def period_start(date_text: str, period: str) -> str:
    day = datetime.strptime(date_text, "%Y-%m-%d").date()
    if period == "week":
        return (day - timedelta(days=day.weekday())).isoformat()
    return day.replace(day=1).isoformat()


def build_period_kpis(metrics: list[dict], daily: list[dict], period: str) -> list[dict]:
    metric_groups = defaultdict(list)
    daily_groups = defaultdict(list)
    for row in metrics:
        metric_groups[(period_start(row["order_date"], period), row["city"])].append(row)
    for row in daily:
        daily_groups[(period_start(row["metric_date"], period), row["city"])].append(row)
    output = []
    for key, rows in sorted(metric_groups.items()):
        daily_rows = daily_groups[key]
        cost = sum(r["delivery_cost"] for r in rows)
        record = {
            f"{period}_start": key[0],
            "city": key[1],
            "orders_delivered": len(rows),
            "total_distance_km": round(sum(r["delivery_distance_km"] for r in rows), 2),
            "total_delivery_cost": round(cost, 2),
            "total_revenue": round(sum(r["revenue"] for r in rows), 2),
            "cpd": round(cost / len(rows), 2),
            "avg_productivity": round(statistics.mean(r["productivity"] for r in daily_rows), 4),
            "avg_utilization_rate": round(statistics.mean(r["utilization_rate"] for r in daily_rows), 4),
        }
        if period == "month":
            record["total_profit"] = round(sum(r["profit"] for r in rows), 2)
        output.append(record)
    return output


def insert_dicts(connection: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    columns = list(rows[0])
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})"
    connection.executemany(sql, ([row[col] for col in columns] for row in rows))


def main() -> None:
    riders, rider_stats = clean_riders(read_csv(DATA_DIR / "riders.csv"))
    orders, order_stats = clean_orders(
        read_csv(DATA_DIR / "orders.csv"), {r["rider_id"] for r in riders}
    )
    ratecard = clean_ratecard(read_csv(DATA_DIR / "payout_ratecard.csv"))
    partner, partner_stats = clean_partner_feed(
        DATA_DIR / "third_party_feed.json", {o["order_id"] for o in orders}
    )
    metrics, anomaly_threshold = build_metrics(orders, riders, ratecard, partner)
    daily = build_rider_daily(metrics, riders)
    weekly = build_period_kpis(metrics, daily, "week")
    monthly = build_period_kpis(metrics, daily, "month")

    with sqlite3.connect(DB_PATH) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        insert_dicts(connection, "riders", riders)
        insert_dicts(connection, "orders", orders)
        insert_dicts(connection, "payout_ratecard", ratecard)
        insert_dicts(connection, "partner_orders", partner)
        insert_dicts(connection, "delivery_metrics", metrics)
        insert_dicts(connection, "rider_daily_metrics", daily)
        insert_dicts(connection, "weekly_kpis", weekly)
        insert_dicts(connection, "monthly_kpis", monthly)
        connection.commit()

    print(f"Database created: {DB_PATH}")
    print(f"Rows loaded: riders={len(riders):,}, orders={len(orders):,}, partner={len(partner):,}")
    print(f"Metrics: deliveries={len(metrics):,}, daily={len(daily):,}, monthly={len(monthly):,}")
    print(f"Cost anomaly threshold: INR {anomaly_threshold:,.2f}")
    print(f"Cleaning audit: riders={rider_stats}, orders={order_stats}, partner={partner_stats}")


if __name__ == "__main__":
    main()
