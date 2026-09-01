from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from database import db
from models import AdminPasswordResetIn, BusinessStatusIn, PlatformExpenseIn, PlatformPlanIn, UserApprovalIn
from security import hash_password, new_id, now_iso, require_superadmin

router = APIRouter(tags=["platform"])
PLATFORM_EXPENSE_CATEGORIES = {"infraestructura", "marketing", "soporte", "licencias", "otros"}


@router.get("/platform/overview")
async def platform_overview(user: dict = Depends(require_superadmin)):
    businesses = await db.businesses.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    now = datetime.now(timezone.utc); d30 = (now - timedelta(days=30)).isoformat(); month = now.isoformat()[:7]
    owners = {u["id"]: u for u in await db.users.find({}, {"_id": 0, "id": 1, "email": 1, "name": 1, "approved": 1}).to_list(10000)}
    async def count_by(coll):
        rows = await db[coll].aggregate([{"$group": {"_id": "$business_id", "n": {"$sum": 1}}}]).to_list(10000)
        return {r["_id"]: r["n"] for r in rows}
    prod_counts, sale_counts, user_counts = await count_by("products"), await count_by("sales"), await count_by("users")
    result = []
    for b in businesses:
        owner = owners.get(b["owner_id"], {})
        result.append({"id": b["id"], "name": b["name"], "type": b.get("type"), "currency": b.get("currency", "USD"), "active": b.get("active", True), "created_at": b.get("created_at"), "owner_email": owner.get("email", "—"), "owner_name": owner.get("name", "—"), "users_count": user_counts.get(b["id"], 0), "products_count": prod_counts.get(b["id"], 0), "sales_count": sale_counts.get(b["id"], 0)})
    expenses = await db.platform_expenses.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    gastos_mes = round(sum(e.get("amount", 0) for e in expenses if e.get("created_at", "")[:7] == month), 2)
    return {"stats": {"total": len(result), "activos": sum(b["active"] for b in result), "inactivos": sum(not b["active"] for b in result), "nuevos_30": sum((b.get("created_at") or "") >= d30 for b in result), "gastos_mes": gastos_mes}, "businesses": result}


@router.get("/platform/pending-users")
async def pending_users(user: dict = Depends(require_superadmin)):
    users = await db.users.find({"platform_role": {"$ne": "superadmin"}, "approved": {"$ne": True}}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(5000)
    return {"users": users}


@router.put("/platform/users/{user_id}/approval")
async def approve_user(user_id: str, data: UserApprovalIn, user: dict = Depends(require_superadmin)):
    result = await db.users.update_one({"id": user_id, "platform_role": {"$ne": "superadmin"}}, {"$set": {"approved": data.approved, "approved_at": now_iso() if data.approved else None, "approved_by": user["id"] if data.approved else None}})
    if result.matched_count == 0: raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"ok": True, "approved": data.approved}


@router.post("/platform/users/{user_id}/reset-password")
async def reset_password(user_id: str, data: AdminPasswordResetIn, user: dict = Depends(require_superadmin)):
    result = await db.users.update_one({"id": user_id, "platform_role": {"$ne": "superadmin"}}, {"$set": {"password_hash": hash_password(data.password)}})
    if result.matched_count == 0: raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"ok": True}


@router.get("/platform/plans")
async def list_plans(user: dict = Depends(require_superadmin)):
    plans = await db.platform_plans.find({}, {"_id": 0}).sort("monthly_price_usd", 1).to_list(100)
    return {"plans": plans}


@router.post("/platform/plans")
async def create_plan(data: PlatformPlanIn, user: dict = Depends(require_superadmin)):
    plan = {"id": new_id(), **data.model_dump(), "created_at": now_iso(), "updated_at": now_iso()}
    await db.platform_plans.insert_one(plan); plan.pop("_id", None)
    return {"plan": plan}


@router.put("/platform/plans/{plan_id}")
async def update_plan(plan_id: str, data: PlatformPlanIn, user: dict = Depends(require_superadmin)):
    result = await db.platform_plans.update_one({"id": plan_id}, {"$set": {**data.model_dump(), "updated_at": now_iso()}})
    if result.matched_count == 0: raise HTTPException(status_code=404, detail="Plan no encontrado")
    return {"ok": True}


@router.delete("/platform/plans/{plan_id}")
async def delete_plan(plan_id: str, user: dict = Depends(require_superadmin)):
    result = await db.platform_plans.delete_one({"id": plan_id})
    if result.deleted_count == 0: raise HTTPException(status_code=404, detail="Plan no encontrado")
    return {"ok": True}


@router.put("/platform/businesses/{business_id}/status")
async def set_business_status(business_id: str, data: BusinessStatusIn, user: dict = Depends(require_superadmin)):
    result = await db.businesses.update_one({"id": business_id}, {"$set": {"active": data.active}})
    if result.matched_count == 0: raise HTTPException(status_code=404, detail="Negocio no encontrado")
    return {"ok": True, "active": data.active}


@router.get("/platform/expenses")
async def list_platform_expenses(user: dict = Depends(require_superadmin)):
    return {"expenses": await db.platform_expenses.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)}


@router.post("/platform/expenses")
async def create_platform_expense(data: PlatformExpenseIn, user: dict = Depends(require_superadmin)):
    if data.category not in PLATFORM_EXPENSE_CATEGORIES: raise HTTPException(status_code=400, detail="Categoría inválida")
    expense = {"id": new_id(), "category": data.category, "description": data.description.strip(), "amount": round(data.amount, 2), "date": data.date or now_iso()[:10], "created_at": now_iso()}
    await db.platform_expenses.insert_one(expense); return {"expense": expense}


@router.delete("/platform/expenses/{expense_id}")
async def delete_platform_expense(expense_id: str, user: dict = Depends(require_superadmin)):
    result = await db.platform_expenses.delete_one({"id": expense_id})
    if result.deleted_count == 0: raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return {"ok": True}
