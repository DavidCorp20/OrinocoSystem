from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends

from database import db
from security import require_business

router = APIRouter(prefix="/ai", tags=["ai"])


def _pct_change(old: float, new: float):
    if old == 0:
        return None
    return round((new - old) / old * 100, 1)


@router.get("/margin-analysis")
async def margin_analysis(user: dict = Depends(require_business)):
    """AI-01 deterministic margin intelligence.

    The backend performs every financial calculation. A language model can be
    layered on top later only to explain these already-calculated facts.
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

    # Purchase history is kept separately from the current product cost so we
    # can distinguish the latest supplier price from the weighted-average cost.
    purchase_history = {}
    for purchase in purchases:
        for item in purchase.get("items", []):
            pid = item.get("product_id")
            if pid:
                purchase_history.setdefault(pid, []).append({
                    "date": purchase.get("created_at"),
                    "unit_cost": float(item.get("unit_cost", 0) or 0),
                    "quantity": float(item.get("quantity", 0) or 0),
                })

    # Sales contain the actual cost snapshot used at the moment of sale. This
    # is the authoritative realized-margin history for the period.
    sales_agg = {}
    for sale in sales:
        for item in sale.get("items", []):
            pid = item.get("product_id")
            if not pid:
                continue
            qty = float(item.get("quantity", 0) or 0)
            revenue = float(item.get("line_total", 0) or 0)
            unit_cost = float(item.get("cost", 0) or 0)
            agg = sales_agg.setdefault(pid, {
                "units": 0.0,
                "revenue": 0.0,
                "profit": 0.0,
                "cost": 0.0,
            })
            agg["units"] += qty
            agg["revenue"] += revenue
            agg["cost"] += unit_cost * qty
            agg["profit"] += revenue - unit_cost * qty

    analyses = []
    alerts = []

    for product in products:
        pid = product["id"]
        price = float(product.get("sale_price", 0) or 0)
        weighted_cost = float(product.get("purchase_price", 0) or 0)
        current_margin = round((price - weighted_cost) / price * 100, 1) if price > 0 else 0

        history = purchase_history.get(pid, [])
        latest_purchase_cost = history[-1]["unit_cost"] if history else None
        previous_purchase_cost = history[-2]["unit_cost"] if len(history) >= 2 else None
        cost_change = _pct_change(previous_purchase_cost, latest_purchase_cost) if previous_purchase_cost is not None else None

        # Compare the latest supplier price with the current weighted-average
        # inventory cost as a second signal; this avoids treating the latest
        # purchase as if it were automatically the accounting cost of stock.
        latest_vs_weighted = _pct_change(weighted_cost, latest_purchase_cost) if latest_purchase_cost is not None and weighted_cost else None

        sales_data = sales_agg.get(pid, {"units": 0.0, "revenue": 0.0, "profit": 0.0, "cost": 0.0})
        units = sales_data["units"]
        revenue = round(sales_data["revenue"], 2)
        realized_cost = round(sales_data["cost"], 2)
        realized_profit = round(sales_data["profit"], 2)
        realized_margin = round(realized_profit / revenue * 100, 1) if revenue else None

        item = {
            "product_id": pid,
            "product_name": product.get("name", "Producto"),
            "sale_price": price,
            "weighted_average_cost": weighted_cost,
            "current_margin_percent": current_margin,
            "latest_purchase_cost": latest_purchase_cost,
            "previous_purchase_cost": previous_purchase_cost,
            "purchase_cost_change_percent": cost_change,
            "latest_vs_weighted_cost_percent": latest_vs_weighted,
            "units_sold_90d": units,
            "revenue_90d": revenue,
            "realized_cost_90d": realized_cost,
            "realized_profit_90d": realized_profit,
            "realized_margin_percent_90d": realized_margin,
        }
        analyses.append(item)

        name = product.get("name", "Producto")
        if cost_change is not None and cost_change >= 10:
            alerts.append({
                "level": "warning",
                "type": "cost_increase",
                "product_id": pid,
                "product_name": name,
                "message": f"El último costo de compra de {name} aumentó {cost_change}% frente a la compra anterior.",
            })
        if price > 0 and current_margin < 0:
            alerts.append({
                "level": "critical",
                "type": "negative_margin",
                "product_id": pid,
                "product_name": name,
                "message": f"{name} tiene margen negativo de {current_margin}% con el costo promedio actual.",
            })
        elif price > 0 and current_margin < 15:
            alerts.append({
                "level": "warning",
                "type": "low_margin",
                "product_id": pid,
                "product_name": name,
                "message": f"{name} tiene un margen actual de {current_margin}%, por debajo del umbral de 15%.",
            })
        if realized_margin is not None and realized_margin < 15 and units > 0:
            alerts.append({
                "level": "warning" if realized_margin >= 0 else "critical",
                "type": "realized_margin",
                "product_id": pid,
                "product_name": name,
                "message": f"El margen realizado de los últimos 90 días es {realized_margin}%.",
            })

    analyses.sort(key=lambda x: x["realized_profit_90d"], reverse=True)
    priority = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda x: priority.get(x["level"], 9))

    total_revenue = round(sum(x["revenue_90d"] for x in analyses), 2)
    total_cost = round(sum(x["realized_cost_90d"] for x in analyses), 2)
    total_profit = round(sum(x["realized_profit_90d"] for x in analyses), 2)
    overall_margin = round(total_profit / total_revenue * 100, 1) if total_revenue else 0

    return {
        "period_days": 90,
        "methodology": {
            "current_cost": "weighted_average_purchase_cost_on_product",
            "realized_margin": "historical_cost_snapshot_saved_on_each_sale",
            "cost_change": "latest_purchase_unit_cost_vs_previous_purchase_unit_cost",
        },
        "summary": {
            "products_analyzed": len(analyses),
            "products_with_sales": sum(1 for x in analyses if x["units_sold_90d"] > 0),
            "revenue_90d": total_revenue,
            "realized_cost_90d": total_cost,
            "realized_profit_90d": total_profit,
            "realized_margin_percent": overall_margin,
            "alerts_count": len(alerts),
        },
        "alerts": alerts[:20],
        "products": analyses,
        "generated_at": now.isoformat(),
    }
