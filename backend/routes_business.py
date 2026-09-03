from fastapi import APIRouter, Depends, HTTPException

from database import db
from models import BusinessIn, SettingsIn, TeamUserIn
from security import get_current_user, hash_password, new_id, now_iso, public_user, require_roles
from plan_access import require_user_capacity

router = APIRouter(tags=["business"])
BUSINESS_FIELDS = {"_id": 0}

async def _resolve_business_id(user: dict):
    business_id = user.get("business_id")
    if business_id:
        return business_id
    if user.get("role", "propietario") == "propietario":
        business = await db.businesses.find_one({"owner_id": user["id"]}, {"_id": 0, "id": 1})
        if business and business.get("id"):
            business_id = business["id"]
            await db.users.update_one({"id": user["id"]}, {"$set": {"business_id": business_id}})
    return business_id

@router.get("/business")
async def get_business(user: dict = Depends(get_current_user)):
    business_id = await _resolve_business_id(user)
    if not business_id: return {"business": None}
    business = await db.businesses.find_one({"id": business_id}, BUSINESS_FIELDS)
    return {"business": business}

@router.post("/business")
async def create_business(data: BusinessIn, user: dict = Depends(get_current_user)):
    business_id = await _resolve_business_id(user)
    if business_id: raise HTTPException(400,"Ya tienes un negocio registrado")
    biz={"id":new_id(),"owner_id":user["id"],"name":data.name.strip(),"type":data.type,"currency":data.currency,"display_currency":"dual","price_reference":"usd","active":True,"bcv_mode":"auto","bcv_rate":None,"rif":None,"address":None,"phone":None,"created_at":now_iso()}
    await db.businesses.insert_one(biz);await db.users.update_one({"id":user["id"]},{"$set":{"business_id":biz["id"]}})
    for i,p in enumerate(data.initial_products):
        pid=new_id();product={"id":pid,"business_id":biz["id"],"name":p.name.strip(),"sku":f"P-{i+1:04d}","barcode":None,"category":p.category or "General","brand":None,"supplier":None,"purchase_price":p.purchase_price,"sale_price":p.sale_price,"stock":p.stock,"min_stock":5,"max_stock":None,"unit":"unidad","status":"activo","created_at":now_iso(),"updated_at":now_iso()}
        await db.products.insert_one(product)
        if p.stock>0: await db.inventory_movements.insert_one({"id":new_id(),"business_id":biz["id"],"product_id":pid,"product_name":p.name.strip(),"type":"entrada","reason":"carga_inicial","quantity":p.stock,"stock_after":p.stock,"user_email":user["email"],"notes":None,"created_at":now_iso()})
    biz.pop("_id",None);return {"business":biz}

@router.put("/business/settings")
async def update_settings(data: SettingsIn, user: dict = Depends(require_roles("propietario"))):
    updates={k:v for k,v in data.model_dump().items() if v is not None}
    if "bcv_mode" in updates and updates["bcv_mode"] not in ("auto","manual"): raise HTTPException(400,"Modo de tasa inválido")
    if "price_reference" in updates and updates["price_reference"] not in ("usd","eur"): raise HTTPException(400,"Moneda de comparación inválida")
    if "bcv_rate" in updates: updates["bcv_rate_date"]=now_iso()[:10]
    if updates.get("bcv_mode")=="auto": updates["bcv_rate"]=None;updates["bcv_rate_date"]=None
    if not updates: raise HTTPException(400,"Nada que actualizar")
    await db.businesses.update_one({"id":user["business_id"]},{"$set":updates});return {"business":await db.businesses.find_one({"id":user["business_id"]},BUSINESS_FIELDS)}

@router.get("/business/currency")
async def get_currency_config(user: dict = Depends(get_current_user)):
    b=await db.businesses.find_one({"id":user.get("business_id")},BUSINESS_FIELDS) or {}
    return {"display_currency":b.get("display_currency","dual"),"price_reference":b.get("price_reference","usd"),"currency":"USD","dual_currency":True}

@router.put("/business/currency")
async def update_currency_config(payload: dict, user: dict = Depends(require_roles("propietario"))):
    display=payload.get("display_currency","dual");reference=payload.get("price_reference","usd")
    if display not in ("dual","usd","bs"): raise HTTPException(400,"Moneda de visualización inválida")
    if reference not in ("usd","eur"): raise HTTPException(400,"Moneda de comparación inválida")
    await db.businesses.update_one({"id":user["business_id"]},{"$set":{"display_currency":display,"price_reference":reference}})
    return {"display_currency":display,"price_reference":reference,"dual_currency":True}

@router.get("/team")
async def list_team(user: dict = Depends(require_roles("propietario"))):
    members=await db.users.find({"business_id":user["business_id"]},{"_id":0,"password_hash":0}).sort("created_at",1).to_list(100);return {"team":[public_user(m) for m in members]}

@router.post("/team")
async def add_team_member(data: TeamUserIn,user:dict=Depends(require_roles("propietario"))):
    if data.role not in ("administrador","vendedor"): raise HTTPException(400,"Rol inválido: usa administrador o vendedor")
    await require_user_capacity(user["business_id"])
    email=data.email.lower()
    if await db.users.find_one({"email":email}): raise HTTPException(400,"Ya existe una cuenta con este correo")
    member={"id":new_id(),"email":email,"name":data.name.strip(),"password_hash":hash_password(data.password),"role":data.role,"platform_role":None,"business_id":user["business_id"],"created_at":now_iso()};await db.users.insert_one(member);return {"member":public_user(member)}

@router.delete("/team/{member_id}")
async def remove_team_member(member_id:str,user:dict=Depends(require_roles("propietario"))):
    member=await db.users.find_one({"id":member_id,"business_id":user["business_id"]})
    if not member: raise HTTPException(404,"Usuario no encontrado")
    if member.get("role","propietario")=="propietario": raise HTTPException(400,"No puedes eliminar al propietario del negocio")
    await db.users.delete_one({"id":member_id});return {"ok":True}
