from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from database import db
from models import ObligationIn, ObligationPaymentIn
from security import new_id, now_iso, require_business, require_roles

router=APIRouter(tags=["obligations"])
MANAGER=Depends(require_roles("propietario","administrador"))

@router.get("/obligations")
async def list_obligations(kind:Optional[str]=None,status:Optional[str]=None,user:dict=Depends(require_business)):
    q={"business_id":user["business_id"]}
    if kind:q["kind"]=kind
    if status:q["status"]=status
    docs=await db.obligations.find(q,{"_id":0}).sort("due_date",1).to_list(5000)
    now=datetime.now(timezone.utc).date().isoformat()
    for d in docs:
        if d.get("status")=="pendiente" and d.get("due_date") and d["due_date"]<now:d["status"]="vencida"
    return {"obligations":docs}

@router.post("/obligations")
async def create_obligation(data:ObligationIn,user:dict=MANAGER):
    doc={"id":new_id(),"business_id":user["business_id"],**data.model_dump(),"status":"pendiente","paid_amount":0,"remaining_amount":round(data.amount,2),"created_at":now_iso(),"updated_at":now_iso()}
    await db.obligations.insert_one(doc);doc.pop("_id",None);return {"obligation":doc}

@router.post("/obligations/{obligation_id}/payments")
async def pay_obligation(obligation_id:str,data:ObligationPaymentIn,user:dict=MANAGER):
    doc=await db.obligations.find_one({"id":obligation_id,"business_id":user["business_id"]},{"_id":0})
    if not doc:raise HTTPException(404,"Cuenta no encontrada")
    remaining=round(float(doc.get("remaining_amount",doc["amount"]-doc.get("paid_amount",0))),2)
    if data.amount>remaining+0.01:raise HTTPException(400,"El pago supera el saldo pendiente")
    payment={"id":new_id(),"obligation_id":obligation_id,"business_id":user["business_id"],"amount":round(data.amount,2),"payment_method":data.payment_method,"notes":data.notes,"paid_at":now_iso()}
    new_paid=round(float(doc.get("paid_amount",0))+data.amount,2); new_remaining=round(float(doc["amount"])-new_paid,2); status="pagada" if new_remaining<=0.009 else "pendiente"
    await db.obligation_payments.insert_one(payment);await db.obligations.update_one({"id":obligation_id},{"$set":{"paid_amount":new_paid,"remaining_amount":max(0,new_remaining),"status":status,"updated_at":now_iso()}});payment.pop("_id",None)
    return {"payment":payment,"remaining_amount":max(0,new_remaining),"status":status}

@router.get("/obligations/{obligation_id}/payments")
async def list_obligation_payments(obligation_id:str,user:dict=Depends(require_business)):
    if not await db.obligations.find_one({"id":obligation_id,"business_id":user["business_id"]},{"_id":1}):raise HTTPException(404,"Cuenta no encontrada")
    return {"payments":await db.obligation_payments.find({"obligation_id":obligation_id,"business_id":user["business_id"]},{"_id":0}).sort("paid_at",-1).to_list(1000)}

@router.patch("/obligations/{obligation_id}/status")
async def update_obligation_status(obligation_id:str,status:str,user:dict=MANAGER):
    if status not in {"pendiente","pagada","cancelada"}:raise HTTPException(400,"Estado inválido")
    result=await db.obligations.update_one({"id":obligation_id,"business_id":user["business_id"]},{"$set":{"status":status,"updated_at":now_iso()}})
    if not result.matched_count:raise HTTPException(404,"Cuenta no encontrada")
    return {"ok":True}

@router.delete("/obligations/{obligation_id}")
async def delete_obligation(obligation_id:str,user:dict=MANAGER):
    result=await db.obligations.delete_one({"id":obligation_id,"business_id":user["business_id"]})
    if not result.deleted_count:raise HTTPException(404,"Cuenta no encontrada")
    await db.obligation_payments.delete_many({"obligation_id":obligation_id,"business_id":user["business_id"]})
    return {"ok":True}
