import os

from database import db
from security import now_iso


async def ensure_managed_accounts_approved():
    """Approve only application-managed demo/admin accounts.

    Public registrations remain pending until an administrator approves them.
    Startup never mass-approves arbitrary legacy users.
    """
    emails = {
        "kiosco.demo@controlpyme.com",
        "verduleria.demo@controlpyme.com",
        "repuestos.demo@controlpyme.com",
    }
    admin_email = os.environ.get("ADMIN_EMAIL")
    if admin_email:
        emails.add(admin_email.lower())

    await db.users.update_many(
        {"email": {"$in": sorted(emails)}},
        {"$set": {"approved": True, "approved_at": now_iso(), "approved_by": "system_seed"}},
    )
