"""PLATIA Business Score v1.

Internal 0-1000 indicator assembled from explainable business health/risk
signals. It is NOT a credit score and must not be used for external lending
decisions without independent validation.
"""
from datetime import datetime, timedelta, timezone

from financial_health import calculate_financial_health
from risk_engine import calculate_risk

VERSION = "1.1"


def _clip(v):
    return round(max(0.0, min(100.0, float(v))), 1)


def _band(score):
    if score >= 800: return "excelente"
    if score >= 700: return "bueno"
    if score >= 600: return "moderado"
    if score >= 500: return "elevado"
    return "alto"


async def calculate_platia_score(business_id: str, days: int = 90) -> dict:
    days = max(30, min(int(days), 3650))
    health = await calculate_financial_health(business_id, days)
    risk = await calculate_risk(business_id, days)

    health_score = _clip(health["score"])
    risk_score = _clip(risk["risk_score"])
    normalized = _clip(0.55 * health_score + 0.45 * (100 - risk_score))
    raw_score = round(normalized * 10)

    # Critical conditions must be visible in the final score. Otherwise a
    # strong liquidity signal can mathematically offset a catastrophic margin
    # and produce a misleading "moderate" score.
    snapshot = health.get("financial_snapshot", {})
    operating_margin = float(snapshot.get("operating_margin", 0) or 0)
    revenue = float(snapshot.get("revenue", 0) or 0)
    inventory = float(snapshot.get("inventory_value", 0) or 0)
    net_cash_flow = float(snapshot.get("net_cash_flow", 0) or 0)
    inventory_ratio = inventory / revenue * 100 if revenue > 0 else 0
    cash_flow_ratio = net_cash_flow / revenue * 100 if revenue > 0 else 0

    score = raw_score
    caps = []
    if operating_margin <= -20:
        score = min(score, 499)
        caps.append("Margen operativo críticamente negativo")
    elif operating_margin < 0:
        score = min(score, 599)
        caps.append("Margen operativo negativo")
    if inventory_ratio >= 150:
        score = min(score, 599)
        caps.append("Inventario excesivamente alto frente a ventas")
    if cash_flow_ratio <= -25:
        score = min(score, 499)
        caps.append("Flujo de caja críticamente negativo")

    score = int(score)
    components = [
        {"name": "Salud financiera", "score": round(health_score * 10), "weight": 55},
        {"name": "Riesgo operativo", "score": round((100 - risk_score) * 10), "weight": 45},
    ]
    strengths = [c["name"] for c in health["components"] if c["score"] >= 75]
    weaknesses = [f["name"] for f in risk["factors"] if f["risk"] >= 60]

    return {
        "score": score,
        "raw_score": raw_score,
        "band": _band(score),
        "version": VERSION,
        "period_days": days,
        "components": components,
        "strengths": strengths[:5],
        "weaknesses": weaknesses[:5],
        "risk_alerts": risk["alerts"][:5],
        "actions": risk["actions"][:6],
        "score_caps": caps,
        "methodology": "v1.1 = 55% Financial Health + 45% (100 - Risk Engine), con límites de seguridad cuando existen pérdidas operativas, inventario desproporcionado o flujo de caja críticamente negativo. El resultado se escala a 0-1000.",
        "source_models": {"financial_health": health["score"], "risk": risk["risk_score"]},
        "disclaimer": "PLATIA Business Score es un indicador interno de salud/riesgo empresarial. No es un credit score, no implica probabilidad de pago y no debe utilizarse para decisiones crediticias externas sin validación, calibración y revisión de sesgos.",
    }
