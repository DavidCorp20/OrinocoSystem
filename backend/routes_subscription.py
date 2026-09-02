from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from database import db
from models import MerchantPaymentIn
from rates import get_bcv_rate
from security import get_current_user, require_roles, require_superadmin, new_id, now_iso

router = APIRouter(tags=["subscription"])


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.get("/subscription/me")
async def my_subscription(user: dict = Depends(require_roles("propietario", "administrador"))):
    sub = await db.platform_subscriptions.find_one(
        {"business_id": user["business_id"], "status": {"$ne": "cancelado"}},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    business = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0})
    plan = None
    if sub:
        plan = await db.platform_plans.find_one({"id": sub.get("plan_id")}, {"_id": 0})
    payments = []
    if sub:
        payments = await db.platform_billing.find({"subscription_id": sub["id"]}, {"_id": 0}).sort("paid_at", -1).to_list(24)
    bcv = await get_bcv_rate()
    return {
        "business": {"id": business.get("id"), "name": business.get("name"), "created_at": business.get("created_at")} if business else None,
        "subscription": sub,
        "plan": plan,
        "payments": payments,
        "bcv_rate": bcv.get("rate") if bcv else None,
        "bcv_date": bcv.get("effective_date") if bcv else None,
        "rate_source": bcv.get("provider") if bcv else None,
    }


@router.post("/subscription/payments")
async def submit_payment(data: MerchantPaymentIn, user: dict = Depends(require_roles("propietario", "administrador"))):
    sub = await db.platform_subscriptions.find_one({"id": data.subscription_id, "business_id": user["business_id"], "status": {"$ne": "cancelado"}}, {"_id": 0})
    if not sub:
        raise HTTPException(404, "No se encontró una suscripción activa para tu negocio")
    if data.amount_usd <= 0:
        raise HTTPException(400, "El monto USD debe ser mayor que cero")
    if data.bcv_rate <= 0 or data.market_rate <= 0:
        raise HTTPException(400, "Las tasas deben ser mayores que cero")
    average_rate = round((data.bcv_rate + data.market_rate) / 2, 4)
    amount_bs = round(data.amount_usd * average_rate, 2)
    paid_at = data.paid_at or now_iso()
    payment = {
        "id": new_id(),
        "subscription_id": sub["id"],
        "business_id": user["business_id"],
        "amount": round(data.amount_usd, 2),
        "amount_usd": round(data.amount_usd, 2),
        "amount_bs": amount_bs,
        "payment_method": data.payment_method,
        "reference": data.reference,
        "paid_at": paid_at,
        "bcv_rate": data.bcv_rate,
        "market_rate": data.market_rate,
        "average_rate": average_rate,
        "rate_split": 0.5,
        "status": "pendiente_verificacion",
        "notes": data.notes,
        "created_at": now_iso(),
        "created_by": user["id"],
    }
    await db.platform_billing.insert_one(payment)
    payment.pop("_id", None)
    return {"ok": True, "payment": payment, "message": "Pago enviado para verificación."}


@router.patch("/platform/billing/{billing_id}/verify")
async def verify_payment(billing_id: str, approved: bool, user: dict = Depends(require_superadmin)):
    payment = await db.platform_billing.find_one({"id": billing_id}, {"_id": 0})
    if not payment:
        raise HTTPException(404, "Pago no encontrado")
    status = "aprobado" if approved else "rechazado"
    await db.platform_billing.update_one({"id": billing_id}, {"$set": {"status": status, "verified_at": now_iso(), "verified_by": user["id"]}})
    if approved:
        sub = await db.platform_subscriptions.find_one({"id": payment["subscription_id"]}, {"_id": 0})
        if sub:
            base = _parse_date(sub.get("due_date")) or datetime.now(timezone.utc)
            if base < datetime.now(timezone.utc):
                base = datetime.now(timezone.utc)
            next_due = (base + timedelta(days=30)).date().isoformat()
            await db.platform_subscriptions.update_one({"id": sub["id"]}, {"$set": {"status": "activo", "due_date": next_due, "updated_at": now_iso()}})
            await db.businesses.update_one({"id": sub["business_id"]}, {"$set": {"subscription_status": "activo", "subscription_due_date": next_due}})
    return {"ok": True, "status": status}
