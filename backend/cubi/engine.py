from datetime import datetime, timedelta, timezone

from .anomalies import detect_revenue_anomaly
from .config import cubi_config
from .features import build_sales_features
from .forecast import forecast_daily_sales
from .inventory import inventory_recommendations


def _safe_pct_change(old: float, new: float):
    if old == 0:
        return None
    return round((new - old) / abs(old) * 100, 1)


def _classify_abc(rows: list[dict]) -> list[dict]:
    rows = sorted(rows, key=lambda x: x["revenue"], reverse=True)
    total = sum(x["revenue"] for x in rows)
    cumulative = 0.0
    for row in rows:
        cumulative += row["revenue"]
        share = cumulative / total if total else 0
        row["abc_class"] = "A" if share <= 0.80 else "B" if share <= 0.95 else "C"
    return rows


def _health_score(summary: dict) -> dict:
    """Transparent score; every component is derived from observed business data."""
    components = {}

    margin = summary.get("margin_percent")
    components["margin"] = round(max(0, min(100, margin * 2 if margin is not None else 0)), 1)

    growth = summary.get("revenue_growth_percent")
    components["growth"] = round(max(0, min(100, 50 + (growth or 0) * 2)), 1)

    expense_ratio = summary.get("expense_ratio_percent")
    components["expenses"] = round(max(0, min(100, 100 - (expense_ratio or 0) * 2)), 1)

    inventory_risk = summary.get("inventory_risk_percent")
    components["inventory"] = round(max(0, min(100, 100 - (inventory_risk or 0))), 1)

    score = round(
        components["margin"] * 0.35
        + components["growth"] * 0.20
        + components["expenses"] * 0.20
        + components["inventory"] * 0.25,
        1,
    )
    return {"score": score, "components": components, "method": "margin_35_growth_20_expenses_20_inventory_25"}


def _build_diagnosis(summary: dict, top_products: list[dict], inventory: list[dict], anomaly: dict, forecast: dict) -> dict:
    facts = []
    risks = []
    opportunities = []
    recommendations = []

    growth = summary.get("revenue_growth_percent")
    margin = summary.get("margin_percent", 0)
    expense_ratio = summary.get("expense_ratio_percent", 0)

    if growth is not None:
        direction = "subieron" if growth >= 0 else "bajaron"
        facts.append(f"Las ventas {direction} {abs(growth)}% frente al período anterior.")
    facts.append(f"El margen bruto estimado es {margin}%.")

    if growth is not None and growth > 10 and margin < 20:
        risks.append("El negocio está creciendo, pero con poco margen por venta.")
        recommendations.append("Revisar primero los productos de mayor venta que tengan menor margen.")
    elif growth is not None and growth > 0:
        opportunities.append("El crecimiento de ventas es una señal favorable para escalar con control de costos.")

    if expense_ratio > 30:
        risks.append(f"Los gastos representan {expense_ratio}% de las ventas.")
        recommendations.append("Revisar los gastos que más crecieron antes de asumir nuevos compromisos.")

    urgent_stock = [x for x in inventory if x.get("estimated_days_to_stockout") is not None and x["estimated_days_to_stockout"] <= 7]
    if urgent_stock:
        risks.append(f"Hay {len(urgent_stock)} producto(s) con riesgo de agotarse en 7 días o menos.")
        recommendations.append("Priorizar la reposición de los productos con menor cantidad de días de inventario.")

    if anomaly.get("is_anomaly"):
        opportunities.append("Se detectó un comportamiento de ventas fuera de lo habitual; conviene revisar qué lo provocó antes de extrapolarlo.")

    if forecast.get("available") and forecast.get("trend_percent", 0) > 10:
        opportunities.append("La tendencia reciente apunta a mayor venta; conviene preparar inventario sin sobrecomprar.")

    confidence = "high" if summary.get("sales_count", 0) >= 20 else "medium" if summary.get("sales_count", 0) >= 7 else "low"
    return {
        "facts": facts[:6],
        "diagnosis": risks[:6],
        "risks": risks[:6],
        "opportunities": opportunities[:6],
        "recommendations": recommendations[:6],
        "confidence": confidence,
        "confidence_reason": "Basada en cantidad de ventas y disponibilidad de datos históricos; no representa certeza causal.",
        "teaching": [
            {"term": "Margen bruto", "meaning": "Lo que queda de una venta después de cubrir el costo del producto."},
            {"term": "Ticket promedio", "meaning": "Cuánto representa, en promedio, cada venta."},
        ],
    }


async def build_business_insights(db, business_id: str) -> dict:
    """Build exact, explainable business facts for Cubi to interpret in human language."""
    now = datetime.now(timezone.utc)
    sales = await db.sales.find({"business_id": business_id}, {"_id": 0}).sort("created_at", 1).to_list(5000)
    products = await db.products.find({"business_id": business_id}, {"_id": 0}).to_list(5000)
    expenses = await db.expenses.find({"business_id": business_id}, {"_id": 0}).sort("created_at", 1).to_list(10000)

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
        name = product.get("name") or product.get("product_name") or "Producto"
        product_metrics.append({
            "product_id": pid, "product_name": name, "name": name,
            "units": round(float(units), 2), "revenue": round(revenue, 2),
            "cost": round(cost, 2), "profit": round(profit, 2),
            "margin_percent": round(margin, 1),
        })

    abc = _classify_abc(product_metrics)
    inventory = inventory_recommendations(products, features["product_units"], horizon_days=cubi_config.low_stock_horizon_days, observed_days=features["days"])
    anomaly = detect_revenue_anomaly(features["daily_revenue"], z_threshold=cubi_config.anomaly_z_threshold)
    forecast = forecast_daily_sales(features["daily_revenue"], horizon_days=cubi_config.forecast_horizon_days)

    cutoff = now - timedelta(days=30)
    prior_cutoff = cutoff - timedelta(days=30)
    current_sales = [s for s in sales if _date(s.get("created_at")) and _date(s.get("created_at")) >= cutoff]
    prior_sales = [s for s in sales if _date(s.get("created_at")) and prior_cutoff <= _date(s.get("created_at")) < cutoff]

    current_revenue = round(sum(float(s.get("total", 0) or 0) for s in current_sales), 2)
    prior_revenue = round(sum(float(s.get("total", 0) or 0) for s in prior_sales), 2)
    current_expenses = round(sum(float(e.get("amount", e.get("total", 0)) or 0) for e in expenses if _date(e.get("created_at")) and _date(e.get("created_at")) >= cutoff), 2)
    expense_ratio = round(current_expenses / current_revenue * 100, 1) if current_revenue else 0
    total_revenue = round(sum(x["revenue"] for x in product_metrics), 2)
    total_profit = round(sum(x["profit"] for x in product_metrics), 2)
    margin = round(total_profit / total_revenue * 100, 1) if total_revenue else 0
    stock_capital = round(sum(float(p.get("stock", 0) or 0) * float(p.get("purchase_price", 0) or 0) for p in products), 2)
    low_stock_value = round(sum(float(p.get("stock", 0) or 0) * float(p.get("purchase_price", 0) or 0) for p in products if float(p.get("stock", 0) or 0) <= float(p.get("min_stock", 0) or 0)), 2)
    inventory_risk = round(low_stock_value / stock_capital * 100, 1) if stock_capital else 0
    revenue_growth = _safe_pct_change(prior_revenue, current_revenue)
    avg_ticket = round(current_revenue / len(current_sales), 2) if current_sales else 0

    summary = {
        "revenue": total_revenue,
        "profit": total_profit,
        "margin_percent": margin,
        "products_sold": len(product_metrics),
        "sales_count": len(current_sales),
        "revenue_current_30d": current_revenue,
        "revenue_prior_30d": prior_revenue,
        "revenue_growth_percent": revenue_growth,
        "expenses_30d": current_expenses,
        "expense_ratio_percent": expense_ratio,
        "average_ticket": avg_ticket,
        "inventory_capital": stock_capital,
        "low_stock_value": low_stock_value,
        "inventory_risk_percent": inventory_risk,
    }
    health = _health_score(summary)
    diagnosis = _build_diagnosis(summary, abc[:10], inventory, anomaly, forecast)

    return {
        "engine": "cubi-native-financial-bi-v2",
        "generated_at": now.isoformat(),
        "business_id": business_id,
        "methodology": {
            "principle": "data -> calculation -> context -> reasoning -> action",
            "llm_role": "interpret calculated facts; never invent financial figures",
            "margin": "product purchase cost multiplied by units sold",
            "growth": "current 30 days versus previous 30 days",
            "health_score": health["method"],
        },
        "history": {"sales_count": features["sales_count"], "days": features["days"], "observed_days": features["observed_days"]},
        "summary": summary,
        "health_score": health,
        "analysis": diagnosis,
        "top_products": sorted(abc, key=lambda x: x["units"], reverse=True)[:10],
        "top_products_by_revenue": sorted(abc, key=lambda x: x["revenue"], reverse=True)[:10],
        "abc_analysis": abc[:30],
        "forecast": forecast,
        "inventory_recommendations": inventory[:20],
        "anomaly": anomaly,
    }


def _date(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None
