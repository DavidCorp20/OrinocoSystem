import os

from database import db
from security import now_iso


async def ensure_managed_accounts_approved():
    """Approve managed accounts and guarantee the platform administrator role.

    Public registrations remain pending until a platform administrator approves them.
    Only ADMIN_EMAIL is promoted to superadmin; ordinary business administrators are
    never promoted by this startup migration.
    """
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

    # In production seed_all() is intentionally skipped. Therefore the managed
    # ADMIN_EMAIL account must be promoted here so it can access Platform and
    # Plan Permissions. This affects only the configured platform admin email.
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
