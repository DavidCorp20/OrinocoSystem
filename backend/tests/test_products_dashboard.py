"""Products CRUD + CSV export, and Dashboard payload."""
import pytest

from conftest import API


@pytest.fixture(scope="class")
def created_product_ids():
    return []


@pytest.fixture(scope="class", autouse=True)
def cleanup(admin, created_product_ids):
    yield
    for pid in created_product_ids:
        admin.delete(f"{API}/products/{pid}")


class TestProducts:
    def test_list_demo_products(self, admin):
        r = admin.get(f"{API}/products")
        assert r.status_code == 200
        products = r.json()["products"]
        assert len(products) >= 12
        p = products[0]
        for key in ("id", "name", "stock", "sale_price", "purchase_price", "min_stock"):
            assert key in p
        assert "_id" not in p

    def test_demo_has_out_of_stock_and_low_stock(self, admin):
        products = admin.get(f"{API}/products").json()["products"]
        agotados = [p for p in products if p["stock"] <= 0]
        bajos = [p for p in products if 0 < p["stock"] <= p.get("min_stock", 0)]
        assert agotados, "demo seed should include at least one out-of-stock product"
        assert bajos, "demo seed should include at least one low-stock product"

    def test_create_update_delete_product(self, admin, created_product_ids):
        payload = {"name": "TEST_Martillo QA", "category": "Herramientas", "purchase_price": 5.5,
                   "sale_price": 9.99, "stock": 20, "min_stock": 4, "unit": "unidad"}
        r = admin.post(f"{API}/products", json=payload)
        assert r.status_code in (200, 201), r.text[:300]
        prod = r.json().get("product", r.json())
        pid = prod["id"]
        created_product_ids.append(pid)
        assert prod["name"] == payload["name"]
        assert prod["sale_price"] == 9.99

        listed = {p["id"]: p for p in admin.get(f"{API}/products").json()["products"]}
        assert pid in listed and listed[pid]["stock"] == 20

        r = admin.put(f"{API}/products/{pid}", json={**payload, "name": "TEST_Martillo QA v2", "sale_price": 12.0})
        assert r.status_code == 200, r.text[:300]
        listed = {p["id"]: p for p in admin.get(f"{API}/products").json()["products"]}
        assert listed[pid]["name"] == "TEST_Martillo QA v2"
        assert listed[pid]["sale_price"] == 12.0

        r = admin.delete(f"{API}/products/{pid}")
        assert r.status_code in (200, 204), r.text[:300]
        listed = {p["id"]: p for p in admin.get(f"{API}/products").json()["products"]}
        assert pid not in listed
        created_product_ids.remove(pid)

    def test_create_product_validation(self, admin):
        r = admin.post(f"{API}/products", json={"name": "", "sale_price": -3})
        assert r.status_code == 422

    def test_update_nonexistent_product_404(self, admin):
        r = admin.put(f"{API}/products/does-not-exist", json={"name": "X", "sale_price": 1})
        assert r.status_code == 404

    def test_export_products_csv(self, admin):
        r = admin.get(f"{API}/products/export/csv")
        assert r.status_code == 200
        assert "csv" in r.headers.get("content-type", "").lower()
        assert len(r.text.splitlines()) >= 13


class TestDashboard:
    def test_dashboard_payload(self, admin):
        r = admin.get(f"{API}/dashboard")
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for key in ("ventas_hoy", "ventas_30", "ganancia_estimada", "margen", "trend",
                    "top_vendidos", "agotados", "bajos", "semaforo", "recomendaciones",
                    "productos_count", "recent_sales"):
            assert key in d, f"missing dashboard key {key}"
        assert len(d["trend"]) == 14, f"trend should have 14 days, got {len(d['trend'])}"
        assert d["semaforo"]["nivel"] == "rojo", f"demo has out-of-stock products; got {d['semaforo']}"
        assert d["agotados"], "expected agotados in demo dashboard"
        assert d["recomendaciones"], "expected actionable recommendations"
        assert d["recent_sales"], "expected recent sales in demo"
        assert d["productos_count"] >= 12

    def test_finances_summary(self, admin):
        r = admin.get(f"{API}/finances/summary")
        assert r.status_code == 200, r.text[:300]
        f = r.json()
        assert isinstance(f, dict) and f
        assert "_id" not in str(f)
