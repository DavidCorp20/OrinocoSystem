from fastapi import APIRouter, Depends

from security import require_business
from stats import compute_dashboard

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(user: dict = Depends(require_business)):
    return await compute_dashboard(user["business_id"])
