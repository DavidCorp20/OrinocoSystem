from statistics import mean, pstdev


def detect_revenue_anomaly(daily_revenue: dict[str, float], z_threshold: float = 2.5) -> dict:
    """Detect an unusual latest daily revenue value using an explainable z-score."""
    values = [float(v or 0) for v in daily_revenue.values()]
    if len(values) < 7:
        return {"detected": False, "reason": "insufficient_history", "sample_size": len(values)}
    baseline = values[:-1]
    latest = values[-1]
    sd = pstdev(baseline)
    if sd == 0:
        return {"detected": latest != mean(baseline), "z_score": None, "latest": latest}
    z = (latest - mean(baseline)) / sd
    return {
        "detected": abs(z) >= z_threshold,
        "z_score": round(z, 2),
        "latest": round(latest, 2),
        "baseline_mean": round(mean(baseline), 2),
        "baseline_std": round(sd, 2),
    }
