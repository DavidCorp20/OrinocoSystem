from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from database import db
from models import ObligationIn, ObligationPaymentIn
from security import new_id, now_iso, require_business, require_roles
from ledger import record_cash_movement, is_cash_method
from data_foundation import ensure_customer, ensure_supplier

router=APIRouter(tags=["obligations"])
MANAGER=Depends(require_roles("propietario","administrador"))

async def _resolve_party(data, business_id):
    customer_id = data.customer_id if data.kind == "por_cobrar" else None
    supplier_id = data.supplier_id if data.kind == "por_pagar" else None
    if data.kind == "por_cobrar":
        if customer_id:
            party = await db.customers.find_one({"id":customer_id,"business_id":business_id},{"_id":0})
            if not party: raise HTTPException(400,"Cliente no encontrado en este negocio")
        else:
            party = await ensure_customer(business_id, data.contact)
            customer_id = party["id"] if party else None
    else:
        if supplier_id:
            party = await db.suppliers.find_one({"id":supplier_id,"business_id":business_id},{"_id":0})
            if not party: raise HTTPException(400,"Proveedor no encontrado en este negocio")
        else:
            party = await ensure_supplier(business_id, data.contact)
            supplier_id = party["id"] if party else None
    return customer_id, supplier_id

@router.get("/obligations")
async def list_obligations(kind:Optional[str]=None,status:Optional[str]=None,user:dict=Depends(require_business)):
    q={"business_id":user["business_id"]}
    if kind:q["kind"]=kind
    if status:q["status"]=status
    docs=await db.obligations.find(q,{"_id":0}).sort("due_date",1).to_list(5000)
    now=datetime.now(timezone.utc).date().isoformat()
    for d in docs:
        if d.get("status") in {"pendiente","parcial"} and d.get("due_date") and d["due_date"]<now:d["status"]="vencida"
    return {"obligations":docs}

@router.post("/obligations")
async def create_obligation(data:ObligationIn,user:dict=MANAGER):
    if data.kind not in {"por_cobrar","por_pagar"}: raise HTTPException(400,"Tipo de cuenta inválido")
    bid=user["business_id"]
    customer_id,supplier_id=await _resolve_party(data,bid)
    amount=round(data.amount,2)
    doc={"id":new_id(),"business_id":bid,"kind":data.kind,"contact":data.contact,"description":data.description,"amount":amount,"original_amount":amount,"paid_amount":0,"remaining_amount":amount,"outstanding_amount":amount,"due_date":data.due_date,"notes":data.notes,"customer_id":customer_id,"supplier_id":supplier_id,"currency":data.currency.upper(),"status":"pendiente","created_at":now_iso(),"updated_at":now_iso()}
    await db.obligations.insert_one(doc);doc.pop("_id",None);return {"obligation":doc}

@router.post("/obligations/{obligation_id}/payments")
async def pay_obligation(obligation_id:str,data:ObligationPaymentIn,user:dict=MANAGER):
    bid=user["business_id"]
    doc=await db.obligations.find_one({"id":obligation_id,"business_id":bid},{"_id":0})
    if not doc:raise HTTPException(404,"Cuenta no encontrada")
    remaining=round(float(doc.get("remaining_amount",doc.get("outstanding_amount",doc.get("amount",0)-doc.get("paid_amount",0)))),2)
    amount=round(float(data.amount),2)
    if amount<=0: raise HTTPException(400,"El monto del pago debe ser mayor a cero")
    if amount>remaining+0.01:raise HTTPException(400,"El pago supera el saldo pendiente")
    paid_at=now_iso(); method=data.payment_method.strip().lower(); payment_id=new_id()
    new_remaining=max(0,round(remaining-amount,2)); new_paid=round(float(doc.get("paid_amount",0))+amount,2); status="pagada" if new_remaining<=0.009 else "parcial"
    updated=await db.obligations.update_one({"id":obligation_id,"business_id":bid,"remaining_amount":{"$gte":amount-0.01}},{"$set":{"paid_amount":new_paid,"remaining_amount":new_remaining,"outstanding_amount":new_remaining,"status":status,"updated_at":now_iso()}})
    if not updated.modified_count: raise HTTPException(409,"La cuenta cambió antes de registrar el pago; inténtalo nuevamente")
    payment={"id":payment_id,"obligation_id":obligation_id,"business_id":bid,"amount":amount,"payment_method":method,"notes":data.notes,"paid_at":paid_at,"user_email":user["email"]}
    try:
        await db.obligation_payments.insert_one(payment.copy())
    except Exception:
        await db.obligations.update_one({"id":obligation_id,"business_id":bid},{"$inc":{"paid_amount":-amount,"remaining_amount":amount,"outstanding_amount":amount},"$set":{"status":"parcial" if new_paid>0 else "pendiente","updated_at":now_iso()}})
        raise
    if is_cash_method(method):
        direction="in" if doc.get("kind")=="por_cobrar" else "out"
        cm=await record_cash_movement(business_id=bid,direction=direction,movement_type="receivable_payment" if direction=="in" else "payable_payment",source_type="obligation_payment",source_id=payment_id,amount=amount,payment_method=method,user_email=user["email"],occurred_at=paid_at,notes=f"Pago cuenta {obligation_id[:8]}")
        payment["cash_movement_id"]=cm["id"]
        await db.obligation_payments.update_one({"id":payment_id,"business_id":bid},{"$set":{"cash_movement_id":cm["id"]}})
    payment.pop("_id",None); return {"payment":payment,"remaining_amount":new_remaining,"status":status}

@router.get("/obligations/{obligation_id}/payments")
async def list_obligation_payments(obligation_id:str,user:dict=Depends(require_business)):
    if not await db.obligations.find_one({"id":obligation_id,"business_id":user["business_id"]},{"_id":1}):raise HTTPException(404,"Cuenta no encontrada")
    return {"payments":await db.obligation_payments.find({"obligation_id":obligation_id,"business_id":user["business_id"]},{"_id":0}).sort("paid_at",-1).to_list(1000)}

@router.get("/cash-movements")
async def list_cash_movements(direction:Optional[str]=None,movement_type:Optional[str]=None,from_date:Optional[str]=None,to_date:Optional[str]=None,user:dict=Depends(require_business)):
    q={"business_id":user["business_id"]}
    if direction in {"in","out"}:q["direction"]=direction
    if movement_type:q["type"]=movement_type
    if from_date or to_date:
        q["occurred_at"]={}
        if from_date:q["occurred_at"]["$gte"]=from_date
        if to_date:q["occurred_at"]["$lte"]=to_date+"T23:59:59"
    movements=await db.cash_movements.find(q,{"_id":0}).sort("occurred_at",-1).to_list(5000)
    total_in=round(sum(float(x.get("amount",0) or 0) for x in movements if x.get("direction")=="in"),2)
    total_out=round(sum(float(x.get("amount",0) or 0) for x in movements if x.get("direction")=="out"),2)
    return {"movements":movements,"total_in":total_in,"total_out":total_out,"net":round(total_in-total_out,2)}

@router.patch("/obligations/{obligation_id}/status")
async def update_obligation_status(obligation_id:str,status:str,user:dict=MANAGER):
    if status not in {"pendiente","parcial","pagada","cancelada"}:raise HTTPException(400,"Estado inválido")
    result=await db.obligations.update_one({"id":obligation_id,"business_id":user["business_id"]},{"$set":{"status":status,"updated_at":now_iso()}})
    if not result.matched_count:raise HTTPException(404,"Cuenta no encontrada")
    return {"ok":True}

@router.delete("/obligations/{obligation_id}")
async def delete_obligation(obligation_id:str,user:dict=MANAGER):
    bid=user["business_id"]
    existing=await db.obligations.find_one({"id":obligation_id,"business_id":bid},{"_id":0})
    if not existing:raise HTTPException(404,"Cuenta no encontrada")
    payments=await db.obligation_payments.count_documents({"obligation_id":obligation_id,"business_id":bid})
    if payments:raise HTTPException(409,"No se puede eliminar una cuenta con pagos registrados; usa cancelar para conservar el historial financiero")
    await db.obligations.delete_one({"id":obligation_id,"business_id":bid})
    return {"ok":True}
