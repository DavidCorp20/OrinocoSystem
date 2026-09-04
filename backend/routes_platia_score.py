from fastapi import APIRouter, Depends, HTTPException

from platia_score import calculate_platia_score
from security import require_business

router = APIRouter(tags=["platia-score"])


@router.get("/platia-score")
async def platia_score(days: int = 90, user: dict = Depends(require_business)):
    if days < 30 or days > 3650:
        raise HTTPException(400, "days debe estar entre 30 y 3650")
    return await calculate_platia_score(user["business_id"], days)
