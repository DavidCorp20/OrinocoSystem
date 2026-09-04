"""Phase 6 - Financial Health Engine.

Produces an explainable 0-100 internal business-health indicator from the
Financial Engine. It is not a credit score and must not be used for lending
without independent validation.
"""
from datetime import datetime, timedelta, timezone

from database import db
from financial_engine import calculate_financial_snapshot


def _score_positive(value, good, weak):
    if value >= good: return 100
    if value <= weak: return 0
    return round((value - weak) / (good - weak) * 100, 1)


def _score_negative(value, weak, bad):
    if value <= weak: return 100
    if value >= bad: return 0
    return round((bad - value) / (bad - weak) * 100, 1)


def _component(name, score, explanation):
    return {"name": name, "score": round(max(0, min(100, score)), 1), "explanation": explanation}


async def calculate_financial_health(business_id: str, days: int = 90) -> dict:
    days = max(30, min(int(days), 3650))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    snapshot = await calculate_financial_snapshot(business_id, start, end)

    revenue = snapshot["revenue"]
    gross_margin = snapshot["gross_margin"]
    operating_margin = snapshot["operating_margin"]
    net_cash_flow = snapshot["net_cash_flow"]
    cash_balance = snapshot["cash_balance"]
    receivables = snapshot["receivables"]
    payables = snapshot["payables"]
    inventory = snapshot["inventory_value"]

    profitability = _score_positive(operating_margin, 20, -10)
    cash = _score_positive(net_cash_flow / revenue * 100 if revenue else 0, 15, -10)
    liquidity_base = cash_balance + receivables + inventory
    liquidity_ratio = liquidity_base / payables if payables > 0 else (2 if liquidity_base > 0 else 0)
    liquidity = _score_positive(liquidity_ratio, 2, 0.75)
    working_capital = snapshot["working_capital"]
    working_capital_score = _score_positive(working_capital / revenue * 100 if revenue else 0, 30, -10)
    data_quality = snapshot["data_quality"]
    quality_issues = data_quality["missing_sale_costs"] + data_quality["missing_date_records"] + data_quality["missing_inventory_cost_products"]
    quality = _score_negative(quality_issues, 0, max(10, int(revenue > 0) * 20))

    components = [
        _component("Rentabilidad", profitability, f"Margen operativo de {operating_margin:.2f}%"),
        _component("Caja", cash, f"Flujo neto de caja de {net_cash_flow:.2f} en el período"),
        _component("Liquidez", liquidity, f"Activos líquidos/realizables frente a cuentas por pagar: {liquidity_ratio:.2f}x"),
        _component("Capital de trabajo", working_capital_score, f"Capital de trabajo de {working_capital:.2f}"),
        _component("Calidad de datos", quality, f"Incidencias de calidad detectadas: {quality_issues}"),
    ]
    weights = [0.30, 0.25, 0.20, 0.15, 0.10]
    score = round(sum(c["score"] * w for c, w in zip(components, weights)), 1)
    if score >= 80: band = "saludable"
    elif score >= 65: band = "estable"
    elif score >= 50: band = "vigilancia"
    elif score >= 35: band = "débil"
    else: band = "crítica"

    alerts = []
    if operating_margin < 0: alerts.append("El negocio está operando con margen negativo.")
    if net_cash_flow < 0: alerts.append("El flujo neto de caja del período es negativo.")
    if payables > cash_balance + receivables: alerts.append("Las obligaciones superan la caja y cuentas por cobrar disponibles.")
    if quality_issues: alerts.append("La calidad de datos limita la confiabilidad de algunas métricas.")

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
        "score": score, "band": band, "components": components,
        "alerts": alerts[:8],
        "financial_snapshot": snapshot,
        "methodology": "Indicador interno 0-100 basado en rentabilidad 30%, caja 25%, liquidez 20%, capital de trabajo 15% y calidad de datos 10%.",
        "disclaimer": "PLATIA Financial Health no es un credit score ni una decisión crediticia. Requiere validación independiente antes de cualquier uso financiero externo.",
    }
