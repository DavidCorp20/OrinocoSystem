from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

from security import require_business
from financial_engine import calculate_financial_snapshot, get_financial_snapshot

router = APIRouter(tags=["financial-engine"])


@router.get("/financial-engine/snapshot")
async def financial_engine_snapshot(days: int = 30, user: dict = Depends(require_business)):
    if days < 1 or days > 3650:
        raise HTTPException(400, "days debe estar entre 1 y 3650")
    return await get_financial_snapshot(user["business_id"], days)


@router.get("/financial-engine/snapshot/range")
async def financial_engine_snapshot_range(start: str, end: str, user: dict = Depends(require_business)):
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(400, "start y end deben ser fechas ISO válidas")
    if end_dt <= start_dt:
        raise HTTPException(400, "end debe ser posterior a start")
    if end_dt - start_dt > timedelta(days=3650):
        raise HTTPException(400, "El período máximo es de 3650 días")
    return await calculate_financial_snapshot(user["business_id"], start_dt, end_dt)
