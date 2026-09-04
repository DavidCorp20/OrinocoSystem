from datetime import datetime, timezone, timedelta
from typing import Optional

from database import db


VOID_STATUSES = {"cancelada", "cancelado", "anulada", "anulado", "void", "cancelled"}


def _parse_dt(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        value = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _in_period(doc: dict, start: datetime, end: datetime) -> bool:
    dt = _parse_dt(doc.get("created_at") or doc.get("occurred_at") or doc.get("paid_at") or doc.get("date"))
    return bool(dt and start <= dt < end)


def _valid(doc: dict) -> bool:
    status = str(doc.get("status") or "").strip().lower()
    return status not in VOID_STATUSES


def _money(value) -> float:
    return round(float(value or 0), 2)


async def calculate_revenue(business_id: str, start: datetime, end: datetime) -> float:
    sales = await db.sales.find({"business_id": business_id}, {"_id": 0}).to_list(50000)
    return _money(sum(s.get("total", 0) for s in sales if _valid(s) and _in_period(s, start, end)))


async def calculate_cogs(business_id: str, start: datetime, end: datetime) -> float:
    sales = await db.sales.find({"business_id": business_id}, {"_id": 0}).to_list(50000)
    total = 0.0
    for sale in sales:
        if not _valid(sale) or not _in_period(sale, start, end):
            continue
        if sale.get("cost_total") is not None:
            total += float(sale.get("cost_total") or 0)
        else:
            total += sum(float(i.get("cost", 0) or 0) * float(i.get("quantity", 0) or 0) for i in sale.get("items", []))
    return _money(total)


async def calculate_operating_expenses(business_id: str, start: datetime, end: datetime) -> float:
    expenses = await db.expenses.find({"business_id": business_id}, {"_id": 0}).to_list(50000)
    return _money(sum(e.get("amount", 0) for e in expenses if _valid(e) and _in_period(e, start, end)))


async def calculate_cash_flow(business_id: str, start: datetime, end: datetime) -> dict:
    movements = await db.cash_movements.find({"business_id": business_id}, {"_id": 0}).to_list(100000)
    movements = [m for m in movements if _in_period(m, start, end)]
    cash_in = _money(sum(m.get("amount", 0) for m in movements if m.get("direction") == "in"))
    cash_out = _money(sum(m.get("amount", 0) for m in movements if m.get("direction") == "out"))
    return {"cash_in": cash_in, "cash_out": cash_out, "net_cash_flow": _money(cash_in - cash_out)}


async def calculate_cash_balance(business_id: str) -> float:
    pipeline = [{"$match": {"business_id": business_id}}, {"$group": {"_id": "$direction", "total": {"$sum": {"$ifNull": ["$amount", 0]}}}}]
    rows = await db.cash_movements.aggregate(pipeline).to_list(10)
    totals = {r.get("_id"): float(r.get("total", 0) or 0) for r in rows}
    return _money(totals.get("in", 0) - totals.get("out", 0))


async def calculate_receivables(business_id: str) -> float:
    pipeline = [{"$match": {"business_id": business_id, "kind": "por_cobrar", "status": {"$ne": "cancelada"}}}, {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$remaining_amount", {"$ifNull": ["$outstanding_amount", 0]}]}}}}]
    rows = await db.obligations.aggregate(pipeline).to_list(1)
    return _money(rows[0]["total"] if rows else 0)


async def calculate_payables(business_id: str) -> float:
    pipeline = [{"$match": {"business_id": business_id, "kind": "por_pagar", "status": {"$ne": "cancelada"}}}, {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$remaining_amount", {"$ifNull": ["$outstanding_amount", 0]}]}}}}]
    rows = await db.obligations.aggregate(pipeline).to_list(1)
    return _money(rows[0]["total"] if rows else 0)


async def calculate_inventory_value(business_id: str) -> dict:
    products = await db.products.find({"business_id": business_id}, {"_id": 0}).to_list(50000)
    value = 0.0
    missing_cost = 0
    for product in products:
        stock = float(product.get("stock", 0) or 0)
        cost = product.get("weighted_average_purchase_cost", product.get("purchase_price"))
        if stock > 0 and (cost is None or float(cost or 0) < 0):
            missing_cost += 1
            continue
        value += stock * float(cost or 0)
    return {"inventory_value": _money(value), "products_count": len(products), "missing_cost_products": missing_cost}


async def calculate_financial_snapshot(business_id: str, start: datetime, end: datetime) -> dict:
    revenue = await calculate_revenue(business_id, start, end)
    cogs = await calculate_cogs(business_id, start, end)
    gross_profit = _money(revenue - cogs)
    expenses = await calculate_operating_expenses(business_id, start, end)
    operating_profit = _money(gross_profit - expenses)
    cash = await calculate_cash_flow(business_id, start, end)
    cash_balance = await calculate_cash_balance(business_id)
    receivables = await calculate_receivables(business_id)
    payables = await calculate_payables(business_id)
    inventory = await calculate_inventory_value(business_id)
    working_capital = _money(cash_balance + receivables + inventory["inventory_value"] - payables)

    sales = await db.sales.find({"business_id": business_id}, {"_id": 0}).to_list(50000)
    expenses_docs = await db.expenses.find({"business_id": business_id}, {"_id": 0}).to_list(50000)
    missing_sale_costs = sum(1 for s in sales if _valid(s) and _in_period(s, start, end) and any(i.get("cost") is None for i in s.get("items", [])))
    missing_dates = sum(1 for s in sales + expenses_docs if not _parse_dt(s.get("created_at") or s.get("date")))

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "revenue": revenue,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "gross_margin": round(gross_profit / revenue * 100, 2) if revenue else 0,
        "operating_expenses": expenses,
        "operating_profit": operating_profit,
        "operating_margin": round(operating_profit / revenue * 100, 2) if revenue else 0,
        **cash,
        "cash_balance": cash_balance,
        "receivables": receivables,
        "payables": payables,
        "inventory_value": inventory["inventory_value"],
        "working_capital": working_capital,
        "data_quality": {
            "missing_sale_costs": missing_sale_costs,
            "missing_date_records": missing_dates,
            "missing_inventory_cost_products": inventory["missing_cost_products"],
            "cash_ledger_available": True,
        },
    }


async def get_financial_snapshot(business_id: str, days: int = 30) -> dict:
    days = max(1, min(int(days), 3650))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return await calculate_financial_snapshot(business_id, start, end)
