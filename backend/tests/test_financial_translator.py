from financial_translator import translate_financial_snapshot


def snapshot(**overrides):
    data = {
        "revenue": 10000,
        "cogs": 6000,
        "gross_profit": 4000,
        "gross_margin": 40,
        "operating_expenses": 1500,
        "operating_profit": 2500,
        "operating_margin": 25,
        "cash_in": 9000,
        "cash_out": 7000,
        "net_cash_flow": 2000,
        "cash_balance": 5000,
        "receivables": 1000,
        "payables": 1200,
        "inventory_value": 3000,
        "working_capital": 7800,
        "data_quality": {
            "missing_sale_costs": 0,
            "missing_date_records": 0,
            "missing_inventory_cost_products": 0,
        },
    }
    data.update(overrides)
    return data


def test_translator_explains_healthy_business():
    result = translate_financial_snapshot(snapshot())
    assert "Generaste 10,000.00 en ventas" in result["insights"][0]["title"]
    assert result["summary"]["operating_profit"] == 2500
    assert result["warnings"] == []


def test_translator_flags_negative_operating_profit():
    result = translate_financial_snapshot(snapshot(
        gross_profit=1000,
        gross_margin=10,
        operating_expenses=1500,
        operating_profit=-500,
        operating_margin=-5,
    ))
    assert any(w["metric"] == "operating_margin" and w["severity"] == "high" for w in result["warnings"])
    assert "no está dejando utilidad" in result["summary"]["headline"]


def test_translator_separates_profitability_from_cash_flow():
    result = translate_financial_snapshot(snapshot(net_cash_flow=-500, cash_in=5000, cash_out=5500))
    assert any(w["metric"] == "net_cash_flow" for w in result["warnings"])
    assert "consumiendo caja" in result["summary"]["headline"]


def test_translator_flags_data_quality():
    result = translate_financial_snapshot(snapshot(data_quality={"missing_sale_costs": 2}))
    assert any(w["metric"] == "data_quality" for w in result["warnings"])
