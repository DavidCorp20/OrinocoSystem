from fastapi import APIRouter, Depends, HTTPException

from security import require_business
from supplier_intelligence import get_supplier_intelligence

router = APIRouter(tags=["supplier-intelligence"])


@router.get("/supplier-intelligence")
async def supplier_intelligence(days: int = 90, user: dict = Depends(require_business)):
    if days < 1 or days > 3650:
        raise HTTPException(400, "days debe estar entre 1 y 3650")
    return await get_supplier_intelligence(user["business_id"], days)
