"""Deterministic intelligence layer built on Financial Engine facts.

Phase 4 intentionally avoids opaque AI decisions. It compares two periods and
emits auditable trends, deterioration signals and actionable recommendations.
"""
from datetime import datetime, timezone, timedelta

from database import db
from financial_engine import calculate_financial_snapshot, _parse_dt, _valid, _money


def _pct_change(current, previous):
    current = float(current or 0)
    previous = float(previous or 0)
    if previous == 0:
        return None if current == 0 else 100.0
    return round((current - previous) / abs(previous) * 100, 2)


def _trend(metric, current, previous, label):
    change = _pct_change(current, previous)
    if change is None:
        return None
    direction = "subió" if change > 0 else "bajó" if change < 0 else "se mantuvo estable"
    return {
        "metric": metric,
        "current": _money(current),
        "previous": _money(previous),
        "change_pct": change,
        "direction": "up" if change > 0 else "down" if change < 0 else "flat",
        "title": f"{label} {direction} {abs(change):.1f}% frente al período anterior.",
    }


async def _sales_product_concentration(business_id, start, end):
    sales = await db.sales.find({"business_id": business_id}, {"_id": 0}).to_list(50000)
    totals = {}
    revenue = 0.0
    for sale in sales:
        if not _valid(sale) or not _in_period(sale, start, end):
            continue
        for item in sale.get("items", []):
            name = item.get("name") or item.get("product_name") or "Producto"
            total = float(item.get("line_total", item.get("total", 0)) or 0)
            totals[name] = totals.get(name, 0) + total
            revenue += total
    if revenue <= 0 or not totals:
        return None
    top_name, top_value = max(totals.items(), key=lambda x: x[1])
    share = round(top_value / revenue * 100, 2)
    if share < 30:
        return None
    return {"product": top_name, "share_pct": share, "revenue": _money(top_value)}


def _in_period(doc, start, end):
    dt = _parse_dt(doc.get("created_at") or doc.get("occurred_at") or doc.get("paid_at") or doc.get("date"))
    return bool(dt and start <= dt < end)


async def calculate_intelligence(business_id: str, days: int = 30) -> dict:
    days = max(7, min(int(days), 3650))
    end = datetime.now(timezone.utc)
    current_start = end - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)

    current = await calculate_financial_snapshot(business_id, current_start, end)
    previous = await calculate_financial_snapshot(business_id, previous_start, current_start)

    trends = []
    for key, label in (
        ("revenue", "Las ventas"),
        ("gross_profit", "La utilidad bruta"),
        ("operating_profit", "La utilidad operativa"),
        ("operating_expenses", "Los gastos operativos"),
        ("net_cash_flow", "El flujo neto de caja"),
        ("receivables", "Las cuentas por cobrar"),
    ):
        item = _trend(key, current.get(key), previous.get(key), label)
        if item:
            trends.append(item)

    alerts = []
    actions = []

    revenue_change = _pct_change(current.get("revenue"), previous.get("revenue"))
    margin_delta = round(float(current.get("gross_margin", 0)) - float(previous.get("gross_margin", 0)), 2)
    expense_change = _pct_change(current.get("operating_expenses"), previous.get("operating_expenses"))
    cash_change = _pct_change(current.get("net_cash_flow"), previous.get("net_cash_flow"))

    if revenue_change is not None and revenue_change <= -10:
        alerts.append({"type": "revenue", "severity": "high", "title": "Las ventas están retrocediendo", "detail": f"Las ventas cambiaron {revenue_change:.1f}% frente al período anterior."})
        actions.append("Revisa qué productos, clientes o días explican la caída antes de aumentar gastos.")
    elif revenue_change is not None and revenue_change >= 15:
        alerts.append({"type": "revenue", "severity": "positive", "title": "Las ventas están acelerando", "detail": f"Las ventas crecieron {revenue_change:.1f}% frente al período anterior."})

    if margin_delta <= -3:
        alerts.append({"type": "margin", "severity": "high", "title": "El margen bruto se está comprimiendo", "detail": f"El margen pasó de {previous.get('gross_margin', 0):.2f}% a {current.get('gross_margin', 0):.2f}%."})
        actions.append("Identifica aumentos de costo, descuentos y productos que estén reduciendo el margen.")

    if expense_change is not None and expense_change >= 15 and (revenue_change is None or expense_change > revenue_change):
        alerts.append({"type": "expenses", "severity": "medium", "title": "Los gastos están creciendo más rápido que las ventas", "detail": f"Gastos: {expense_change:.1f}% vs ventas: {revenue_change if revenue_change is not None else 0:.1f}%."})
        actions.append("Separa gastos recurrentes de gastos extraordinarios y revisa los que crecen sin generar ventas adicionales.")

    if current.get("net_cash_flow", 0) < 0 and previous.get("net_cash_flow", 0) >= 0:
        alerts.append({"type": "cash", "severity": "high", "title": "La caja pasó a territorio negativo", "detail": "El flujo neto del período actual es negativo después de haber sido no negativo en el período anterior."})
        actions.append("Protege liquidez: acelera cobros y prioriza pagos y compras esenciales.")

    concentration = await _sales_product_concentration(business_id, current_start, end)
    if concentration:
        alerts.append({"type": "concentration", "severity": "medium", "title": "Existe concentración en un producto", "detail": f"{concentration['product']} representa {concentration['share_pct']:.1f}% de las ventas calculadas."})
        actions.append("Monitorea la dependencia de ese producto y desarrolla alternativas para reducir concentración.")

    return {
        "period_days": days,
        "current": current,
        "previous": previous,
        "trends": trends[:10],
        "alerts": alerts[:8],
        "actions": list(dict.fromkeys(actions))[:6],
        "methodology": "Comparación determinística de períodos consecutivos usando únicamente datos del Financial Engine y operaciones registradas.",
    }
