from datetime import datetime, timezone, timedelta

from database import db


def _dt(doc) -> datetime:
    return datetime.fromisoformat(doc["created_at"])


async def compute_dashboard(bid: str) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    d30 = now - timedelta(days=30)
    d60 = now - timedelta(days=60)

    products = await db.products.find({"business_id": bid}, {"_id": 0}).to_list(10000)
    sales = await db.sales.find({"business_id": bid}, {"_id": 0}).to_list(50000)
    purchases = await db.purchases.find({"business_id": bid}, {"_id": 0}).to_list(20000)
    expenses = await db.expenses.find({"business_id": bid}, {"_id": 0}).to_list(20000)

    sales_30 = [s for s in sales if _dt(s) >= d30]
    sales_prev = [s for s in sales if d60 <= _dt(s) < d30]
    sales_today = [s for s in sales if _dt(s) >= today_start]

    ventas_hoy = round(sum(s["total"] for s in sales_today), 2)
    num_ventas_hoy = len(sales_today)
    ventas_30 = round(sum(s["total"] for s in sales_30), 2)
    ventas_prev = round(sum(s["total"] for s in sales_prev), 2)
    utilidad_30 = round(sum(s["profit"] for s in sales_30), 2)
    gastos_30 = round(sum(e["amount"] for e in expenses if _dt(e) >= d30), 2)
    compras_30 = round(sum(p["total"] for p in purchases if _dt(p) >= d30), 2)
    ganancia = round(utilidad_30 - gastos_30, 2)
    margen = round(utilidad_30 / ventas_30 * 100, 1) if ventas_30 else 0
    ticket = round(ventas_30 / len(sales_30), 2) if sales_30 else 0
    variacion = round((ventas_30 - ventas_prev) / ventas_prev * 100, 1) if ventas_prev else None

    trend = []
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).date()
        total_d = sum(s["total"] for s in sales if _dt(s).date() == day)
        trend.append({"fecha": day.strftime("%d/%m"), "ventas": round(total_d, 2)})

    agg = {}
    for s in sales_30:
        for it in s["items"]:
            a = agg.setdefault(it["product_id"], {"nombre": it["name"], "unidades": 0, "ingresos": 0, "ganancia": 0})
            a["unidades"] += it["quantity"]
            a["ingresos"] += it["line_total"]
            a["ganancia"] += it["line_total"] - it["cost"] * it["quantity"]
    for a in agg.values():
        a["ingresos"] = round(a["ingresos"], 2)
        a["ganancia"] = round(a["ganancia"], 2)
    top_vendidos = sorted(agg.values(), key=lambda x: -x["unidades"])[:5]
    top_rentables = sorted(agg.values(), key=lambda x: -x["ganancia"])[:5]

    agotados = [{"id": p["id"], "nombre": p["name"], "stock": p["stock"], "min_stock": p.get("min_stock", 0)} for p in products if p["stock"] <= 0]
    bajos = [{"id": p["id"], "nombre": p["name"], "stock": p["stock"], "min_stock": p.get("min_stock", 0)} for p in products if 0 < p["stock"] <= p.get("min_stock", 0)]

    daily_rate = {pid: a["unidades"] / 30 for pid, a in agg.items()}
    por_agotarse = []
    for p in products:
        rate = daily_rate.get(p["id"])
        if rate and p["stock"] > 0:
            days_left = p["stock"] / rate
            if days_left <= 10:
                por_agotarse.append({"nombre": p["name"], "dias": max(1, round(days_left)), "stock": p["stock"]})
    por_agotarse.sort(key=lambda x: x["dias"])

    if not sales:
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
    if not sales:
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
        recomendaciones.append({"level": "atencion", "text": f"Tu margen es {margen}%. Revisa el costo y precio de tus productos menos rentables."})
    if top_vendidos:
        tv = top_vendidos[0]
        if tv["unidades"] >= 10 and ventas_30 > 0:
            ganancia_pct = round(tv["ganancia"] / tv["ingresos"] * 100, 1) if tv["ingresos"] else 0
            if ganancia_pct < 20:
                recomendaciones.append({"level": "atencion", "text": f"'{tv['nombre']}' vende mucho pero deja solo {ganancia_pct}% de margen. Considera ajustar su precio."})
    if compras_30 > 0 and ventas_30 > 0 and compras_30 > ventas_30 * 0.9:
        recomendaciones.append({"level": "info", "text": "Estás comprando casi todo lo que vendes. Revisa si tienes capital inmovilizado en productos de baja rotación."})

    recent_sales = sorted(sales, key=_dt, reverse=True)[:5]

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
        "valor_inventario": round(sum(p["stock"] * p.get("purchase_price", 0) for p in products), 2),
        "recent_sales": [
            {
                "id": s["id"],
                "created_at": s["created_at"],
                "total": s["total"],
                "profit": s["profit"],
                "payment_method": s["payment_method"],
                "items_count": len(s["items"]),
                "resumen": ", ".join(f"{i['name']} x{i['quantity']:g}" for i in s["items"][:2]) + ("…" if len(s["items"]) > 2 else ""),
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
        f"Ganancia estimada (30d): {d['ganancia_estimada']} | Margen: {d['margen']}% | Ticket promedio: {d['ticket_promedio']} | Núm. ventas 30d: {d['num_ventas_30']}",
        f"Gastos operativos (30d): {d['gastos_30']} | Compras (30d): {d['compras_30']} | Valor del inventario: {d['valor_inventario']}",
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
