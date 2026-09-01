from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def build_sales_features(sales: list[dict], days: int = 30) -> dict:
    """Create lightweight, explainable features from historical sales."""
    today = datetime.now().astimezone().date()
    start_date = today - timedelta(days=max(days - 1, 0))
    cutoff = datetime.combine(start_date, datetime.min.time()).astimezone()
    daily = defaultdict(float)
    product_units = defaultdict(float)
    product_revenue = defaultdict(float)
    valid_sales = 0

    for sale in sales:
        created = _parse_date(sale.get("created_at"))
        if not created or created < cutoff:
            continue
        valid_sales += 1
        day = created.astimezone().date().isoformat()
        daily[day] += float(sale.get("total", 0) or 0)
        for item in sale.get("items", []):
            pid = item.get("product_id")
            if not pid:
                continue
            qty = float(item.get("base_quantity", item.get("quantity", 0)) or 0)
            product_units[pid] += qty
            product_revenue[pid] += float(item.get("line_total", 0) or 0)

    daily_series = {
        (start_date + timedelta(days=i)).isoformat(): round(daily.get((start_date + timedelta(days=i)).isoformat(), 0.0), 2)
        for i in range(days)
    }

    return {
        "daily_revenue": daily_series,
        "product_units": dict(product_units),
        "product_revenue": dict(product_revenue),
        "days": days,
        "sales_count": valid_sales,
        "observed_days": sum(1 for value in daily_series.values() if value > 0),
    }
