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
    cutoff = datetime.now().astimezone() - timedelta(days=days)
    daily = defaultdict(float)
    product_units = defaultdict(float)
    product_revenue = defaultdict(float)

    for sale in sales:
        created = _parse_date(sale.get("created_at"))
        if created and created < cutoff:
            continue
        day = created.date().isoformat() if created else "unknown"
        daily[day] += float(sale.get("total", 0) or 0)
        for item in sale.get("items", []):
            pid = item.get("product_id")
            if not pid:
                continue
            qty = float(item.get("base_quantity", item.get("quantity", 0)) or 0)
            product_units[pid] += qty
            product_revenue[pid] += float(item.get("line_total", 0) or 0)

    return {
        "daily_revenue": dict(daily),
        "product_units": dict(product_units),
        "product_revenue": dict(product_revenue),
        "days": days,
        "sales_count": len(sales),
    }
