"""Expands the demo tenant to a richer 20-product catalog without duplicating data."""
import os
import random
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from database import db
from security import new_id, now_iso

DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@cuadrapp.com").strip().lower()
DEMO_BUSINESS = "Repuestos El Pistón Demo"

EXTRA_PRODUCTS = [
    ("Correa de distribución", "Motor", 18.00, 29.90, 4, 35, "Gates"),
    ("Termostato 82°C", "Motor", 7.50, 12.90, 5, 40, "Motorad"),
    ("Bomba de agua", "Motor", 24.00, 39.90, 3, 25, "GMB"),
    ("Amortiguador delantero", "Suspensión", 28.00, 45.90, 4, 28, "Monroe"),
    ("Rodamiento de rueda", "Suspensión", 14.00, 23.90, 5, 35, "SKF"),
    ("Disco de freno delantero", "Frenos", 22.00, 35.90, 4, 25, "Brembo"),
    ("Sensor de oxígeno", "Eléctrico", 18.00, 31.90, 3, 22, "Bosch"),
    ("Relé automotriz 12V", "Eléctrico", 2.20, 4.50, 8, 60, "Hella"),
    ("Terminal de batería", "Eléctrico", 1.80, 3.90, 8, 60, "Universal"),
    ("Silicón para juntas", "Accesorios", 3.20, 6.50, 6, 45, "Permatex"),
]


def _ts(day, hour, minute):
    return datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).replace(hour=hour, minute=minute).isoformat()


def _image(name):
    return f"https://placehold.co/600x600/png?text={quote_plus(name)}"


async def upgrade_demo_catalog():
    if os.getenv("DEMO_SEED_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return

    user = await db.users.find_one({"email": DEMO_EMAIL})
    if not user or not user.get("business_id"):
        return
    bid = user["business_id"]
    business = await db.businesses.find_one({"id": bid, "is_demo": True})
    if not business:
        return

    existing = await db.products.count_documents({"business_id": bid})
    if existing >= 20:
        return

    rng = random.Random(20260902)
    now = datetime.now(timezone.utc)
    products = []
    movements = []
    for offset, (name, category, cost, price, minimum, initial, brand) in enumerate(EXTRA_PRODUCTS, 11):
        if await db.products.find_one({"business_id": bid, "sku": f"DEMO-{offset:04d}"}):
            continue
        pid = new_id()
        products.append({
            "id": pid, "business_id": bid, "name": name, "sku": f"DEMO-{offset:04d}",
            "barcode": f"775{rng.randint(1000000000, 9999999999)}", "category": category,
            "brand": brand, "supplier": "Distribuidora AutoPartes", "purchase_price": cost,
            "sale_price": price, "stock": initial, "min_stock": minimum, "max_stock": initial * 2,
            "unit": "unidad", "status": "activo", "image_url": _image(name),
            "created_at": (now - timedelta(days=31)).isoformat(), "updated_at": now_iso(),
        })
    if not products:
        return
    await db.products.insert_many(products)

    stock = {p["id"]: p["stock"] for p in products}
    for p in products:
        movements.append({"id": new_id(), "business_id": bid, "product_id": p["id"], "product_name": p["name"],
                          "type": "entrada", "reason": "carga_inicial", "quantity": p["stock"],
                          "stock_after": p["stock"], "user_email": DEMO_EMAIL, "notes": "Ampliación catálogo demo",
                          "created_at": (now - timedelta(days=31)).isoformat()})

    sales = []
    demand = [2, 2, 1, 2, 2, 1, 3, 4, 3, 1]
    for days_ago in range(30, -1, -1):
        day = (now - timedelta(days=days_ago)).date()
        daily_sales = 4 if day.weekday() < 5 else 3
        for sale_no in range(daily_sales):
            idx = (days_ago * 2 + sale_no) % len(products)
            p = products[idx]
            qty = max(1, int(round(demand[idx] * (0.9 + rng.random() * 0.2))))
            line = round(p["sale_price"] * qty, 2)
            cost_total = round(p["purchase_price"] * qty, 2)
            stock[p["id"]] -= qty
            sales.append({"id": new_id(), "business_id": bid,
                          "items": [{"product_id": p["id"], "name": p["name"], "quantity": qty,
                                     "unit_price": p["sale_price"], "discount": 0.0,
                                     "cost": p["purchase_price"], "line_total": line}],
                          "total": line, "cost_total": cost_total, "profit": round(line - cost_total, 2),
                          "payment_method": ["efectivo", "tarjeta", "transferencia"][sale_no % 3],
                          "customer_name": ["Cliente mostrador", "Taller El Centro", "Auto Servicio Caracas", None][sale_no % 4],
                          "customer_rif": None, "user_email": DEMO_EMAIL,
                          "created_at": _ts(day, 9 + sale_no * 2, rng.randint(0, 59))})
            movements.append({"id": new_id(), "business_id": bid, "product_id": p["id"], "product_name": p["name"],
                              "type": "salida", "reason": "venta", "quantity": qty, "stock_after": stock[p["id"]],
                              "user_email": DEMO_EMAIL, "notes": "Venta demo", "created_at": _ts(day, 9 + sale_no * 2, rng.randint(0, 59))})

    purchases = []
    for days_ago in (22, 10):
        day = (now - timedelta(days=days_ago)).date()
        items = []
        total = 0.0
        for p in products:
            qty = 12 if p["purchase_price"] < 10 else 6
            stock[p["id"]] += qty
            line = round(p["purchase_price"] * qty, 2)
            total += line
            items.append({"product_id": p["id"], "name": p["name"], "quantity": qty,
                          "unit_cost": p["purchase_price"], "line_total": line})
            movements.append({"id": new_id(), "business_id": bid, "product_id": p["id"], "product_name": p["name"],
                              "type": "entrada", "reason": "compra", "quantity": qty,
                              "stock_after": stock[p["id"]], "user_email": DEMO_EMAIL,
                              "notes": "Reposición demo", "created_at": _ts(day, 8, 30)})
        purchases.append({"id": new_id(), "business_id": bid, "supplier": "Distribuidora AutoPartes",
                          "supplier_rif": None, "items": items, "total": round(total, 2),
                          "payment_method": "transferencia", "status": "completada", "user_email": DEMO_EMAIL,
                          "created_at": _ts(day, 8, 30)})

    if sales: await db.sales.insert_many(sales)
    if purchases: await db.purchases.insert_many(purchases)
    if movements: await db.inventory_movements.insert_many(movements)
    for p in products:
        await db.products.update_one({"id": p["id"]}, {"$set": {"stock": max(0, stock[p["id"]]), "updated_at": now_iso()}})
