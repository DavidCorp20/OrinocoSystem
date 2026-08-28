"""Critical flows: sale decrements stock, purchase increments stock, manual movements, expenses."""
import pytest

from conftest import API


@pytest.fixture(scope="class")
def qa_product(admin):
    """Dedicated TEST_ product so seeded data is never mutated."""
    r = admin.post(f"{API}/products", json={
        "name": "TEST_Flujo Producto", "category": "QA", "purchase_price": 4.0,
        "sale_price": 10.0, "stock": 50, "min_stock": 5, "unit": "unidad"})
    assert r.status_code in (200, 201), r.text[:300]
    prod = r.json().get("product", r.json())
    yield prod
    admin.delete(f"{API}/products/{prod['id']}")


def stock_of(admin, pid):
    for p in admin.get(f"{API}/products").json()["products"]:
        if p["id"] == pid:
            return p["stock"]
    return None


class TestSalesFlow:
    def test_sale_decrements_stock_and_creates_movement(self, admin, qa_product):
        pid = qa_product["id"]
        before = stock_of(admin, pid)
        r = admin.post(f"{API}/sales", json={
            "items": [{"product_id": pid, "quantity": 3}],
            "payment_method": "efectivo", "customer": "TEST_Cliente"})
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        sale = body["sale"]
        assert "low_stock" in body
        assert "_id" not in sale
        assert sale["total"] == 30.0, sale
        assert sale["cost_total"] == 12.0
        assert sale["profit"] == 18.0
        assert sale["items"][0]["unit_price"] == 10.0

        assert stock_of(admin, pid) == before - 3

        movs = admin.get(f"{API}/movements", params={"product_id": pid}).json()["movements"]
        salidas = [m for m in movs if m["type"] == "salida" and m["reason"] == "venta"]
        assert salidas, movs
        assert salidas[0]["quantity"] == 3
        assert salidas[0]["stock_after"] == before - 3

        assert any(s["id"] == sale["id"] for s in admin.get(f"{API}/sales").json()["sales"])

    def test_sale_over_stock_rejected_and_no_side_effect(self, admin, qa_product):
        pid = qa_product["id"]
        before = stock_of(admin, pid)
        sales_before = len(admin.get(f"{API}/sales").json()["sales"])
        r = admin.post(f"{API}/sales", json={"items": [{"product_id": pid, "quantity": before + 100}]})
        assert r.status_code == 400, r.text[:300]
        assert "Stock insuficiente" in r.json()["detail"]
        assert stock_of(admin, pid) == before
        assert len(admin.get(f"{API}/sales").json()["sales"]) == sales_before

    def test_sale_empty_items_422(self, admin):
        assert admin.post(f"{API}/sales", json={"items": []}).status_code == 422

    def test_sale_zero_quantity_422(self, admin, qa_product):
        r = admin.post(f"{API}/sales", json={"items": [{"product_id": qa_product["id"], "quantity": 0}]})
        assert r.status_code == 422

    def test_export_sales_csv_with_range(self, admin):
        r = admin.get(f"{API}/sales/export/csv", params={"from_date": "2020-01-01", "to_date": "2030-01-01"})
        assert r.status_code == 200
        assert "csv" in r.headers.get("content-type", "").lower()
        assert "fecha" in r.text.splitlines()[0]


class TestPurchaseFlow:
    def test_purchase_increments_stock_and_movement(self, admin, qa_product):
        pid = qa_product["id"]
        before = stock_of(admin, pid)
        r = admin.post(f"{API}/purchases", json={
            "supplier": "TEST_Proveedor",
            "items": [{"product_id": pid, "quantity": 10, "unit_cost": 4.5}],
            "payment_method": "efectivo", "status": "completada"})
        assert r.status_code == 200, r.text[:300]
        purchase = r.json().get("purchase", r.json())
        assert "_id" not in purchase
        assert purchase["total"] == 45.0, purchase

        assert stock_of(admin, pid) == before + 10

        movs = admin.get(f"{API}/movements", params={"product_id": pid, "type": "entrada"}).json()["movements"]
        compras = [m for m in movs if m["reason"] == "compra"]
        assert compras and compras[0]["quantity"] == 10
        assert compras[0]["stock_after"] == before + 10

    def test_purchase_export_csv(self, admin):
        r = admin.get(f"{API}/purchases/export/csv")
        assert r.status_code == 200


class TestMovements:
    def test_entry_reposicion(self, admin, qa_product):
        pid = qa_product["id"]
        before = stock_of(admin, pid)
        r = admin.post(f"{API}/movements", json={
            "product_id": pid, "type": "entrada", "reason": "reposicion",
            "quantity": 7, "notes": "TEST_reposicion"})
        assert r.status_code == 200, r.text[:300]
        assert r.json()["stock"] == before + 7
        assert stock_of(admin, pid) == before + 7

    def test_exit_danado(self, admin, qa_product):
        pid = qa_product["id"]
        before = stock_of(admin, pid)
        r = admin.post(f"{API}/movements", json={
            "product_id": pid, "type": "salida", "reason": "danado", "quantity": 2})
        assert r.status_code == 200, r.text[:300]
        assert r.json()["stock"] == before - 2
        assert stock_of(admin, pid) == before - 2

    def test_exit_over_stock_rejected(self, admin, qa_product):
        pid = qa_product["id"]
        before = stock_of(admin, pid)
        r = admin.post(f"{API}/movements", json={
            "product_id": pid, "type": "salida", "reason": "perdida", "quantity": before + 50})
        assert r.status_code == 400
        assert "Stock insuficiente" in r.json()["detail"]
        assert stock_of(admin, pid) == before

    def test_invalid_reason_for_type(self, admin, qa_product):
        r = admin.post(f"{API}/movements", json={
            "product_id": qa_product["id"], "type": "entrada", "reason": "venta", "quantity": 1})
        assert r.status_code == 400
        assert "Motivo" in r.json()["detail"]

    def test_movement_unknown_product_404(self, admin):
        r = admin.post(f"{API}/movements", json={
            "product_id": "nope", "type": "entrada", "reason": "reposicion", "quantity": 1})
        assert r.status_code == 404


class TestExpenses:
    def test_create_list_delete_expense(self, admin):
        summary_before = admin.get(f"{API}/finances/summary").json()
        r = admin.post(f"{API}/expenses", json={
            "category": "servicios", "description": "TEST_Luz QA", "amount": 123.45})
        assert r.status_code in (200, 201), r.text[:300]
        exp = r.json().get("expense", r.json())
        eid = exp["id"]
        assert exp["amount"] == 123.45
        assert "_id" not in exp

        listed = {e["id"]: e for e in admin.get(f"{API}/expenses").json()["expenses"]}
        assert eid in listed and listed[eid]["description"] == "TEST_Luz QA"

        summary_after = admin.get(f"{API}/finances/summary").json()
        if "gastos" in summary_before and "gastos" in summary_after:
            assert summary_after["gastos"] >= summary_before["gastos"]

        r = admin.delete(f"{API}/expenses/{eid}")
        assert r.status_code in (200, 204)
        listed = {e["id"]: e for e in admin.get(f"{API}/expenses").json()["expenses"]}
        assert eid not in listed

    def test_expense_validation(self, admin):
        r = admin.post(f"{API}/expenses", json={"category": "servicios", "description": "x", "amount": -5})
        assert r.status_code == 422

    def test_delete_unknown_expense_404(self, admin):
        assert admin.delete(f"{API}/expenses/nope").status_code == 404
