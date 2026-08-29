"""Iteration 3.1 retest: fiscal numbering gaps, bcv_rate cleanup on auto, barcodes,
platform overview cleanliness, product unit exposure."""
import os
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

ROOT_DIR = Path(__file__).resolve().parents[2]
frontend_env = {}
frontend_dotenv = ROOT_DIR / "frontend" / ".env"
if frontend_dotenv.exists():
    frontend_env = dotenv_values(frontend_dotenv)
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"


def _creds():
    email = os.environ.get("TEST_ADMIN_EMAIL") or os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("TEST_ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        pytest.skip("No hay credenciales de prueba en TEST_ADMIN_EMAIL / TEST_ADMIN_PASSWORD")
    return email, password


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    email, password = _creds()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Admin login failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("access_token")
    assert token
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# --- RETEST 1: barcodes en Ferretería El Candado ---
class TestBarcodes:
    def test_all_ferreteria_products_have_barcode(self, admin):
        r = admin.get(f"{API}/products", timeout=30)
        assert r.status_code == 200
        products = r.json()["products"]
        assert len(products) >= 12
        missing = [p["name"] for p in products if not p.get("barcode")]
        assert not missing, f"Productos sin barcode: {missing}"

    def test_barcode_exact_search_returns_single_product(self, admin):
        products = admin.get(f"{API}/products", timeout=30).json()["products"]
        bc = products[0]["barcode"]
        r = admin.get(f"{API}/products", params={"search": bc}, timeout=30)
        assert r.status_code == 200
        found = r.json()["products"]
        assert any(p["barcode"] == bc for p in found), f"Búsqueda por barcode {bc} no devolvió el producto"

    def test_no_mongo_id_leaked(self, admin):
        products = admin.get(f"{API}/products", timeout=30).json()["products"]
        assert all("_id" not in p for p in products)


# --- RETEST 2: settings BCV manual -> auto limpia bcv_rate ---
class TestBcvSettings:
    def test_manual_then_auto_clears_rate(self, admin):
        r = admin.put(f"{API}/business/settings", json={"bcv_mode": "manual", "bcv_rate": 100}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        cur = admin.get(f"{API}/business", timeout=30).json()["business"]
        assert cur.get("bcv_mode") == "manual"
        assert float(cur.get("bcv_rate")) == 100.0
        rates = admin.get(f"{API}/rates/current", timeout=30).json()
        assert float(rates.get("rate")) == 100.0, f"rates/current no refleja la tasa manual: {rates}"

        r = admin.put(f"{API}/business/settings", json={"bcv_mode": "auto"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        cur = admin.get(f"{API}/business", timeout=30).json()["business"]
        assert cur.get("bcv_mode") == "auto"
        assert cur.get("bcv_rate") is None, f"bcv_rate no quedó null tras volver a auto: {cur.get('bcv_rate')}"
        rates = admin.get(f"{API}/rates/current", timeout=30).json()
        assert float(rates.get("rate")) > 200, f"tasa BCV inesperada tras volver a auto: {rates}"


# --- RETEST 5: numeración fiscal sin huecos ---
class TestFiscalNumbering:
    def test_failed_sale_does_not_consume_invoice_number(self, admin):
        products = admin.get(f"{API}/products", timeout=30).json()["products"]
        prod = next(p for p in products if p.get("stock", 0) > 0)

        sales = admin.get(f"{API}/sales", timeout=30).json()["sales"]
        numbered = [s["invoice_number"] for s in sales if s.get("invoice_number")]

        def seq(n):
            return int(n.split("-")[1])

        last_before = max((seq(n) for n in numbered), default=0)

        # Venta que debe fallar por stock insuficiente
        bad = admin.post(f"{API}/sales", json={
            "items": [{"product_id": prod["id"], "quantity": prod["stock"] + 500}],
            "payment_method": "efectivo",
        }, timeout=30)
        assert bad.status_code == 400, f"Se esperaba 400 por stock insuficiente, llegó {bad.status_code}: {bad.text[:200]}"
        assert "Stock insuficiente" in bad.text

        # Venta válida siguiente debe ser consecutiva
        good = admin.post(f"{API}/sales", json={
            "items": [{"product_id": prod["id"], "quantity": 1}],
            "payment_method": "efectivo",
            "customer_name": "TEST_QA Numeracion",
        }, timeout=30)
        assert good.status_code in (200, 201), good.text[:300]
        sale = good.json()["sale"]
        assert seq(sale["invoice_number"]) == last_before + 1, (
            f"Hueco en numeración: anterior {last_before}, nueva {sale['invoice_number']}")

        # Persistencia
        listed = admin.get(f"{API}/sales", timeout=30).json()["sales"]
        assert any(s["id"] == sale["id"] and s["invoice_number"] == sale["invoice_number"] for s in listed)

    def test_failed_sale_does_not_change_stock(self, admin):
        products = admin.get(f"{API}/products", timeout=30).json()["products"]
        prod = next(p for p in products if p.get("stock", 0) > 0)
        before = prod["stock"]
        r = admin.post(f"{API}/sales", json={
            "items": [{"product_id": prod["id"], "quantity": 1},
                      {"product_id": prod["id"], "quantity": before + 999}],
            "payment_method": "efectivo",
        }, timeout=30)
        assert r.status_code == 400, f"esperado 400, llegó {r.status_code}"
        after = next(p for p in admin.get(f"{API}/products", timeout=30).json()["products"] if p["id"] == prod["id"])["stock"]
        assert after == before, f"stock cambió en venta fallida: {before} -> {after} (falta rollback)"


# --- RETEST 7: unidad de medida expuesta en productos ---
class TestProductUnit:
    def test_products_expose_unit(self, admin):
        products = admin.get(f"{API}/products", timeout=30).json()["products"]
        assert all(p.get("unit") for p in products), "Productos sin campo 'unit'"

    def test_verduleria_uses_kg(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": "verduleria.demo@controlpyme.com", "password": "Demo2026!"}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
        products = s.get(f"{API}/products", timeout=30).json()["products"]
        units = {p.get("unit") for p in products}
        assert "kg" in units, f"Verdulería sin unidad kg: {units}"


# --- RETEST 8: plataforma limpia ---
class TestPlatformClean:
    def test_overview_only_four_demo_businesses(self, admin):
        r = admin.get(f"{API}/platform/overview", timeout=30)
        assert r.status_code == 200
        data = r.json()
        names = [b["name"] for b in data["businesses"]]
        # los tenants TEST_ los crea el propio suite en paralelo; se purgan al final
        demo_names = [n for n in names if not n.startswith("TEST_")]
        assert len(demo_names) == 4, f"Se esperaban 4 negocios reales, hay {len(demo_names)}: {demo_names}"
        for expected in ("Ferretería", "Kiosco", "Verdulería", "Repuestos"):
            assert any(expected in n for n in demo_names), f"Falta negocio {expected}: {demo_names}"

    def test_overview_kpis_coherent(self, admin):
        data = admin.get(f"{API}/platform/overview", timeout=30).json()
        assert data["stats"]["total"] == len(data["businesses"])
        assert data["stats"]["inactivos"] == 0, f"negocios inactivos: {data['stats']['inactivos']}"
        assert all(b.get("active") is True for b in data["businesses"]), "Hay negocios inactivos"
        assert all("_id" not in b for b in data["businesses"])

    def test_toggle_disable_login_403_then_reactivate(self, admin):
        data = admin.get(f"{API}/platform/overview", timeout=30).json()
        kiosco = next(b for b in data["businesses"] if "Kiosco" in b["name"])
        try:
            r = admin.put(f"{API}/platform/businesses/{kiosco['id']}/status", json={"active": False}, timeout=30)
            assert r.status_code == 200, r.text[:300]
            login = requests.post(f"{API}/auth/login", json={"email": "kiosco.demo@controlpyme.com", "password": "Demo2026!"}, timeout=30)
            assert login.status_code == 403, f"esperado 403 con negocio deshabilitado, llegó {login.status_code}"
        finally:
            r = admin.put(f"{API}/platform/businesses/{kiosco['id']}/status", json={"active": True}, timeout=30)
            assert r.status_code == 200
        login = requests.post(f"{API}/auth/login", json={"email": "kiosco.demo@controlpyme.com", "password": "Demo2026!"}, timeout=30)
        assert login.status_code == 200, f"reactivación falló, login={login.status_code}"
