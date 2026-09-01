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
    usd = payload.get("USD")
    eur = payload.get("EUR")
    if not isinstance(usd, (int, float)) or usd <= 0:
        raise ValueError("Tasa USD inválida desde el proveedor")
    if not isinstance(eur, (int, float)) or eur <= 0:
        raise ValueError("Tasa EUR inválida desde el proveedor")
    return {
        "usd": float(usd),
        "eur": float(eur),
        "effective_date": payload.get("effective_date"),
        "retrieved_at": now_iso(),
        "provider": "bcv.today",
    }


async def get_bcv_rates(force: bool = False):
    doc = await db.rates.find_one({"_id": "bcv_rates"})
    if doc and not force and doc.get("expires_at", "") > now_iso():
        return doc
    try:
        fresh = await _fetch_bcv()
        fresh["_id"] = "bcv_rates"
        fresh["expires_at"] = (now() + timedelta(minutes=CACHE_MINUTES)).isoformat()
        await db.rates.replace_one({"_id": "bcv_rates"}, fresh, upsert=True)
        fresh["stale"] = False
        return fresh
    except Exception:
        if doc:
            return {**doc, "stale": True}
        return None


async def get_bcv_rate(force: bool = False):
    rates = await get_bcv_rates(force=force)
    if not rates:
        return None
    return {
        "rate": rates.get("usd"),
        "effective_date": rates.get("effective_date"),
        "retrieved_at": rates.get("retrieved_at"),
        "provider": rates.get("provider", "bcv.today"),
        "stale": rates.get("stale", False),
    }


async def get_effective_rate(business: dict) -> dict:
    if business.get("bcv_mode") == "manual" and business.get("bcv_rate"):
        return {"rate": business["bcv_rate"], "source": "manual", "date": business.get("bcv_rate_date"), "stale": False}
    auto = await get_bcv_rate()
    if auto:
        return {"rate": auto["rate"], "source": "bcv", "date": auto.get("effective_date"), "stale": auto.get("stale", False)}
    if business.get("bcv_rate"):
        return {"rate": business["bcv_rate"], "source": "manual", "date": business.get("bcv_rate_date"), "stale": True}
    return {"rate": None, "source": None, "date": None, "stale": False}
