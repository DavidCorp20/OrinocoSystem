from fastapi import APIRouter, Depends, HTTPException

from intelligence_engine import calculate_intelligence
from security import require_business

router = APIRouter(tags=["intelligence"])


@router.get("/intelligence")
async def intelligence(days: int = 30, user: dict = Depends(require_business)):
    if days < 7 or days > 3650:
        raise HTTPException(400, "days debe estar entre 7 y 3650")
    return await calculate_intelligence(user["business_id"], days)
