from math import ceil


def inventory_recommendations(
    products: list[dict],
    product_units: dict,
    horizon_days: int = 7,
    observed_days: int = 30,
) -> list[dict]:
    """Return transparent reorder recommendations from observed demand."""
    recommendations = []
    demand_days = max(observed_days, 1)
    for product in products:
        pid = product.get("id")
        if not pid:
            continue
        units = float(product_units.get(pid, 0) or 0)
        daily_demand = units / demand_days
        stock = float(product.get("stock", 0) or 0)
        min_stock = float(product.get("min_stock", 0) or 0)
        max_stock = product.get("max_stock")
        target = max(min_stock, daily_demand * horizon_days)
        if max_stock is not None:
            target = min(max(float(max_stock), min_stock), max(target, min_stock))
        suggested = max(0, ceil(target - stock))
        if stock <= min_stock or suggested > 0:
            days_left = (stock / daily_demand) if daily_demand > 0 else None
            recommendations.append({
                "product_id": pid,
                "product_name": product.get("name", "Producto"),
                "stock": stock,
                "min_stock": min_stock,
                "max_stock": max_stock,
                "daily_demand": round(daily_demand, 2),
                "estimated_days_to_stockout": round(days_left, 1) if days_left is not None else None,
                "suggested_purchase": suggested,
            })
    return sorted(
        recommendations,
        key=lambda x: (
            x["estimated_days_to_stockout"] is None,
            x["estimated_days_to_stockout"] or 999999,
        ),
    )
