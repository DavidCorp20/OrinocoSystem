import asyncio
import os
import random
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from database import db
from security import hash_password, new_id, now_iso

VERSION = 1
PASSWORD = os.getenv("DEMO_PASSWORD")
if not PASSWORD:
    raise RuntimeError("DEMO_PASSWORD is required to bootstrap showcase users")

PROFILES = [
    {
        "email": "cafe.demo@platia.app", "name": "María González", "business": "Café Aroma Caracas", "type": "cafeteria",
        "mode": "winner", "seed": 101,
        "products": [
            ("Café espresso 250g", "Café", 4.2, 8.5), ("Café molido 500g", "Café", 7.5, 14.9), ("Cappuccino", "Bebidas", 0.9, 3.8),
            ("Latte", "Bebidas", 1.0, 4.2), ("Americano", "Bebidas", 0.5, 2.8), ("Chocolate caliente", "Bebidas", 0.8, 3.5),
            ("Té verde", "Bebidas", 0.45, 2.5), ("Croissant", "Panadería", 0.8, 3.2), ("Brownie", "Panadería", 0.7, 3.5),
            ("Cheesecake porción", "Repostería", 1.7, 5.9), ("Galleta chips", "Repostería", 0.35, 1.8), ("Sandwich de pollo", "Comida", 2.4, 7.5),
            ("Club house", "Comida", 3.2, 9.5), ("Ensalada César", "Comida", 2.1, 7.2), ("Jugo natural", "Bebidas", 0.7, 3.8),
            ("Agua 600ml", "Bebidas", 0.25, 1.5), ("Refresco lata", "Bebidas", 0.5, 2.0), ("Syrup vainilla", "Insumos", 3.5, 7.9),
            ("Leche entera 1L", "Insumos", 1.2, 2.8), ("Leche de almendras 1L", "Insumos", 2.4, 4.9),
        ],
        "expenses": [("alquiler", "Alquiler del local", 650), ("servicios", "Luz, agua e internet", 145), ("personal", "Nómina", 780), ("marketing", "Instagram y promociones", 120), ("otros", "Insumos y limpieza", 85)],
    },
    {
        "email": "barber.demo@platia.app", "name": "Carlos Rivas", "business": "Barbería Central Caracas", "type": "barberia",
        "mode": "winner", "seed": 202,
        "products": [
            ("Cera mate 100g", "Styling", 3.5, 9.9), ("Pomada clásica", "Styling", 4.0, 11.5), ("Gel profesional", "Styling", 2.8, 8.5),
            ("Shampoo barber 500ml", "Cuidado", 4.5, 10.9), ("Acondicionador 500ml", "Cuidado", 4.2, 10.5), ("Aceite para barba", "Barba", 3.8, 12.5),
            ("Bálsamo para barba", "Barba", 4.2, 13.5), ("After shave", "Cuidado", 3.1, 9.9), ("Perfume barber", "Fragancias", 8.0, 19.9),
            ("Navajas pack 10", "Herramientas", 2.5, 7.5), ("Peine carbono", "Herramientas", 1.2, 4.5), ("Cepillo barba", "Barba", 2.0, 6.9),
            ("Capa profesional", "Accesorios", 2.8, 7.9), ("Toalla negra", "Accesorios", 1.5, 4.9), ("Máquina spray desinfectante", "Higiene", 5.0, 12.9),
            ("Polvo texturizador", "Styling", 4.5, 12.9), ("Crema definidora", "Styling", 3.8, 10.9), ("Mascarilla capilar", "Cuidado", 3.2, 9.5),
            ("Shampoo anticaspa", "Cuidado", 4.8, 11.9), ("Kit cuidado barba", "Barba", 9.0, 24.9),
        ],
        "expenses": [("alquiler", "Alquiler del local", 700), ("servicios", "Servicios", 110), ("personal", "Comisiones barberos", 900), ("marketing", "Publicidad digital", 150), ("otros", "Limpieza y consumibles", 95)],
    },
    {
        "email": "moda.demo@platia.app", "name": "Ana Pérez", "business": "Moda Urbana Caracas", "type": "tienda_ropa",
        "mode": "red", "seed": 303,
        "products": [
            ("Franela básica blanca", "Franelas", 12, 10), ("Franela básica negra", "Franelas", 12, 10), ("Jean clásico", "Pantalones", 28, 24),
            ("Jean skinny", "Pantalones", 30, 25), ("Camisa manga corta", "Camisas", 18, 15), ("Camisa manga larga", "Camisas", 21, 17),
            ("Vestido casual", "Vestidos", 32, 26), ("Vestido noche", "Vestidos", 45, 35), ("Falda denim", "Faldas", 22, 18),
            ("Short deportivo", "Shorts", 16, 13), ("Pantalón cargo", "Pantalones", 29, 23), ("Hoodie", "Abrigos", 34, 27),
            ("Chaqueta denim", "Abrigos", 42, 34), ("Suéter básico", "Abrigos", 24, 19), ("Gorra urbana", "Accesorios", 9, 7),
            ("Cinturón cuero", "Accesorios", 14, 11), ("Bolso casual", "Accesorios", 26, 20), ("Cartera", "Accesorios", 18, 14),
            ("Zapatillas urbanas", "Calzado", 48, 39), ("Sandalias", "Calzado", 22, 18),
        ],
        "expenses": [("alquiler", "Alquiler del local", 1200), ("servicios", "Servicios", 180), ("personal", "Nómina", 1100), ("marketing", "Publicidad", 450), ("otros", "Bolsas y empaques", 180), ("otros", "Pérdidas y descuentos", 350)],
    },
]

def image_url(name, seed):
    return f"https://loremflickr.com/600/600/{quote_plus(name.replace(' ', ','))}?lock={seed}"

def ts(days_ago, hour, rng):
    now = datetime.now(timezone.utc)
    day = (now - timedelta(days=days_ago)).date()
    return datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).replace(hour=hour, minute=rng.randint(0, 59)).isoformat()

async def seed_profile(profile):
    user = await db.users.find_one({"email": profile["email"]})
    if not user:
        user = {"id": new_id(), "email": profile["email"], "name": profile["name"], "password_hash": hash_password(PASSWORD), "role": "propietario", "platform_role": None, "business_id": None, "approved": True, "approved_at": now_iso(), "approved_by": "demo_seed", "created_at": now_iso()}
        await db.users.insert_one(user)
    else:
        await db.users.update_one({"email": profile["email"]}, {"$set": {"password_hash": hash_password(PASSWORD), "name": profile["name"], "role": "propietario", "approved": True, "approved_at": now_iso(), "approved_by": "demo_seed"}})
        user = await db.users.find_one({"email": profile["email"]})

    existing = await db.businesses.find_one({"owner_id": user["id"], "name": profile["business"]})
    if existing and existing.get("demo_showcase_version") == VERSION:
        return
    old = await db.businesses.find_one({"owner_id": user["id"]})
    if old:
        bid = old["id"]
        for c in ("products", "sales", "purchases", "expenses", "inventory_movements"):
            await getattr(db, c).delete_many({"business_id": bid})
        await db.businesses.delete_one({"id": bid})
    bid = new_id()
    now = datetime.now(timezone.utc)
    await db.businesses.insert_one({"id": bid, "owner_id": user["id"], "name": profile["business"], "type": profile["type"], "currency": "USD", "active": True, "bcv_mode": "auto", "bcv_rate": None, "rif": "J-00000000-0", "address": "Caracas, Venezuela", "phone": None, "is_demo": True, "demo_showcase_version": VERSION, "created_at": (now - timedelta(days=45)).isoformat()})
    await db.users.update_one({"id": user["id"]}, {"$set": {"business_id": bid, "is_demo": True}})

    rng = random.Random(profile["seed"])
    products = []
    for i, (name, cat, cost, price) in enumerate(profile["products"], 1):
        pid = new_id(); initial = 80 if profile["mode"] == "red" else 60
        products.append({"id": pid, "business_id": bid, "name": name, "sku": f"DEMO-{profile['seed']}-{i:03d}", "barcode": f"775{rng.randint(1000000000,9999999999)}", "category": cat, "brand": "Demo", "supplier": "Distribuidora Demo", "purchase_price": cost, "sale_price": price, "stock": initial, "min_stock": max(5, initial // 5), "max_stock": initial * 2, "unit": "unidad", "status": "activo", "image_url": image_url(name, profile["seed"] + i), "created_at": (now - timedelta(days=45)).isoformat(), "updated_at": now_iso()})
    await db.products.insert_many(products)

    stock = {p["id"]: p["stock"] for p in products}; movements = []; sales = []; purchases = []
    for p in products:
        movements.append({"id": new_id(), "business_id": bid, "product_id": p["id"], "product_name": p["name"], "type": "entrada", "reason": "carga_inicial", "quantity": p["stock"], "stock_after": p["stock"], "user_email": profile["email"], "notes": "Catálogo demo PLATIA", "created_at": (now - timedelta(days=45)).isoformat()})

    for days_ago in range(44, -1, -1):
        count = rng.randint(7, 11) if profile["mode"] == "winner" else rng.randint(4, 7)
        for n in range(count):
            picks = rng.sample(products, 2 if rng.random() < 0.7 else 1); items=[]; total=0; cost_total=0
            for p in picks:
                qty = rng.randint(1, 4)
                if stock[p["id"]] < qty: continue
                line = round(p["sale_price"] * qty, 2); c = round(p["purchase_price"] * qty, 2)
                items.append({"product_id": p["id"], "name": p["name"], "quantity": qty, "unit_price": p["sale_price"], "discount": 0, "cost": p["purchase_price"], "line_total": line}); total += line; cost_total += c; stock[p["id"]] -= qty
                movements.append({"id": new_id(), "business_id": bid, "product_id": p["id"], "product_name": p["name"], "type": "salida", "reason": "venta", "quantity": qty, "stock_after": stock[p["id"]], "user_email": profile["email"], "notes": "Venta demo", "created_at": ts(days_ago, rng.randint(8,19), rng)})
            if items:
                created = ts(days_ago, rng.randint(8,19), rng); sales.append({"id": new_id(), "business_id": bid, "items": items, "total": round(total,2), "cost_total": round(cost_total,2), "profit": round(total-cost_total,2), "payment_method": rng.choice(["efectivo","tarjeta","transferencia","pago móvil"]), "customer_name": rng.choice(["Cliente mostrador","Cliente frecuente","Venta online",None]), "customer_rif": None, "user_email": profile["email"], "created_at": created})

    for days_ago in (38, 25, 12, 4):
        picks = rng.sample(products, 6); items=[]; total=0
        for p in picks:
            qty = rng.randint(15,30); stock[p["id"]] += qty; line=round(p["purchase_price"]*qty,2); total += line
            items.append({"product_id":p["id"],"name":p["name"],"quantity":qty,"unit_cost":p["purchase_price"],"line_total":line})
            movements.append({"id":new_id(),"business_id":bid,"product_id":p["id"],"product_name":p["name"],"type":"entrada","reason":"compra","quantity":qty,"stock_after":stock[p["id"]],"user_email":profile["email"],"notes":"Reposición demo","created_at":ts(days_ago,9,rng)})
        purchases.append({"id":new_id(),"business_id":bid,"supplier":"Distribuidora Demo","supplier_rif":None,"items":items,"total":round(total,2),"payment_method":"transferencia","status":"completada","user_email":profile["email"],"created_at":ts(days_ago,9,rng)})

    expenses=[]
    for cat,desc,amount in profile["expenses"]:
        for d in (38, 8) if cat in {"alquiler","personal"} else (20,):
            expenses.append({"id":new_id(),"business_id":bid,"category":cat,"description":desc,"amount":amount,"date":(now-timedelta(days=d)).date().isoformat(),"user_email":profile["email"],"created_at":ts(d,18,rng)})
    await db.sales.insert_many(sales); await db.purchases.insert_many(purchases); await db.expenses.insert_many(expenses); await db.inventory_movements.insert_many(movements)
    for p in products:
        await db.products.update_one({"id":p["id"]},{"$set":{"stock":max(0,stock[p["id"]]),"updated_at":now_iso()}})

async def seed_showcase():
    for profile in PROFILES:
        await seed_profile(profile)

if __name__ == "__main__":
    asyncio.run(seed_showcase())
