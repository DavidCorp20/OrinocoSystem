import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from database import db
from financial_engine import calculate_financial_snapshot, _parse_dt, _valid
from platia_score import calculate_platia_score
from security import require_superadmin

router = APIRouter(tags=["platform-intelligence"])


def _in_period(doc, start, end):
    dt = _parse_dt(doc.get("created_at") or doc.get("occurred_at") or doc.get("paid_at") or doc.get("date"))
    return bool(dt and start <= dt < end)


async def _business_metrics(business, start, end, owner):
    bid = business["id"]
    snapshot_task = calculate_financial_snapshot(bid, start, end)
    score_task = calculate_platia_score(bid, max(30, (end - start).days))
    sales_task = db.sales.find({"business_id": bid}, {"_id": 0}).to_list(50000)
    purchases_task = db.purchases.find({"business_id": bid}, {"_id": 0}).to_list(50000)
    products_task = db.products.count_documents({"business_id": bid})
    users_task = db.users.count_documents({"business_id": bid})
    sales, purchases, snapshot, score, products_count, users_count = await asyncio.gather(
        sales_task, purchases_task, snapshot_task, score_task, products_task, users_task
    )

    period_sales = [x for x in sales if _valid(x) and _in_period(x, start, end)]
    period_purchases = [x for x in purchases if _valid(x) and _in_period(x, start, end)]
    purchase_amount = round(sum(float(x.get("total", 0) or 0) for x in period_purchases), 2)
    average_ticket = round(snapshot["revenue"] / len(period_sales), 2) if period_sales else 0

    return {
        "id": bid,
        "name": business.get("name", "Negocio"),
        "type": business.get("type"),
        "active": bool(business.get("active", True)),
        "currency": business.get("currency", "USD"),
        "owner_name": owner.get("name", "—"),
        "owner_email": owner.get("email", "—"),
        "created_at": business.get("created_at"),
        "users_count": users_count,
        "products_count": products_count,
        "sales_count": len(period_sales),
        "purchases_count": len(period_purchases),
        "sales": snapshot["revenue"],
        "cogs": snapshot["cogs"],
        "gross_profit": snapshot["gross_profit"],
        "gross_margin": snapshot["gross_margin"],
        "operating_expenses": snapshot["operating_expenses"],
        "operating_profit": snapshot["operating_profit"],
        "operating_margin": snapshot["operating_margin"],
        "purchase_amount": purchase_amount,
        "average_ticket": average_ticket,
        "cash_balance": snapshot["cash_balance"],
        "cash_flow": snapshot["net_cash_flow"],
        "receivables": snapshot["receivables"],
        "payables": snapshot["payables"],
        "inventory_value": snapshot["inventory_value"],
        "working_capital": snapshot["working_capital"],
        "score": score["score"],
        "score_band": score["band"],
        "score_components": score.get("components", []),
        "score_alerts": score.get("risk_alerts", []),
        "score_actions": score.get("actions", []),
        "data_quality": snapshot.get("data_quality", {}),
    }


@router.get("/platform/intelligence")
async def platform_intelligence(days: int = 90, user: dict = Depends(require_superadmin)):
    if days < 30 or days > 3650:
        raise HTTPException(400, "days debe estar entre 30 y 3650")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    businesses = await db.businesses.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    owners = {
        u["id"]: u
        for u in await db.users.find({}, {"_id": 0, "id": 1, "email": 1, "name": 1}).to_list(10000)
    }

    semaphore = asyncio.Semaphore(8)

    async def one(business):
        async with semaphore:
            return await _business_metrics(business, start, end, owners.get(business.get("owner_id"), {}))

    rows = await asyncio.gather(*(one(b) for b in businesses))
    active = [x for x in rows if x["active"]]
    revenue = round(sum(x["sales"] for x in rows), 2)
    gross_profit = round(sum(x["gross_profit"] for x in rows), 2)
    operating_profit = round(sum(x["operating_profit"] for x in rows), 2)
    purchases = round(sum(x["purchase_amount"] for x in rows), 2)
    expenses = round(sum(x["operating_expenses"] for x in rows), 2)
    inventory = round(sum(x["inventory_value"] for x in rows), 2)
    scores = [x["score"] for x in active if x.get("score") is not None]

    suppliers = await db.suppliers.find({}, {"_id": 0}).to_list(50000)
    supplier_events = await db.supplier_events.find({}, {"_id": 0}).to_list(100000)
    business_names = {b["id"]: b.get("name", "Negocio") for b in businesses}
    supplier_map = {s["id"]: s for s in suppliers}
    supplier_rows = {}
    for event in supplier_events:
        if event.get("event_type") != "purchase" or not _in_period(event, start, end):
            continue
        sid = event.get("supplier_id")
        supplier = supplier_map.get(sid)
        if not supplier:
            continue
        key = f"{supplier.get('business_id')}:{sid}"
        row = supplier_rows.setdefault(key, {
            "supplier_id": sid,
            "business_id": supplier.get("business_id"),
            "business_name": business_names.get(supplier.get("business_id"), "Negocio"),
            "name": supplier.get("name", "Proveedor"),
            "rif": supplier.get("rif"),
            "purchases": 0,
            "purchase_amount": 0.0,
            "items": 0,
            "last_purchase": None,
        })
        row["purchases"] += 1
        row["purchase_amount"] += float(event.get("amount", 0) or 0)
        row["items"] += int(event.get("items_count", 0) or 0)
        dt = _parse_dt(event.get("event_date") or event.get("created_at"))
        if dt and (row["last_purchase"] is None or dt > row["last_purchase"]):
            row["last_purchase"] = dt

    supplier_list = list(supplier_rows.values())
    supplier_total = sum(x["purchase_amount"] for x in supplier_list)
    for row in supplier_list:
        row["purchase_amount"] = round(row["purchase_amount"], 2)
        row["purchase_share_pct"] = round(row["purchase_amount"] / supplier_total * 100, 2) if supplier_total else 0
        row["last_purchase"] = row["last_purchase"].isoformat() if row["last_purchase"] else None
        row["activity_score"] = min(100, row["purchases"] * 10)
    supplier_list.sort(key=lambda x: x["purchase_amount"], reverse=True)

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
        "summary": {
            "businesses": len(rows),
            "active_businesses": len(active),
            "sales": revenue,
            "gross_profit": gross_profit,
            "operating_profit": operating_profit,
            "operating_margin": round(operating_profit / revenue * 100, 2) if revenue else 0,
            "purchases": purchases,
            "operating_expenses": expenses,
            "inventory": inventory,
            "average_score": round(sum(scores) / len(scores)) if scores else 0,
            "scored_businesses": len(scores),
            "suppliers": len(supplier_list),
        },
        "businesses": sorted(rows, key=lambda x: x["sales"], reverse=True),
        "suppliers": supplier_list[:500],
    }
