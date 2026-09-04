import pytest

from ledger import is_cash_method
from models import ObligationIn, ObligationPaymentIn


def test_cash_methods_are_explicit():
    assert is_cash_method("efectivo")
    assert is_cash_method(" CASH ")
    assert is_cash_method("transferencia") is False
    assert is_cash_method("pagomovil") is False


def test_obligation_requires_positive_amount_and_valid_kind():
    doc=ObligationIn(kind="por_cobrar",contact="Cliente",description="Factura",amount=100,due_date="2026-09-30")
    assert doc.amount==100
    with pytest.raises(Exception): ObligationIn(kind="otro",contact="Cliente",description="Factura",amount=100,due_date="2026-09-30")
    with pytest.raises(Exception): ObligationPaymentIn(amount=0)


def test_obligation_payment_model_accepts_cash_and_notes():
    payment=ObligationPaymentIn(amount=25,payment_method="efectivo",notes="Abono")
    assert payment.amount==25
    assert payment.payment_method=="efectivo"
