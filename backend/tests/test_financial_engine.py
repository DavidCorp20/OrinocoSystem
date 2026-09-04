from datetime import datetime, timezone

from financial_engine import _money, _parse_dt, _valid


def test_money_rounds_to_two_decimals():
    assert _money(10.129) == 10.13


def test_parse_dt_accepts_iso_and_zulu():
    dt = _parse_dt("2026-09-03T12:30:00Z")
    assert dt == datetime(2026, 9, 3, 12, 30, tzinfo=timezone.utc)


def test_parse_dt_rejects_invalid_values():
    assert _parse_dt("not-a-date") is None
    assert _parse_dt(None) is None


def test_valid_excludes_financial_void_statuses():
    assert _valid({"status": "pagada"})
    assert not _valid({"status": "anulada"})
    assert not _valid({"status": "cancelada"})
    assert _valid({})
