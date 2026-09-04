import asyncio
import os
from datetime import datetime, timezone

from database import db
from security import hash_password

DEMO_VERSION = 1

async def main():
    pro = await db.platform_plans.find_one({"name": "Pro", "active": True}, {"_id": 0})
    demo_password = os.getenv("DEMO_PASSWORD")
    emails = (
        ("cafe.demo@platia.app", "Café Aroma Caracas"),
        ("barber.demo@platia.app", "Barbería Central Caracas"),
        ("moda.demo@platia.app", "Moda Urbana Caracas"),
    )

    for email, name in emails:
        user = await db.users.find_one({"email": email})
        if not user or not user.get("business_id"):
            continue

        # Clear lockouts caused by previous failed demo login attempts.
        await db.login_attempts.delete_one({"identifier": email})

        if demo_password:
            await db.users.update_one(
                {"email": email},
                {"$set": {
                    "password_hash": hash_password(demo_password),
                    "approved": True,
                    "approved_at": datetime.now(timezone.utc).isoformat(),
                    "approved_by": "demo_patch",
                }},
            )
            user = await db.users.find_one({"email": email})

        bid = user["business_id"]
        business = await db.businesses.find_one(
            {"id": bid}, {"_id": 0, "demo_expenses_finalized": 1}
        )
        if not business:
            continue

        if name == "Café Aroma Caracas" and not business.get("demo_expenses_finalized"):
            async for e in db.expenses.find({"business_id": bid}):
                await db.expenses.update_one(
                    {"id": e["id"]},
                    {"$set": {"amount": round(float(e.get("amount", 0)) * 0.55, 2)}},
                )
            await db.businesses.update_one(
                {"id": bid}, {"$set": {"demo_expenses_finalized": True}}
            )

        if pro:
            sub = await db.platform_subscriptions.find_one(
                {"business_id": bid, "status": "activo"}
            )
            if not sub:
                await db.platform_subscriptions.insert_one({
                    "id": f"demo-{user['id']}",
                    "business_id": bid,
                    "plan_id": pro["id"],
                    "status": "activo",
                    "monthly_price_usd": pro.get("monthly_price_usd", 0),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

        await db.businesses.update_one(
            {"id": bid},
            {"$set": {
                "demo_showcase_version": DEMO_VERSION,
                "is_demo": True,
                "active": True,
            }},
        )

if __name__ == "__main__":
    asyncio.run(main())
