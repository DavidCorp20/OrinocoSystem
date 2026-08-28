"""Onboarding (register -> create business) and multi-tenant isolation."""
import requests

from conftest import API, new_email


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
