from database import db
from ledger import record_cash_movement, is_cash_method
from security import now_iso

MIGRATION_KEY = "phase1_cash_ledger_v1"


async def backfill_cash_ledger():
    """Materialize historical cash portions exactly once.

    Operational routes already create ledger entries for new transactions;
    this migration only reconstructs records that existed before the ledger.
    """
    marker = await db.migration_state.find_one({"key": MIGRATION_KEY}, {"_id": 0})
    if marker and marker.get("completed"):
        return {"status": "already_completed", "inserted": 0}

    inserted = 0
    async for sale in db.sales.find(
        {"business_id": {"$exists": True}},
        {"id": 1, "business_id": 1, "payment_parts": 1, "payment_method": 1,
         "total": 1, "created_at": 1, "user_email": 1},
    ):
        parts = sale.get("payment_parts") or [
            {"method": sale.get("payment_method"), "amount": sale.get("total", 0)}
        ]
        for idx, part in enumerate(parts):
            method = (part.get("method") or "").strip().lower()
            if is_cash_method(method):
                before = await db.cash_movements.count_documents({
                    "business_id": sale["business_id"],
                    "source_type": "sale",
                    "source_id": f"{sale.get('id')}:cash:{idx}",
                    "direction": "in",
                    "payment_method": method,
                })
                await record_cash_movement(
                    business_id=sale["business_id"], direction="in",
                    movement_type="sale", source_type="sale",
                    source_id=f"{sale.get('id')}:cash:{idx}",
                    amount=part.get("amount", 0), payment_method=method,
                    user_email=sale.get("user_email"),
                    occurred_at=sale.get("created_at"),
                )
                inserted += int(before == 0)

    async for purchase in db.purchases.find(
        {"business_id": {"$exists": True}},
        {"id": 1, "business_id": 1, "payment_parts": 1, "payment_method": 1,
         "total": 1, "created_at": 1, "user_email": 1},
    ):
        parts = purchase.get("payment_parts") or [
            {"method": purchase.get("payment_method"), "amount": purchase.get("total", 0)}
        ]
        for idx, part in enumerate(parts):
            method = (part.get("method") or "").strip().lower()
            if is_cash_method(method):
                before = await db.cash_movements.count_documents({
                    "business_id": purchase["business_id"],
                    "source_type": "purchase",
                    "source_id": f"{purchase.get('id')}:cash:{idx}",
                    "direction": "out",
                    "payment_method": method,
                })
                await record_cash_movement(
                    business_id=purchase["business_id"], direction="out",
                    movement_type="purchase", source_type="purchase",
                    source_id=f"{purchase.get('id')}:cash:{idx}",
                    amount=part.get("amount", 0), payment_method=method,
                    user_email=purchase.get("user_email"),
                    occurred_at=purchase.get("created_at"),
                )
                inserted += int(before == 0)

    async for expense in db.expenses.find(
        {"business_id": {"$exists": True}},
        {"id": 1, "business_id": 1, "payment_method": 1, "amount": 1,
         "created_at": 1, "user_email": 1, "description": 1},
    ):
        method = (expense.get("payment_method") or "").strip().lower()
        if is_cash_method(method):
            before = await db.cash_movements.count_documents({
                "business_id": expense["business_id"],
                "source_type": "expense",
                "source_id": expense.get("id"),
                "direction": "out",
                "payment_method": method,
            })
            await record_cash_movement(
                business_id=expense["business_id"], direction="out",
                movement_type="expense", source_type="expense",
                source_id=expense.get("id"), amount=expense.get("amount", 0),
                payment_method=method, user_email=expense.get("user_email"),
                occurred_at=expense.get("created_at"),
                notes=expense.get("description"),
            )
            inserted += int(before == 0)

    await db.migration_state.update_one(
        {"key": MIGRATION_KEY},
        {"$set": {"key": MIGRATION_KEY, "completed": True, "completed_at": now_iso(), "inserted": inserted}},
        upsert=True,
    )
    return {"status": "completed", "inserted": inserted}
