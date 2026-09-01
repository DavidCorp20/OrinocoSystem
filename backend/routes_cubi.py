from fastapi import APIRouter, Depends

from database import db
from security import require_business
from cubi.engine import build_business_insights

router = APIRouter(prefix="/cubi", tags=["cubi"])


@router.get("/insights")
async def get_cubi_insights(user: dict = Depends(require_business)):
    """Return native Cubi intelligence for the authenticated business."""
    return await build_business_insights(db, user["business_id"])
