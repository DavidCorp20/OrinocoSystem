"""Onboarding (register -> create business) and multi-tenant isolation."""
import asyncio

import pytest
import requests
from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient

from conftest import API, new_email


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_tenants():
    """Remove TEST_ tenants (and their data) created by this module so the
    platform overview / KPIs stay clean for the demo accounts."""
    yield

    async def _purge():
        env = dotenv_values("/app/backend/.env")
        client = AsyncIOMotorClient(env["MONGO_URL"])
        db = client[env["DB_NAME"]]
        biz_ids = [b["id"] for b in await db.businesses.find({"name": {"$regex": "^TEST_"}}, {"_id": 0, "id": 1}).to_list(500)]
        if biz_ids:
            for coll in ("products", "sales", "purchases", "expenses", "inventory_movements", "users", "clients"):
                await db[coll].delete_many({"business_id": {"$in": biz_ids}})
            await db.businesses.delete_many({"id": {"$in": biz_ids}})
        await db.users.delete_many({"business_id": None, "email": {"$regex": "^onb"}})
        client.close()

    asyncio.run(_purge())


class TestOnboardingAndTenant:
    def test_register_then_business_then_isolation(self, admin):
        email = new_email("onb")
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{API}/auth/register", json={"name": "Nuevo Dueno", "email": email, "password": "TestPyme2026!"})
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["business"] is None
        assert body["user"]["business_id"] is None

        # business-scoped endpoints must complain before onboarding
        r = s.get(f"{API}/products")
        assert r.status_code == 400
        assert "negocio" in r.json()["detail"].lower()

        r = s.post(f"{API}/business", json={
            "name": "TEST_Tienda QA", "type": "tienda", "currency": "USD",
            "initial_products": [{"name": "TEST_Producto A", "sale_price": 10, "purchase_price": 6, "stock": 3}],
        })
        assert r.status_code == 200, r.text[:300]
        biz = r.json()["business"]
        assert biz["name"] == "TEST_Tienda QA" and biz["currency"] == "USD"
        assert "_id" not in biz

        # persisted on /me
        me = s.get(f"{API}/auth/me").json()
        assert me["business"]["id"] == biz["id"]

        # duplicate business rejected
        assert s.post(f"{API}/business", json={"name": "Otro", "type": "tienda"}).status_code == 400

        # multi-tenant: only its own product, never the demo's 12
        mine = s.get(f"{API}/products").json()["products"]
        assert len(mine) == 1 and mine[0]["name"] == "TEST_Producto A"
        admin_products = admin.get(f"{API}/products").json()["products"]
        admin_ids = {p["id"] for p in admin_products}
        assert mine[0]["id"] not in admin_ids
        assert len(admin_products) >= 12

        # cross-tenant write blocked
        r = s.post(f"{API}/sales", json={"items": [{"product_id": admin_products[0]["id"], "quantity": 1}]})
        assert r.status_code == 400
        assert "no existe" in r.json()["detail"].lower()

        # empty dashboard for the new tenant
        dash = s.get(f"{API}/dashboard")
        assert dash.status_code == 200
        d = dash.json()
        assert d["ventas_hoy"] == 0
        assert d["ventas_30"] == 0
        assert d["productos_count"] == 1
        assert d["semaforo"]["nivel"] in ("verde", "amarillo", "rojo")
