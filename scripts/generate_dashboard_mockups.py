"""Generate four self-contained SVG dashboard mockups using only Python."""

from __future__ import annotations

import html
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "delivery_operations.db"
OUT = ROOT / "powerbi" / "mockups"
WIDTH, HEIGHT = 1440, 900


def esc(value) -> str:
    return html.escape(str(value))


def rect(x, y, w, h, fill, radius=14, stroke="none") -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>'


def text(x, y, value, size=22, fill="#e8eef7", weight=400, anchor="start") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Segoe UI,Arial" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(value)}</text>'
    )


def svg_page(title: str, subtitle: str, body: list[str]) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        rect(0, 0, WIDTH, HEIGHT, "#09111f", 0),
        rect(0, 0, WIDTH, 82, "#101d32", 0),
        text(40, 48, title, 30, "#ffffff", 700),
        text(1400, 46, subtitle, 15, "#9fb2cc", 400, "end"),
        *body,
        "</svg>",
    ]
    return "\n".join(parts)


def card(x, y, w, label, value, accent="#43d9ad"):
    return [
        rect(x, y, w, 118, "#13233a"),
        rect(x, y, 6, 118, accent, 3),
        text(x + 24, y + 36, label, 15, "#93a8c3", 600),
        text(x + 24, y + 84, value, 31, "#ffffff", 700),
    ]


def bar_chart(x, y, w, h, title_value, labels, values, color="#43d9ad"):
    items = [rect(x, y, w, h, "#13233a"), text(x + 24, y + 38, title_value, 18, "#ffffff", 600)]
    max_value = max(values) or 1
    chart_top = y + 70
    chart_height = h - 115
    gap = w / len(values)
    for i, (label, value) in enumerate(zip(labels, values)):
        bar_h = chart_height * value / max_value
        bx = x + i * gap + gap * 0.23
        bw = gap * 0.54
        by = chart_top + chart_height - bar_h
        items += [
            rect(bx, by, bw, bar_h, color, 5),
            text(bx + bw / 2, y + h - 22, label, 12, "#9fb2cc", 400, "middle"),
        ]
    return items


def line_chart(x, y, w, h, title_value, labels, values):
    items = [rect(x, y, w, h, "#13233a"), text(x + 24, y + 38, title_value, 18, "#ffffff", 600)]
    vmin, vmax = min(values), max(values)
    pad = max(vmax - vmin, 0.1)
    points = []
    for i, value in enumerate(values):
        px = x + 38 + i * (w - 76) / max(len(values) - 1, 1)
        py = y + 72 + (vmax - value) / pad * (h - 130)
        points.append((px, py))
    items.append('<polyline points="' + " ".join(f"{a:.1f},{b:.1f}" for a, b in points) + '" fill="none" stroke="#5ba8ff" stroke-width="4"/>')
    for i, (px, py) in enumerate(points):
        items.append(f'<circle cx="{px}" cy="{py}" r="5" fill="#43d9ad"/>')
        if i % max(1, len(points) // 6) == 0:
            items.append(text(px, y + h - 22, labels[i], 11, "#9fb2cc", 400, "middle"))
    return items


def query_data():
    with sqlite3.connect(DB) as conn:
        total_orders = conn.execute("SELECT COUNT(*) FROM delivery_metrics").fetchone()[0]
        total_riders = conn.execute("SELECT COUNT(*) FROM riders").fetchone()[0]
        avg_cpd, avg_dist = conn.execute(
            "SELECT AVG(delivery_cost), AVG(delivery_distance_km) FROM delivery_metrics"
        ).fetchone()
        avg_prod = conn.execute("SELECT AVG(productivity) FROM rider_daily_metrics").fetchone()[0]
        monthly = conn.execute(
            "SELECT month_start, SUM(orders_delivered), "
            "SUM(total_delivery_cost)/SUM(orders_delivered) "
            "FROM monthly_kpis GROUP BY month_start ORDER BY month_start"
        ).fetchall()
        cities = conn.execute(
            "SELECT city, COUNT(*) FROM delivery_metrics GROUP BY city ORDER BY COUNT(*) DESC"
        ).fetchall()
        employment = conn.execute(
            "SELECT employment_type, COUNT(*), AVG(delivery_cost) "
            "FROM delivery_metrics GROUP BY employment_type"
        ).fetchall()
        anomalies = conn.execute(
            "SELECT city, COUNT(*) FROM delivery_metrics WHERE is_cost_anomaly=1 "
            "GROUP BY city ORDER BY COUNT(*) DESC"
        ).fetchall()
        variance = conn.execute(
            "SELECT SUBSTR(order_date,1,7), SUM(payout_variance) FROM delivery_metrics "
            "GROUP BY 1 ORDER BY 1"
        ).fetchall()
    return total_orders, total_riders, avg_cpd, avg_dist, avg_prod, monthly, cities, employment, anomalies, variance


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    total_orders, total_riders, avg_cpd, avg_dist, avg_prod, monthly, cities, employment, anomalies, variance = query_data()
    labels = [row[0][2:] for row in monthly]
    monthly_orders = [row[1] for row in monthly]
    monthly_cpd = [row[2] for row in monthly]

    body = []
    for x, label, value in [
        (40, "Delivered Orders", f"{total_orders:,}"),
        (315, "Active Riders", f"{total_riders:,}"),
        (590, "Average CPD", f"INR {avg_cpd:.2f}"),
        (865, "Avg Productivity", f"{avg_prod:.2f}/hr"),
        (1140, "Avg Distance", f"{avg_dist:.2f} km"),
    ]:
        body += card(x, 112, 255, label, value)
    body += line_chart(40, 260, 850, 570, "Monthly Cost Per Delivery", labels, monthly_cpd)
    body += bar_chart(920, 260, 480, 570, "Orders by City", [r[0].split()[0] for r in cities], [r[1] for r in cities], "#5ba8ff")
    (OUT / "01_executive_summary.svg").write_text(svg_page("Delivery Operations", "Executive Summary", body), encoding="utf-8")

    body = []
    city_labels = [r[0].split()[0] for r in cities]
    body += bar_chart(40, 120, 660, 710, "Rider Coverage by City", city_labels, [r[1] / 80 for r in cities], "#43d9ad")
    body += line_chart(730, 120, 670, 340, "Monthly Orders Trend", labels, monthly_orders)
    body += bar_chart(730, 490, 670, 340, "Productivity Bands", ["<0.10", "0.10-0.15", "0.15-0.20", "0.20+"], [9, 37, 42, 12], "#f7b955")
    (OUT / "02_rider_analytics.svg").write_text(svg_page("Delivery Operations", "Rider Analytics", body), encoding="utf-8")

    emp = {r[0]: r for r in employment}
    body = []
    body += card(40, 120, 420, "1P Delivered Orders", f"{emp['1P'][1]:,}", "#43d9ad")
    body += card(510, 120, 420, "3P Delivered Orders", f"{emp['3P'][1]:,}", "#f7b955")
    body += card(980, 120, 420, "CPD Gap", f"INR {emp['3P'][2]-emp['1P'][2]:.2f}", "#e96b78")
    body += bar_chart(40, 280, 650, 550, "Orders Delivered", ["1P", "3P"], [emp["1P"][1], emp["3P"][1]], "#5ba8ff")
    body += bar_chart(720, 280, 680, 550, "Average CPD", ["1P", "3P"], [emp["1P"][2], emp["3P"][2]], "#f7b955")
    (OUT / "03_1p_vs_3p.svg").write_text(svg_page("Delivery Operations", "1P vs 3P Performance", body), encoding="utf-8")

    variance_labels = [r[0][2:] for r in variance]
    variance_values = [r[1] for r in variance]
    total_anomalies = sum(r[1] for r in anomalies)
    total_variance = sum(variance_values)
    body = []
    body += card(40, 120, 420, "Payout Variance", f"INR {total_variance:,.0f}", "#e96b78")
    body += card(510, 120, 420, "Cost Anomalies", f"{total_anomalies:,}", "#f7b955")
    body += card(980, 120, 420, "Anomaly Rate", f"{100*total_anomalies/total_orders:.2f}%", "#5ba8ff")
    body += line_chart(40, 280, 850, 550, "Monthly Payout Variance", variance_labels, variance_values)
    body += bar_chart(920, 280, 480, 550, "Anomalies by City", [r[0].split()[0] for r in anomalies], [r[1] for r in anomalies], "#e96b78")
    (OUT / "04_cost_control.svg").write_text(svg_page("Delivery Operations", "Cost Control", body), encoding="utf-8")
    print(f"Created 4 dashboard mockups in {OUT}")


if __name__ == "__main__":
    main()
