from datetime import datetime, timezone, timedelta

from database import db
from financial_engine import calculate_financial_snapshot, _parse_dt, _valid


def _dt(doc):
    return _parse_dt(doc.get("created_at") or doc.get("date"))


async def compute_dashboard(bid: str) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    d30 = now - timedelta(days=30)
    d60 = now - timedelta(days=60)

    products = await db.products.find({"business_id": bid}, {"_id": 0}).to_list(10000)
    sales = await db.sales.find({"business_id": bid}, {"_id": 0}).to_list(50000)
    purchases = await db.purchases.find({"business_id": bid}, {"_id": 0}).to_list(20000)

    # Single source of truth for core financial metrics.
    financial = await calculate_financial_snapshot(bid, d30, now)
    previous_financial = await calculate_financial_snapshot(bid, d60, d30)

    valid_sales = [s for s in sales if _valid(s)]
    sales_today = [s for s in valid_sales if (_dt(s) and _dt(s) >= today_start)]
    sales_30 = [s for s in valid_sales if (_dt(s) and _dt(s) >= d30)]

    ventas_hoy = round(sum(float(s.get("total", 0) or 0) for s in sales_today), 2)
    num_ventas_hoy = len(sales_today)
    ventas_30 = financial["revenue"]
    ventas_prev = previous_financial["revenue"]
    utilidad_30 = financial["gross_profit"]
    gastos_30 = financial["operating_expenses"]
    compras_30 = round(sum(float(p.get("total", 0) or 0) for p in purchases if _valid(p) and (_dt(p) and _dt(p) >= d30)), 2)
    ganancia = financial["operating_profit"]
    margen = financial["gross_margin"]
    ticket = round(ventas_30 / len(sales_30), 2) if sales_30 else 0
    variacion = round((ventas_30 - ventas_prev) / ventas_prev * 100, 1) if ventas_prev else None

    trend = []
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).date()
        total_d = sum(float(s.get("total", 0) or 0) for s in valid_sales if _dt(s) and _dt(s).date() == day)
        trend.append({"fecha": day.strftime("%d/%m"), "ventas": round(total_d, 2)})

    agg = {}
    for s in sales_30:
        for it in s.get("items", []):
            pid = it.get("product_id")
            a = agg.setdefault(pid, {"nombre": it.get("name", "Producto"), "unidades": 0, "ingresos": 0, "ganancia": 0})
            qty = float(it.get("quantity", 0) or 0)
            line_total = float(it.get("line_total", 0) or 0)
            cost = float(it.get("cost", 0) or 0)
            a["unidades"] += qty
            a["ingresos"] += line_total
            a["ganancia"] += line_total - cost * qty
    for a in agg.values():
        a["ingresos"] = round(a["ingresos"], 2)
        a["ganancia"] = round(a["ganancia"], 2)
    top_vendidos = sorted(agg.values(), key=lambda x: -x["unidades"])[:5]
    top_rentables = sorted(agg.values(), key=lambda x: -x["ganancia"])[:5]

    agotados = [{"id": p["id"], "nombre": p["name"], "stock": p["stock"], "min_stock": p.get("min_stock", 0)} for p in products if p.get("stock", 0) <= 0]
    bajos = [{"id": p["id"], "nombre": p["name"], "stock": p["stock"], "min_stock": p.get("min_stock", 0)} for p in products if 0 < p.get("stock", 0) <= p.get("min_stock", 0)]

    daily_rate = {pid: a["unidades"] / 30 for pid, a in agg.items()}
    por_agotarse = []
    for p in products:
        rate = daily_rate.get(p.get("id"))
        stock = float(p.get("stock", 0) or 0)
        if rate and stock > 0:
            days_left = stock / rate
            if days_left <= 10:
                por_agotarse.append({"nombre": p["name"], "dias": max(1, round(days_left)), "stock": stock})
    por_agotarse.sort(key=lambda x: x["dias"])

    if not valid_sales:
        nivel, titulo, mensaje = "verde", "Todo listo para empezar", "Registra tu primera venta para activar los indicadores de tu negocio."
    elif agotados or (ventas_30 > 0 and margen < 0):
        nivel, titulo = "rojo", "Acción urgente requerida"
        mensaje = "Tienes productos agotados o margen negativo. Revisa las recomendaciones."
    elif bajos or (variacion is not None and variacion < -5):
        nivel, titulo = "amarillo", "Atención requerida"
        mensaje = "Hay productos por agotarse o tus ventas bajaron respecto al período anterior."
    else:
        nivel, titulo, mensaje = "verde", "Negocio en buen estado", "Ventas estables, margen positivo y stock saludable."

    recomendaciones = []
    if not valid_sales:
        recomendaciones.append({"level": "info", "text": "Registra tu primera venta desde el botón '+ Venta' para ver cómo descuenta tu stock automáticamente."})
    if agotados:
        names = ", ".join(p["nombre"] for p in agotados[:3])
        recomendaciones.append({"level": "urgente", "text": f"Tienes {len(agotados)} producto(s) agotado(s): {names}. Repón cuanto antes para no perder ventas."})
    if bajos:
        names = ", ".join(p["nombre"] for p in bajos[:3])
        recomendaciones.append({"level": "atencion", "text": f"{len(bajos)} producto(s) están por debajo del stock mínimo ({names}). Considera reponerlos."})
    for pa in por_agotarse[:3]:
        recomendaciones.append({"level": "atencion", "text": f"'{pa['nombre']}' podría agotarse en ~{pa['dias']} día(s) al ritmo actual de venta."})
    if variacion is not None and variacion > 5:
        recomendaciones.append({"level": "positivo", "text": f"Tus ventas subieron {variacion}% respecto al período anterior. Asegura stock de tus productos más vendidos."})
    elif variacion is not None and variacion < -5:
        recomendaciones.append({"level": "atencion", "text": f"Tus ventas bajaron {abs(variacion)}% respecto al período anterior. Revisa precios o considera una promoción."})
    if ventas_30 > 0 and 0 < margen < 15:
        recomendaciones.append({"level": "atencion", "text": f"Tu margen bruto es {margen}%. Revisa el costo y precio de tus productos menos rentables."})
    if top_vendidos:
        tv = top_vendidos[0]
        ganancia_pct = round(tv["ganancia"] / tv["ingresos"] * 100, 1) if tv["ingresos"] else 0
        if tv["unidades"] >= 10 and ganancia_pct < 20:
            recomendaciones.append({"level": "atencion", "text": f"'{tv['nombre']}' vende mucho pero deja solo {ganancia_pct}% de margen. Considera ajustar su precio."})
    if compras_30 > 0 and ventas_30 > 0 and compras_30 > ventas_30 * 0.9:
        recomendaciones.append({"level": "info", "text": "Estás comprando casi todo lo que vendes. Revisa si tienes capital inmovilizado en productos de baja rotación."})

    recent_sales = sorted(valid_sales, key=lambda s: _dt(s) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:5]

    return {
        "ventas_hoy": ventas_hoy,
        "num_ventas_hoy": num_ventas_hoy,
        "ventas_30": ventas_30,
        "ventas_prev": ventas_prev,
        "variacion": variacion,
        "gastos_30": gastos_30,
        "compras_30": compras_30,
        "utilidad_30": utilidad_30,
        "ganancia_estimada": ganancia,
        "margen": margen,
        "margen_bruto": financial["gross_margin"],
        "margen_operativo": financial["operating_margin"],
        "cogs_30": financial["cogs"],
        "flujo_caja_30": financial["net_cash_flow"],
        "cash_in_30": financial["cash_in"],
        "cash_out_30": financial["cash_out"],
        "saldo_caja": financial["cash_balance"],
        "por_cobrar": financial["receivables"],
        "por_pagar": financial["payables"],
        "capital_trabajo": financial["working_capital"],
        "ticket_promedio": ticket,
        "num_ventas_30": len(sales_30),
        "trend": trend,
        "top_vendidos": top_vendidos,
        "top_rentables": top_rentables,
        "agotados": agotados,
        "bajos": bajos,
        "por_agotarse": por_agotarse,
        "semaforo": {"nivel": nivel, "titulo": titulo, "mensaje": mensaje},
        "recomendaciones": recomendaciones[:6],
        "productos_count": len(products),
        "valor_inventario": financial["inventory_value"],
        "recent_sales": [
            {
                "id": s["id"],
                "created_at": s["created_at"],
                "total": s["total"],
                "profit": s.get("profit", 0),
                "payment_method": s.get("payment_method"),
                "items_count": len(s.get("items", [])),
                "resumen": ", ".join(f"{i.get('name', 'Producto')} x{float(i.get('quantity', 0) or 0):g}" for i in s.get("items", [])[:2]) + ("…" if len(s.get("items", [])) > 2 else ""),
            }
            for s in recent_sales
        ],
    }


async def build_assistant_context(bid: str, business: dict) -> str:
    d = await compute_dashboard(bid)
    products = await db.products.find({"business_id": bid}, {"_id": 0}).to_list(200)
    lines = [
        f"Negocio: {business.get('name')} (rubro: {business.get('type')}), moneda: {business.get('currency', 'USD')}",
        f"Ventas hoy: {d['ventas_hoy']} | Ventas últimos 30 días: {d['ventas_30']} | Período anterior (30 días): {d['ventas_prev']}",
        f"Ganancia operativa (30d): {d['ganancia_estimada']} | Margen bruto: {d['margen_bruto']}% | Margen operativo: {d['margen_operativo']}% | Ticket promedio: {d['ticket_promedio']}",
        f"COGS (30d): {d['cogs_30']} | Gastos operativos (30d): {d['gastos_30']} | Compras (30d): {d['compras_30']}",
        f"Caja: {d['saldo_caja']} | Flujo de caja 30d: {d['flujo_caja_30']} | Por cobrar: {d['por_cobrar']} | Por pagar: {d['por_pagar']}",
        f"Valor del inventario: {d['valor_inventario']} | Capital de trabajo: {d['capital_trabajo']}",
        f"Semáforo: {d['semaforo']['nivel']} — {d['semaforo']['titulo']}",
        f"Productos agotados: {', '.join(p['nombre'] for p in d['agotados']) or 'ninguno'}",
        'Productos con stock bajo: ' + (', '.join(f"{p['nombre']} ({p['stock']:g}/{p['min_stock']:g})" for p in d['bajos']) or 'ninguno'),
        'Por agotarse pronto: ' + (', '.join(f"{p['nombre']} (~{p['dias']} días)" for p in d['por_agotarse']) or 'ninguno'),
        'Más vendidos (30d): ' + (', '.join(f"{t['nombre']} ({t['unidades']:g} uds)" for t in d['top_vendidos']) or 'sin datos'),
        'Más rentables (30d): ' + (', '.join(f"{t['nombre']} ({t['ganancia']})" for t in d['top_rentables']) or 'sin datos'),
        "Inventario actual: " + ("; ".join(f"{p['name']}: {p['stock']:g} {p.get('unit','unidad')}(s), costo {p.get('purchase_price',0)}, precio {p.get('sale_price',0)}, mín {p.get('min_stock',0)}" for p in products[:60]) or "sin productos"),
        "Ventas recientes: " + ("; ".join(f"{s['created_at'][:10]} {s['resumen']} = {s['total']}" for s in d['recent_sales']) or "sin ventas"),
    ]
    return "\n".join(lines)
