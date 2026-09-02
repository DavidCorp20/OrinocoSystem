"""Optional production-safe demo account with a deliberately stable business history."""
import os
import random
from datetime import datetime, timedelta, timezone

from database import db
from security import hash_password, new_id, now_iso

DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@cuadrapp.com").strip().lower()
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "Demo2026!")
DEMO_BUSINESS = "Repuestos El Pistón Demo"

PRODUCTS = [
    ("Aceite 20W-50 (galón)", "Lubricantes", 13.50, 19.90, 8, 60),
    ("Bujía NGK", "Encendido", 1.90, 3.40, 10, 80),
    ("Bombillo H4 12V", "Eléctrico", 2.20, 3.90, 10, 70),
    ("Filtro de aceite", "Filtros", 4.50, 7.90, 8, 50),
    ("Filtro de aire", "Filtros", 5.20, 9.00, 6, 45),
    ("Líquido de frenos DOT3", "Frenos", 2.80, 4.90, 8, 50),
    ("Pastillas de freno delanteras", "Frenos", 11.00, 18.50, 5, 35),
    ("Refrigerante verde (galón)", "Lubricantes", 6.40, 10.90, 6, 45),
    ("Limpiaparabrisas 22 pulgadas", "Carrocería", 3.10, 5.50, 7, 40),
    ("Batería 12V 600A", "Eléctrico", 52.00, 74.90, 3, 15),
]


def _ts(day, hour, minute):
    return datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).replace(hour=hour, minute=minute).isoformat()


async def seed_demo_account():
    """Create one demo tenant once. Re-running never duplicates its data."""
    if os.getenv("DEMO_SEED_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return

    user = await db.users.find_one({"email": DEMO_EMAIL})
    if user and user.get("business_id"):
        return

    if not user:
        user = {
            "id": new_id(), "email": DEMO_EMAIL, "name": "Usuario Demo",
            "password_hash": hash_password(DEMO_PASSWORD), "role": "propietario",
            "platform_role": None, "business_id": None, "created_at": now_iso(),
        }
        await db.users.insert_one(user)

    business = await db.businesses.find_one({"owner_id": user["id"], "name": DEMO_BUSINESS})
    if not business:
        bid = new_id()
        business = {
            "id": bid, "owner_id": user["id"], "name": DEMO_BUSINESS, "type": "repuestos",
            "currency": "USD", "active": True, "bcv_mode": "auto", "bcv_rate": None,
            "rif": "J-00000000-0", "address": "Venezuela", "phone": None,
            "is_demo": True, "created_at": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
        }
        await db.businesses.insert_one(business)
    else:
        bid = business["id"]

    await db.users.update_one({"id": user["id"]}, {"$set": {"business_id": bid, "is_demo": True}})

    if await db.products.count_documents({"business_id": bid}) > 0:
        return

    rng = random.Random(20260901)
    now = datetime.now(timezone.utc)
    products = []
    stock = {}
    for i, (name, category, cost, price, minimum, initial) in enumerate(PRODUCTS, 1):
        pid = new_id()
        products.append({
            "id": pid, "business_id": bid, "name": name, "sku": f"DEMO-{i:04d}",
            "barcode": f"775{rng.randint(1000000000, 9999999999)}", "category": category,
            "brand": None, "supplier": "Distribuidora AutoPartes", "purchase_price": cost,
            "sale_price": price, "stock": initial, "min_stock": minimum, "max_stock": initial * 2,
            "unit": "unidad", "status": "activo", "created_at": (now - timedelta(days=31)).isoformat(),
            "updated_at": now_iso(),
        })
        stock[pid] = initial
    await db.products.insert_many(products)

    movements = []
    for p in products:
        movements.append({"id": new_id(), "business_id": bid, "product_id": p["id"], "product_name": p["name"],
                          "type": "entrada", "reason": "carga_inicial", "quantity": p["stock"],
                          "stock_after": p["stock"], "user_email": DEMO_EMAIL, "notes": "Carga inicial demo",
                          "created_at": (now - timedelta(days=31)).isoformat()})

    # Stable demand: the same mix every day with only small random variation.
    demand = [5, 3, 3, 2, 2, 2, 1, 1, 1, 0.25]
    sales = []
    for days_ago in range(30, -1, -1):
        day = (now - timedelta(days=days_ago)).date()
        daily_sales = 5 if day.weekday() < 5 else 4
        for sale_no in range(daily_sales):
            items = []
            total = 0.0
            cost_total = 0.0
            # Rotate products while preserving a stable product mix.
            base = (days_ago + sale_no * 2) % len(products)
            indexes = [(base + j) % len(products) for j in range(2)]
            for idx in indexes:
                p = products[idx]
                qty = max(1, int(round(demand[idx] * (0.85 + rng.random() * 0.30))))
                if idx == 9:
                    qty = 1 if rng.random() < 0.25 else 0
                if qty <= 0:
                    continue
                line_total = round(p["sale_price"] * qty, 2)
                items.append({"product_id": p["id"], "name": p["name"], "quantity": qty,
                              "unit_price": p["sale_price"], "discount": 0.0,
                              "cost": p["purchase_price"], "line_total": line_total})
                total += line_total
                cost_total += p["purchase_price"] * qty
                stock[p["id"]] -= qty
                movements.append({"id": new_id(), "business_id": bid, "product_id": p["id"], "product_name": p["name"],
                                  "type": "salida", "reason": "venta", "quantity": qty,
                                  "stock_after": stock[p["id"]], "user_email": DEMO_EMAIL,
                                  "notes": "Venta demo", "created_at": _ts(day, 9 + sale_no * 2, rng.randint(0, 59))})
            if items:
                sales.append({"id": new_id(), "business_id": bid, "items": items, "total": round(total, 2),
                              "cost_total": round(cost_total, 2), "profit": round(total - cost_total, 2),
                              "payment_method": ["efectivo", "tarjeta", "transferencia"][sale_no % 3],
                              "customer_name": None, "customer_rif": None, "user_email": DEMO_EMAIL,
                              "created_at": _ts(day, 9 + sale_no * 2, rng.randint(0, 59))})

    # Small recurring purchases keep stock healthy and demonstrate replenishment.
    purchases = []
    for days_ago in (24, 14, 4):
        day = (now - timedelta(days=days_ago)).date()
        items = []
        total = 0.0
        for idx in range(0, len(products), 2):
            p = products[idx]
            qty = 18 if idx < 6 else 10
            line = round(p["purchase_price"] * qty, 2)
            stock[p["id"]] += qty
            total += line
            items.append({"product_id": p["id"], "name": p["name"], "quantity": qty,
                          "unit_cost": p["purchase_price"], "line_total": line})
            movements.append({"id": new_id(), "business_id": bid, "product_id": p["id"], "product_name": p["name"],
                              "type": "entrada", "reason": "compra", "quantity": qty,
                              "stock_after": stock[p["id"]], "user_email": DEMO_EMAIL,
                              "notes": "Compra demo", "created_at": _ts(day, 8, 30)})
        purchases.append({"id": new_id(), "business_id": bid, "supplier": "Distribuidora AutoPartes",
                          "supplier_rif": None, "items": items, "total": round(total, 2),
                          "payment_method": "transferencia", "status": "completada",
                          "user_email": DEMO_EMAIL, "created_at": _ts(day, 8, 30)})

    expenses = []
    for description, amount, days_ago in [("Alquiler del local", 350, 27), ("Luz e internet", 80, 21),
                                          ("Pago vendedor", 250, 16), ("Pago vendedor", 250, 2),
                                          ("Publicidad", 40, 11)]:
        expenses.append({"id": new_id(), "business_id": bid, "category": "operativo", "description": description,
                         "amount": amount, "date": (now - timedelta(days=days_ago)).date().isoformat(),
                         "user_email": DEMO_EMAIL, "created_at": (now - timedelta(days=days_ago)).isoformat()})

    if sales: await db.sales.insert_many(sales)
    if purchases: await db.purchases.insert_many(purchases)
    if expenses: await db.expenses.insert_many(expenses)
    if movements: await db.inventory_movements.insert_many(movements)
    for p in products:
        await db.products.update_one({"id": p["id"]}, {"$set": {"stock": max(0, stock[p["id"]]), "updated_at": now_iso()}})
