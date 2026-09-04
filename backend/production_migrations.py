import os

from database import db
from security import now_iso
from data_foundation import ensure_data_foundation


async def ensure_managed_accounts_approved():
    """Production startup migrations and Phase 1 data foundation."""
    emails = {
        "kiosco.demo@controlpyme.com",
        "verduleria.demo@controlpyme.com",
        "repuestos.demo@controlpyme.com",
    }
    admin_email = os.environ.get("ADMIN_EMAIL")
    if admin_email:
        admin_email = admin_email.strip().lower()
        emails.add(admin_email)

    await db.users.update_many(
        {"email": {"$in": sorted(emails)}},
        {"$set": {"approved": True, "approved_at": now_iso(), "approved_by": "system_seed"}},
    )

    if admin_email:
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {
                "platform_role": "superadmin",
                "approved": True,
                "approved_at": now_iso(),
                "approved_by": "system_seed",
            }},
        )

    # Fase 1: indexes, canonical entities and idempotent historical backfill.
    await ensure_data_foundation()
