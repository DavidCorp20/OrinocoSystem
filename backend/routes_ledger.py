from typing import Optional
from fastapi import APIRouter, Depends
from database import db
from security import require_business

router = APIRouter(tags=["ledger"])

@router.get("/cash-movements")
async def list_cash_movements(direction: Optional[str] = None, movement_type: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None, user: dict = Depends(require_business)):
    q = {"business_id": user["business_id"]}
    if direction in {"in", "out"}: q["direction"] = direction
    if movement_type: q["type"] = movement_type
    if from_date or to_date:
        q["occurred_at"] = {}
        if from_date: q["occurred_at"]["$gte"] = from_date
        if to_date: q["occurred_at"]["$lte"] = to_date + "T23:59:59"
    movements = await db.cash_movements.find(q, {"_id": 0}).sort("occurred_at", -1).to_list(5000)
    total_in = round(sum(float(x.get("amount", 0) or 0) for x in movements if x.get("direction") == "in"), 2)
    total_out = round(sum(float(x.get("amount", 0) or 0) for x in movements if x.get("direction") == "out"), 2)
    return {"movements": movements, "total_in": total_in, "total_out": total_out, "net": round(total_in - total_out, 2)}
