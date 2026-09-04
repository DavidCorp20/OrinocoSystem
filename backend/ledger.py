from typing import Any, Optional
from pymongo.errors import DuplicateKeyError
from database import db
from security import new_id, now_iso

CASH_METHODS={"efectivo","cash","caja","contado","efectivo_bs","efectivo_usd"}

def is_cash_method(method:Optional[str])->bool:return (method or "").strip().lower() in CASH_METHODS

async def record_cash_movement(*,business_id:str,direction:str,movement_type:str,source_type:str,source_id:str,amount:float,payment_method:str,user_email:Optional[str]=None,occurred_at:Optional[str]=None,currency:Optional[str]=None,notes:Optional[str]=None)->dict[str,Any]:
    amount=round(float(amount),2)
    if amount<=0:raise ValueError("Cash movement amount must be positive")
    if direction not in {"in","out"}:raise ValueError("Invalid cash movement direction")
    method=(payment_method or "").strip().lower(); key=f"{business_id}:{source_type}:{source_id}:{method}:{direction}"
    query={"business_id":business_id,"source_type":source_type,"source_id":source_id,"payment_method":method,"direction":direction}
    existing=await db.cash_movements.find_one(query,{"_id":0})
    if existing:return existing
    doc={"id":new_id(),"business_id":business_id,"direction":direction,"type":movement_type,"source_type":source_type,"source_id":source_id,"amount":amount,"payment_method":method,"currency":currency,"idempotency_key":key,"occurred_at":occurred_at or now_iso(),"user_email":user_email,"notes":notes,"created_at":now_iso()}
    try:
        result=await db.cash_movements.update_one({"idempotency_key":key},{"$setOnInsert":doc},upsert=True)
        if result.upserted_id is not None:return doc
    except DuplicateKeyError:
        pass
    existing=await db.cash_movements.find_one({"idempotency_key":key},{"_id":0})
    return existing or doc

async def record_payment_parts_as_cash(*,business_id:str,source_type:str,source_id:str,parts:list[dict],direction:str,user_email:Optional[str]=None,occurred_at:Optional[str]=None,currency:Optional[str]=None):
    result=[]
    for idx,part in enumerate(parts or []):
        method=(part.get("method") or part.get("payment_method") or "").strip().lower()
        if not is_cash_method(method):continue
        result.append(await record_cash_movement(business_id=business_id,direction=direction,movement_type=source_type,source_type=source_type,source_id=f"{source_id}:cash:{idx}",amount=part.get("amount",0),payment_method=method,user_email=user_email,occurred_at=occurred_at,currency=currency))
    return result
