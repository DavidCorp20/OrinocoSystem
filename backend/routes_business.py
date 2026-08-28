from fastapi import APIRouter, Depends, HTTPException

from database import db
from models import BusinessIn
from security import get_current_user, new_id, now_iso

router = APIRouter(tags=["business"])


@router.get("/business")
async def get_business(user: dict = Depends(get_current_user)):
    if not user.get("business_id"):
        return {"business": None}
    business = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0})
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
