from fastapi import APIRouter, Depends, HTTPException

from financial_health import calculate_financial_health
from security import require_business

router = APIRouter(tags=["financial-health"])


@router.get("/financial-health")
async def financial_health(days: int = 90, user: dict = Depends(require_business)):
    if days < 30 or days > 3650:
        raise HTTPException(400, "days debe estar entre 30 y 3650")
    return await calculate_financial_health(user["business_id"], days)
