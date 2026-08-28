from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from database import db
from models import PurchaseIn
from rates import get_effective_rate
from routes_products import _csv_response
from security import new_id, now_iso, require_roles
from pymongo import ReturnDocument

router = APIRouter(tags=["purchases"])

MANAGER = Depends(require_roles("propietario", "administrador"))


@router.get("/purchases")
async def list_purchases(user: dict = MANAGER):
    purchases = await db.purchases.find({"business_id": user["business_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"purchases": purchases}


@router.post("/purchases")
async def create_purchase(data: PurchaseIn, user: dict = MANAGER):
    bid = user["business_id"]
    product_ids = [i.product_id for i in data.items]
    docs = await db.products.find({"id": {"$in": product_ids}, "business_id": bid}).to_list(1000)
    catalog = {p["id"]: p for p in docs}

    items = []
    total = 0.0
    for item in data.items:
        product = catalog.get(item.product_id)
        if not product:
            raise HTTPException(status_code=400, detail="Uno de los productos no existe en tu catálogo")
        line_total = round(item.unit_cost * item.quantity, 2)
        items.append({
            "product_id": product["id"],
            "name": product["name"],
            "quantity": item.quantity,
            "unit_cost": item.unit_cost,
            "line_total": line_total,
        })
        total += line_total

    business = await db.businesses.find_one({"id": bid}, {"_id": 0})
    rate = (await get_effective_rate(business or {})).get("rate")
    counter = await db.counters.find_one_and_update(
        {"_id": f"factura-compra:{bid}"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER
    )
    total_rounded = round(total, 2)
    subtotal = round(total_rounded / 1.16, 2)

    purchase = {
        "id": new_id(),
        "business_id": bid,
        "supplier": data.supplier,
        "supplier_rif": data.supplier_rif,
        "items": items,
        "total": total_rounded,
        "invoice_number": f"C-{counter['seq']:06d}",
        "iva_percent": 16,
        "subtotal": subtotal,
        "iva_amount": round(total_rounded - subtotal, 2),
        "exchange_rate": rate,
        "total_bs": round(total_rounded * rate, 2) if rate else None,
        "payment_method": data.payment_method,
        "status": data.status,
        "user_email": user["email"],
        "created_at": now_iso(),
    }
    await db.purchases.insert_one(purchase)

    for item in items:
        product = catalog[item["product_id"]]
        old_stock = product["stock"]
        old_cost = product.get("purchase_price", 0)
        new_cost = round((old_stock * old_cost + item["quantity"] * item["unit_cost"]) / (old_stock + item["quantity"]), 4)
        updates = {"purchase_price": new_cost, "updated_at": now_iso()}
        if data.supplier and not product.get("supplier"):
            updates["supplier"] = data.supplier
        updated = await db.products.find_one_and_update(
            {"id": product["id"], "business_id": bid},
            {"$inc": {"stock": item["quantity"]}, "$set": updates},
            return_document=ReturnDocument.AFTER,
        )
        new_stock = updated["stock"]
        await db.inventory_movements.insert_one({
            "id": new_id(),
            "business_id": bid,
            "product_id": product["id"],
            "product_name": product["name"],
            "type": "entrada",
            "reason": "compra",
            "quantity": item["quantity"],
            "stock_after": new_stock,
            "user_email": user["email"],
            "notes": f"Compra {purchase['id'][:8]}",
            "created_at": now_iso(),
        })

    purchase.pop("_id", None)
    return {"purchase": purchase}


@router.get("/purchases/export/csv")
async def export_purchases(from_date: Optional[str] = None, to_date: Optional[str] = None, user: dict = MANAGER):
    query = {"business_id": user["business_id"]}
    if from_date:
        query["created_at"] = {"$gte": from_date}
    if to_date:
        query.setdefault("created_at", {})["$lte"] = to_date + "T23:59:59"
    purchases = await db.purchases.find(query, {"_id": 0}).sort("created_at", -1).to_list(50000)
    rows = [
        [p["created_at"][:10], p.get("invoice_number", ""), p.get("supplier") or "", p.get("supplier_rif") or "",
         "; ".join(f"{i['name']} x{i['quantity']:g}" for i in p["items"]),
         p["payment_method"], p.get("status", ""), p["total"], p.get("subtotal", ""), p.get("iva_amount", ""),
         p.get("exchange_rate") or "", p.get("total_bs") or "", p.get("user_email", "")]
        for p in purchases
    ]
    return _csv_response(rows, ["fecha", "comprobante", "proveedor", "rif_proveedor", "productos", "metodo_pago", "estado", "total_usd", "base_imponible", "iva", "tasa_bcv", "total_bs", "usuario"], "compras")
