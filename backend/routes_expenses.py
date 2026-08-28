from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from database import db
from models import ExpenseIn
from routes_products import _csv_response
from security import new_id, now_iso, require_business

router = APIRouter(tags=["expenses"])

CATEGORIES = {"alquiler", "servicios", "personal", "transporte", "marketing", "otros"}


@router.get("/expenses")
async def list_expenses(user: dict = Depends(require_business)):
    expenses = await db.expenses.find({"business_id": user["business_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"expenses": expenses}


@router.post("/expenses")
async def create_expense(data: ExpenseIn, user: dict = Depends(require_business)):
    if data.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Categoría inválida")
    expense = {
        "id": new_id(),
        "business_id": user["business_id"],
        "category": data.category,
        "description": data.description.strip(),
        "amount": round(data.amount, 2),
        "date": data.date or now_iso()[:10],
        "user_email": user["email"],
        "created_at": now_iso(),
    }
    await db.expenses.insert_one(expense)
    expense.pop("_id", None)
    return {"expense": expense}


@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str, user: dict = Depends(require_business)):
    result = await db.expenses.delete_one({"id": expense_id, "business_id": user["business_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return {"ok": True}


@router.get("/expenses/export/csv")
async def export_expenses(from_date: Optional[str] = None, to_date: Optional[str] = None, user: dict = Depends(require_business)):
    query = {"business_id": user["business_id"]}
    if from_date:
        query["created_at"] = {"$gte": from_date}
    if to_date:
        query.setdefault("created_at", {})["$lte"] = to_date + "T23:59:59"
    expenses = await db.expenses.find(query, {"_id": 0}).sort("created_at", -1).to_list(50000)
    rows = [[e["created_at"][:10], e["category"], e["description"], e["amount"], e.get("user_email", "")] for e in expenses]
    return _csv_response(rows, ["fecha", "categoria", "descripcion", "monto", "usuario"], "gastos")


@router.get("/finances/summary")
async def finances_summary(user: dict = Depends(require_business)):
    bid = user["business_id"]
    now = datetime.now(timezone.utc)
    d30 = now - timedelta(days=30)

    sales = await db.sales.find({"business_id": bid}, {"_id": 0}).to_list(50000)
    expenses = await db.expenses.find({"business_id": bid}, {"_id": 0}).to_list(20000)
    purchases = await db.purchases.find({"business_id": bid}, {"_id": 0}).to_list(20000)

    def dt(o):
        return datetime.fromisoformat(o["created_at"])

    sales_30 = [s for s in sales if dt(s) >= d30]
    exp_30 = [e for e in expenses if dt(e) >= d30]
    pur_30 = [p for p in purchases if dt(p) >= d30]

    ingresos = round(sum(s["total"] for s in sales_30), 2)
    utilidad_bruta = round(sum(s["profit"] for s in sales_30), 2)
    gastos_op = round(sum(e["amount"] for e in exp_30), 2)
    compras = round(sum(p["total"] for p in pur_30), 2)
    ganancia = round(utilidad_bruta - gastos_op, 2)
    margen = round(utilidad_bruta / ingresos * 100, 1) if ingresos else 0

    by_category = {}
    for e in exp_30:
        by_category[e["category"]] = round(by_category.get(e["category"], 0) + e["amount"], 2)

    weekly = []
    for i in range(7, -1, -1):
        start = (now - timedelta(days=i * 7 + 6)).date()
        end = (now - timedelta(days=i * 7)).date()
        inc = sum(s["total"] for s in sales if start <= dt(s).date() <= end)
        exp = sum(e["amount"] for e in expenses if start <= dt(e).date() <= end)
        weekly.append({"semana": end.strftime("%d/%m"), "ingresos": round(inc, 2), "gastos": round(exp, 2)})

    return {
        "ingresos_30": ingresos,
        "utilidad_bruta_30": utilidad_bruta,
        "gastos_operativos_30": gastos_op,
        "compras_30": compras,
        "ganancia_estimada_30": ganancia,
        "margen": margen,
        "gastos_por_categoria": by_category,
        "flujo_semanal": weekly,
    }
