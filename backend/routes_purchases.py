from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from models import PurchaseIn
from database import db
from rates import get_effective_rate
from routes_products import _csv_response, _xlsx_response
from security import new_id, now_iso, require_roles
from data_foundation import ensure_supplier
from ledger import record_payment_parts_as_cash
from pymongo import ReturnDocument

router = APIRouter(tags=["purchases"])
MANAGER = Depends(require_roles("propietario", "administrador"))
UNIT_FACTORS = {"unidad":1,"unidades":1,"und":1,"kg":1000,"kilo":1000,"kilogramo":1000,"g":1,"gramo":1,"lb":453.592,"libra":453.592,"l":1000,"litro":1000,"ml":1,"mililitro":1,"m":100,"metro":100,"cm":1,"centimetro":1}
def factor(unit): return UNIT_FACTORS.get((unit or "unidad").strip().lower(), 1)
def _validate_payments(total, payment_method, parts):
    if not parts: return [{"method": payment_method.strip().lower(), "amount": round(total, 2)}]
    normalized=[{"method":p.method.strip().lower(),"amount":round(p.amount,2)} for p in parts]
    if len(normalized)<2: raise HTTPException(400,"Usa al menos dos métodos para un pago combinado")
    paid=round(sum(p["amount"] for p in normalized),2)
    if abs(paid-round(total,2))>0.01: raise HTTPException(400,f"Los pagos suman {paid:.2f} y la compra total es {total:.2f}")
    return normalized

@router.get("/purchases")
async def list_purchases(user:dict=MANAGER): return {"purchases":await db.purchases.find({"business_id":user["business_id"]},{"_id":0}).sort("created_at",-1).to_list(500)}

@router.post("/purchases")
async def create_purchase(data:PurchaseIn,user:dict=MANAGER):
    bid=user["business_id"]; ids=[i.product_id for i in data.items]; docs=await db.products.find({"id":{"$in":ids},"business_id":bid}).to_list(1000); catalog={p["id"]:p for p in docs}; items=[]; base=0
    for item in data.items:
        product=catalog.get(item.product_id)
        if not product: raise HTTPException(400,"Uno de los productos no existe en tu catálogo")
        unit=(item.unit or product.get("unit") or "unidad").lower(); base_unit=(product.get("base_unit") or product.get("unit") or "unidad").lower()
        if unit not in UNIT_FACTORS or base_unit not in UNIT_FACTORS: raise HTTPException(400,"Unidad de medida no soportada")
        conversion=factor(unit)/factor(base_unit); base_qty=round(item.quantity*conversion,6); base_unit_cost=round(item.unit_cost/conversion,6) if conversion else item.unit_cost
        line_total=round(item.unit_cost*item.quantity,2); base+=line_total
        items.append({"product_id":product["id"],"name":product["name"],"quantity":item.quantity,"unit":unit,"base_quantity":base_qty,"base_unit":base_unit,"unit_cost":item.unit_cost,"base_unit_cost":base_unit_cost,"line_total":line_total})
    business=await db.businesses.find_one({"id":bid},{"_id":0}) or {}; base=round(base,2); iva_enabled=business.get("iva_enabled",False); iva_percent=float(business.get("iva_percent",16) or 0) if iva_enabled else 0; iva_amount=round(base*iva_percent/100,2); delivery_enabled=bool(business.get("delivery_enabled",False)); delivery_amount=round(float(business.get("delivery_amount",0) or 0),2) if delivery_enabled else 0; before=round(base+iva_amount+delivery_amount,2)
    foreign={"usd","divisas","zelle","tarjeta_divisa"}; foreign_base=sum(p.amount for p in data.payment_parts if p.method.strip().lower() in foreign) if data.payment_parts else (before if data.payment_method.strip().lower() in foreign else 0); igtf_enabled=bool(business.get("igtf_enabled",False)); igtf_percent=float(business.get("igtf_percent",3) or 0) if igtf_enabled else 0; igtf_amount=round(float(foreign_base)*igtf_percent/100,2) if igtf_enabled else 0; total=round(before+igtf_amount,2); payments=_validate_payments(total,data.payment_method,data.payment_parts); rate=(await get_effective_rate(business)).get("rate")
    created_at=now_iso(); purchase={"id":new_id(),"business_id":bid,"supplier":data.supplier,"supplier_rif":data.supplier_rif,"supplier_invoice_number":data.supplier_invoice_number,"items":items,"total":total,"iva_enabled":iva_enabled,"iva_percent":iva_percent,"base":base,"iva_amount":iva_amount,"igtf_enabled":igtf_enabled,"igtf_percent":igtf_percent,"igtf_amount":igtf_amount,"delivery_enabled":delivery_enabled,"delivery_amount":delivery_amount,"exchange_rate":rate,"total_bs":round(total*rate,2) if rate else None,"payment_method":"combinado" if len(payments)>1 else payments[0]["method"],"payment_parts":payments,"status":data.status,"notes":data.notes,"user_email":user["email"],"created_at":created_at}
    await db.purchases.insert_one(purchase)
    for item in items:
        product=catalog[item["product_id"]]; old_stock=float(product.get("stock",0) or 0); old_cost=float(product.get("purchase_price",0) or 0); qty=item["base_quantity"]; denominator=old_stock+qty; new_cost=round((old_stock*old_cost+qty*item["base_unit_cost"])/denominator,4) if denominator else item["base_unit_cost"]; updates={"purchase_price":new_cost,"unit":item["base_unit"],"base_unit":item["base_unit"],"updated_at":now_iso()}
        if data.supplier and not product.get("supplier"): updates["supplier"]=data.supplier
        updated=await db.products.find_one_and_update({"id":product["id"],"business_id":bid},{"$inc":{"stock":qty},"$set":updates},return_document=ReturnDocument.AFTER)
        await db.inventory_movements.insert_one({"id":new_id(),"business_id":bid,"product_id":product["id"],"product_name":product["name"],"type":"entrada","reason":"compra","quantity":qty,"unit":item["base_unit"],"source_quantity":item["quantity"],"source_unit":item["unit"],"stock_after":updated["stock"],"user_email":user["email"],"notes":f"Compra {purchase['id'][:8]}","created_at":now_iso()})
    supplier=await ensure_supplier(bid,data.supplier,data.supplier_rif) if data.supplier else None
    if supplier:
        await db.supplier_events.update_one({"business_id":bid,"source_id":purchase["id"],"event_type":"purchase"},{"$setOnInsert":{"id":new_id(),"business_id":bid,"supplier_id":supplier["id"],"event_type":"purchase","source_id":purchase["id"],"event_date":created_at,"amount":total,"status":data.status,"items_count":len(items),"created_at":now_iso()}},upsert=True)
    await record_payment_parts_as_cash(business_id=bid,source_type="purchase",source_id=purchase["id"],parts=payments,direction="out",user_email=user["email"],occurred_at=created_at,currency=business.get("currency"))
    purchase.pop("_id",None); return {"purchase":purchase}

@router.get("/purchases/export/csv")
async def export_purchases(from_date:Optional[str]=None,to_date:Optional[str]=None,user:dict=MANAGER):
    query={"business_id":user["business_id"]};
    if from_date: query["created_at"]={"$gte":from_date}
    if to_date: query.setdefault("created_at",{})["$lte"]=to_date+"T23:59:59"
    purchases=await db.purchases.find(query,{"_id":0}).sort("created_at",-1).to_list(50000); rows=[[p["created_at"][:10],p.get("supplier_invoice_number") or "",p.get("supplier") or "",p.get("supplier_rif") or "", "; ".join(f"{i['name']} x{i['quantity']:g} {i.get('unit','unidad')}" for i in p["items"]),p.get("payment_method",""),p.get("status",""),p["total"],p.get("base",""),p.get("iva_amount",""),p.get("igtf_amount",""),p.get("delivery_amount",""),p.get("exchange_rate") or "",p.get("total_bs") or "",p.get("user_email","")] for p in purchases]
    return _csv_response(rows,["fecha","factura_proveedor","proveedor","rif_proveedor","productos","metodo_pago","estado","total","base","iva","igtf","delivery","tasa_bcv","total_bs","usuario"],"compras")

@router.get("/purchases/export/xlsx")
async def export_purchases_xlsx(from_date:Optional[str]=None,to_date:Optional[str]=None,user:dict=MANAGER):
    query={"business_id":user["business_id"]}
    if from_date:query["created_at"]={"$gte":from_date}
    if to_date:query.setdefault("created_at",{})["$lte"]=to_date+"T23:59:59"
    purchases=await db.purchases.find(query,{"_id":0}).sort("created_at",-1).to_list(50000)
    rows=[[p["created_at"][:10],p.get("supplier_invoice_number") or "",p.get("supplier") or "",p.get("supplier_rif") or "","; ".join(f"{i['name']} x{i['quantity']:g} {i.get('unit','unidad')}" for i in p["items"]),p.get("payment_method",""),p.get("status",""),p.get("total",0),p.get("base",0),p.get("iva_amount",0),p.get("igtf_amount",0),p.get("delivery_amount",0),p.get("exchange_rate") or "",p.get("total_bs") or "",p.get("user_email","")] for p in purchases]
    headers=["Fecha","Factura proveedor","Proveedor","RIF proveedor","Productos","Método de pago","Estado","Total","Base","IVA","IGTF","Delivery","Tasa","Total Bs","Usuario"]
    return _xlsx_response(rows,headers,"compras")
