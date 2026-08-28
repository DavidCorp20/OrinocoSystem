from datetime import timedelta

import httpx

from database import db
from security import now, now_iso

BCV_URL = "https://bcv.today/api/v1/rate.json"
CACHE_MINUTES = 60


async def _fetch_bcv() -> dict:
    async with httpx.AsyncClient(timeout=6.0) as http:
        r = await http.get(BCV_URL, headers={"Accept": "application/json"})
        r.raise_for_status()
        payload = r.json()
    rate = payload.get("USD")
    if not isinstance(rate, (int, float)) or rate <= 0:
        raise ValueError("Tasa BCV inválida desde el proveedor")
    return {
        "rate": float(rate),
        "effective_date": payload.get("effective_date"),
        "retrieved_at": now_iso(),
        "provider": "bcv.today",
    }


async def get_bcv_rate(force: bool = False):
    doc = await db.rates.find_one({"_id": "bcv_usd"})
    if doc and not force and doc.get("expires_at", "") > now_iso():
        return doc
    try:
        fresh = await _fetch_bcv()
        fresh["_id"] = "bcv_usd"
        fresh["expires_at"] = (now() + timedelta(minutes=CACHE_MINUTES)).isoformat()
        await db.rates.replace_one({"_id": "bcv_usd"}, fresh, upsert=True)
        fresh["stale"] = False
        return fresh
    except Exception:
        if doc:
            return {**doc, "stale": True}
        return None


async def get_effective_rate(business: dict) -> dict:
    if business.get("bcv_mode") == "manual" and business.get("bcv_rate"):
        return {"rate": business["bcv_rate"], "source": "manual", "date": business.get("bcv_rate_date"), "stale": False}
    auto = await get_bcv_rate()
    if auto:
        return {"rate": auto["rate"], "source": "bcv", "date": auto.get("effective_date"), "stale": auto.get("stale", False)}
    if business.get("bcv_rate"):
        return {"rate": business["bcv_rate"], "source": "manual", "date": business.get("bcv_rate_date"), "stale": True}
    return {"rate": None, "source": None, "date": None, "stale": False}
