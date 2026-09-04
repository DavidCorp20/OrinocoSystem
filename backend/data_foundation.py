"""Phase 1 Data Foundation utilities.

Keeps the existing operational collections compatible while introducing stable
business-scoped entities and indexes needed by the Financial Engine.
"""
from datetime import datetime, timezone
from pymongo import ASCENDING, DESCENDING
from database import db
from security import new_id, now_iso


def _now():
    return datetime.now(timezone.utc).isoformat()


async def ensure_data_foundation():
    """Create tenant-safe indexes and backfill canonical entities idempotently."""
    # Tenant isolation + common time-series access patterns.
    indexes = {
        "users": [("business_id", ASCENDING), ("email", ASCENDING)],
        "businesses": [("id", ASCENDING)],
        "products": [("business_id", ASCENDING), ("id", ASCENDING), ("sku", ASCENDING)],
        "categories": [("business_id", ASCENDING), ("id", ASCENDING), ("name", ASCENDING)],
        "customers": [("business_id", ASCENDING), ("id", ASCENDING), ("rif", ASCENDING)],
        "suppliers": [("business_id", ASCENDING), ("id", ASCENDING), ("rif", ASCENDING)],
        "supplier_events": [("business_id", ASCENDING), ("supplier_id", ASCENDING), ("event_date", DESCENDING)],
        "sales": [("business_id", ASCENDING), ("created_at", DESCENDING)],
        "purchases": [("business_id", ASCENDING), ("created_at", DESCENDING)],
        "inventory_movements": [("business_id", ASCENDING), ("product_id", ASCENDING), ("created_at", DESCENDING)],
        "expenses": [("business_id", ASCENDING), ("date", DESCENDING)],
        "cash_movements": [("business_id", ASCENDING), ("created_at", DESCENDING)],
        "obligations": [("business_id", ASCENDING), ("kind", ASCENDING), ("status", ASCENDING), ("due_date", ASCENDING)],
        "obligation_payments": [("business_id", ASCENDING), ("obligation_id", ASCENDING), ("paid_at", DESCENDING)],
    }
    for collection, fields in indexes.items():
        try:
            await db[collection].create_index(fields)
        except Exception:
            # Some older databases can contain duplicate legacy values. Do not
            # block application startup; the indexes above are non-unique.
            pass

    # Canonical categories from the existing product.category string field.
    async for product in db.products.find({"business_id": {"$exists": True}, "category": {"$nin": [None, ""]}}, {"business_id": 1, "category": 1}):
        name = str(product.get("category", "")).strip()
        if not name:
            continue
        await db.categories.update_one(
            {"business_id": product["business_id"], "name": name},
            {"$setOnInsert": {"id": new_id(), "business_id": product["business_id"], "name": name, "active": True, "created_at": _now()}},
            upsert=True,
        )

    # Canonical suppliers from products and historical purchases.
    async for purchase in db.purchases.find({"business_id": {"$exists": True}, "supplier": {"$nin": [None, ""]}}, {"business_id": 1, "supplier": 1, "supplier_rif": 1}):
        await _ensure_supplier_doc(purchase["business_id"], purchase.get("supplier"), purchase.get("supplier_rif"))
    async for product in db.products.find({"business_id": {"$exists": True}, "supplier": {"$nin": [None, ""]}}, {"business_id": 1, "supplier": 1}):
        await _ensure_supplier_doc(product["business_id"], product.get("supplier"), None)

    # Canonical customers from historical sales.
    async for sale in db.sales.find({"business_id": {"$exists": True}, "customer_name": {"$nin": [None, ""]}}, {"business_id": 1, "customer_name": 1, "customer_rif": 1}):
        name = str(sale.get("customer_name", "")).strip()
        if name:
            await db.customers.update_one(
                {"business_id": sale["business_id"], "$or": [{"rif": sale.get("customer_rif")} , {"name": name}]},
                {"$setOnInsert": {"id": new_id(), "business_id": sale["business_id"], "name": name, "rif": sale.get("customer_rif"), "active": True, "created_at": _now(), "updated_at": _now()}},
                upsert=True,
            )

    # Idempotently create supplier purchase events for historical purchases.
    async for purchase in db.purchases.find({"business_id": {"$exists": True}, "supplier": {"$nin": [None, ""]}}, {"id": 1, "business_id": 1, "supplier": 1, "supplier_rif": 1, "created_at": 1, "total": 1, "items": 1, "status": 1}):
        supplier = await _ensure_supplier_doc(purchase["business_id"], purchase.get("supplier"), purchase.get("supplier_rif"))
        if supplier:
            await db.supplier_events.update_one(
                {"business_id": purchase["business_id"], "source_id": purchase.get("id"), "event_type": "purchase"},
                {"$setOnInsert": {
                    "id": new_id(), "business_id": purchase["business_id"], "supplier_id": supplier["id"],
                    "event_type": "purchase", "source_id": purchase.get("id"),
                    "event_date": purchase.get("created_at") or _now(), "amount": float(purchase.get("total", 0) or 0),
                    "status": purchase.get("status", "desconocido"), "items_count": len(purchase.get("items", [])),
                    "created_at": _now(),
                }}, upsert=True,
            )


async def _ensure_supplier_doc(business_id, name, rif=None):
    name = str(name or "").strip()
    if not name:
        return None
    query = {"business_id": business_id, "name": name}
    doc = await db.suppliers.find_one(query, {"_id": 0})
    if doc:
        if rif and not doc.get("rif"):
            await db.suppliers.update_one(query, {"$set": {"rif": rif, "updated_at": _now()}})
            doc["rif"] = rif
        return doc
    doc = {"id": new_id(), "business_id": business_id, "name": name, "rif": rif, "active": True, "created_at": _now(), "updated_at": _now()}
    await db.suppliers.insert_one(doc.copy())
    return doc


async def ensure_customer(business_id, name, rif=None, phone=None, email=None):
    name = str(name or "").strip()
    if not name:
        return None
    doc = await db.customers.find_one({"business_id": business_id, "$or": [{"rif": rif} if rif else {"name": name}, {"name": name}]}, {"_id": 0})
    if doc:
        return doc
    doc = {"id": new_id(), "business_id": business_id, "name": name, "rif": rif, "phone": phone, "email": email, "active": True, "created_at": _now(), "updated_at": _now()}
    await db.customers.insert_one(doc.copy())
    return doc


async def ensure_supplier(business_id, name, rif=None, phone=None, email=None):
    doc = await _ensure_supplier_doc(business_id, name, rif)
    if doc and (phone or email):
        await db.suppliers.update_one({"id": doc["id"], "business_id": business_id}, {"$set": {"phone": phone or doc.get("phone"), "email": email or doc.get("email"), "updated_at": _now()}})
    return doc
