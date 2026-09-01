from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from database import db
from models import CashClosureIn
from security import new_id, now_iso, require_roles

router = APIRouter(tags=["cash-closure"])
MANAGER = Depends(require_roles("propietario", "administrador"))


def _date_bounds(date: str):
    return f"{date}T00:00:00", f"{date}T23:59:59.999999"


def _cash_amount(document: dict) -> float:
    parts = document.get("payment_parts") or []
    if parts:
        return round(sum(float(p.get("amount", 0) or 0) for p in parts if str(p.get("method", "")).strip().lower() in {"efectivo", "cash"}), 2)
    method = str(document.get("payment_method", "")).strip().lower()
    return round(float(document.get("total", document.get("amount", 0)) or 0), 2) if method in {"efectivo", "cash"} else 0.0


async def _summary(bid: str, date: str):
    start, end = _date_bounds(date)
    sales = await db.sales.find({"business_id": bid, "created_at": {"$gte": start, "$lte": end}}, {"_id": 0}).to_list(50000)
    purchases = await db.purchases.find({"business_id": bid, "created_at": {"$gte": start, "$lte": end}}, {"_id": 0}).to_list(50000)
    expenses = await db.expenses.find({"business_id": bid, "date": date}, {"_id": 0}).to_list(50000)
    obligation_payments = await db.obligation_payments.find({"business_id": bid, "paid_at": {"$gte": start, "$lte": end}}, {"_id": 0}).to_list(50000)

    cash_sales = round(sum(_cash_amount(s) for s in sales), 2)
    cash_purchases = round(sum(_cash_amount(p) for p in purchases if p.get("status", "pagada") != "pendiente"), 2)
    cash_expenses = round(sum(float(e.get("amount", 0) or 0) for e in expenses if str(e.get("payment_method", "efectivo")).strip().lower() in {"efectivo", "cash"}), 2)
    cash_receivables = round(sum(float(p.get("amount", 0) or 0) for p in obligation_payments if p.get("kind") == "por_cobrar" and str(p.get("payment_method", "")).strip().lower() in {"efectivo", "cash"}), 2)
    cash_payables = round(sum(float(p.get("amount", 0) or 0) for p in obligation_payments if p.get("kind") == "por_pagar" and str(p.get("payment_method", "")).strip().lower() in {"efectivo", "cash"}), 2)
    return {
        "date": date,
        "cash_sales": cash_sales,
        "cash_receivables": cash_receivables,
        "cash_purchases": cash_purchases,
        "cash_payables": cash_payables,
        "cash_expenses": cash_expenses,
        "sales_count": len(sales),
        "purchases_count": len(purchases),
        "expenses_count": len(expenses),
        "expected_before_opening": round(cash_sales + cash_receivables - cash_purchases - cash_payables - cash_expenses, 2),
    }


@router.get("/cash-closures/summary")
async def cash_closure_summary(date: Optional[str] = None, user: dict = MANAGER):
    target = date or datetime.now(timezone.utc).date().isoformat()
    summary = await _summary(user["business_id"], target)
    previous = await db.cash_closures.find_one({"business_id": user["business_id"], "date": {"$lt": target}}, {"_id": 0}, sort=[("date", -1), ("closed_at", -1)])
    summary["previous_closing_cash"] = round(float(previous.get("counted_cash", 0) or 0), 2) if previous else 0.0
    summary["previous_closure_date"] = previous.get("date") if previous else None
    summary["last_closure"] = await db.cash_closures.find_one({"business_id": user["business_id"], "date": target}, {"_id": 0}, sort=[("closed_at", -1)])
    return summary


@router.get("/cash-closures")
async def list_cash_closures(limit: int = 50, user: dict = MANAGER):
    closures = await db.cash_closures.find({"business_id": user["business_id"]}, {"_id": 0}).sort([("date", -1), ("closed_at", -1)]).to_list(max(1, min(limit, 200)))
    return {"closures": closures}


@router.post("/cash-closures")
async def create_cash_closure(data: CashClosureIn, user: dict = MANAGER):
    bid = user["business_id"]
    summary = await _summary(bid, data.date)
    previous = await db.cash_closures.find_one({"business_id": bid, "date": {"$lt": data.date}}, {"_id": 0}, sort=[("date", -1), ("closed_at", -1)])
    opening_cash = round(float(data.opening_cash), 2)
    if data.use_previous_closing and previous:
        opening_cash = round(float(previous.get("counted_cash", 0) or 0), 2)
    expected_cash = round(opening_cash + summary["expected_before_opening"] + data.other_cash_in - data.other_cash_out, 2)
    denominations = [{"value": float(d.value), "quantity": int(d.quantity), "subtotal": round(float(d.value) * int(d.quantity), 2)} for d in data.denominations]
    counted_cash = round(sum(d["subtotal"] for d in denominations), 2) if denominations else round(float(data.counted_cash or 0), 2)
    difference = round(counted_cash - expected_cash, 2)
    closure = {
        "id": new_id(), "business_id": bid, "date": data.date, "opening_cash": opening_cash,
        "cash_sales": summary["cash_sales"], "cash_receivables": summary["cash_receivables"],
        "cash_purchases": summary["cash_purchases"], "cash_payables": summary["cash_payables"],
        "cash_expenses": summary["cash_expenses"], "other_cash_in": round(data.other_cash_in, 2),
        "other_cash_out": round(data.other_cash_out, 2), "expected_cash": expected_cash,
        "counted_cash": counted_cash, "difference": difference, "denominations": denominations,
        "observations": data.observations.strip() if data.observations else None,
        "user_email": user["email"], "closed_at": now_iso(),
    }
    await db.cash_closures.insert_one(closure)
    closure.pop("_id", None)
    return {"closure": closure}
