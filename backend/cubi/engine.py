from datetime import datetime, timezone

from .anomalies import detect_revenue_anomaly
from .config import cubi_config
from .features import build_sales_features
from .forecast import forecast_daily_sales
from .inventory import inventory_recommendations


def _classify_abc(rows: list[dict]) -> list[dict]:
    """Classify products by cumulative revenue contribution (A/B/C)."""
    rows = sorted(rows, key=lambda x: x["revenue"], reverse=True)
    total = sum(x["revenue"] for x in rows)
    cumulative = 0.0
    for row in rows:
        cumulative += row["revenue"]
        share = cumulative / total if total else 0
        row["abc_class"] = "A" if share <= 0.80 else "B" if share <= 0.95 else "C"
    return rows


async def build_business_insights(db, business_id: str) -> dict:
    """Generate explainable native Cubi intelligence for one tenant."""
    sales = await db.sales.find({"business_id": business_id}, {"_id": 0}).sort("created_at", 1).to_list(5000)
    products = await db.products.find({"business_id": business_id}, {"_id": 0}).to_list(5000)
    features = build_sales_features(sales, days=30)
    product_map = {p.get("id"): p for p in products if p.get("id")}

    product_metrics = []
    for pid, units in features["product_units"].items():
        product = product_map.get(pid, {})
        revenue = float(features["product_revenue"].get(pid, 0) or 0)
        purchase_price = float(product.get("purchase_price", 0) or 0)
        cost = purchase_price * float(units)
        profit = revenue - cost
        margin = (profit / revenue * 100) if revenue else 0
        product_metrics.append({
            "product_id": pid,
            "product_name": product.get("name", "Producto"),
            "units": round(float(units), 2),
            "revenue": round(revenue, 2),
            "cost": round(cost, 2),
            "profit": round(profit, 2),
            "margin_percent": round(margin, 1),
        })

    abc = _classify_abc(product_metrics)
    inventory = inventory_recommendations(
        products,
        features["product_units"],
        horizon_days=cubi_config.low_stock_horizon_days,
        observed_days=features["days"],
    )
    anomaly = detect_revenue_anomaly(
        features["daily_revenue"],
        z_threshold=cubi_config.anomaly_z_threshold,
    )
    forecast = forecast_daily_sales(
        features["daily_revenue"],
        horizon_days=cubi_config.forecast_horizon_days,
    )

    return {
        "engine": "cubi-native-ml-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "business_id": business_id,
        "history": {
            "sales_count": features["sales_count"],
            "days": features["days"],
            "observed_days": features["observed_days"],
        },
        "top_products": sorted(abc, key=lambda x: x["units"], reverse=True)[:10],
        "abc_analysis": abc[:30],
        "forecast": forecast,
        "inventory_recommendations": inventory[:20],
        "anomaly": anomaly,
    }
