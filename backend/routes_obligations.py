from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from database import db
from models import ObligationIn
from security import new_id, now_iso, require_business, require_roles

router = APIRouter(tags=["obligations"])
MANAGER = Depends(require_roles("propietario", "administrador"))

@router.get("/obligations")
async def list_obligations(kind: Optional[str] = None, status: Optional[str] = None, user: dict = Depends(require_business)):
    q = {"business_id": user["business_id"]}
    if kind: q["kind"] = kind
    if status: q["status"] = status
    docs = await db.obligations.find(q, {"_id": 0}).sort("due_date", 1).to_list(5000)
    return {"obligations": docs}

@router.post("/obligations")
async def create_obligation(data: ObligationIn, user: dict = MANAGER):
    doc = {"id": new_id(), "business_id": user["business_id"], **data.model_dump(), "status": "pendiente", "created_at": now_iso(), "updated_at": now_iso()}
    await db.obligations.insert_one(doc)
    doc.pop("_id", None)
    return {"obligation": doc}

@router.patch("/obligations/{obligation_id}/status")
async def update_obligation_status(obligation_id: str, status: str, user: dict = MANAGER):
    if status not in {"pendiente", "pagada", "cancelada"}:
        raise HTTPException(status_code=400, detail="Estado inválido")
    result = await db.obligations.update_one({"id": obligation_id, "business_id": user["business_id"]}, {"$set": {"status": status, "updated_at": now_iso()}})
    if not result.modified_count: raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return {"ok": True}

@router.delete("/obligations/{obligation_id}")
async def delete_obligation(obligation_id: str, user: dict = MANAGER):
    result = await db.obligations.delete_one({"id": obligation_id, "business_id": user["business_id"]})
    if not result.deleted_count: raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return {"ok": True}
