"""Phase 7 - Risk Engine.

Explainable internal operating-risk indicators built from Financial Engine and
Financial Health. This is not a lending or regulated credit decision model.
"""
from datetime import datetime, timedelta, timezone

from database import db
from financial_engine import calculate_financial_snapshot


def _clip(v):
    return round(max(0.0, min(100.0, float(v))), 1)


def _risk_from_negative(value, good=0.0, bad=100.0):
    if value <= good: return 0.0
    return _clip((value - good) / (bad - good) * 100) if bad > good else 100.0


def _risk_from_ratio(value, safe=2.0, critical=0.75):
    if value >= safe: return 0.0
    if value <= critical: return 100.0
    return _clip((safe - value) / (safe - critical) * 100)


async def calculate_risk(business_id: str, days: int = 90) -> dict:
    days = max(30, min(int(days), 3650))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    snapshot = await calculate_financial_snapshot(business_id, start, end)

    revenue = snapshot["revenue"]
    gross_margin = snapshot["gross_margin"]
    operating_margin = snapshot["operating_margin"]
    net_cash_flow = snapshot["net_cash_flow"]
    cash = snapshot["cash_balance"]
    receivables = snapshot["receivables"]
    payables = snapshot["payables"]
    inventory = snapshot["inventory_value"]
    quality = snapshot["data_quality"]

    liquidity_ratio = (cash + receivables + inventory) / payables if payables > 0 else (2 if cash + receivables + inventory > 0 else 0)
    cash_burn_pct = max(0, -net_cash_flow / revenue * 100) if revenue else 0
    margin_risk = _clip((15 - operating_margin) / 25 * 100)
    cash_risk = _risk_from_negative(cash_burn_pct, 0, 25)
    liquidity_risk = _risk_from_ratio(liquidity_ratio)
    receivable_dependency = receivables / revenue * 100 if revenue else 0
    receivable_risk = _risk_from_negative(max(0, receivable_dependency - 20), 0, 50)
    inventory_dependency = inventory / revenue * 100 if revenue else 0
    inventory_risk = _risk_from_negative(max(0, inventory_dependency - 30), 0, 100)
    quality_issues = quality["missing_sale_costs"] + quality["missing_date_records"] + quality["missing_inventory_cost_products"]
    data_risk = _risk_from_negative(quality_issues, 0, 20)

    factors = [
        {"name": "Rentabilidad", "risk": margin_risk, "severity": "high" if margin_risk >= 70 else "medium" if margin_risk >= 40 else "low", "evidence": f"Margen operativo {operating_margin:.2f}%"},
        {"name": "Flujo de caja", "risk": cash_risk, "severity": "high" if cash_risk >= 70 else "medium" if cash_risk >= 40 else "low", "evidence": f"Flujo neto {net_cash_flow:.2f}"},
        {"name": "Liquidez", "risk": liquidity_risk, "severity": "high" if liquidity_risk >= 70 else "medium" if liquidity_risk >= 40 else "low", "evidence": f"Cobertura de obligaciones {liquidity_ratio:.2f}x"},
        {"name": "Cuentas por cobrar", "risk": receivable_risk, "severity": "high" if receivable_risk >= 70 else "medium" if receivable_risk >= 40 else "low", "evidence": f"CxC {receivables:.2f}"},
        {"name": "Inventario", "risk": inventory_risk, "severity": "high" if inventory_risk >= 70 else "medium" if inventory_risk >= 40 else "low", "evidence": f"Inventario equivalente a {inventory_dependency:.1f}% de ventas del período"},
        {"name": "Calidad de datos", "risk": data_risk, "severity": "high" if data_risk >= 70 else "medium" if data_risk >= 40 else "low", "evidence": f"{quality_issues} incidencias"},
    ]

    weights = [0.25, 0.25, 0.20, 0.15, 0.10, 0.05]
    overall = _clip(sum(f["risk"] * w for f, w in zip(factors, weights)))
    band = "bajo" if overall < 25 else "moderado" if overall < 50 else "elevado" if overall < 75 else "alto"
    alerts = [f["evidence"] for f in factors if f["risk"] >= 70]
    actions = []
    if cash_risk >= 40: actions.append("Prioriza liquidez y controla salidas de caja antes de aumentar compromisos.")
    if liquidity_risk >= 40: actions.append("Reduce presión de obligaciones o acelera la cobranza de cuentas pendientes.")
    if margin_risk >= 40: actions.append("Revisa precios, costos y gastos para recuperar margen operativo.")
    if receivable_risk >= 40: actions.append("Fortalece políticas de cobranza y límites de crédito a clientes.")
    if inventory_risk >= 40: actions.append("Revisa rotación y compras para evitar capital inmovilizado en inventario.")
    if data_risk >= 40: actions.append("Completa costos y fechas faltantes para mejorar la confiabilidad del análisis.")

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
        "risk_score": overall, "risk_band": band, "factors": factors,
        "alerts": alerts[:8], "actions": actions[:8],
        "financial_snapshot": snapshot,
        "methodology": "Riesgo operativo interno basado en rentabilidad 25%, caja 25%, liquidez 20%, cuentas por cobrar 15%, inventario 10% y calidad de datos 5%.",
        "disclaimer": "PLATIA Risk Engine es un indicador interno explicable. No es un credit score, no predice incumplimiento por sí solo y no debe utilizarse para decisiones crediticias externas sin validación independiente.",
    }
