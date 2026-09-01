from datetime import datetime, timezone

from .anomalies import detect_revenue_anomaly
from .config import cubi_config
from .features import build_sales_features
from .inventory import inventory_recommendations


async def build_business_insights(db, business_id: str) -> dict:
    """Generate the first native Cubi insight payload for one tenant."""
    sales = await db.sales.find({"business_id": business_id}, {"_id": 0}).sort("created_at", 1).to_list(5000)
    products = await db.products.find({"business_id": business_id}, {"_id": 0}).to_list(5000)
    features = build_sales_features(sales, days=30)
    inventory = inventory_recommendations(
        products,
        features["product_units"],
        horizon_days=cubi_config.low_stock_horizon_days,
    )
    anomaly = detect_revenue_anomaly(
        features["daily_revenue"],
        z_threshold=cubi_config.anomaly_z_threshold,
    )

    top_products = sorted(
        (
            {"product_id": pid, "units": round(units, 2)}
            for pid, units in features["product_units"].items()
        ),
        key=lambda x: x["units"],
        reverse=True,
    )[:10]

    return {
        "engine": "cubi-native-ml-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "business_id": business_id,
        "history": {"sales_count": features["sales_count"], "days": features["days"]},
        "top_products": top_products,
        "inventory_recommendations": inventory[:20],
        "anomaly": anomaly,
    }
