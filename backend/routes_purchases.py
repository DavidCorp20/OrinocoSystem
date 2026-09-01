from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from models import PurchaseIn
from database import db
from rates import get_effective_rate
from routes_products import _csv_response
from security import new_id, now_iso, require_roles
from pymongo import ReturnDocument

router = APIRouter(tags=["purchases"])
MANAGER = Depends(require_roles("propietario", "administrador"))

def _validate_payments(total, payment_method, parts):
    if not parts:
        return [{"method": payment_method.strip().lower(), "amount": round(total, 2)}]
    normalized = [{"method": p.method.strip().lower(), "amount": round(p.amount, 2)} for p in parts]
    if len(normalized) < 2: raise HTTPException(status_code=400, detail="Usa al menos dos métodos para un pago combinado")
    paid = round(sum(p["amount"] for p in normalized), 2)
    if abs(paid - round(total, 2)) > 0.01: raise HTTPException(status_code=400, detail=f"Los pagos suman {paid:.2f} y la compra total es {total:.2f}")
    return normalized

@router.get("/purchases")
async def list_purchases(user: dict = MANAGER):
    return {"purchases": await db.purchases.find({"business_id": user["business_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)}

@router.post("/purchases")
async def create_purchase(data: PurchaseIn, user: dict = MANAGER):
    bid = user["business_id"]
    product_ids = [i.product_id for i in data.items]
    docs = await db.products.find({"id": {"$in": product_ids}, "business_id": bid}).to_list(1000)
    catalog = {p["id"]: p for p in docs}
    items = []; base = 0.0
    for item in data.items:
        product = catalog.get(item.product_id)
        if not product: raise HTTPException(status_code=400, detail="Uno de los productos no existe en tu catálogo")
        line_total = round(item.unit_cost * item.quantity, 2); base += line_total
        items.append({"product_id": product["id"], "name": product["name"], "quantity": item.quantity, "unit_cost": item.unit_cost, "line_total": line_total})
    business = await db.businesses.find_one({"id": bid}, {"_id": 0}) or {}
    base = round(base, 2)
    iva_enabled = business.get("iva_enabled", False); iva_percent = float(business.get("iva_percent", 16) or 0) if iva_enabled else 0
    iva_amount = round(base * iva_percent / 100, 2)
    delivery_enabled = bool(business.get("delivery_enabled", False)); delivery_amount = round(float(business.get("delivery_amount", 0) or 0), 2) if delivery_enabled else 0
    total_before_igtf = round(base + iva_amount + delivery_amount, 2)
    foreign_methods = {"usd", "divisas", "zelle", "tarjeta_divisa"}
    foreign_base = sum(p.amount for p in data.payment_parts if p.method.strip().lower() in foreign_methods) if data.payment_parts else (total_before_igtf if data.payment_method.strip().lower() in foreign_methods else 0)
    igtf_enabled = bool(business.get("igtf_enabled", False)); igtf_percent = float(business.get("igtf_percent", 3) or 0) if igtf_enabled else 0
    igtf_amount = round(float(foreign_base) * igtf_percent / 100, 2) if igtf_enabled else 0
    total = round(total_before_igtf + igtf_amount, 2)
    payments = _validate_payments(total, data.payment_method, data.payment_parts)
    rate = (await get_effective_rate(business)).get("rate")
    counter = await db.counters.find_one_and_update({"_id": f"factura-compra:{bid}"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    purchase = {"id": new_id(), "business_id": bid, "supplier": data.supplier, "supplier_rif": data.supplier_rif, "items": items, "total": total, "invoice_number": f"C-{counter['seq']:06d}", "iva_enabled": iva_enabled, "iva_percent": iva_percent, "base": base, "iva_amount": iva_amount, "igtf_enabled": igtf_enabled, "igtf_percent": igtf_percent, "igtf_amount": igtf_amount, "delivery_enabled": delivery_enabled, "delivery_amount": delivery_amount, "exchange_rate": rate, "total_bs": round(total * rate, 2) if rate else None, "payment_method": "combinado" if len(payments)>1 else payments[0]["method"], "payment_parts": payments, "status": data.status, "user_email": user["email"], "created_at": now_iso()}
    await db.purchases.insert_one(purchase)
    for item in items:
        product = catalog[item["product_id"]]; old_stock = product["stock"]; old_cost = product.get("purchase_price", 0)
        denominator = old_stock + item["quantity"]
        new_cost = round((old_stock * old_cost + item["quantity"] * item["unit_cost"]) / denominator, 4) if denominator else item["unit_cost"]
        updates = {"purchase_price": new_cost, "updated_at": now_iso()}
        if data.supplier and not product.get("supplier"): updates["supplier"] = data.supplier
        updated = await db.products.find_one_and_update({"id": product["id"], "business_id": bid}, {"$inc": {"stock": item["quantity"]}, "$set": updates}, return_document=ReturnDocument.AFTER)
        await db.inventory_movements.insert_one({"id": new_id(), "business_id": bid, "product_id": product["id"], "product_name": product["name"], "type": "entrada", "reason": "compra", "quantity": item["quantity"], "stock_after": updated["stock"], "user_email": user["email"], "notes": f"Compra {purchase['id'][:8]}", "created_at": now_iso()})
    purchase.pop("_id", None)
    return {"purchase": purchase}

@router.get("/purchases/export/csv")
async def export_purchases(from_date: Optional[str] = None, to_date: Optional[str] = None, user: dict = MANAGER):
    query = {"business_id": user["business_id"]}
    if from_date: query["created_at"] = {"$gte": from_date}
    if to_date: query.setdefault("created_at", {})["$lte"] = to_date + "T23:59:59"
    purchases = await db.purchases.find(query, {"_id": 0}).sort("created_at", -1).to_list(50000)
    rows = [[p["created_at"][:10], p.get("invoice_number", ""), p.get("supplier") or "", p.get("supplier_rif") or "", "; ".join(f"{i['name']} x{i['quantity']:g}" for i in p["items"]), p.get("payment_method", ""), p.get("status", ""), p["total"], p.get("base", ""), p.get("iva_amount", ""), p.get("igtf_amount", ""), p.get("delivery_amount", ""), p.get("exchange_rate") or "", p.get("total_bs") or "", p.get("user_email", "")] for p in purchases]
    return _csv_response(rows, ["fecha", "comprobante", "proveedor", "rif_proveedor", "productos", "metodo_pago", "estado", "total", "base", "iva", "igtf", "delivery", "tasa_bcv", "total_bs", "usuario"], "compras")
