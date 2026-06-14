"""Generate deterministic synthetic delivery operations data."""

from __future__ import annotations

import csv
import json
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 42
RIDER_COUNT = 600
ORDER_COUNT = 60_000
PARTNER_ORDER_COUNT = 12_000

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

CITIES = {
    "Bengaluru": (0.28, 1.12),
    "Delhi NCR": (0.22, 1.08),
    "Mumbai": (0.18, 1.18),
    "Hyderabad": (0.13, 0.98),
    "Pune": (0.11, 1.00),
    "Chennai": (0.08, 0.96),
}
VEHICLES = {
    "Bicycle": {"speed": 13, "distance_factor": 0.72},
    "Motorcycle": {"speed": 27, "distance_factor": 1.08},
    "Electric Scooter": {"speed": 23, "distance_factor": 0.96},
}
FIRST_NAMES = [
    "Aarav", "Aditi", "Akash", "Aman", "Ananya", "Arjun", "Deepak", "Diya",
    "Farhan", "Gaurav", "Ishita", "Kabir", "Karan", "Kavya", "Manish", "Meera",
    "Mohit", "Neha", "Nikhil", "Pooja", "Priya", "Rahul", "Riya", "Rohan",
    "Sahil", "Sana", "Simran", "Sneha", "Varun", "Vikram",
]
LAST_NAMES = [
    "Agarwal", "Bansal", "Das", "Gupta", "Iyer", "Jain", "Kapoor", "Khan",
    "Kumar", "Mehta", "Mishra", "Nair", "Patel", "Rao", "Reddy", "Shah",
    "Sharma", "Singh", "Verma", "Yadav",
]
RATECARD = [
    {"vehicle_type": "Bicycle", "base_payout": 18.0, "payout_per_km": 4.5, "payout_per_order": 6.0},
    {"vehicle_type": "Motorcycle", "base_payout": 22.0, "payout_per_km": 6.5, "payout_per_order": 8.0},
    {"vehicle_type": "Electric Scooter", "base_payout": 20.0, "payout_per_km": 5.5, "payout_per_order": 7.0},
]


def weighted_choice(rng: random.Random, weighted_values: dict[str, float]) -> str:
    values = list(weighted_values)
    return rng.choices(values, weights=[weighted_values[v] for v in values], k=1)[0]


def generate_riders(rng: random.Random) -> list[dict]:
    riders = []
    start = date(2021, 1, 1)
    for i in range(1, RIDER_COUNT + 1):
        city = weighted_choice(rng, {k: v[0] for k, v in CITIES.items()})
        vehicle = rng.choices(list(VEHICLES), weights=[0.17, 0.58, 0.25], k=1)[0]
        employment = rng.choices(["1P", "3P"], weights=[0.66, 0.34], k=1)[0]
        joining = start + timedelta(days=rng.randint(0, 1276))
        riders.append(
            {
                "rider_id": f"RDR{i:04d}",
                "rider_name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                "joining_date": joining.isoformat(),
                "city": city,
                "vehicle_type": vehicle,
                "employment_type": employment,
                "shift_hours": rng.choices([6, 8, 9, 10, 12], weights=[0.08, 0.52, 0.12, 0.23, 0.05], k=1)[0],
            }
        )
    return riders


def seasonal_multiplier(day: date) -> float:
    weekend = 1.18 if day.weekday() >= 5 else 1.0
    annual = 1.0 + 0.12 * math.sin((day.timetuple().tm_yday / 365) * 2 * math.pi)
    growth = 0.90 + ((day - date(2024, 1, 1)).days / 730) * 0.22
    return weekend * annual * growth


def generate_orders(rng: random.Random, riders: list[dict]) -> list[dict]:
    start = date(2024, 1, 1)
    end = date(2025, 12, 31)
    days = (end - start).days + 1
    date_population = [start + timedelta(days=i) for i in range(days)]
    date_weights = [seasonal_multiplier(d) for d in date_population]
    riders_by_city: dict[str, list[dict]] = {}
    for rider in riders:
        riders_by_city.setdefault(rider["city"], []).append(rider)

    orders = []
    for i in range(1, ORDER_COUNT + 1):
        order_day = rng.choices(date_population, weights=date_weights, k=1)[0]
        city = weighted_choice(rng, {k: v[0] for k, v in CITIES.items()})
        rider = rng.choice(riders_by_city[city])
        vehicle = VEHICLES[rider["vehicle_type"]]
        city_factor = CITIES[city][1]
        distance = max(0.5, min(28.0, rng.lognormvariate(1.23, 0.58) * vehicle["distance_factor"]))
        traffic = rng.uniform(1.0, 1.65) * city_factor
        service_time = rng.uniform(7, 16)
        delivery_time = distance / vehicle["speed"] * 60 * traffic + service_time
        if rng.random() < 0.008:
            delivery_time *= rng.uniform(1.8, 2.8)
        status = rng.choices(
            ["Delivered", "Cancelled", "Failed"],
            weights=[0.947, 0.038, 0.015],
            k=1,
        )[0]
        rating = "" if status != "Delivered" or rng.random() < 0.035 else round(min(5, max(1, rng.gauss(4.35, 0.55))), 1)
        order_value = round(max(90, rng.lognormvariate(5.72, 0.55)), 2)
        orders.append(
            {
                "order_id": f"ORD{i:07d}",
                "order_date": order_day.isoformat(),
                "rider_id": rider["rider_id"],
                "city": city,
                "delivery_distance_km": round(distance, 2),
                "delivery_time_minutes": round(delivery_time, 1),
                "customer_rating": rating,
                "order_value": order_value,
                "delivery_status": status,
            }
        )

    # Add controlled data-quality issues so the ETL cleaning logic is exercised.
    orders.extend(dict(row) for row in rng.sample(orders, 75))
    for row in rng.sample(orders[:ORDER_COUNT], 25):
        row["customer_rating"] = ""
    for row in rng.sample(orders[:ORDER_COUNT], 10):
        row["order_date"] = "2025-13-40"
    return orders


def generate_partner_feed(rng: random.Random, orders: list[dict], riders: list[dict]) -> dict:
    employment = {r["rider_id"]: r["employment_type"] for r in riders}
    candidates = [
        o for o in orders[:ORDER_COUNT]
        if employment[o["rider_id"]] == "3P" and o["delivery_status"] == "Delivered"
    ]
    selected = rng.sample(candidates, min(PARTNER_ORDER_COUNT, len(candidates)))
    partner_orders = []
    for order in selected:
        distance = float(order["delivery_distance_km"])
        expected_proxy = 28 + 6.2 * distance
        noise = rng.gauss(1.0, 0.055)
        if rng.random() < 0.018:
            noise *= rng.uniform(1.25, 1.65)
        partner_orders.append(
            {
                "order_id": order["order_id"],
                "distance": distance,
                "partner_fee": round(expected_proxy * noise, 2),
                "delivery_time": float(order["delivery_time_minutes"]),
            }
        )
    return {
        "partner_name": "XYZ Logistics",
        "generated_at": datetime(2026, 6, 14, 12, 0, 0).isoformat(),
        "partner_orders": partner_orders,
    }


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rng = random.Random(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    riders = generate_riders(rng)
    orders = generate_orders(rng, riders)
    partner_feed = generate_partner_feed(rng, orders, riders)

    write_csv(DATA_DIR / "riders.csv", riders, list(riders[0]))
    write_csv(DATA_DIR / "orders.csv", orders, list(orders[0]))
    write_csv(DATA_DIR / "payout_ratecard.csv", RATECARD, list(RATECARD[0]))
    with (DATA_DIR / "third_party_feed.json").open("w", encoding="utf-8") as handle:
        json.dump(partner_feed, handle, indent=2)

    print(
        f"Generated {len(riders):,} riders, {len(orders):,} raw order rows, "
        f"and {len(partner_feed['partner_orders']):,} partner deliveries."
    )


if __name__ == "__main__":
    main()
