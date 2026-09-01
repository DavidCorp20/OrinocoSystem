from fastapi import APIRouter, Depends

from database import db
from rates import get_bcv_rate, get_bcv_rates, get_effective_rate
from security import require_business, require_roles

router = APIRouter(tags=["rates"])


@router.get("/rates/current")
async def current_rate(user: dict = Depends(require_business)):
    business = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0})
    effective = await get_effective_rate(business or {})
    auto = await get_bcv_rates()
    return {
        "rate": effective.get("rate"),
        "source": effective.get("source"),
        "date": effective.get("date"),
        "stale": effective.get("stale", False),
        "mode": (business or {}).get("bcv_mode", "auto"),
        "manual_rate": (business or {}).get("bcv_rate"),
        "auto_rate": auto.get("usd") if auto else None,
        "auto_rate_usd": auto.get("usd") if auto else None,
        "auto_rate_eur": auto.get("eur") if auto else None,
        "auto_date": auto.get("effective_date") if auto else None,
        "provider": auto.get("provider") if auto else None,
        "retrieved_at": auto.get("retrieved_at") if auto else None,
    }


@router.post("/rates/refresh")
async def refresh_rate(user: dict = Depends(require_roles("propietario", "administrador"))):
    auto = await get_bcv_rates(force=True)
    if not auto:
        return {"ok": False, "detail": "No se pudieron obtener las tasas BCV en este momento"}
    return {
        "ok": True,
        "rate": auto["usd"],
        "usd": auto["usd"],
        "eur": auto["eur"],
        "date": auto.get("effective_date"),
        "stale": auto.get("stale", False),
        "provider": auto.get("provider"),
    }
