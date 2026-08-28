"""Iteration 3 backend tests: facturación venezolana, tasa BCV, roles de equipo,
dashboard de plataforma (superadmin) y aislamiento entre negocios demo."""
import uuid

import pytest
import requests

from conftest import API

DEMO_PASSWORD = "Demo2026!"
DEMOS = {
    "kiosco": "kiosco.demo@controlpyme.com",
    "verduleria": "verduleria.demo@controlpyme.com",
    "repuestos": "repuestos.demo@controlpyme.com",
}


def login(email, password):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    return s, r


def auth_session(email, password):
    s, r = login(email, password)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text[:200]}"
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


# ---------------------------------------------------------------- rates (BCV)
class TestRates:
    def test_current_rate(self, admin):
        r = admin.get(f"{API}/rates/current")
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert isinstance(d["rate"], (int, float)) and d["rate"] > 0
        assert d["source"] in ("bcv", "manual")
        assert d["mode"] in ("auto", "manual")
        # sanity: venezuelan rate order of magnitude
        assert 10 < d["rate"] < 100000, f"unexpected rate {d['rate']}"

    def test_refresh_rate(self, admin):
        r = admin.post(f"{API}/rates/refresh")
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("ok") is True, f"refresh failed: {d}"
        assert d["rate"] > 0

    def test_rates_requires_auth(self, api_client):
        assert api_client.get(f"{API}/rates/current").status_code == 401


# ------------------------------------------------------------------- facturas
class TestFacturaVenta:
    def test_sale_invoice_fields(self, admin):
        prods = admin.get(f"{API}/products").json()["products"]
        p = next(x for x in prods if x["stock"] >= 2)
        stock_before = p["stock"]

        rate = admin.get(f"{API}/rates/current").json()["rate"]
        r = admin.post(f"{API}/sales", json={
            "items": [{"product_id": p["id"], "quantity": 1}],
            "payment_method": "efectivo",
            "customer_name": "TEST_Cliente QA",
            "customer_rif": "J-123456789",
        })
        assert r.status_code == 200, r.text[:300]
        sale = r.json()["sale"]

        assert sale["invoice_number"].startswith("F-")
        assert len(sale["invoice_number"]) == 8, sale["invoice_number"]
        assert sale["iva_percent"] == 16
        assert round(sale["subtotal"] + sale["iva_amount"], 2) == sale["total"]
        assert round(sale["total"] / 1.16, 2) == sale["subtotal"]
        assert sale["exchange_rate"] == pytest.approx(rate, rel=0.01)
        assert sale["total_bs"] == pytest.approx(sale["total"] * sale["exchange_rate"], rel=0.001)
        assert sale["customer_name"] == "TEST_Cliente QA"
        assert sale["customer_rif"] == "J-123456789"
        assert "_id" not in sale

        # persistence via GET
        listed = admin.get(f"{API}/sales").json()["sales"]
        found = next((s for s in listed if s["id"] == sale["id"]), None)
        assert found, "sale not persisted"
        assert found["invoice_number"] == sale["invoice_number"]
        assert found["total_bs"] == sale["total_bs"]

        # stock decremented
        after = admin.get(f"{API}/products").json()["products"]
        assert next(x for x in after if x["id"] == p["id"])["stock"] == stock_before - 1

    def test_invoice_numbers_increment(self, admin):
        prods = admin.get(f"{API}/products").json()["products"]
        p = next(x for x in prods if x["stock"] >= 3)
        nums = []
        for _ in range(2):
            r = admin.post(f"{API}/sales", json={"items": [{"product_id": p["id"], "quantity": 1}]})
            assert r.status_code == 200, r.text[:200]
            nums.append(int(r.json()["sale"]["invoice_number"].split("-")[1]))
        assert nums[1] == nums[0] + 1, nums

    def test_purchase_invoice_fields(self, admin):
        prods = admin.get(f"{API}/products").json()["products"]
        p = prods[0]
        r = admin.post(f"{API}/purchases", json={
            "supplier": "TEST_Proveedor QA",
            "supplier_rif": "J-987654321",
            "items": [{"product_id": p["id"], "quantity": 2, "unit_cost": 3.5}],
        })
        assert r.status_code == 200, r.text[:300]
        pur = r.json()["purchase"]
        assert pur["invoice_number"].startswith("C-"), pur.get("invoice_number")
        assert round(pur["subtotal"] + pur["iva_amount"], 2) == pur["total"]
        assert pur["supplier_rif"] == "J-987654321"
        assert pur["total_bs"] and pur["total_bs"] > pur["total"]

        listed = admin.get(f"{API}/purchases").json()["purchases"]
        assert any(x["invoice_number"] == pur["invoice_number"] for x in listed)


# ----------------------------------------------------------------- barcode search
class TestBarcodeSearch:
    def test_search_by_exact_barcode_kiosco(self):
        """Scanner (keyboard-wedge) relies on exact-barcode lookup."""
        s = auth_session(DEMOS["kiosco"], DEMO_PASSWORD)
        prods = s.get(f"{API}/products").json()["products"]
        with_bc = [p for p in prods if p.get("barcode")]
        assert with_bc, "kiosco demo has no barcodes (scanner cannot work)"
        bc = with_bc[0]["barcode"]
        r = s.get(f"{API}/products", params={"search": bc})
        assert r.status_code == 200
        res = r.json()["products"]
        assert any(p["barcode"] == bc for p in res), f"search by barcode {bc} returned {len(res)} rows"

    def test_ferreteria_demo_products_have_barcodes(self, admin):
        """KNOWN GAP: the main demo tenant (Ferretería El Candado) was seeded without barcodes,
        so the barcode scanner cannot be demoed on the account the user actually logs in with."""
        prods = admin.get(f"{API}/products").json()["products"]
        with_bc = [p for p in prods if p.get("barcode")]
        assert with_bc, f"0/{len(prods)} Ferretería products have a barcode"

    def test_search_by_name(self, admin):
        prods = admin.get(f"{API}/products").json()["products"]
        term = prods[0]["name"].split()[0]
        r = admin.get(f"{API}/products", params={"search": term})
        assert r.status_code == 200
        assert len(r.json()["products"]) >= 1


# ----------------------------------------------------------------------- roles
class TestRoles:
    @pytest.fixture(scope="class")
    def team(self, admin):
        created = []
        tag = uuid.uuid4().hex[:6]
        for role in ("vendedor", "administrador"):
            r = admin.post(f"{API}/team", json={
                "name": f"TEST_{role}",
                "email": f"qa.{role}.{tag}@mail.com",
                "password": "QaPyme2026!",
                "role": role,
            })
            assert r.status_code == 200, f"create {role}: {r.status_code} {r.text[:200]}"
            created.append((role, r.json()["member"]))
        yield {role: m for role, m in created}
        for _role, m in created:
            admin.delete(f"{API}/team/{m['id']}")

    def test_vendedor_permissions(self, admin, team):
        m = team["vendedor"]
        assert m["role"] == "vendedor"
        s = auth_session(m["email"], "QaPyme2026!")
        prods = s.get(f"{API}/products").json()["products"]
        p = next(x for x in prods if x["stock"] >= 1)

        assert s.post(f"{API}/sales", json={"items": [{"product_id": p["id"], "quantity": 1}]}).status_code == 200
        assert s.post(f"{API}/purchases", json={"items": [{"product_id": p["id"], "quantity": 1, "unit_cost": 1}]}).status_code == 403
        assert s.post(f"{API}/expenses", json={"category": "otros", "description": "TEST_x", "amount": 5}).status_code == 403
        assert s.get(f"{API}/team").status_code == 403
        assert s.get(f"{API}/dashboard").status_code == 200
        assert s.get(f"{API}/platform/overview").status_code == 403

    def test_administrador_permissions(self, admin, team):
        m = team["administrador"]
        s = auth_session(m["email"], "QaPyme2026!")
        prods = s.get(f"{API}/products").json()["products"]
        p = prods[0]
        r = s.post(f"{API}/purchases", json={"items": [{"product_id": p["id"], "quantity": 1, "unit_cost": 2}]})
        assert r.status_code == 200, r.text[:200]
        assert s.post(f"{API}/expenses", json={"category": "otros", "description": "TEST_gasto admin", "amount": 3}).status_code == 200
        assert s.get(f"{API}/team").status_code == 403
        assert s.put(f"{API}/business/settings", json={"phone": "0412"}).status_code == 403

    def test_invalid_role_rejected(self, admin):
        r = admin.post(f"{API}/team", json={
            "name": "TEST_bad", "email": f"qa.bad.{uuid.uuid4().hex[:6]}@mail.com",
            "password": "QaPyme2026!", "role": "propietario",
        })
        assert r.status_code == 400

    def test_duplicate_email_rejected(self, admin, team):
        r = admin.post(f"{API}/team", json={
            "name": "TEST_dup", "email": team["vendedor"]["email"],
            "password": "QaPyme2026!", "role": "vendedor",
        })
        assert r.status_code == 400


# -------------------------------------------------------------------- platform
class TestPlatform:
    def test_overview_superadmin(self, admin):
        r = admin.get(f"{API}/platform/overview")
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert set(["total", "activos", "nuevos_30", "gastos_mes"]).issubset(d["stats"].keys())
        names = " | ".join(b["name"] for b in d["businesses"])
        for expected in ("Ferreter", "Kiosco", "Verduler", "Repuestos"):
            assert expected in names, f"{expected} missing from platform list: {names}"
        assert all("_id" not in b for b in d["businesses"])

    def test_overview_forbidden_for_normal_tenant(self):
        s = auth_session(DEMOS["kiosco"], DEMO_PASSWORD)
        assert s.get(f"{API}/platform/overview").status_code == 403
        assert s.get(f"{API}/platform/expenses").status_code == 403
        assert s.post(f"{API}/platform/expenses", json={"category": "otros", "description": "x", "amount": 1}).status_code == 403

    def test_platform_expense_crud(self, admin):
        before = admin.get(f"{API}/platform/overview").json()["stats"]["gastos_mes"]
        r = admin.post(f"{API}/platform/expenses", json={
            "category": "infraestructura", "description": "TEST_QA servidor", "amount": 42.5,
        })
        assert r.status_code == 200, r.text[:300]
        exp = r.json()["expense"]
        assert exp["amount"] == 42.5
        after = admin.get(f"{API}/platform/overview").json()["stats"]["gastos_mes"]
        assert round(after - before, 2) == 42.5, (before, after)
        assert admin.delete(f"{API}/platform/expenses/{exp['id']}").status_code == 200
        final = admin.get(f"{API}/platform/overview").json()["stats"]["gastos_mes"]
        assert final == pytest.approx(before, abs=0.01)

    def test_invalid_expense_category(self, admin):
        r = admin.post(f"{API}/platform/expenses", json={"category": "nope", "description": "x", "amount": 1})
        assert r.status_code == 400

    def test_disable_business_blocks_login_and_api(self, admin):
        s = auth_session(DEMOS["kiosco"], DEMO_PASSWORD)
        bid = s.get(f"{API}/auth/me").json()["user"]["business_id"]
        try:
            assert admin.put(f"{API}/platform/businesses/{bid}/status", json={"active": False}).status_code == 200
            _, r = login(DEMOS["kiosco"], DEMO_PASSWORD)
            assert r.status_code == 403, f"disabled login -> {r.status_code}"
            assert "deshabilitada" in r.text.lower()
            # existing valid token must also be blocked
            r2 = s.get(f"{API}/dashboard")
            assert r2.status_code == 403, f"disabled tenant dashboard -> {r2.status_code}"
        finally:
            admin.put(f"{API}/platform/businesses/{bid}/status", json={"active": True})
        _, r = login(DEMOS["kiosco"], DEMO_PASSWORD)
        assert r.status_code == 200, "re-activation failed"

    def test_status_unknown_business(self, admin):
        r = admin.put(f"{API}/platform/businesses/{uuid.uuid4()}/status", json={"active": False})
        assert r.status_code == 404


# ------------------------------------------------------------------ demo seeds
class TestDemoBusinesses:
    @pytest.mark.parametrize("key", list(DEMOS))
    def test_demo_login_and_data(self, key):
        s = auth_session(DEMOS[key], DEMO_PASSWORD)
        me = s.get(f"{API}/auth/me").json()["user"]
        assert me["business_id"]
        biz = s.get(f"{API}/business").json()["business"]
        assert biz["active"] is True
        prods = s.get(f"{API}/products").json()["products"]
        assert len(prods) >= 5, f"{key} only has {len(prods)} products"
        assert all(p["business_id"] == me["business_id"] for p in prods), "tenant leak in products"
        dash = s.get(f"{API}/dashboard").json()
        assert dash, "empty dashboard"
        sales = s.get(f"{API}/sales").json()["sales"]
        assert all(x["business_id"] == me["business_id"] for x in sales), "tenant leak in sales"

    def test_kiosco_has_venezuelan_catalog(self):
        s = auth_session(DEMOS["kiosco"], DEMO_PASSWORD)
        names = " | ".join(p["name"].lower() for p in s.get(f"{API}/products").json()["products"])
        assert "harina" in names, names[:300]

    def test_verduleria_uses_kg(self):
        s = auth_session(DEMOS["verduleria"], DEMO_PASSWORD)
        units = {p.get("unit") for p in s.get(f"{API}/products").json()["products"]}
        assert "kg" in units, units

    def test_cross_tenant_product_access_blocked(self):
        a = auth_session(DEMOS["kiosco"], DEMO_PASSWORD)
        b = auth_session(DEMOS["repuestos"], DEMO_PASSWORD)
        pid = a.get(f"{API}/products").json()["products"][0]["id"]
        # no single-product GET route exists (405); tenant isolation checked via list + sale
        assert pid not in [p["id"] for p in b.get(f"{API}/products").json()["products"]]
        r2 = b.post(f"{API}/sales", json={"items": [{"product_id": pid, "quantity": 1}]})
        assert r2.status_code == 400, f"cross-tenant sale -> {r2.status_code}"


# ------------------------------------------------------------------- settings
class TestBcvSettings:
    def test_manual_mode_roundtrip(self, admin):
        try:
            r = admin.put(f"{API}/business/settings", json={"bcv_mode": "manual", "bcv_rate": 100.0})
            assert r.status_code == 200, r.text[:300]
            assert r.json()["business"]["bcv_mode"] == "manual"
            cur = admin.get(f"{API}/rates/current").json()
            assert cur["rate"] == 100.0 and cur["source"] == "manual", cur

            prods = admin.get(f"{API}/products").json()["products"]
            p = next(x for x in prods if x["stock"] >= 1)
            sale = admin.post(f"{API}/sales", json={"items": [{"product_id": p["id"], "quantity": 1}]}).json()["sale"]
            assert sale["exchange_rate"] == 100.0
            assert sale["total_bs"] == pytest.approx(sale["total"] * 100, rel=0.001)
        finally:
            admin.put(f"{API}/business/settings", json={"bcv_mode": "auto"})
        back = admin.get(f"{API}/rates/current").json()
        assert back["mode"] == "auto" and back["source"] == "bcv", back

    def test_invalid_mode(self, admin):
        assert admin.put(f"{API}/business/settings", json={"bcv_mode": "cripto"}).status_code == 400

    def test_rif_settings_saved(self, admin):
        r = admin.put(f"{API}/business/settings", json={"rif": "J-40123456-7", "phone": "0212-5551234"})
        assert r.status_code == 200
        b = r.json()["business"]
        assert b["rif"] == "J-40123456-7" and b["phone"] == "0212-5551234"
        assert admin.get(f"{API}/business").json()["business"]["rif"] == "J-40123456-7"
