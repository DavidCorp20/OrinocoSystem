from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from database import db
from models import BusinessStatusIn, PlatformExpenseIn
from security import new_id, now_iso, require_superadmin

router = APIRouter(tags=["platform"])

PLATFORM_EXPENSE_CATEGORIES = {"infraestructura", "marketing", "soporte", "licencias", "otros"}


@router.get("/platform/overview")
async def platform_overview(user: dict = Depends(require_superadmin)):
    businesses = await db.businesses.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    now = datetime.now(timezone.utc)
    d30 = (now - timedelta(days=30)).isoformat()

    owners = {u["id"]: u for u in await db.users.find({}, {"_id": 0, "id": 1, "email": 1, "name": 1}).to_list(10000)}

    async def count_by(coll):
        rows = await db[coll].aggregate([{"$group": {"_id": "$business_id", "n": {"$sum": 1}}}]).to_list(10000)
        return {r["_id"]: r["n"] for r in rows}

    prod_counts = await count_by("products")
    sale_counts = await count_by("sales")
    user_counts = await count_by("users")

    result = []
    for b in businesses:
        owner = owners.get(b["owner_id"], {})
        result.append({
            "id": b["id"],
            "name": b["name"],
            "type": b.get("type"),
            "currency": b.get("currency", "USD"),
            "active": b.get("active", True),
            "created_at": b.get("created_at"),
            "owner_email": owner.get("email", "—"),
            "owner_name": owner.get("name", "—"),
            "users_count": user_counts.get(b["id"], 0),
            "products_count": prod_counts.get(b["id"], 0),
            "sales_count": sale_counts.get(b["id"], 0),
        })

    activos = sum(1 for b in result if b["active"])
    nuevos_30 = sum(1 for b in result if (b.get("created_at") or "") >= d30)

    expenses = await db.platform_expenses.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    month_prefix = now.isoformat()[:7]
    gastos_mes = round(sum(e["amount"] for e in expenses if e["created_at"][:7] == month_prefix), 2)
    por_categoria = {}
    for e in expenses:
        if e["created_at"][:7] == month_prefix:
            por_categoria[e["category"]] = round(por_categoria.get(e["category"], 0) + e["amount"], 2)

    return {
        "stats": {
            "total": len(result),
            "activos": activos,
            "inactivos": len(result) - activos,
            "nuevos_30": nuevos_30,
            "gastos_mes": gastos_mes,
            "gastos_por_categoria": por_categoria,
        },
        "businesses": result,
    }


@router.put("/platform/businesses/{business_id}/status")
async def set_business_status(business_id: str, data: BusinessStatusIn, user: dict = Depends(require_superadmin)):
    result = await db.businesses.update_one({"id": business_id}, {"$set": {"active": data.active}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")
    return {"ok": True, "active": data.active}


@router.get("/platform/expenses")
async def list_platform_expenses(user: dict = Depends(require_superadmin)):
    expenses = await db.platform_expenses.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"expenses": expenses}


@router.post("/platform/expenses")
async def create_platform_expense(data: PlatformExpenseIn, user: dict = Depends(require_superadmin)):
    if data.category not in PLATFORM_EXPENSE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Categoría inválida")
    expense = {
        "id": new_id(),
        "category": data.category,
        "description": data.description.strip(),
        "amount": round(data.amount, 2),
        "date": data.date or now_iso()[:10],
        "created_at": now_iso(),
    }
    await db.platform_expenses.insert_one(expense)
    expense.pop("_id", None)
    return {"expense": expense}


@router.delete("/platform/expenses/{expense_id}")
async def delete_platform_expense(expense_id: str, user: dict = Depends(require_superadmin)):
    result = await db.platform_expenses.delete_one({"id": expense_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return {"ok": True}
