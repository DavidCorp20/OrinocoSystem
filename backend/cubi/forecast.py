from statistics import mean


def forecast_daily_sales(daily_revenue: dict[str, float], horizon_days: int = 7) -> dict:
    """Baseline forecast using recent daily average; intentionally explainable for v1."""
    values = [float(v or 0) for v in daily_revenue.values() if v is not None]
    if len(values) < 7:
        return {"available": False, "reason": "insufficient_history", "observations": len(values)}

    recent = values[-14:]
    baseline = mean(recent)
    return {
        "available": True,
        "method": "recent_14_day_mean",
        "horizon_days": horizon_days,
        "predicted_daily_revenue": round(baseline, 2),
        "predicted_period_revenue": round(baseline * horizon_days, 2),
        "observations": len(values),
    }
