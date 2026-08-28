from fastapi import APIRouter, Depends, HTTPException

from database import db
from models import BusinessIn, SettingsIn, TeamUserIn
from security import get_current_user, hash_password, new_id, now_iso, public_user, require_roles

router = APIRouter(tags=["business"])

BUSINESS_FIELDS = {"_id": 0}


@router.get("/business")
async def get_business(user: dict = Depends(get_current_user)):
    if not user.get("business_id"):
        return {"business": None}
    business = await db.businesses.find_one({"id": user["business_id"]}, BUSINESS_FIELDS)
    return {"business": business}


@router.post("/business")
async def create_business(data: BusinessIn, user: dict = Depends(get_current_user)):
    if user.get("business_id"):
        raise HTTPException(status_code=400, detail="Ya tienes un negocio registrado")
    biz = {
        "id": new_id(),
        "owner_id": user["id"],
        "name": data.name.strip(),
        "type": data.type,
        "currency": data.currency,
        "active": True,
        "bcv_mode": "auto",
        "bcv_rate": None,
        "rif": None,
        "address": None,
        "phone": None,
        "created_at": now_iso(),
    }
    await db.businesses.insert_one(biz)
    await db.users.update_one({"id": user["id"]}, {"$set": {"business_id": biz["id"]}})

    for i, p in enumerate(data.initial_products):
        pid = new_id()
        product = {
            "id": pid,
            "business_id": biz["id"],
            "name": p.name.strip(),
            "sku": f"P-{i + 1:04d}",
            "barcode": None,
            "category": p.category or "General",
            "brand": None,
            "supplier": None,
            "purchase_price": p.purchase_price,
            "sale_price": p.sale_price,
            "stock": p.stock,
            "min_stock": 5,
            "max_stock": None,
            "unit": "unidad",
            "status": "activo",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        await db.products.insert_one(product)
        if p.stock > 0:
            await db.inventory_movements.insert_one({
                "id": new_id(),
                "business_id": biz["id"],
                "product_id": pid,
                "product_name": p.name.strip(),
                "type": "entrada",
                "reason": "carga_inicial",
                "quantity": p.stock,
                "stock_after": p.stock,
                "user_email": user["email"],
                "notes": None,
                "created_at": now_iso(),
            })

    biz.pop("_id", None)
    return {"business": biz}


@router.put("/business/settings")
async def update_settings(data: SettingsIn, user: dict = Depends(require_roles("propietario"))):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if "bcv_mode" in updates and updates["bcv_mode"] not in ("auto", "manual"):
        raise HTTPException(status_code=400, detail="Modo de tasa inválido")
    if "bcv_rate" in updates:
        updates["bcv_rate_date"] = now_iso()[:10]
    if updates.get("bcv_mode") == "auto":
        updates["bcv_rate"] = None
        updates["bcv_rate_date"] = None
    if not updates:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    await db.businesses.update_one({"id": user["business_id"]}, {"$set": updates})
    business = await db.businesses.find_one({"id": user["business_id"]}, BUSINESS_FIELDS)
    return {"business": business}


@router.get("/team")
async def list_team(user: dict = Depends(require_roles("propietario"))):
    members = await db.users.find(
        {"business_id": user["business_id"]}, {"_id": 0, "password_hash": 0}
    ).sort("created_at", 1).to_list(100)
    return {"team": [public_user(m) for m in members]}


@router.post("/team")
async def add_team_member(data: TeamUserIn, user: dict = Depends(require_roles("propietario"))):
    if data.role not in ("administrador", "vendedor"):
        raise HTTPException(status_code=400, detail="Rol inválido: usa administrador o vendedor")
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Ya existe una cuenta con este correo")
    member = {
        "id": new_id(),
        "email": email,
        "name": data.name.strip(),
        "password_hash": hash_password(data.password),
        "role": data.role,
        "platform_role": None,
        "business_id": user["business_id"],
        "created_at": now_iso(),
    }
    await db.users.insert_one(member)
    return {"member": public_user(member)}


@router.delete("/team/{member_id}")
async def remove_team_member(member_id: str, user: dict = Depends(require_roles("propietario"))):
    member = await db.users.find_one({"id": member_id, "business_id": user["business_id"]})
    if not member:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if member.get("role", "propietario") == "propietario":
        raise HTTPException(status_code=400, detail="No puedes eliminar al propietario del negocio")
    await db.users.delete_one({"id": member_id})
    return {"ok": True}
