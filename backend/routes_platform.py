from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from database import db
from models import AdminPasswordResetIn, BusinessStatusIn, PlatformExpenseIn, PlatformPlanIn, PlatformSubscriptionIn, UserApprovalIn
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
        result.append({"id": b["id"], "name": b["name"], "type": b.get("type"), "currency": b.get("currency", "USD"), "active": b.get("active", True), "created_at": b.get("created_at"), "owner_email": owner.get("email", "—"), "owner_name": owner.get("name", "—"), "users_count": user_counts.get(b["id"], 0), "products_count": prod_counts.get(b["id"], 0), "sales_count": sale_counts.get(b["id"], 0), "plan_id": b.get("plan_id"), "subscription_status": b.get("subscription_status", "sin_plan"), "subscription_due_date": b.get("subscription_due_date")})
    expenses = await db.platform_expenses.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    gastos_mes = round(sum(e.get("amount", 0) for e in expenses if e.get("created_at", "")[:7] == month), 2)
    subscriptions = await db.platform_subscriptions.find({"status": "activo"}, {"_id": 0}).to_list(5000)
    mrr = round(sum(float(s.get("monthly_price_usd", 0) or 0) for s in subscriptions), 2)
    return {"stats": {"total": len(result), "activos": sum(b["active"] for b in result), "inactivos": sum(not b["active"] for b in result), "nuevos_30": sum((b.get("created_at") or "") >= d30 for b in result), "gastos_mes": gastos_mes, "suscripciones_activas": len(subscriptions), "mrr_usd": mrr, "proyeccion_mes_usd": mrr}, "businesses": result}

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

@router.post("/platform/businesses/{business_id}/subscription")
async def assign_subscription(business_id: str, data: PlatformSubscriptionIn, user: dict = Depends(require_superadmin)):
    plan = await db.platform_plans.find_one({"id": data.plan_id, "active": True}, {"_id": 0})
    if not plan: raise HTTPException(status_code=404, detail="Plan activo no encontrado")
    price = round(data.monthly_price_usd or plan["monthly_price_usd"], 2)
    sub = {"id": new_id(), "business_id": business_id, "plan_id": plan["id"], "plan_name": plan["name"], "status": data.status, "monthly_price_usd": price, "due_date": data.due_date, "created_at": now_iso(), "updated_at": now_iso()}
    await db.platform_subscriptions.update_many({"business_id": business_id, "status": {"$ne": "cancelado"}}, {"$set": {"status": "cancelado", "updated_at": now_iso()}})
    await db.platform_subscriptions.insert_one(sub)
    await db.businesses.update_one({"id": business_id}, {"$set": {"plan_id": plan["id"], "plan_name": plan["name"], "subscription_status": data.status, "subscription_due_date": data.due_date, "monthly_price_usd": price}})
    sub.pop("_id", None)
    return {"subscription": sub}

@router.get("/platform/subscriptions")
async def list_subscriptions(status: str | None = None, user: dict = Depends(require_superadmin)):
    q = {} if not status else {"status": status}
    return {"subscriptions": await db.platform_subscriptions.find(q, {"_id": 0}).sort("due_date", 1).to_list(5000)}

@router.patch("/platform/subscriptions/{subscription_id}/status")
async def subscription_status(subscription_id: str, status: str, user: dict = Depends(require_superadmin)):
    if status not in {"activo", "pendiente", "vencido", "cancelado"}: raise HTTPException(status_code=400, detail="Estado inválido")
    sub = await db.platform_subscriptions.find_one_and_update({"id": subscription_id}, {"$set": {"status": status, "updated_at": now_iso()}}, projection={"_id": 0}, return_document=True)
    if not sub: raise HTTPException(status_code=404, detail="Suscripción no encontrada")
    await db.businesses.update_one({"id": sub["business_id"]}, {"$set": {"subscription_status": status}})
    return {"subscription": sub}

@router.get("/platform/billing-metrics")
async def billing_metrics(user: dict = Depends(require_superadmin)):
    now = datetime.now(timezone.utc); month = now.strftime("%Y-%m")
    subs = await db.platform_subscriptions.find({}, {"_id": 0}).to_list(10000)
    expenses = await db.platform_expenses.find({"created_at": {"$regex": f"^{month}"}}, {"_id": 0}).to_list(5000)
    active = [s for s in subs if s.get("status") == "activo"]
    mrr = round(sum(float(s.get("monthly_price_usd", 0) or 0) for s in active), 2)
    costs = round(sum(float(e.get("amount", 0) or 0) for e in expenses), 2)
    return {"month": month, "active_customers": len(active), "mrr_usd": mrr, "projected_revenue_usd": mrr, "platform_costs_usd": costs, "projected_net_usd": round(mrr - costs, 2), "due_soon": sorted([s for s in subs if s.get("status") in {"pendiente", "vencido"}], key=lambda x: x.get("due_date") or "")[:100]}

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
