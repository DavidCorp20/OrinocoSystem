import pytest

from ledger import is_cash_method


def test_cash_methods_are_normalized():
    assert is_cash_method("efectivo")
    assert is_cash_method(" CASH ")
    assert not is_cash_method("zelle")
    assert not is_cash_method("tarjeta")


@pytest.mark.parametrize("method", ["efectivo", "cash", "caja"])
def test_supported_cash_methods(method):
    assert is_cash_method(method)
