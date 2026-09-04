"""PLATIA Business Score v1.

Internal 0-1000 indicator assembled from explainable business health/risk
signals. It is NOT a credit score and must not be used for external lending
decisions without independent validation.
"""
from datetime import datetime, timedelta, timezone

from financial_health import calculate_financial_health
from risk_engine import calculate_risk

VERSION = "1.0"


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

    # Score v1: health carries the positive signal; risk is the downside signal.
    # 55% health + 45% inverse risk. Both source models are explainable.
    health_score = _clip(health["score"])
    risk_score = _clip(risk["risk_score"])
    normalized = _clip(0.55 * health_score + 0.45 * (100 - risk_score))
    score = round(normalized * 10)

    components = [
        {"name": "Salud financiera", "score": round(health_score * 10), "weight": 55},
        {"name": "Riesgo operativo", "score": round((100 - risk_score) * 10), "weight": 45},
    ]
    strengths = [c["name"] for c in health["components"] if c["score"] >= 75]
    weaknesses = [f["name"] for f in risk["factors"] if f["risk"] >= 60]

    return {
        "score": score,
        "band": _band(score),
        "version": VERSION,
        "period_days": days,
        "components": components,
        "strengths": strengths[:5],
        "weaknesses": weaknesses[:5],
        "risk_alerts": risk["alerts"][:5],
        "actions": risk["actions"][:6],
        "methodology": "v1 = 55% Financial Health + 45% (100 - Risk Engine). El resultado se escala linealmente a 0-1000.",
        "source_models": {"financial_health": health["score"], "risk": risk["risk_score"]},
        "disclaimer": "PLATIA Business Score es un indicador interno de salud/riesgo empresarial. No es un credit score, no implica probabilidad de pago y no debe utilizarse para decisiones crediticias externas sin validación, calibración y revisión de sesgos.",
    }
