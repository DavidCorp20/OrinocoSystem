from fastapi import APIRouter, Depends, HTTPException

from financial_engine import get_financial_snapshot
from financial_translator import translate_financial_snapshot
from security import require_business

router = APIRouter(tags=["financial-insights"])


@router.get("/financial-insights")
async def financial_insights(days: int = 30, user: dict = Depends(require_business)):
    if days < 1 or days > 3650:
        raise HTTPException(400, "days debe estar entre 1 y 3650")
    snapshot = await get_financial_snapshot(user["business_id"], days)
    result = translate_financial_snapshot(snapshot)
    result["period"] = snapshot["period"]
    return result
