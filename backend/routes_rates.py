from fastapi import APIRouter, Depends

from database import db
from rates import get_bcv_rate, get_effective_rate
from security import require_business, require_roles

router = APIRouter(tags=["rates"])


@router.get("/rates/current")
async def current_rate(user: dict = Depends(require_business)):
    business = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0})
    effective = await get_effective_rate(business or {})
    auto = await get_bcv_rate()
    return {
        "rate": effective.get("rate"),
        "source": effective.get("source"),
        "date": effective.get("date"),
        "stale": effective.get("stale", False),
        "mode": (business or {}).get("bcv_mode", "auto"),
        "manual_rate": (business or {}).get("bcv_rate"),
        "auto_rate": auto.get("rate") if auto else None,
        "auto_date": auto.get("effective_date") if auto else None,
    }


@router.post("/rates/refresh")
async def refresh_rate(user: dict = Depends(require_roles("propietario", "administrador"))):
    auto = await get_bcv_rate(force=True)
    if not auto:
        return {"ok": False, "detail": "No se pudo obtener la tasa BCV en este momento"}
    return {"ok": True, "rate": auto["rate"], "date": auto.get("effective_date"), "stale": auto.get("stale", False)}
