from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends

from database import db
from security import require_business

router = APIRouter(prefix="/ai", tags=["ai"])


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _pct_change(old: float, new: float):
    if old == 0:
        return None
    return round((new - old) / old * 100, 1)


@router.get("/margin-analysis")
async def margin_analysis(user: dict = Depends(require_business)):
    """AI-01 deterministic analysis: margin, cost changes and actionable alerts.

    Financial calculations are performed by the backend. A language model should
    only explain these results later; it must not calculate financial figures.
    """
    bid = user["business_id"]
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=90)

    products = await db.products.find({"business_id": bid}, {"_id": 0}).to_list(10000)
    purchases = await db.purchases.find(
        {"business_id": bid, "created_at": {"$gte": since.isoformat()}},
        {"_id": 0},
    ).sort("created_at", 1).to_list(20000)
    sales = await db.sales.find(
        {"business_id": bid, "created_at": {"$gte": since.isoformat()}},
        {"_id": 0},
    ).sort("created_at", 1).to_list(50000)

    purchase_history = {}
    for purchase in purchases:
        for item in purchase.get("items", []):
            pid = item.get("product_id")
            if pid:
                purchase_history.setdefault(pid, []).append({
                    "date": purchase["created_at"],
                    "unit_cost": float(item.get("unit_cost", 0) or 0),
                })

    sales_agg = {}
    for sale in sales:
        for item in sale.get("items", []):
            pid = item.get("product_id")
            if not pid:
                continue
            agg = sales_agg.setdefault(pid, {"units": 0, "revenue": 0.0, "profit": 0.0})
            qty = float(item.get("quantity", 0) or 0)
            revenue = float(item.get("line_total", 0) or 0)
            cost = float(item.get("cost", 0) or 0) * qty
            agg["units"] += qty
            agg["revenue"] += revenue
            agg["profit"] += revenue - cost

    analyses = []
    alerts = []
    for product in products:
        pid = product["id"]
        price = float(product.get("sale_price", 0) or 0)
        current_cost = float(product.get("purchase_price", 0) or 0)
        margin = round((price - current_cost) / price * 100, 1) if price > 0 else 0

        history = purchase_history.get(pid, [])
        cost_change = None
        previous_cost = None
        if len(history) >= 2:
            previous_cost = history[-2]["unit_cost"]
            cost_change = _pct_change(previous_cost, history[-1]["unit_cost"])

        sales_data = sales_agg.get(pid, {"units": 0, "revenue": 0.0, "profit": 0.0})
        units = sales_data["units"]
        revenue = round(sales_data["revenue"], 2)
        profit = round(sales_data["profit"], 2)

        item = {
            "product_id": pid,
            "product_name": product.get("name", "Producto"),
            "sale_price": price,
            "current_cost": current_cost,
            "margin_percent": margin,
            "previous_purchase_cost": previous_cost,
            "cost_change_percent": cost_change,
            "units_sold_90d": units,
            "revenue_90d": revenue,
            "profit_90d": profit,
        }
        analyses.append(item)

        if cost_change is not None and cost_change >= 10:
            alerts.append({
                "level": "warning",
                "type": "cost_increase",
                "product_id": pid,
                "product_name": product.get("name", "Producto"),
                "message": f"El costo de compra aumentó {cost_change}% respecto a la compra anterior. Revisa el precio de venta para proteger el margen.",
            })
        if price > 0 and margin < 15:
            alerts.append({
                "level": "warning" if margin >= 0 else "critical",
                "type": "low_margin",
                "product_id": pid,
                "product_name": product.get("name", "Producto"),
                "message": f"El margen actual es {margin}%. Revisa costo y precio de venta.",
            })

    analyses.sort(key=lambda x: x["profit_90d"], reverse=True)
    alerts.sort(key=lambda x: 0 if x["level"] == "critical" else 1)

    total_revenue = round(sum(x["revenue_90d"] for x in analyses), 2)
    total_profit = round(sum(x["profit_90d"] for x in analyses), 2)
    overall_margin = round(total_profit / total_revenue * 100, 1) if total_revenue else 0

    return {
        "period_days": 90,
        "summary": {
            "products_analyzed": len(analyses),
            "products_with_sales": sum(1 for x in analyses if x["units_sold_90d"] > 0),
            "revenue_90d": total_revenue,
            "profit_90d": total_profit,
            "margin_percent": overall_margin,
            "alerts_count": len(alerts),
        },
        "alerts": alerts[:20],
        "products": analyses,
        "generated_at": now.isoformat(),
    }
