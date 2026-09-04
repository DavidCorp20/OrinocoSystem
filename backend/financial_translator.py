"""Translate Financial Engine facts into plain-language business insights.

The translator is deterministic and auditable: it never invents facts and every
insight is tied to a metric returned by the Financial Engine.
"""


def _money(value):
    return round(float(value or 0), 2)


def _pct(value):
    return round(float(value or 0), 2)


def translate_financial_snapshot(snapshot: dict) -> dict:
    revenue = _money(snapshot.get("revenue"))
    cogs = _money(snapshot.get("cogs"))
    gross_profit = _money(snapshot.get("gross_profit"))
    expenses = _money(snapshot.get("operating_expenses"))
    operating_profit = _money(snapshot.get("operating_profit"))
    gross_margin = _pct(snapshot.get("gross_margin"))
    operating_margin = _pct(snapshot.get("operating_margin"))
    cash_in = _money(snapshot.get("cash_in"))
    cash_out = _money(snapshot.get("cash_out"))
    net_cash_flow = _money(snapshot.get("net_cash_flow"))
    cash_balance = _money(snapshot.get("cash_balance"))
    receivables = _money(snapshot.get("receivables"))
    payables = _money(snapshot.get("payables"))
    inventory = _money(snapshot.get("inventory_value"))
    working_capital = _money(snapshot.get("working_capital"))

    insights = []
    actions = []
    warnings = []

    if revenue <= 0:
        insights.append({
            "type": "info",
            "metric": "revenue",
            "title": "Todavía no hay ventas en el período",
            "explanation": "PLATIA necesita ventas registradas para evaluar rentabilidad y tendencia.",
        })
        actions.append("Registra ventas reales y mantén sus costos históricos para activar el análisis financiero.")
    else:
        insights.append({
            "type": "fact",
            "metric": "revenue",
            "title": f"Generaste {revenue:,.2f} en ventas",
            "explanation": f"De esas ventas, {gross_profit:,.2f} quedan después del costo de mercancía.",
        })

    if revenue > 0:
        cogs_ratio = cogs / revenue * 100
        expense_ratio = expenses / revenue * 100
        insights.append({
            "type": "margin",
            "metric": "gross_margin",
            "title": f"Tu margen bruto es {gross_margin}%",
            "explanation": f"El costo de mercancía consume aproximadamente {cogs_ratio:.1f}% de tus ventas.",
        })
        insights.append({
            "type": "expense",
            "metric": "operating_margin",
            "title": f"Tu margen operativo es {operating_margin}%",
            "explanation": f"Tus gastos operativos representan aproximadamente {expense_ratio:.1f}% de las ventas.",
        })

        if gross_margin < 20:
            warnings.append({
                "metric": "gross_margin",
                "severity": "high",
                "title": "Margen bruto bajo",
                "explanation": "Hay poco espacio entre precio de venta y costo. Un aumento de costos puede deteriorar rápidamente la rentabilidad.",
            })
            actions.append("Revisa los productos de mayor volumen y menor margen antes de aumentar gastos o inventario.")
        elif gross_margin < 35:
            warnings.append({
                "metric": "gross_margin",
                "severity": "medium",
                "title": "Margen bruto ajustado",
                "explanation": "Existe rentabilidad, pero el negocio tiene menos colchón ante aumentos de costos o descuentos.",
            })

        if operating_margin < 0:
            warnings.append({
                "metric": "operating_margin",
                "severity": "high",
                "title": "Las operaciones están perdiendo dinero",
                "explanation": f"Después de costos y gastos operativos, el resultado es {operating_profit:,.2f}.",
            })
            actions.append("Prioriza reducir gastos estructurales o mejorar margen antes de acelerar el crecimiento.")
        elif operating_margin < 10:
            warnings.append({
                "metric": "operating_margin",
                "severity": "medium",
                "title": "Rentabilidad operativa limitada",
                "explanation": "El negocio genera utilidad, pero el margen deja poco espacio para errores o shocks de costos.",
            })

    if cash_out > 0 or cash_in > 0:
        insights.append({
            "type": "cash",
            "metric": "net_cash_flow",
            "title": f"El flujo neto de caja fue {net_cash_flow:,.2f}",
            "explanation": f"Entraron {cash_in:,.2f} y salieron {cash_out:,.2f} por movimientos registrados en caja.",
        })
        if net_cash_flow < 0:
            warnings.append({
                "metric": "net_cash_flow",
                "severity": "high",
                "title": "La caja está consumiéndose",
                "explanation": "El negocio tuvo más salidas de caja que entradas durante el período.",
            })
            actions.append("Investiga qué salidas están consumiendo caja y evita financiar inventario o gastos sin retorno visible.")

    if receivables > 0:
        insights.append({
            "type": "working_capital",
            "metric": "receivables",
            "title": f"Tienes {receivables:,.2f} por cobrar",
            "explanation": "Parte de las ventas todavía no se ha convertido en efectivo disponible.",
        })
        if revenue > 0 and receivables / revenue >= 0.25:
            warnings.append({
                "metric": "receivables",
                "severity": "medium",
                "title": "Una parte relevante de tus ventas está pendiente de cobro",
                "explanation": "Las cuentas por cobrar representan al menos una cuarta parte de las ventas del período.",
            })
            actions.append("Revisa antigüedad y vencimientos de las cuentas por cobrar antes de seguir vendiendo a crédito.")

    if payables > 0:
        insights.append({
            "type": "working_capital",
            "metric": "payables",
            "title": f"Tienes {payables:,.2f} por pagar",
            "explanation": "Son obligaciones pendientes que deberán convertirse en futuras salidas de caja.",
        })

    if inventory > 0:
        insights.append({
            "type": "inventory",
            "metric": "inventory_value",
            "title": f"Tienes {inventory:,.2f} invertidos en inventario",
            "explanation": "Ese capital está dentro del negocio hasta que el inventario se venda y convierta en efectivo.",
        })
        if revenue > 0 and inventory / revenue > 1:
            actions.append("Analiza rotación antes de seguir comprando: tienes más de un período de ventas equivalente en inventario registrado.")

    insights.append({
        "type": "working_capital",
        "metric": "working_capital",
        "title": f"Tu capital de trabajo es {working_capital:,.2f}",
        "explanation": "PLATIA lo calcula como caja + cuentas por cobrar + inventario - cuentas por pagar.",
    })

    if cash_balance < 0:
        warnings.append({
            "metric": "cash_balance",
            "severity": "high",
            "title": "El saldo de caja calculado es negativo",
            "explanation": "Las salidas acumuladas del ledger superan las entradas registradas.",
        })

    data_quality = snapshot.get("data_quality", {})
    if any(data_quality.get(k, 0) for k in ("missing_sale_costs", "missing_date_records", "missing_inventory_cost_products")):
        warnings.append({
            "metric": "data_quality",
            "severity": "medium",
            "title": "Hay datos que limitan la precisión del análisis",
            "explanation": "PLATIA detectó registros con costos, fechas o costos de inventario incompletos.",
        })
        actions.append("Completa costos y fechas faltantes para mejorar la calidad de las conclusiones financieras.")

    return {
        "summary": {
            "headline": _headline(operating_profit, operating_margin, net_cash_flow),
            "revenue": revenue,
            "gross_profit": gross_profit,
            "operating_profit": operating_profit,
            "gross_margin": gross_margin,
            "operating_margin": operating_margin,
            "net_cash_flow": net_cash_flow,
            "cash_balance": cash_balance,
            "receivables": receivables,
            "payables": payables,
            "inventory_value": inventory,
            "working_capital": working_capital,
        },
        "insights": insights[:8],
        "warnings": warnings[:6],
        "actions": list(dict.fromkeys(actions))[:6],
        "methodology": "Conclusiones determinísticas construidas exclusivamente a partir del Financial Engine; no se generan hechos no presentes en los datos.",
    }


def _headline(operating_profit, operating_margin, net_cash_flow):
    if operating_profit < 0:
        return "El negocio vende, pero hoy la operación no está dejando utilidad."
    if net_cash_flow < 0:
        return "El negocio puede ser rentable y aun así estar consumiendo caja."
    if operating_margin < 10:
        return "El negocio es rentable, pero tiene un margen operativo estrecho."
    return "El negocio genera utilidad operativa y mantiene flujo de caja positivo en el período."
