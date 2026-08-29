import os
import random
from datetime import datetime, time, timedelta, timezone

from database import db
from security import hash_password, new_id, now_iso, verify_password

DEMO_PASSWORD = "Demo2026!"

FERRETERIA = {
    "name": "Ferretería El Candado",
    "type": "ferreteria",
    "products": [
        ("Martillo de carpintero 16oz", "Herramientas", "Ferreimport SA", 6.5, 12.0, 8, 60, "unidad"),
        ("Juego de destornilladores 6 pzs", "Herramientas", "Ferreimport SA", 4.0, 8.5, 6, 45, "unidad"),
        ("Cinta métrica 5m", "Herramientas", "Distribuidora López", 2.2, 5.0, 6, 50, "unidad"),
        ("Taladro percutor 650W", "Herramientas eléctricas", "Ferreimport SA", 38.0, 65.0, 3, 20, "unidad"),
        ("Pintura látex blanca 1gal", "Pinturas", "Pinturas del Norte", 11.0, 19.0, 6, 40, "unidad"),
        ("Brocha 4 pulgadas", "Pinturas", "Pinturas del Norte", 1.1, 2.5, 10, 80, "unidad"),
        ("Cemento gris 42.5kg", "Construcción", "Distribuidora López", 6.8, 9.5, 10, 70, "unidad"),
        ("Cable THW calibre 12 (metro)", "Electricidad", "Ferreimport SA", 0.35, 0.7, 50, 300, "metro"),
        ("Bombillo LED 9W", "Electricidad", "Distribuidora López", 0.9, 2.2, 15, 120, "unidad"),
        ("Tubería PVC 1/2 pulgada 3m", "Fontanería", "Distribuidora López", 1.6, 3.4, 8, 60, "unidad"),
        ("Pegamento PVC 1/4 galón", "Fontanería", "Distribuidora López", 2.8, 5.5, 5, 35, "unidad"),
        ("Candado de acero 50mm", "Seguridad", "Ferreimport SA", 3.2, 6.8, 5, 40, "unidad"),
    ],
    "expenses": [
        ("alquiler", "Alquiler del local", 400.0, 27), ("alquiler", "Alquiler del local", 400.0, 2),
        ("servicios", "Luz y agua", 95.0, 20), ("personal", "Pago ayudante (quincena)", 175.0, 16),
        ("personal", "Pago ayudante (quincena)", 175.0, 3), ("transporte", "Flete de mercancía", 40.0, 12),
        ("transporte", "Flete de mercancía", 40.0, 5), ("marketing", "Volantes promocionales", 60.0, 9),
    ],
}

KIOSCO = {
    "name": "Kiosco La Esquina",
    "type": "abarrotes",
    "products": [
        ("Harina P.A.N. blanca 1kg", "Alimentos", "Alimentos Polar CA", 0.95, 1.30, 15, 80, "unidad"),
        ("Arroz Mary 1kg", "Alimentos", "Distribuidora Makro", 1.05, 1.45, 15, 70, "unidad"),
        ("Malta Maltín Polar 330ml", "Bebidas", "Alimentos Polar CA", 0.55, 0.85, 24, 96, "unidad"),
        ("Refresco Frescolita 2L", "Bebidas", "Distribuidora Makro", 1.40, 1.95, 12, 48, "unidad"),
        ("Café Fama de América 250g", "Alimentos", "Distribuidora Makro", 3.10, 4.25, 8, 32, "unidad"),
        ("Azúcar refinada 1kg", "Alimentos", "Distribuidora Makro", 0.90, 1.25, 12, 60, "unidad"),
        ("Aceite de girasol 1L", "Alimentos", "Distribuidora Makro", 2.60, 3.40, 10, 40, "unidad"),
        ("Leche en polvo 400g", "Alimentos", "Distribuidora Makro", 4.20, 5.50, 6, 24, "unidad"),
        ("Atún en lata 140g", "Enlatados", "Distribuidora Makro", 1.15, 1.65, 10, 50, "unidad"),
        ("Pasta spaghetti 1kg", "Alimentos", "Distribuidora Makro", 1.05, 1.50, 10, 45, "unidad"),
        ("Sardina en lata 170g", "Enlatados", "Distribuidora Makro", 0.95, 1.35, 10, 40, "unidad"),
        ("Galletas María Puig (paquete)", "Dulces", "Distribuidora Makro", 0.85, 1.25, 12, 48, "unidad"),
    ],
    "expenses": [
        ("alquiler", "Alquiler del kiosco", 250.0, 26), ("servicios", "Luz", 60.0, 18),
        ("personal", "Pago cajera (quincena)", 150.0, 15), ("personal", "Pago cajera (quincena)", 150.0, 1),
        ("transporte", "Flete desde mayorista", 25.0, 10), ("otros", "Bolsas y empaques", 30.0, 7),
    ],
}

VERDULERIA = {
    "name": "Verdulería Doña Rosa",
    "type": "alimentos",
    "products": [
        ("Tomate", "Verduras", "Mercado Mayorista Coche", 0.80, 1.30, 8, 40, "kg"),
        ("Cebolla", "Verduras", "Mercado Mayorista Coche", 0.70, 1.15, 8, 40, "kg"),
        ("Papa", "Verduras", "Mercado Mayorista Coche", 0.60, 1.00, 10, 50, "kg"),
        ("Zanahoria", "Verduras", "Mercado Mayorista Coche", 0.55, 0.95, 6, 30, "kg"),
        ("Pimentón", "Verduras", "Mercado Mayorista Coche", 1.20, 1.90, 4, 15, "kg"),
        ("Yuca", "Verduras", "Mercado Mayorista Coche", 0.50, 0.85, 8, 35, "kg"),
        ("Plátano", "Frutas", "Mercado Mayorista Coche", 0.65, 1.10, 6, 25, "kg"),
        ("Cambur", "Frutas", "Mercado Mayorista Coche", 0.75, 1.25, 6, 30, "kg"),
        ("Lechosa", "Frutas", "Mercado Mayorista Coche", 0.90, 1.50, 3, 12, "kg"),
        ("Aguacate", "Frutas", "Mercado Mayorista Coche", 1.40, 2.30, 4, 15, "unidad"),
        ("Limón", "Frutas", "Mercado Mayorista Coche", 0.60, 1.00, 5, 20, "kg"),
        ("Cilantro (manojo)", "Hierbas", "Mercado Mayorista Coche", 0.30, 0.60, 6, 30, "manojo"),
    ],
    "expenses": [
        ("alquiler", "Puesto en el mercado", 180.0, 25), ("servicios", "Luz y agua", 45.0, 19),
        ("transporte", "Viaje al mayorista", 35.0, 14), ("transporte", "Viaje al mayorista", 35.0, 4),
        ("personal", "Ayudante semanal", 60.0, 8), ("otros", "Bolsas y bandejas", 20.0, 6),
    ],
}

REPUESTOS = {
    "name": "Repuestos El Pistón",
    "type": "otro",
    "products": [
        ("Filtro de aceite sincrónico", "Filtros", "Importadora AutoPartes", 4.50, 7.90, 6, 25, "unidad"),
        ("Filtro de aire", "Filtros", "Importadora AutoPartes", 5.20, 9.00, 5, 20, "unidad"),
        ("Pastillas de freno delanteras", "Frenos", "Distribuidora El Motor", 11.00, 18.50, 4, 16, "juego"),
        ("Líquido de frenos DOT3", "Frenos", "Distribuidora El Motor", 2.80, 4.90, 6, 24, "unidad"),
        ("Bujía NGK", "Encendido", "Importadora AutoPartes", 1.90, 3.40, 8, 40, "unidad"),
        ("Correa de distribución", "Motor", "Distribuidora El Motor", 8.50, 14.90, 3, 12, "unidad"),
        ("Aceite 20W-50 (galón)", "Lubricantes", "Distribuidora El Motor", 13.50, 19.90, 6, 24, "unidad"),
        ("Batería 12V 600A", "Eléctrico", "Importadora AutoPartes", 52.00, 74.90, 2, 8, "unidad"),
        ("Bombillo H4 12V", "Eléctrico", "Importadora AutoPartes", 2.20, 3.90, 8, 30, "unidad"),
        ("Espejo retrovisor lateral", "Carrocería", "Distribuidora El Motor", 9.80, 16.50, 3, 10, "unidad"),
        ("Limpiaparabrisas 22 pulgadas", "Carrocería", "Distribuidora El Motor", 3.10, 5.50, 6, 22, "unidad"),
        ("Refrigerante verde (galón)", "Lubricantes", "Distribuidora El Motor", 6.40, 10.90, 5, 20, "unidad"),
    ],
    "expenses": [
        ("alquiler", "Alquiler del local", 350.0, 27), ("servicios", "Luz e internet", 80.0, 21),
        ("personal", "Pago vendedor (quincena)", 250.0, 16), ("personal", "Pago vendedor (quincena)", 250.0, 2),
        ("marketing", "Publicidad Instagram", 40.0, 11),
    ],
}

PAYMENTS = ["efectivo", "efectivo", "efectivo", "tarjeta", "transferencia", "pago móvil"]


async def _ensure_user(email: str, name: str, password: str, role="propietario", platform_role=None):
    existing = await db.users.find_one({"email": email})
    if not existing:
        user = {
            "id": new_id(), "email": email, "name": name, "password_hash": hash_password(password),
            "role": role, "platform_role": platform_role, "business_id": None, "created_at": now_iso(),
        }
        await db.users.insert_one(user)
        return user
    updates = {}
    if not verify_password(password, existing["password_hash"]):
        updates["password_hash"] = hash_password(password)
    if existing.get("role") != role:
        updates["role"] = role
    if existing.get("platform_role") != platform_role:
        updates["platform_role"] = platform_role
    if updates:
        await db.users.update_one({"email": email}, {"$set": updates})
    return await db.users.find_one({"email": email})


async def _seed_profile(user, profile, rng_seed):
    if not user or user.get("business_id"):
        return
    rng = random.Random(rng_seed)
    bid = new_id()
    now = datetime.now(timezone.utc)

    await db.businesses.insert_one({
        "id": bid, "owner_id": user["id"], "name": profile["name"], "type": profile["type"],
        "currency": "USD", "active": True, "bcv_mode": "auto", "bcv_rate": None,
        "rif": f"J-{rng.randint(10000000, 49999999)}-{rng.randint(0, 9)}",
        "address": "Venezuela", "phone": None,
        "created_at": (now - timedelta(days=32)).isoformat(),
    })
    await db.users.update_one({"id": user["id"]}, {"$set": {"business_id": bid}})

    products = []
    stock_map = {}
    for i, (name, cat, sup, cost, price, min_stock, initial, unit) in enumerate(profile["products"]):
        pid = new_id()
        products.append({
            "id": pid, "business_id": bid, "name": name, "sku": f"P-{i + 1:04d}",
            "barcode": f"775{rng.randint(1000000000, 9999999999)}",
            "category": cat, "brand": None, "supplier": sup,
            "purchase_price": cost, "sale_price": price, "stock": initial,
            "min_stock": min_stock, "max_stock": None, "unit": unit, "status": "activo",
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
                "payment_method": rng.choice(PAYMENTS), "customer_name": None, "customer_rif": None,
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
            "id": new_id(), "business_id": bid, "supplier": p["supplier"], "supplier_rif": None,
            "items": items, "total": round(total, 2), "payment_method": "transferencia",
            "status": "completada", "user_email": user["email"], "created_at": created,
        })
    if purchase_docs:
        await db.purchases.insert_many(purchase_docs)

    expense_docs = [{
        "id": new_id(), "business_id": bid, "category": cat, "description": desc, "amount": amount,
        "date": (now - timedelta(days=days_ago)).date().isoformat(), "user_email": user["email"],
        "created_at": ts(days_ago, 18),
    } for cat, desc, amount, days_ago in profile["expenses"]]
    await db.expenses.insert_many(expense_docs)

    # Escenario de semáforo: un agotado y dos con stock bajo
    stock_map[products[10]["id"]] = 0
    stock_map[products[3]["id"]] = 2
    stock_map[products[4]["id"]] = 4
    for p in products:
        await db.products.update_one({"id": p["id"]}, {"$set": {"stock": stock_map[p["id"]]}})

    if movements:
        await db.inventory_movements.insert_many(movements)


async def _drop_business_data(business_ids):
    if not business_ids:
        return
    await db.products.delete_many({"business_id": {"$in": business_ids}})
    await db.sales.delete_many({"business_id": {"$in": business_ids}})
    await db.purchases.delete_many({"business_id": {"$in": business_ids}})
    await db.expenses.delete_many({"business_id": {"$in": business_ids}})
    await db.inventory_movements.delete_many({"business_id": {"$in": business_ids}})
    await db.businesses.delete_many({"id": {"$in": business_ids}})


async def _purge_owner_stale_businesses(owner_id: str, expected_name: str | None = None):
    if not owner_id:
        return
    query = {"owner_id": owner_id}
    if expected_name:
        query["name"] = {"$ne": expected_name}
    stale_businesses = await db.businesses.find(query, {"id": 1, "name": 1}).to_list(length=None)
    stale_ids = [b["id"] for b in stale_businesses if b.get("id")]
    if stale_ids:
        await _drop_business_data(stale_ids)


async def _ensure_demo_business(user, profile, rng_seed, *, force_rebuild=False):
    if not user:
        return None

    await _purge_owner_stale_businesses(user["id"], profile["name"])

    business_query = {"owner_id": user["id"]}
    if profile["name"]:
        business_query["name"] = profile["name"]

    existing_business = await db.businesses.find_one(business_query)
    if not existing_business:
        existing_business = await db.businesses.find_one({"owner_id": user["id"]})

    if existing_business and existing_business.get("name") != profile["name"]:
        await db.businesses.update_one({"id": existing_business["id"]}, {"$set": {"name": profile["name"]}})
        existing_business = await db.businesses.find_one({"id": existing_business["id"]})

    if not existing_business:
        bid = new_id()
        existing_business = {
            "id": bid,
            "owner_id": user["id"],
            "name": profile["name"],
            "type": profile["type"],
            "currency": "USD",
            "active": True,
            "bcv_mode": "auto",
            "bcv_rate": None,
            "rif": None,
            "address": "Venezuela",
            "phone": None,
            "created_at": now_iso(),
        }
        await db.businesses.insert_one(existing_business)
    else:
        bid = existing_business["id"]
        await db.businesses.update_one(
            {"id": bid},
            {"$set": {
                "owner_id": user["id"],
                "name": profile["name"],
                "type": profile["type"],
                "currency": "USD",
                "active": True,
                "bcv_mode": existing_business.get("bcv_mode", "auto"),
                "bcv_rate": existing_business.get("bcv_rate"),
                "address": existing_business.get("address", "Venezuela"),
                "phone": existing_business.get("phone"),
            }}
        )

    await db.users.update_one({"id": user["id"]}, {"$set": {"business_id": bid}})

    if force_rebuild:
        await db.products.delete_many({"business_id": bid})
        await db.sales.delete_many({"business_id": bid})
        await db.purchases.delete_many({"business_id": bid})
        await db.expenses.delete_many({"business_id": bid})
        await db.inventory_movements.delete_many({"business_id": bid})

    rng = random.Random(rng_seed)
    now = datetime.now(timezone.utc)

    if await db.products.count_documents({"business_id": bid}) == 0 or force_rebuild:
        products = []
        for i, (name, cat, sup, cost, price, min_stock, initial, unit) in enumerate(profile["products"]):
            pid = new_id()
            products.append({
                "id": pid,
                "business_id": bid,
                "name": name,
                "sku": f"P-{i + 1:04d}",
                "barcode": f"775{rng.randint(1000000000, 9999999999)}",
                "category": cat,
                "brand": None,
                "supplier": sup,
                "purchase_price": cost,
                "sale_price": price,
                "stock": initial,
                "min_stock": min_stock,
                "max_stock": None,
                "unit": unit,
                "status": "activo",
                "created_at": (now - timedelta(days=31)).isoformat(),
                "updated_at": now_iso(),
            })
        if products:
            await db.products.insert_many(products)

        # Build deterministic movement history for the seed
        stock_map = {p["id"]: p["stock"] for p in products}
        movements = []
        for p in products:
            movements.append({
                "id": new_id(),
                "business_id": bid,
                "product_id": p["id"],
                "product_name": p["name"],
                "type": "entrada",
                "reason": "carga_inicial",
                "quantity": p["stock"],
                "stock_after": p["stock"],
                "user_email": user["email"],
                "notes": None,
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
                        "product_id": p["id"],
                        "name": p["name"],
                        "quantity": qty,
                        "unit_price": price,
                        "discount": discount,
                        "cost": p["purchase_price"],
                        "line_total": line_total,
                    })
                    total += line_total
                    cost_total += p["purchase_price"] * qty
                    stock_map[p["id"]] -= qty
                    movements.append({
                        "id": new_id(),
                        "business_id": bid,
                        "product_id": p["id"],
                        "product_name": p["name"],
                        "type": "salida",
                        "reason": "venta",
                        "quantity": qty,
                        "stock_after": stock_map[p["id"]],
                        "user_email": user["email"],
                        "notes": "Venta (demo)",
                        "created_at": created,
                    })
                if not items:
                    continue
                total = round(total, 2)
                cost_total = round(cost_total, 2)
                sales_docs.append({
                    "id": new_id(),
                    "business_id": bid,
                    "items": items,
                    "total": total,
                    "cost_total": cost_total,
                    "profit": round(total - cost_total, 2),
                    "payment_method": rng.choice(PAYMENTS),
                    "customer_name": None,
                    "customer_rif": None,
                    "user_email": user["email"],
                    "created_at": created,
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
                    "product_id": p["id"],
                    "name": p["name"],
                    "quantity": qty,
                    "unit_cost": p["purchase_price"],
                    "line_total": line_total,
                })
                total += line_total
                stock_map[p["id"]] += qty
                movements.append({
                    "id": new_id(),
                    "business_id": bid,
                    "product_id": p["id"],
                    "product_name": p["name"],
                    "type": "entrada",
                    "reason": "compra",
                    "quantity": qty,
                    "stock_after": stock_map[p["id"]],
                    "user_email": user["email"],
                    "notes": "Compra (demo)",
                    "created_at": created,
                })
            purchase_docs.append({
                "id": new_id(),
                "business_id": bid,
                "supplier": products[0]["supplier"],
                "supplier_rif": None,
                "items": items,
                "total": round(total, 2),
                "payment_method": "transferencia",
                "status": "completada",
                "user_email": user["email"],
                "created_at": created,
            })
        if purchase_docs:
            await db.purchases.insert_many(purchase_docs)

        expense_docs = [{
            "id": new_id(),
            "business_id": bid,
            "category": cat,
            "description": desc,
            "amount": amount,
            "date": (now - timedelta(days=days_ago)).date().isoformat(),
            "user_email": user["email"],
            "created_at": ts(days_ago, 18),
        } for cat, desc, amount, days_ago in profile["expenses"]]
        if expense_docs:
            await db.expenses.insert_many(expense_docs)

        # Ensure demo stock conditions expected by dashboard tests
        stock_map[products[10]["id"]] = 0
        stock_map[products[3]["id"]] = 2
        stock_map[products[4]["id"]] = 4
        for p in products:
            await db.products.update_one({"id": p["id"]}, {"$set": {"stock": stock_map[p["id"]], "updated_at": now_iso()}})
        if movements:
            await db.inventory_movements.insert_many(movements)

    # Backfill idempotente: negocios antiguos sin 'active' y productos sin código de barras
    await db.businesses.update_many({"active": {"$exists": False}}, {"$set": {"active": True}})
    rng = random.Random(99)
    async for p in db.products.find({"barcode": None}, {"id": 1}):
        await db.products.update_one({"id": p["id"]}, {"$set": {"barcode": f"775{rng.randint(1000000000, 9999999999)}"}})

    return existing_business


async def seed_all():
    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if admin_email and admin_password:
        admin = await _ensure_user(admin_email, "David Arenas", admin_password, role="propietario", platform_role="superadmin")
        await _purge_owner_stale_businesses(admin["id"], FERRETERIA["name"])
        await _ensure_demo_business(admin, FERRETERIA, 7)

    demo_profiles = [
        ("kiosco.demo@controlpyme.com", "Luis Martínez", KIOSCO, 21),
        ("verduleria.demo@controlpyme.com", "Rosa Jiménez", VERDULERIA, 33),
        ("repuestos.demo@controlpyme.com", "Carlos Pirela", REPUESTOS, 47),
    ]
    for email, name, profile, rng_seed in demo_profiles:
        user = await _ensure_user(email, name, DEMO_PASSWORD)
        await _purge_owner_stale_businesses(user["id"], profile["name"])
        await _ensure_demo_business(user, profile, rng_seed)

    # Backfill idempotente: negocios antiguos sin 'active' y productos sin código de barras
    await db.businesses.update_many({"active": {"$exists": False}}, {"$set": {"active": True}})
    rng = random.Random(99)
    async for p in db.products.find({"barcode": None}, {"id": 1}):
        await db.products.update_one({"id": p["id"]}, {"$set": {"barcode": f"775{rng.randint(1000000000, 9999999999)}"}})


async def reset_demo_state():
    app_env = os.environ.get("APP_ENV", "development").strip().lower()
    if app_env not in {"development", "testing"}:
        raise RuntimeError("reset_demo_state() solo está permitido en development/testing.")
    if os.environ.get("ALLOW_DEV_RESET", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        raise RuntimeError("reset_demo_state() requiere ALLOW_DEV_RESET=1 para ejecutarse explícitamente.")

    expected_demo_names = {
        FERRETERIA["name"],
        KIOSCO["name"],
        VERDULERIA["name"],
        REPUESTOS["name"],
    }

    stale_businesses = await db.businesses.find({"name": {"$nin": list(expected_demo_names)}}, {"id": 1, "owner_id": 1, "name": 1}).to_list(length=None)
    stale_business_ids = [b["id"] for b in stale_businesses if b.get("name") not in {"", None}]
    if stale_business_ids:
        await db.products.delete_many({"business_id": {"$in": stale_business_ids}})
        await db.sales.delete_many({"business_id": {"$in": stale_business_ids}})
        await db.purchases.delete_many({"business_id": {"$in": stale_business_ids}})
        await db.expenses.delete_many({"business_id": {"$in": stale_business_ids}})
        await db.inventory_movements.delete_many({"business_id": {"$in": stale_business_ids}})
        await db.businesses.delete_many({"id": {"$in": stale_business_ids}})

    demo_emails = [
        os.environ.get("ADMIN_EMAIL"),
        "kiosco.demo@controlpyme.com",
        "verduleria.demo@controlpyme.com",
        "repuestos.demo@controlpyme.com",
    ]
    demo_emails = [email for email in demo_emails if email]

    for collection_name in ["sales", "purchases", "expenses", "products", "inventory_movements", "assistant_messages", "login_attempts"]:
        await getattr(db, collection_name).delete_many({})

    user_ids = [u["id"] async for u in db.users.find({"email": {"$in": demo_emails}}, {"id": 1})]
    if user_ids:
        await db.businesses.delete_many({"owner_id": {"$in": user_ids}})
    await db.users.delete_many({"email": {"$in": demo_emails}})

    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if admin_email and admin_password:
        admin = await _ensure_user(admin_email, "David Arenas", admin_password, role="propietario", platform_role="superadmin")
        await _ensure_demo_business(admin, FERRETERIA, 7, force_rebuild=True)

    for email, name, profile, rng_seed in [
        ("kiosco.demo@controlpyme.com", "Luis Martínez", KIOSCO, 21),
        ("verduleria.demo@controlpyme.com", "Rosa Jiménez", VERDULERIA, 33),
        ("repuestos.demo@controlpyme.com", "Carlos Pirela", REPUESTOS, 47),
    ]:
        user = await _ensure_user(email, name, DEMO_PASSWORD)
        await _ensure_demo_business(user, profile, rng_seed, force_rebuild=True)

    await db.businesses.update_many({"active": {"$exists": False}}, {"$set": {"active": True}})
    await db.users.create_index("email", unique=True)

    remaining_names = [b["name"] async for b in db.businesses.find({"name": {"$in": list(expected_demo_names)}}, {"name": 1})]
    if sorted(set(remaining_names)) != sorted(list(expected_demo_names)):
        raise RuntimeError(f"No quedó el estado demo esperado: {sorted(set(remaining_names))}")
