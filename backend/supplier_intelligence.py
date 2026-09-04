"""Phase 5 - Supplier Intelligence.

Deterministic supplier analytics built from tenant-scoped supplier_events.
No external assumptions are introduced: missing dimensions remain unknown.
"""
from datetime import datetime, timedelta, timezone

from database import db


async def get_supplier_intelligence(business_id: str, days: int = 90) -> dict:
    days = max(1, min(int(days), 3650))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    suppliers = await db.suppliers.find({"business_id": business_id}, {"_id": 0}).to_list(50000)
    events = await db.supplier_events.find({"business_id": business_id}, {"_id": 0}).to_list(100000)

    stats = {}
    for s in suppliers:
        stats[s["id"]] = {
            "supplier_id": s["id"], "name": s.get("name", "Proveedor"),
            "purchases": 0, "purchase_amount": 0.0, "items": 0,
            "first_event": None, "last_event": None,
        }

    for e in events:
        if e.get("event_type") != "purchase":
            continue
        dt = _parse(e.get("event_date") or e.get("created_at"))
        if not dt or not (start <= dt < end):
            continue
        sid = e.get("supplier_id")
        if sid not in stats:
            continue
        x = stats[sid]
        x["purchases"] += 1
        x["purchase_amount"] += float(e.get("amount", 0) or 0)
        x["items"] += int(e.get("items_count", 0) or 0)
        if x["first_event"] is None or dt < x["first_event"]: x["first_event"] = dt
        if x["last_event"] is None or dt > x["last_event"]: x["last_event"] = dt

    ranked = []
    total = sum(x["purchase_amount"] for x in stats.values())
    for x in stats.values():
        amount = round(x["purchase_amount"], 2)
        share = round(amount / total * 100, 2) if total else 0
        # Scores are deliberately limited to observable dimensions.
        activity_score = min(100, x["purchases"] * 10)
        concentration_score = round(100 - min(100, share), 2)
        ranked.append({
            "supplier_id": x["supplier_id"], "name": x["name"],
            "purchases": x["purchases"], "purchase_amount": amount,
            "purchase_share_pct": share, "items": x["items"],
            "activity_score": activity_score,
            "concentration_score": concentration_score,
        })

    ranked.sort(key=lambda x: x["purchase_amount"], reverse=True)
    insights = []
    actions = []
    if ranked and total:
        top = ranked[0]
        insights.append({"type": "fact", "metric": "supplier_concentration", "title": f"{top['name']} concentra {top['purchase_share_pct']}% de tus compras", "explanation": "La concentración se calcula sobre el monto de compras registrado en el período."})
        if top["purchase_share_pct"] >= 50:
            actions.append("Evalúa proveedores alternativos para reducir dependencia de un solo proveedor.")
    if not ranked or not total:
        insights.append({"type": "info", "metric": "supplier_activity", "title": "Aún no hay compras suficientes para evaluar proveedores", "explanation": "Registra compras con proveedor para construir historial y métricas."})

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "summary": {"suppliers": len(ranked), "purchase_amount": round(total, 2), "active_suppliers": sum(1 for x in ranked if x["purchases"] > 0)},
        "suppliers": ranked[:100], "insights": insights[:6], "actions": actions[:6],
        "methodology": "Métricas determinísticas basadas exclusivamente en eventos de compra registrados por proveedor.",
    }


def _parse(value):
    if not value: return None
    if isinstance(value, datetime): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
