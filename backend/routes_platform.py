from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from database import db
from models import AdminPasswordResetIn, BusinessStatusIn, PlatformBillingIn, PlatformExpenseIn, PlatformPlanIn, PlatformSubscriptionIn, UserApprovalIn
from security import hash_password, new_id, now_iso, require_superadmin
from platia_score import calculate_platia_score

router = APIRouter(tags=["platform"])
PLATFORM_EXPENSE_CATEGORIES={"infraestructura","marketing","soporte","licencias","otros"};SUB_STATUSES={"activo","pendiente","vencido","cancelado"}
def _month(value): return (value or "")[:7]

@router.get("/platform/overview")
async def platform_overview(user:dict=Depends(require_superadmin)):
    businesses=await db.businesses.find({}, {"_id":0}).sort("created_at",-1).to_list(5000);now=datetime.now(timezone.utc);d30=(now-timedelta(days=30)).isoformat();month=now.strftime("%Y-%m")
    owners={u["id"]:u for u in await db.users.find({}, {"_id":0,"id":1,"email":1,"name":1,"approved":1}).to_list(10000)}
    async def count_by(coll):
        rows=await db[coll].aggregate([{"$group":{"_id":"$business_id","n":{"$sum":1}}}]).to_list(10000);return {r["_id"]:r["n"] for r in rows}
    prod_counts,sale_counts,user_counts=await count_by("products"),await count_by("sales"),await count_by("users")
    subs=await db.platform_subscriptions.find({}, {"_id":0}).to_list(10000);plans={p["id"]:p for p in await db.platform_plans.find({}, {"_id":0}).to_list(100)};paid=await db.platform_billing.find({}, {"_id":0}).sort("paid_at",-1).to_list(10000);expenses=await db.platform_expenses.find({}, {"_id":0}).to_list(5000)
    active=[s for s in subs if s.get("status")=="activo"];mrr=round(sum(float(s.get("monthly_price_usd",0) or 0) for s in active),2);month_revenue=round(sum(float(x.get("amount",0) or 0) for x in paid if _month(x.get("paid_at"))==month),2);month_cost=round(sum(float(x.get("amount",0) or 0) for x in expenses if _month(x.get("date") or x.get("created_at"))==month),2)
    result=[]
    for b in businesses:
        owner=owners.get(b.get("owner_id"),{});sub=next((s for s in subs if s.get("business_id")==b["id"] and s.get("status")!="cancelado"),None)
        result.append({"id":b["id"],"name":b["name"],"type":b.get("type"),"currency":b.get("currency","USD"),"active":b.get("active",True),"created_at":b.get("created_at"),"owner_email":owner.get("email","—"),"owner_name":owner.get("name","—"),"users_count":user_counts.get(b["id"],0),"products_count":prod_counts.get(b["id"],0),"sales_count":sale_counts.get(b["id"],0),"plan_id":(sub or {}).get("plan_id",b.get("plan_id")),"plan_name":(sub or {}).get("plan_name",b.get("plan_name")),"subscription_status":(sub or {}).get("status",b.get("subscription_status","sin_plan")),"subscription_created_at":(sub or {}).get("created_at"),"subscription_due_date":(sub or {}).get("due_date")})
    return {"stats":{"total":len(result),"activos":sum(bool(b["active"]) for b in result),"inactivos":sum(not bool(b["active"]) for b in result),"nuevos_30":sum((b.get("created_at") or "")>=d30 for b in result),"gastos_mes":month_cost,"suscripciones_activas":len(active),"mrr_usd":mrr,"proyeccion_mes_usd":mrr,"cobrado_mes_usd":month_revenue,"neto_mes_usd":round(month_revenue-month_cost,2)},"businesses":result,"plans":list(plans.values())}

@router.get("/platform/platia-score/{business_id}")
async def platform_platia_score(business_id:str, days:int=90, user:dict=Depends(require_superadmin)):
    if days < 30 or days > 3650: raise HTTPException(400,"days debe estar entre 30 y 3650")
    business=await db.businesses.find_one({"id":business_id},{"_id":0,"id":1,"name":1})
    if not business: raise HTTPException(404,"Negocio no encontrado")
    return {"business":business,"score":await calculate_platia_score(business_id,days)}

@router.get("/platform/pending-users")
async def pending_users(user:dict=Depends(require_superadmin)): return {"users":await db.users.find({"platform_role":{"$ne":"superadmin"},"approved":{"$ne":True}},{"_id":0,"password_hash":0}).sort("created_at",-1).to_list(5000)}
@router.put("/platform/users/{user_id}/approval")
async def approve_user(user_id:str,data:UserApprovalIn,user:dict=Depends(require_superadmin)):
    result=await db.users.update_one({"id":user_id,"platform_role":{"$ne":"superadmin"}},{"$set":{"approved":data.approved,"approved_at":now_iso() if data.approved else None,"approved_by":user["id"] if data.approved else None}})
    if result.matched_count==0: raise HTTPException(404,"Usuario no encontrado")
    return {"ok":True,"approved":data.approved}
@router.post("/platform/users/{user_id}/reset-password")
async def reset_password(user_id:str,data:AdminPasswordResetIn,user:dict=Depends(require_superadmin)):
    result=await db.users.update_one({"id":user_id,"platform_role":{"$ne":"superadmin"}},{"$set":{"password_hash":hash_password(data.password)}})
    if result.matched_count==0: raise HTTPException(404,"Usuario no encontrado")
    return {"ok":True}
@router.get("/platform/plans")
async def list_plans(user:dict=Depends(require_superadmin)): return {"plans":await db.platform_plans.find({}, {"_id":0}).sort("monthly_price_usd",1).to_list(100)}
@router.post("/platform/plans")
async def create_plan(data:PlatformPlanIn,user:dict=Depends(require_superadmin)):
    plan={"id":new_id(),**data.model_dump(),"created_at":now_iso(),"updated_at":now_iso()};await db.platform_plans.insert_one(plan);plan.pop("_id",None);return {"plan":plan}
@router.put("/platform/plans/{plan_id}")
async def update_plan(plan_id:str,data:PlatformPlanIn,user:dict=Depends(require_superadmin)):
    result=await db.platform_plans.update_one({"id":plan_id},{"$set":{**data.model_dump(),"updated_at":now_iso()}})
    if result.matched_count==0: raise HTTPException(404,"Plan no encontrado")
    return {"ok":True}
@router.delete("/platform/plans/{plan_id}")
async def delete_plan(plan_id:str,user:dict=Depends(require_superadmin)):
    if await db.platform_subscriptions.find_one({"plan_id":plan_id,"status":{"$in":["activo","pendiente"]}}): raise HTTPException(409,"No puedes eliminar un plan con suscripciones activas o pendientes")
    result=await db.platform_plans.delete_one({"id":plan_id});
    if result.deleted_count==0: raise HTTPException(404,"Plan no encontrado")
    return {"ok":True}
@router.post("/platform/businesses/{business_id}/subscription")
async def assign_subscription(business_id:str,data:PlatformSubscriptionIn,user:dict=Depends(require_superadmin)):
    if not await db.businesses.find_one({"id":business_id},{"_id":1}): raise HTTPException(404,"Negocio no encontrado")
    plan=await db.platform_plans.find_one({"id":data.plan_id,"active":True},{"_id":0});
    if not plan: raise HTTPException(404,"Plan activo no encontrado")
    price=round(data.monthly_price_usd or plan["monthly_price_usd"],2);now=now_iso();sub={"id":new_id(),"business_id":business_id,"plan_id":plan["id"],"plan_name":plan["name"],"status":data.status,"monthly_price_usd":price,"due_date":data.due_date,"created_at":now,"updated_at":now}
    await db.platform_subscriptions.update_many({"business_id":business_id,"status":{"$ne":"cancelado"}},{"$set":{"status":"cancelado","updated_at":now}});await db.platform_subscriptions.insert_one(sub);await db.businesses.update_one({"id":business_id},{"$set":{"plan_id":plan["id"],"plan_name":plan["name"],"subscription_status":data.status,"subscription_due_date":data.due_date,"monthly_price_usd":price}});sub.pop("_id",None);return {"subscription":sub}
@router.get("/platform/subscriptions")
async def list_subscriptions(status:str|None=None,business_id:str|None=None,user:dict=Depends(require_superadmin)):
    q={};
    if status:q["status"]=status
    if business_id:q["business_id"]=business_id
    return {"subscriptions":await db.platform_subscriptions.find(q,{"_id":0}).sort("due_date",1).to_list(5000)}
@router.patch("/platform/subscriptions/{subscription_id}/status")
async def subscription_status(subscription_id:str,status:str,user:dict=Depends(require_superadmin)):
    if status not in SUB_STATUSES:raise HTTPException(400,"Estado inválido")
    sub=await db.platform_subscriptions.find_one({"id":subscription_id},{"_id":0});
    if not sub:raise HTTPException(404,"Suscripción no encontrada")
    await db.platform_subscriptions.update_one({"id":subscription_id},{"$set":{"status":status,"updated_at":now_iso()}});await db.businesses.update_one({"id":sub["business_id"]},{"$set":{"subscription_status":status}});return {"subscription":{**sub,"status":status}}
@router.post("/platform/billing")
async def create_billing(data:PlatformBillingIn,user:dict=Depends(require_superadmin)):
    sub=await db.platform_subscriptions.find_one({"id":data.subscription_id},{"_id":0});
    if not sub:raise HTTPException(404,"Suscripción no encontrada")
    paid_at=data.paid_at or now_iso();bill={"id":new_id(),"subscription_id":sub["id"],"business_id":sub["business_id"],"amount":round(data.amount,2),"payment_method":data.payment_method,"paid_at":paid_at,"notes":data.notes,"created_at":now_iso(),"created_by":user["id"],"status":"aprobado"};await db.platform_billing.insert_one(bill)
    due=sub.get("due_date");next_due=None
    if due:
        try:next_due=(datetime.fromisoformat(due.replace("Z","+00:00"))+timedelta(days=30)).date().isoformat()
        except ValueError:pass
    if next_due:await db.platform_subscriptions.update_one({"id":sub["id"]},{"$set":{"status":"activo","due_date":next_due,"updated_at":now_iso()}});await db.businesses.update_one({"id":sub["business_id"]},{"$set":{"subscription_status":"activo","subscription_due_date":next_due}})
    bill.pop("_id",None);return {"billing":bill,"next_due_date":next_due}
@router.get("/platform/billing")
async def list_billing(business_id:str|None=None,status:str|None=None,user:dict=Depends(require_superadmin)):
    q={}
    if business_id:q["business_id"]=business_id
    if status:q["status"]=status
    return {"billing":await db.platform_billing.find(q,{"_id":0}).sort("paid_at",-1).to_list(5000)}
@router.get("/platform/billing-metrics")
async def billing_metrics(user:dict=Depends(require_superadmin)):
    now=datetime.now(timezone.utc);month=now.strftime("%Y-%m");subs=await db.platform_subscriptions.find({}, {"_id":0}).to_list(10000);paid=await db.platform_billing.find({}, {"_id":0}).to_list(10000);expenses=await db.platform_expenses.find({}, {"_id":0}).to_list(5000);active=[s for s in subs if s.get("status")=="activo"];mrr=round(sum(float(s.get("monthly_price_usd",0) or 0) for s in active),2);revenue=round(sum(float(x.get("amount",0) or 0) for x in paid if _month(x.get("paid_at"))==month),2);costs=round(sum(float(e.get("amount",0) or 0) for e in expenses if _month(e.get("date") or e.get("created_at"))==month),2);cutoff=(now+timedelta(days=7)).date().isoformat();due=sorted([s for s in subs if s.get("status") in {"activo","pendiente","vencido"} and s.get("due_date") and s.get("due_date")<=cutoff],key=lambda x:x.get("due_date") or "")[:100];return {"month":month,"active_customers":len(active),"mrr_usd":mrr,"projected_revenue_usd":mrr,"collected_revenue_usd":revenue,"platform_costs_usd":costs,"projected_net_usd":round(mrr-costs,2),"cash_net_usd":round(revenue-costs,2),"due_soon":due}
@router.put("/platform/businesses/{business_id}/status")
async def set_business_status(business_id:str,data:BusinessStatusIn,user:dict=Depends(require_superadmin)):
    result=await db.businesses.update_one({"id":business_id},{"$set":{"active":data.active}})
    if result.matched_count==0:raise HTTPException(404,"Negocio no encontrado")
    return {"ok":True,"active":data.active}
@router.get("/platform/expenses")
async def list_platform_expenses(user:dict=Depends(require_superadmin)):return {"expenses":await db.platform_expenses.find({}, {"_id":0}).sort("created_at",-1).to_list(500)}
@router.post("/platform/expenses")
async def create_platform_expense(data:PlatformExpenseIn,user:dict=Depends(require_superadmin)):
    if data.category not in PLATFORM_EXPENSE_CATEGORIES:raise HTTPException(400,"Categoría inválida")
    expense={"id":new_id(),"category":data.category,"description":data.description.strip(),"amount":round(data.amount,2),"date":data.date or now_iso()[:10],"created_at":now_iso()};await db.platform_expenses.insert_one(expense);return {"expense":expense}
@router.delete("/platform/expenses/{expense_id}")
async def delete_platform_expense(expense_id:str,user:dict=Depends(require_superadmin)):
    result=await db.platform_expenses.delete_one({"id":expense_id});
    if result.deleted_count==0:raise HTTPException(404,"Gasto no encontrado")
    return {"ok":True}
