"""Phase 1 integrity checks for PLATIA.

These checks are intentionally read-only. They identify records that cannot
safely feed the Financial Engine, without mutating business data.
"""
from database import db


COLLECTIONS = (
    "products", "sales", "purchases", "inventory_movements", "expenses",
    "customers", "suppliers", "supplier_events", "obligations",
    "obligation_payments", "cash_closures",
)


async def run_data_integrity_checks(business_id: str | None = None) -> dict:
    """Return counts of Phase 1 integrity violations.

    A production caller may pass a business_id to audit only one tenant.
    """
    scope = {"business_id": business_id} if business_id else {}
    result = {}

    for collection in COLLECTIONS:
        total = await db[collection].count_documents(scope)
        missing_tenant = await db[collection].count_documents(
            {**({"business_id": {"$exists": False}})}
        )
        result[collection] = {"total": total, "missing_business_id": missing_tenant}

    # Referential checks for the records that feed financial calculations.
    products = {p["id"] async for p in db.products.find(scope, {"id": 1}) if p.get("id")}
    customers = {c["id"] async for c in db.customers.find(scope, {"id": 1}) if c.get("id")}
    suppliers = {s["id"] async for s in db.suppliers.find(scope, {"id": 1}) if s.get("id")}

    bad_inventory = 0
    async for movement in db.inventory_movements.find(scope, {"product_id": 1}):
        if movement.get("product_id") not in products:
            bad_inventory += 1

    bad_supplier_events = 0
    async for event in db.supplier_events.find(scope, {"supplier_id": 1}):
        if event.get("supplier_id") not in suppliers:
            bad_supplier_events += 1

    result["references"] = {
        "inventory_movements_missing_product": bad_inventory,
        "supplier_events_missing_supplier": bad_supplier_events,
        "customers_available": len(customers),
        "suppliers_available": len(suppliers),
    }

    return result
