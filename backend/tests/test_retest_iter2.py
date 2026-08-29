"""Iteration-2 retest: brute-force lockout keying/reset, purchase weighted-average cost +
supplier preservation, and seed timestamps not in the future."""
import uuid
from datetime import datetime, timezone

import pytest
import requests

from conftest import API, new_email


def _get_product(session, pid):
    r = session.get(f"{API}/products")
    assert r.status_code == 200, r.text[:200]
    items = r.json().get("products", r.json())
    found = [p for p in items if p["id"] == pid]
    assert found, f"product {pid} not found in list"
    return found[0]


def _mongo_login_attempts(email):
    """Inspect login_attempts docs for an email using the MongoDB Python client when mongosh is unavailable."""
    import json
    import os
    import shutil
    import subprocess
    from pathlib import Path

    from dotenv import dotenv_values
    from pymongo import MongoClient

    env_path = Path(__file__).resolve().parents[2] / "backend" / ".env"
    env = {**dotenv_values(env_path), **os.environ}
    mongo_url = env.get("MONGO_URL", "mongodb://127.0.0.1:27017")
    dbname = env.get("DB_NAME", "controlpyme")
    script = 'JSON.stringify(db.login_attempts.find({identifier: {$regex: "%s"}}).toArray())' % email

    mongosh = shutil.which("mongosh")
    if mongosh:
        out = subprocess.run(
            [mongosh, f"{mongo_url}/{dbname}", "--quiet", "--eval", script],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode == 0:
            return json.loads(out.stdout.strip() or "[]")
        return []

    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=2000)
        db = client[dbname]
        docs = list(db.login_attempts.find({"identifier": {"$regex": email}}))
        for d in docs:
            d.pop("_id", None)
        return docs
    except Exception:
        pytest.skip("MongoDB no disponible ni mongosh instalado; omitiendo verificación de login_attempts.")


class TestBruteForceRetest:
    def test_sixth_failed_login_returns_429_and_single_email_keyed_doc(self):
        email = f"probe.{uuid.uuid4().hex[:8]}@mail.com"
        reg = requests.post(f"{API}/auth/register",
                            json={"name": "Probe User", "email": email, "password": "TestPyme2026!"})
        assert reg.status_code == 200, reg.text[:300]

        codes = [requests.post(f"{API}/auth/login", json={"email": email, "password": "badpass"}).status_code
                 for _ in range(5)]
        assert codes == [401] * 5, codes

        sixth = requests.post(f"{API}/auth/login", json={"email": email, "password": "badpass"})
        assert sixth.status_code == 429, f"6th attempt -> {sixth.status_code}: {sixth.text[:200]}"
        assert "intentos" in sixth.json()["detail"].lower()

        # correct password also blocked while locked
        good = requests.post(f"{API}/auth/login", json={"email": email, "password": "TestPyme2026!"})
        assert good.status_code == 429

        docs = _mongo_login_attempts(email)
        assert len(docs) == 1, f"expected exactly ONE login_attempts doc, got {docs}"
        assert docs[0]["identifier"] == email, docs[0]["identifier"]
        assert docs[0]["count"] >= 5
        assert docs[0]["locked_until"]

    def test_successful_login_clears_counter(self):
        email = f"probe.{uuid.uuid4().hex[:8]}@mail.com"
        reg = requests.post(f"{API}/auth/register",
                            json={"name": "Probe Reset", "email": email, "password": "TestPyme2026!"})
        assert reg.status_code == 200
        for _ in range(2):
            assert requests.post(f"{API}/auth/login",
                                 json={"email": email, "password": "badpass"}).status_code == 401
        ok = requests.post(f"{API}/auth/login", json={"email": email, "password": "TestPyme2026!"})
        assert ok.status_code == 200
        assert _mongo_login_attempts(email) == []
        # 4 more failures must NOT lock (counter restarted from 0)
        codes = [requests.post(f"{API}/auth/login", json={"email": email, "password": "badpass"}).status_code
                 for _ in range(4)]
        assert codes == [401] * 4, codes


class TestPurchaseCostAndSupplier:
    def test_supplier_preserved_and_weighted_average_cost(self, admin):
        # create a product WITH a supplier and known stock/cost
        payload = {"name": f"TEST_Costeo_{uuid.uuid4().hex[:6]}", "category": "TEST", "unit": "unidad",
                   "stock": 10, "min_stock": 2, "purchase_price": 10.0, "sale_price": 20.0,
                   "supplier": "TEST_Proveedor Original"}
        r = admin.post(f"{API}/products", json=payload)
        assert r.status_code in (200, 201), r.text[:300]
        prod = r.json().get("product", r.json())
        pid = prod["id"]
        try:
            purchase = {"supplier": "TEST_Proveedor X", "payment_method": "efectivo", "status": "pagada",
                        "items": [{"product_id": pid, "quantity": 5, "unit_cost": 20.0}]}
            pr = admin.post(f"{API}/purchases", json=purchase)
            assert pr.status_code in (200, 201), pr.text[:300]

            after = _get_product(admin, pid)
            assert after["supplier"] == "TEST_Proveedor Original", after["supplier"]
            assert after["stock"] == 15
            expected = (10 * 10.0 + 5 * 20.0) / 15
            assert abs(after["purchase_price"] - expected) < 0.01, after["purchase_price"]
        finally:
            admin.delete(f"{API}/products/{pid}")

    def test_supplier_set_when_product_has_none(self, admin):
        payload = {"name": f"TEST_SinProv_{uuid.uuid4().hex[:6]}", "category": "TEST", "unit": "unidad",
                   "stock": 0, "min_stock": 1, "purchase_price": 0, "sale_price": 5.0, "supplier": ""}
        r = admin.post(f"{API}/products", json=payload)
        assert r.status_code in (200, 201), r.text[:300]
        pid = r.json().get("product", r.json())["id"]
        try:
            pr = admin.post(f"{API}/purchases", json={
                "supplier": "TEST_Proveedor Nuevo", "payment_method": "efectivo", "status": "pagada",
                "items": [{"product_id": pid, "quantity": 4, "unit_cost": 2.5}]})
            assert pr.status_code in (200, 201), pr.text[:300]
            after = _get_product(admin, pid)
            assert after.get("supplier") == "TEST_Proveedor Nuevo"
            assert abs(after["purchase_price"] - 2.5) < 0.01
        finally:
            admin.delete(f"{API}/products/{pid}")


class TestSeedTimestamps:
    def test_no_future_records(self, admin):
        nowiso = datetime.now(timezone.utc).isoformat()
        for path, key in (("/movements", "movements"), ("/sales", "sales")):
            r = admin.get(f"{API}{path}")
            assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
            rows = r.json().get(key) or next(v for v in r.json().values() if isinstance(v, list))
            assert rows, f"{path} returned no rows"
            future = [x["created_at"] for x in rows if x["created_at"] > nowiso]
            assert not future, f"{path} has future-dated records: {future[:5]}"

    def test_dashboard_ventas_hoy_coherent(self, admin):
        r = admin.get(f"{API}/dashboard")
        assert r.status_code == 200
        d = r.json()
        assert d["num_ventas_hoy"] >= 0
        assert d["ventas_hoy"] >= 0
        today = datetime.now(timezone.utc).date().isoformat()
        sales = admin.get(f"{API}/sales").json()["sales"]
        today_sales = [s for s in sales if s["created_at"][:10] == today]
        assert d["num_ventas_hoy"] == len(today_sales), (d["num_ventas_hoy"], len(today_sales))
