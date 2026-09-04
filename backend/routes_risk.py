from fastapi import APIRouter, Depends, HTTPException

from risk_engine import calculate_risk
from security import require_business

router = APIRouter(tags=["risk"])


@router.get("/risk")
async def risk(days: int = 90, user: dict = Depends(require_business)):
    if days < 30 or days > 3650:
        raise HTTPException(400, "days debe estar entre 30 y 3650")
    return await calculate_risk(user["business_id"], days)
