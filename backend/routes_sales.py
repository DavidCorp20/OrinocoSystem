from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from models import SaleIn
from database import db
from rates import get_effective_rate
from routes_products import _csv_response
from security import new_id, now_iso, require_business, require_roles
from pymongo import ReturnDocument

router = APIRouter(tags=["sales"])

def _validate_payments(total, payment_method, parts):
    if not parts:
        return [{"method": payment_method.strip().lower(), "amount": round(total, 2)}]
    normalized = [{"method": p.method.strip().lower(), "amount": round(p.amount, 2)} for p in parts]
    if len(normalized) < 2:
        raise HTTPException(status_code=400, detail="Usa al menos dos métodos para un pago combinado")
    paid = round(sum(p["amount"] for p in normalized), 2)
    if abs(paid - round(total, 2)) > 0.01:
        raise HTTPException(status_code=400, detail=f"Los pagos suman {paid:.2f} y la venta total es {total:.2f}")
    return normalized

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
    items = []; total = cost_total = 0.0
    for item in data.items:
        product = catalog.get(item.product_id)
        if not product: raise HTTPException(status_code=400, detail="Uno de los productos no existe en tu catálogo")
        if product["stock"] < item.quantity: raise HTTPException(status_code=400, detail=f"Stock insuficiente para '{product['name']}'")
        price = item.unit_price if item.unit_price is not None else product["sale_price"]
        discount = min(item.discount, price * item.quantity)
        line_total = round(price * item.quantity - discount, 2); cost = float(product.get("purchase_price", 0) or 0)
        items.append({"product_id": product["id"], "name": product["name"], "quantity": item.quantity, "unit_price": price, "discount": discount, "cost": cost, "line_total": line_total})
        total += line_total; cost_total += cost * item.quantity
    business = await db.businesses.find_one({"id": bid}, {"_id": 0}) or {}
    iva_enabled = business.get("iva_enabled", True)
    iva_percent = float(business.get("iva_percent", 16) or 0) if iva_enabled else 0
    igtf_enabled = bool(business.get("igtf_enabled", False))
    igtf_percent = float(business.get("igtf_percent", 3) or 0) if igtf_enabled else 0
    delivery_enabled = bool(business.get("delivery_enabled", False))
    delivery_amount = float(business.get("delivery_amount", 0) or 0) if delivery_enabled else 0
    subtotal = round(total, 2)
    iva_amount = round(subtotal * iva_percent / 100, 2)
    total_before_igtf = round(subtotal + iva_amount + delivery_amount, 2)
    payments = _validate_payments(total_before_igtf, data.payment_method, data.payment_parts)
    foreign_amount = sum(p["amount"] for p in payments if p["method"] in {"usd", "divisas", "zelle", "tarjeta_divisa"})
    igtf_amount = round(foreign_amount * igtf_percent / 100, 2) if igtf_enabled else 0
    total_final = round(total_before_igtf + igtf_amount, 2)
    if abs(total_final - total_before_igtf) > 0.01 and data.payment_parts:
        payments = _validate_payments(total_final, data.payment_method, data.payment_parts)
    elif abs(total_final - total_before_igtf) > 0.01:
        payments = _validate_payments(total_final, data.payment_method, [])
    cost_total = round(cost_total, 2)
    rate = (await get_effective_rate(business)).get("rate")
    sale = {"id": new_id(), "business_id": bid, "items": items, "total": total_final, "cost_total": cost_total, "profit": round(subtotal-cost_total,2), "iva_enabled": iva_enabled, "iva_percent": iva_percent, "subtotal": subtotal, "iva_amount": iva_amount, "igtf_enabled": igtf_enabled, "igtf_percent": igtf_percent, "igtf_amount": igtf_amount, "delivery_enabled": delivery_enabled, "delivery_amount": delivery_amount, "exchange_rate":rate, "total_bs":round(total_final*rate,2) if rate else None, "payment_method": "combinado" if len(payments)>1 else payments[0]["method"], "payment_parts":payments, "customer_name":data.customer_name, "customer_rif":data.customer_rif, "user_email":user["email"], "created_at":now_iso()}
    low_stock=[]; applied=[]
    try:
        for item in items:
            product=catalog[item["product_id"]]
            updated=await db.products.find_one_and_update({"id":product["id"],"business_id":bid,"stock":{"$gte":item["quantity"]}},{"$inc":{"stock":-item["quantity"]},"$set":{"updated_at":now_iso()}},return_document=ReturnDocument.AFTER)
            if not updated: raise HTTPException(status_code=400,detail=f"Stock insuficiente para '{product['name']}'")
            applied.append(item)
            await db.inventory_movements.insert_one({"id":new_id(),"business_id":bid,"product_id":product["id"],"product_name":product["name"],"type":"salida","reason":"venta","quantity":item["quantity"],"stock_after":updated["stock"],"user_email":user["email"],"notes":f"Venta {sale['id'][:8]}","created_at":now_iso()})
            if updated["stock"] <= product.get("min_stock",0): low_stock.append({"nombre":product["name"],"stock":updated["stock"],"min_stock":product.get("min_stock",0)})
    except HTTPException:
        for item in applied:
            await db.products.update_one({"id":item["product_id"],"business_id":bid},{"$inc":{"stock":item["quantity"]}})
            await db.inventory_movements.delete_many({"business_id":bid,"product_id":item["product_id"],"notes":f"Venta {sale['id'][:8]}"})
        raise
    counter=await db.counters.find_one_and_update({"_id":f"factura-venta:{bid}"},{"$inc":{"seq":1}},upsert=True,return_document=ReturnDocument.AFTER)
    sale["invoice_number"]=f"F-{counter['seq']:06d}"
    await db.sales.insert_one(sale); sale.pop("_id",None)
    return {"sale":sale,"low_stock":low_stock}

@router.get("/sales/export/csv")
async def export_sales(from_date:Optional[str]=None,to_date:Optional[str]=None,user:dict=Depends(require_roles("propietario","administrador"))):
    query={"business_id":user["business_id"]}
    if from_date: query["created_at"]={"$gte":from_date}
    if to_date: query.setdefault("created_at",{})["$lte"]=to_date+"T23:59:59"
    sales=await db.sales.find(query,{"_id":0}).sort("created_at",-1).to_list(50000)
    rows=[[s["created_at"][:10],s.get("invoice_number",""),"; ".join(f"{i['name']} x{i['quantity']:g}" for i in s["items"]),len(s["items"]),s.get("payment_method",""),s.get("customer_name") or "",s.get("customer_rif") or "",s["total"],s.get("subtotal",""),s.get("iva_amount",""),s.get("igtf_amount",""),s.get("delivery_amount",""),s.get("tasa_bcv") or s.get("exchange_rate") or "",s.get("total_bs") or "",s["cost_total"],s["profit"],s.get("user_email","")] for s in sales]
    return _csv_response(rows,["fecha","factura","productos","num_items","metodo_pago","cliente","rif_cliente","total","base_imponible","iva","igtf","delivery","tasa_bcv","total_bs","costo","ganancia","usuario"],"ventas")
