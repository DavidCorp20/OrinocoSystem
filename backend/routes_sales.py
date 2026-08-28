from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from database import db
from models import SaleIn
from routes_products import _csv_response
from security import new_id, now_iso, require_business
from pymongo import ReturnDocument

router = APIRouter(tags=["sales"])


@router.get("/sales")
async def list_sales(user: dict = Depends(require_business)):
    sales = await db.sales.find({"business_id": user["business_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"sales": sales}


@router.post("/sales")
async def create_sale(data: SaleIn, user: dict = Depends(require_business)):
    bid = user["business_id"]
    product_ids = [i.product_id for i in data.items]
    docs = await db.products.find({"id": {"$in": product_ids}, "business_id": bid}).to_list(1000)
    catalog = {p["id"]: p for p in docs}

    items = []
    total = cost_total = 0.0
    for item in data.items:
        product = catalog.get(item.product_id)
        if not product:
            raise HTTPException(status_code=400, detail="Uno de los productos no existe en tu catálogo")
        if product["stock"] < item.quantity:
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para '{product['name']}': disponible {product['stock']:g}")
        price = item.unit_price if item.unit_price is not None else product["sale_price"]
        discount = min(item.discount, price * item.quantity)
        line_total = round(price * item.quantity - discount, 2)
        cost = product.get("purchase_price", 0)
        items.append({
            "product_id": product["id"],
            "name": product["name"],
            "quantity": item.quantity,
            "unit_price": price,
            "discount": discount,
            "cost": cost,
            "line_total": line_total,
        })
        total += line_total
        cost_total += cost * item.quantity

    total = round(total, 2)
    cost_total = round(cost_total, 2)
    sale = {
        "id": new_id(),
        "business_id": bid,
        "items": items,
        "total": total,
        "cost_total": cost_total,
        "profit": round(total - cost_total, 2),
        "payment_method": data.payment_method,
        "customer": data.customer,
        "user_email": user["email"],
        "created_at": now_iso(),
    }
    await db.sales.insert_one(sale)

    low_stock = []
    for item in items:
        product = catalog[item["product_id"]]
        updated = await db.products.find_one_and_update(
            {"id": product["id"], "business_id": bid, "stock": {"$gte": item["quantity"]}},
            {"$inc": {"stock": -item["quantity"]}, "$set": {"updated_at": now_iso()}},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para '{product['name']}': disponible {product['stock']:g}")
        new_stock = updated["stock"]
        await db.inventory_movements.insert_one({
            "id": new_id(),
            "business_id": bid,
            "product_id": product["id"],
            "product_name": product["name"],
            "type": "salida",
            "reason": "venta",
            "quantity": item["quantity"],
            "stock_after": new_stock,
            "user_email": user["email"],
            "notes": f"Venta {sale['id'][:8]}",
            "created_at": now_iso(),
        })
        if new_stock <= product.get("min_stock", 0):
            low_stock.append({"nombre": product["name"], "stock": new_stock, "min_stock": product.get("min_stock", 0)})

    sale.pop("_id", None)
    return {"sale": sale, "low_stock": low_stock}


@router.get("/sales/export/csv")
async def export_sales(from_date: Optional[str] = None, to_date: Optional[str] = None, user: dict = Depends(require_business)):
    query = {"business_id": user["business_id"]}
    if from_date:
        query["created_at"] = {"$gte": from_date}
    if to_date:
        query.setdefault("created_at", {})["$lte"] = to_date + "T23:59:59"
    sales = await db.sales.find(query, {"_id": 0}).sort("created_at", -1).to_list(50000)
    rows = [
        [s["created_at"][:10], "; ".join(f"{i['name']} x{i['quantity']:g}" for i in s["items"]),
         len(s["items"]), s["payment_method"], s.get("customer") or "", s["total"], s["cost_total"], s["profit"], s.get("user_email", "")]
        for s in sales
    ]
    return _csv_response(rows, ["fecha", "productos", "num_items", "metodo_pago", "cliente", "total", "costo", "ganancia", "usuario"], "ventas")
