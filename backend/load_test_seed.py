"""Controlled load-test data generator for CuadraApp.

Creates isolated LOADTEST-* tenants and data. Safe to rerun with --reset.
Run from backend with the same environment variables used by the API.
"""
import argparse
import asyncio
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorClient


DB_URL = os.getenv("MONGO_URL") or os.getenv("MONGODB_URL")
DB_NAME = os.getenv("DB_NAME", "cuadrapp")

PRODUCTS_PER_BUSINESS = 100
SALES_PER_BUSINESS = 1000
MOVEMENTS_PER_BUSINESS = 3000
EXPENSES_PER_BUSINESS = 100


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--businesses", type=int, default=3)
    parser.add_argument("--products", type=int, default=100)
    parser.add_argument("--sales", type=int, default=1000)
    parser.add_argument("--movements", type=int, default=3000)
    parser.add_argument("--expenses", type=int, default=100)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    if not DB_URL:
        raise RuntimeError("MONGO_URL/MONGODB_URL no está configurado")

    client = AsyncIOMotorClient(DB_URL, maxPoolSize=100, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]

    prefix = "LOADTEST-"
    if args.reset:
        businesses = await db.businesses.find({"name": {"$regex": f"^{prefix}"}}, {"id": 1}).to_list(None)
        ids = [x["id"] for x in businesses]
        if ids:
            for collection in ["products", "sales", "purchases", "expenses", "inventory_movements"]:
                await db[collection].delete_many({"business_id": {"$in": ids}})
            await db.businesses.delete_many({"id": {"$in": ids}})
        print(f"Reset completado: {len(ids)} negocios LOADTEST eliminados")
        return

    categories = ["Alimentos", "Bebidas", "Limpieza", "Hogar", "Ferretería", "Cuidado personal", "Oficina"]
    names = ["LoadTest A", "LoadTest B", "LoadTest C", "LoadTest D", "LoadTest E"]
    rng = random.Random(20260901)
    created_business_ids = []

    for b in range(args.businesses):
        bid = f"{prefix}{b+1:03d}-{uid()}"
        created_business_ids.append(bid)
        business = {
            "id": bid,
            "owner_id": None,
            "name": f"{prefix}{b+1:03d} - {names[b % len(names)]}",
            "type": ["comercio", "ferreteria", "alimentos"][b % 3],
            "currency": "USD",
            "active": True,
            "bcv_mode": "auto",
            "bcv_rate": None,
            "rif": f"J-{rng.randint(10000000,49999999)}-{rng.randint(0,9)}",
            "address": "LOAD TEST",
            "phone": None,
            "created_at": now(),
        }
        await db.businesses.insert_one(business)

        products = []
        for i in range(args.products):
            stock = rng.choice([0, 1, 2, 5, 10, 25, 50, 100, 250, 500])
            cost = round(rng.uniform(0.5, 100), 2)
            price = round(cost * rng.uniform(1.15, 2.2), 2)
            products.append({
                "id": uid(), "business_id": bid,
                "name": f"LOADTEST Producto {b+1:02d}-{i+1:04d}",
                "sku": f"LT{b+1:02d}-{i+1:04d}",
                "barcode": f"779{b+1:02d}{i+1:010d}",
                "category": rng.choice(categories), "brand": None,
                "supplier": "Proveedor Load Test", "purchase_price": cost,
                "sale_price": price, "stock": stock,
                "min_stock": max(1, stock // 4), "max_stock": stock * 3,
                "unit": rng.choice(["unidad", "caja", "kg", "litro"]),
                "status": "activo", "created_at": now(), "updated_at": now(),
            })
        await db.products.insert_many(products)

        movements = []
        for i in range(args.movements):
            p = rng.choice(products)
            qty = rng.randint(1, 20)
            movements.append({
                "id": uid(), "business_id": bid, "product_id": p["id"],
                "product_name": p["name"], "type": rng.choice(["entrada", "salida"]),
                "reason": rng.choice(["carga_inicial", "compra", "ajuste", "venta"]),
                "quantity": qty, "stock_after": rng.randint(0, 500),
                "user_email": "loadtest@cuadrapp.local", "notes": "LOADTEST",
                "created_at": (datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 90))).isoformat(),
            })
        await db.inventory_movements.insert_many(movements)

        sales = []
        for i in range(args.sales):
            chosen = rng.sample(products, k=rng.randint(1, min(4, len(products))))
            items = []
            total = 0.0
            cost_total = 0.0
            for p in chosen:
                qty = rng.randint(1, 5)
                line = round(p["sale_price"] * qty, 2)
                items.append({
                    "product_id": p["id"], "name": p["name"], "quantity": qty,
                    "unit_price": p["sale_price"], "discount": 0,
                    "cost": p["purchase_price"], "line_total": line,
                })
                total += line
                cost_total += p["purchase_price"] * qty
            sales.append({
                "id": uid(), "business_id": bid, "items": items,
                "total": round(total, 2), "cost_total": round(cost_total, 2),
                "profit": round(total - cost_total, 2),
                "payment_method": rng.choice(["efectivo", "tarjeta", "transferencia", "pago móvil"]),
                "customer_name": None, "customer_rif": None,
                "user_email": "loadtest@cuadrapp.local",
                "test_data": True,
                "created_at": (datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 180))).isoformat(),
            })
        for i in range(0, len(sales), 500):
            await db.sales.insert_many(sales[i:i+500])

        expenses = []
        for i in range(args.expenses):
            expenses.append({
                "id": uid(), "business_id": bid,
                "category": rng.choice(["alquiler", "servicios", "personal", "marketing", "otros"]),
                "description": f"LOADTEST gasto {i+1}",
                "amount": round(rng.uniform(10, 500), 2),
                "date": (datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 180))).date().isoformat(),
                "user_email": "loadtest@cuadrapp.local",
                "created_at": now(),
            })
        await db.expenses.insert_many(expenses)

        print(f"{business['name']}: {args.products} productos, {args.sales} ventas, {args.movements} movimientos, {args.expenses} gastos")

    # Helpful indexes for the test workload; existing indexes remain untouched.
    await db.products.create_index([("business_id", 1), ("status", 1)], name="loadtest_products_business_status")
    await db.sales.create_index([("business_id", 1), ("created_at", -1)], name="loadtest_sales_business_date")
    await db.inventory_movements.create_index([("business_id", 1), ("created_at", -1)], name="loadtest_movements_business_date")
    await db.expenses.create_index([("business_id", 1), ("date", -1)], name="loadtest_expenses_business_date")

    print("\nLOAD TEST COMPLETADO")
    print(f"Negocios: {args.businesses}")
    print(f"Documentos aproximados creados: {args.businesses * (1 + args.products + args.sales + args.movements + args.expenses):,}")
    print("Todos los negocios están identificados con prefijo LOADTEST- y pueden eliminarse con --reset.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
