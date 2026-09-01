from statistics import mean


def _linear_regression_forecast(values: list[float], horizon_days: int) -> tuple[float, float]:
    """Fit y=a+bx with ordinary least squares and return daily/period forecast."""
    n = len(values)
    x = list(range(n))
    x_mean = mean(x)
    y_mean = mean(values)
    denominator = sum((xi - x_mean) ** 2 for xi in x)
    slope = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values)) / denominator if denominator else 0.0
    intercept = y_mean - slope * x_mean
    future = [max(0.0, intercept + slope * (n + i)) for i in range(horizon_days)]
    return (mean(future) if future else 0.0, sum(future))


def forecast_daily_sales(daily_revenue: dict[str, float], horizon_days: int = 7) -> dict:
    """Forecast revenue with a transparent linear trend over recent observations."""
    values = [float(v or 0) for v in daily_revenue.values() if v is not None]
    if len(values) < 7:
        return {"available": False, "reason": "insufficient_history", "observations": len(values)}

    recent = values[-14:]
    predicted_daily, predicted_period = _linear_regression_forecast(recent, horizon_days)
    baseline = mean(recent)
    trend_percent = ((predicted_daily / baseline) - 1) * 100 if baseline else 0
    return {
        "available": True,
        "method": "linear_trend_14_day",
        "horizon_days": horizon_days,
        "predicted_daily_revenue": round(predicted_daily, 2),
        "predicted_period_revenue": round(predicted_period, 2),
        "recent_daily_average": round(baseline, 2),
        "trend_percent": round(trend_percent, 1),
        "observations": len(values),
    }
