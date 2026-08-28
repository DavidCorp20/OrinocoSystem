import os
import random
from datetime import datetime, time, timedelta, timezone

from database import db
from security import hash_password, new_id, now_iso, verify_password

DEMO_PRODUCTS = [
    ("Martillo de carpintero 16oz", "Herramientas", "Ferreimport SA", 6.5, 12.0, 8, 60),
    ("Juego de destornilladores 6 pzs", "Herramientas", "Ferreimport SA", 4.0, 8.5, 6, 45),
    ("Cinta métrica 5m", "Herramientas", "Distribuidora López", 2.2, 5.0, 6, 50),
    ("Taladro percutor 650W", "Herramientas eléctricas", "Ferreimport SA", 38.0, 65.0, 3, 20),
    ("Pintura látex blanca 1gal", "Pinturas", "Pinturas del Norte", 11.0, 19.0, 6, 40),
    ("Brocha 4 pulgadas", "Pinturas", "Pinturas del Norte", 1.1, 2.5, 10, 80),
    ("Cemento gris 42.5kg", "Construcción", "Distribuidora López", 6.8, 9.5, 10, 70),
    ("Cable THW calibre 12 (metro)", "Electricidad", "Ferreimport SA", 0.35, 0.7, 50, 300),
    ("Bombillo LED 9W", "Electricidad", "Distribuidora López", 0.9, 2.2, 15, 120),
    ("Tubería PVC 1/2 pulgada 3m", "Fontanería", "Distribuidora López", 1.6, 3.4, 8, 60),
    ("Pegamento PVC 1/4 galón", "Fontanería", "Distribuidora López", 2.8, 5.5, 5, 35),
    ("Candado de acero 50mm", "Seguridad", "Ferreimport SA", 3.2, 6.8, 5, 40),
]

DEMO_EXPENSES = [
    ("alquiler", "Alquiler del local", 400.0, 27),
    ("alquiler", "Alquiler del local", 400.0, 2),
    ("servicios", "Luz y agua", 95.0, 20),
    ("personal", "Pago ayudante (quincena)", 175.0, 16),
    ("personal", "Pago ayudante (quincena)", 175.0, 3),
    ("transporte", "Flete de mercancía", 40.0, 12),
    ("transporte", "Flete de mercancía", 40.0, 5),
    ("marketing", "Volantes promocionales", 60.0, 9),
]

PAYMENTS = ["efectivo", "efectivo", "efectivo", "tarjeta", "transferencia"]


async def seed_admin():
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        return None
    existing = await db.users.find_one({"email": email})
    if not existing:
        user = {
            "id": new_id(),
            "email": email,
            "name": "David Arenas",
            "password_hash": hash_password(password),
            "business_id": None,
            "created_at": now_iso(),
        }
        await db.users.insert_one(user)
        return user
    if not verify_password(password, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})
    return existing


async def seed_demo_business(user):
    if not user or user.get("business_id"):
        return
    rng = random.Random(7)
    bid = new_id()
    now = datetime.now(timezone.utc)

    await db.businesses.insert_one({
        "id": bid,
        "owner_id": user["id"],
        "name": "Ferretería El Candado",
        "type": "ferreteria",
        "currency": "USD",
        "created_at": (now - timedelta(days=32)).isoformat(),
    })
    await db.users.update_one({"id": user["id"]}, {"$set": {"business_id": bid}})

    products = []
    stock_map = {}
    for i, (name, cat, sup, cost, price, min_stock, initial) in enumerate(DEMO_PRODUCTS):
        pid = new_id()
        products.append({
            "id": pid, "business_id": bid, "name": name, "sku": f"P-{i + 1:04d}",
            "barcode": None, "category": cat, "brand": None, "supplier": sup,
            "purchase_price": cost, "sale_price": price, "stock": initial,
            "min_stock": min_stock, "max_stock": None, "unit": "unidad", "status": "activo",
            "created_at": (now - timedelta(days=31)).isoformat(), "updated_at": now_iso(),
        })
        stock_map[pid] = initial
    await db.products.insert_many(products)

    movements = []
    for p in products:
        movements.append({
            "id": new_id(), "business_id": bid, "product_id": p["id"], "product_name": p["name"],
            "type": "entrada", "reason": "carga_inicial", "quantity": p["stock"],
            "stock_after": p["stock"], "user_email": user["email"], "notes": None,
            "created_at": (now - timedelta(days=31)).isoformat(),
        })

    def ts(days_ago, hour):
        if days_ago <= 0:
            return (now - timedelta(minutes=rng.randint(2, 480))).isoformat()
        return datetime.combine((now - timedelta(days=days_ago)).date(), time(hour, rng.randint(0, 59)), tzinfo=timezone.utc).isoformat()

    sales_docs = []
    for days_ago in range(30, -1, -1):
        n_sales = rng.randint(3, 7) if (now - timedelta(days=days_ago)).weekday() >= 5 else rng.randint(2, 5)
        for _ in range(n_sales):
            chosen = rng.sample(products, k=rng.randint(1, 3))
            items = []
            total = cost_total = 0.0
            created = ts(days_ago, rng.randint(8, 19))
            for p in chosen:
                available = stock_map[p["id"]]
                if available <= 0:
                    continue
                qty = min(rng.randint(1, 4), available)
                if rng.random() < 0.12:
                    qty = min(qty * rng.randint(3, 6), available)
                if qty <= 0:
                    continue
                price = p["sale_price"]
                discount = round(price * qty * 0.05, 2) if rng.random() < 0.15 else 0.0
                line_total = round(price * qty - discount, 2)
                items.append({
                    "product_id": p["id"], "name": p["name"], "quantity": qty,
                    "unit_price": price, "discount": discount, "cost": p["purchase_price"],
                    "line_total": line_total,
                })
                total += line_total
                cost_total += p["purchase_price"] * qty
                stock_map[p["id"]] -= qty
                movements.append({
                    "id": new_id(), "business_id": bid, "product_id": p["id"], "product_name": p["name"],
                    "type": "salida", "reason": "venta", "quantity": qty,
                    "stock_after": stock_map[p["id"]], "user_email": user["email"],
                    "notes": "Venta (demo)", "created_at": created,
                })
            if not items:
                continue
            total = round(total, 2)
            cost_total = round(cost_total, 2)
            sales_docs.append({
                "id": new_id(), "business_id": bid, "items": items, "total": total,
                "cost_total": cost_total, "profit": round(total - cost_total, 2),
                "payment_method": rng.choice(PAYMENTS), "customer": None,
                "user_email": user["email"], "created_at": created,
            })
    if sales_docs:
        await db.sales.insert_many(sales_docs)

    purchase_docs = []
    for days_ago, picks in [(24, [6, 8, 5]), (15, [0, 4, 10]), (6, [6, 9, 2])]:
        items = []
        total = 0.0
        created = ts(days_ago, 9)
        for idx in picks:
            p = products[idx]
            qty = rng.randint(20, 45)
            line_total = round(p["purchase_price"] * qty, 2)
            items.append({
                "product_id": p["id"], "name": p["name"], "quantity": qty,
                "unit_cost": p["purchase_price"], "line_total": line_total,
            })
            total += line_total
            stock_map[p["id"]] += qty
            movements.append({
                "id": new_id(), "business_id": bid, "product_id": p["id"], "product_name": p["name"],
                "type": "entrada", "reason": "compra", "quantity": qty,
                "stock_after": stock_map[p["id"]], "user_email": user["email"],
                "notes": "Compra (demo)", "created_at": created,
            })
        purchase_docs.append({
            "id": new_id(), "business_id": bid, "supplier": p["supplier"], "items": items,
            "total": round(total, 2), "payment_method": "transferencia", "status": "completada",
            "user_email": user["email"], "created_at": created,
        })
    if purchase_docs:
        await db.purchases.insert_many(purchase_docs)

    expense_docs = [{
        "id": new_id(), "business_id": bid, "category": cat, "description": desc, "amount": amount,
        "date": (now - timedelta(days=days_ago)).date().isoformat(), "user_email": user["email"],
        "created_at": ts(days_ago, 18),
    } for cat, desc, amount, days_ago in DEMO_EXPENSES]
    await db.expenses.insert_many(expense_docs)

    # Forzar escenario de semáforo: un agotado y dos con stock bajo
    stock_map[products[10]["id"]] = 0   # Pegamento PVC agotado
    stock_map[products[3]["id"]] = 2    # Taladro bajo mínimo
    stock_map[products[4]["id"]] = 4    # Pintura bajo mínimo
    for p in products:
        await db.products.update_one({"id": p["id"]}, {"$set": {"stock": stock_map[p["id"]]}})

    if movements:
        await db.inventory_movements.insert_many(movements)


async def seed_all():
    admin = await seed_admin()
    await seed_demo_business(admin)
