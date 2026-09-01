import asyncio, json, logging, os, time
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from config import settings
from database import db
from models import ChatIn
from security import new_id, now_iso, require_business
from stats import build_assistant_context
from routes_ai import margin_analysis
from cubi.engine import build_business_insights

router = APIRouter(tags=["assistant"])
logger = logging.getLogger(__name__)
SEED_CONTENT = {"Consulta inicial del negocio", "Estoy listo para ayudarte a revisar el negocio."}


async def _ensure_local_history_seed(business_id: str):
    if await db.assistant_messages.count_documents({"business_id": business_id}) > 0:
        return
    await db.assistant_messages.insert_many([
        {"id": new_id(), "business_id": business_id, "role": "user", "content": "Consulta inicial del negocio", "created_at": now_iso()},
        {"id": new_id(), "business_id": business_id, "role": "assistant", "content": "Estoy listo para ayudarte a revisar el negocio.", "created_at": now_iso()},
    ])


def _money(value, currency="USD"):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    formatted = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} {currency}" if currency else formatted


def _number(value):
    try:
        number = float(value)
        return f"{number:,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def _percent(value):
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return None


def _product_name(product):
    return (product or {}).get("product_name") or (product or {}).get("name") or "ese producto"


def _classify_intent(message: str) -> str:
    text = (message or "").strip().lower()
    if not text:
        return "unknown"
    greetings = {"hola", "buenas", "hello", "hey", "holi", "buen día", "buenos días", "buenas tardes", "buenas noches"}
    if text in greetings or text.startswith(("hola ", "buenas ")):
        return "greeting"
    groups = {
        "improve_sales": ("mejorar ventas", "vender más", "vender mas", "aumentar ventas", "subir ventas", "más ventas", "mas ventas", "cómo vendo", "como vendo", "qué hago para vender", "que hago para vender"),
        "sales_detail": ("qué tanto", "que tanto", "cuánto subieron", "cuanto subieron", "cuánto crecieron", "cuanto crecieron", "qué porcentaje", "que porcentaje", "porcentaje de ventas", "cuánto crecieron mis ventas", "cuanto crecieron mis ventas"),
        "sales": ("ventas", "vendí", "vendi", "vendiendo", "vendido", "cómo van", "como van", "cómo estoy vendiendo", "como estoy vendiendo", "cómo fueron las ventas", "como fueron las ventas"),
        "top_products": ("producto más vendido", "producto mas vendido", "productos más vendidos", "productos mas vendidos", "qué se vende más", "que se vende mas", "mejores productos", "qué productos venden", "que productos venden", "qué producto debo vender", "que producto debo vender", "qué debería vender", "que deberia vender"),
        "restock": ("reponer", "reposición", "reposicion", "qué compro", "que compro", "qué debo comprar", "que debo comprar", "qué comprar", "que comprar", "stock", "inventario", "se va a acabar", "se acaba"),
        "profit": ("ganancia", "ganancias", "utilidad", "margen", "rentable", "rentabilidad", "qué me deja más", "que me deja mas", "más ganancia", "mas ganancia"),
        "anomaly": ("alerta", "anomalía", "anomalia", "raro", "extraño", "extrano", "caída", "caida", "problema con ventas"),
        "forecast": ("proyección", "proyeccion", "pronóstico", "pronostico", "futuro", "próximos días", "proximos dias", "cuánto venderé", "cuanto vendre", "qué espero vender", "que espero vender"),
    }
    for intent, keywords in groups.items():
        if any(keyword in text for keyword in keywords):
            return intent
    return "unknown"


async def _native_cubi_reply(business_id: str, user_message: str) -> str:
    """Conversational deterministic Cubi. No external LLM is required."""
    insights = await build_business_insights(db, business_id)
    history = insights.get("history", {})
    forecast = insights.get("forecast", {})
    inventory = insights.get("inventory_recommendations", [])
    anomaly = insights.get("anomaly", {})
    top = insights.get("top_products", [])
    abc = insights.get("abc_analysis", [])

    sales_count = history.get("sales_count", 0)
    observed_days = history.get("observed_days", 0)
    business = await db.businesses.find_one({"id": business_id}, {"_id": 0, "currency": 1}) or {}
    currency = business.get("currency", "USD")
    urgent = [x for x in inventory if x.get("suggested_purchase", 0) > 0]
    intent = _classify_intent(user_message)

    if intent == "greeting":
        return "¡Hola! 👋 ¿Cómo va el negocio? Puedo ayudarte con ventas, productos, inventario o ganancias."

    if sales_count == 0 and intent in {"sales", "sales_detail", "improve_sales", "top_products", "profit", "forecast", "anomaly"}:
        return "Todavía no tengo suficientes ventas registradas para analizar eso. Cuando haya más movimiento, te diré qué está funcionando y qué mejorar."

    if intent == "improve_sales":
        if top:
            names = ", ".join(_product_name(p) for p in top[:3])
            return f"Empezaría por lo que ya funciona: {names}. También puedo decirte cuál te deja más ganancia. ¿Lo revisamos?"
        return "Empezaría revisando tus productos más vendidos y los que dejan más ganancia. ¿Quieres que los compare?"

    if intent == "sales_detail":
        trend = forecast.get("trend_percent")
        if trend is None:
            return f"Tienes {sales_count} ventas registradas. Todavía no tengo una comparación confiable del crecimiento."
        direction = "crecieron" if trend > 0 else "bajaron" if trend < 0 else "se mantuvieron estables"
        return f"Tus ventas {direction} aproximadamente un {_percent(abs(trend))}. ¿Quieres que te diga qué productos explican ese cambio?"

    if intent == "sales":
        trend = forecast.get("trend_percent")
        if trend is None:
            return f"Tienes {sales_count} ventas en {observed_days} días con actividad. ¿Quieres que revise tus productos?"
        if trend > 0:
            return f"Van bien: tus ventas muestran una tendencia al alza de {_percent(trend)}. 📈 ¿Quieres saber qué producto está impulsando el crecimiento?"
        if trend < 0:
            return f"Hay una caída reciente de {_percent(abs(trend))}. Vale la pena revisar qué productos están perdiendo movimiento. ¿Lo hago?"
        return "Tus ventas están bastante estables. Podemos buscar qué productos tienen potencial para hacerlas crecer."

    if intent == "top_products":
        if not top:
            return "Todavía no tengo suficiente información para identificar tus productos más vendidos."
        best = top[0]
        name = _product_name(best)
        units = _number(best.get("units"))
        revenue = _money(best.get("revenue"), currency)
        return f"El que más vendes es {name}: {units} unidades y {revenue} en ventas. ¿Quieres que te diga cuáles siguen después?"

    if intent == "restock":
        if not urgent:
            return "Por ahora no veo productos que necesiten reposición urgente. También puedo revisar cuáles tienen poco stock."
        first = urgent[0]
        names = ", ".join(_product_name(x) for x in urgent[:4])
        qty = first.get("suggested_purchase", 0)
        extra = f" y {len(urgent) - 4} más" if len(urgent) > 4 else ""
        return f"Primero revisaría {names}{extra}. Por ejemplo, de { _product_name(first) } conviene comprar unas {_number(qty)} unidades."

    if intent == "profit":
        candidates = [p for p in abc if p.get("profit") is not None]
        if not candidates:
            return "Todavía no tengo suficientes datos de costos para calcular qué producto te deja más ganancia."
        best = max(candidates, key=lambda p: float(p.get("profit") or 0))
        profit = _money(best.get("profit"), currency)
        margin = _percent(best.get("margin_percent"))
        detail = f" y un margen de {margin}" if margin else ""
        return f"El que más ganancia te deja es {_product_name(best)}: {profit}{detail}. ¿Quieres comparar los 3 mejores?"

    if intent == "forecast":
        if not forecast.get("available"):
            return "Todavía no tengo suficientes datos para hacer una buena proyección."
        value = _money(forecast.get("predicted_period_revenue"), currency)
        days = forecast.get("horizon_days", 7)
        return f"Para los próximos {days} días estimo unas ventas de {value}. Es una guía, no una garantía."

    if intent == "anomaly":
        if anomaly.get("is_anomaly"):
            return "Sí, detecté un cambio fuera de lo habitual en tus ingresos. Podemos revisar qué venta o producto pudo provocarlo."
        return "No veo nada especialmente fuera de lo normal en tus ingresos recientes."

    if intent == "unknown":
        return "Todavía estoy aprendiendo sobre esa parte. Puedo revisar tus ventas, productos, inventario y ganancias."

    if top:
        return f"Puedo ayudarte a revisar tus ventas y productos. Ahora mismo, por ejemplo, { _product_name(top[0]) } es de los que más movimiento tiene. ¿Qué quieres saber?"
    return "Puedo ayudarte a revisar ventas, productos, inventario y ganancias. ¿Qué quieres saber?"


@router.get("/assistant/status")
async def assistant_status(user: dict = Depends(require_business)):
    key = bool(os.getenv("OPENROUTER_API_KEY") or settings.OPENAI_API_KEY)
    openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
    model = (os.getenv("OPENROUTER_MODEL") or "openrouter/auto") if openrouter else (os.getenv("OPENAI_MODEL") or "gpt-5-mini")
    return {"configured": True, "native_cubi": True, "external_ai_configured": key, "provider": "openrouter" if openrouter else "openai" if settings.OPENAI_API_KEY else "native", "model": model if key else None, "message": "Cubi está disponible con inteligencia nativa." if not key else "Cubi está configurado con inteligencia nativa y un proveedor externo opcional."}


@router.get("/assistant/history")
async def assistant_history(user: dict = Depends(require_business)):
    await _ensure_local_history_seed(user["business_id"])
    messages = await db.assistant_messages.find({"business_id": user["business_id"]}, {"_id": 0}).sort("created_at", 1).to_list(40)
    return {"messages": messages[-30:]}


@router.post("/assistant/chat")
async def assistant_chat(data: ChatIn, user: dict = Depends(require_business)):
    bid = user["business_id"]
    business = await db.businesses.find_one({"id": bid}, {"_id": 0})
    try:
        native_reply = await _native_cubi_reply(bid, data.message)
    except Exception:
        logger.exception("[assistant] native Cubi failed")
        native_reply = "Cubi está disponible, pero no pudo revisar los datos en este momento. Inténtalo de nuevo en unos segundos."

    await db.assistant_messages.insert_one({"id": new_id(), "business_id": bid, "role": "user", "content": data.message, "created_at": now_iso()})

    use_external_ai = bool(os.getenv("CUBI_EXTERNAL_AI", "false").lower() == "true")
    if not use_external_ai:
        async def native_generator():
            yield f"data: {json.dumps({'c': native_reply}, ensure_ascii=False)}\n\n"
            await db.assistant_messages.insert_one({"id": new_id(), "business_id": bid, "role": "assistant", "content": native_reply, "created_at": now_iso()})
            yield "data: [DONE]\n\n"
        return StreamingResponse(native_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"})

    try:
        context = await build_assistant_context(bid, business or {})
        margin_data = await margin_analysis(user)
        summary = margin_data["summary"]
        alerts = margin_data["alerts"][:10]
        context += f"\n\nANÁLISIS FINANCIERO AI-01 (90 días):\nIngresos: {summary['revenue_90d']} | Costo realizado: {summary['realized_cost_90d']} | Utilidad realizada: {summary['realized_profit_90d']} | Margen realizado: {summary['realized_margin_percent']}%\nAlertas detectadas: {summary['alerts_count']}"
        if alerts:
            context += "\nAlertas: " + " | ".join(a["message"] for a in alerts)
    except Exception:
        logger.exception("[assistant] context failed")
        context = "No se pudo cargar parte del contexto operativo."

    system_template = f'''Eres "Cubi", el asesor inteligente del negocio "{(business or {}).get("name", "tu negocio")}". Responde SIEMPRE en español, con frases cortas, tono cercano, práctico y directo. Usa EXCLUSIVAMENTE los datos del negocio. No inventes cifras. Si falta un dato, dilo. No uses lenguaje técnico ni entregues informes largos. Responde normalmente en 1 a 4 frases y, cuando tenga sentido, termina con una pregunta sencilla que ayude al dueño a profundizar. La moneda es {(business or {}).get("currency", "USD")}.\n\nDATOS:\n{context}'''
    history_messages = await db.assistant_messages.find({"business_id": bid}, {"_id": 0}).sort("created_at", -1).to_list(12)
    history_messages.reverse()
    messages = [{"role": "system", "content": system_template}]
    for item in history_messages:
        if item.get("role") in {"user", "assistant"} and item.get("content") and item.get("content") not in SEED_CONTENT:
            messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": data.message})

    async def event_generator():
        full = ""
        client = None
        started = time.monotonic()
        try:
            api_key = os.getenv("OPENROUTER_API_KEY") or settings.OPENAI_API_KEY
            is_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
            if not api_key:
                raise RuntimeError("proveedor externo no configurado")
            kwargs = {"api_key": api_key, "timeout": 15.0}
            if is_openrouter:
                kwargs.update({"base_url": "https://openrouter.ai/api/v1", "default_headers": {"HTTP-Referer": "https://cuadrapp.up.railway.app", "X-Title": "CuadraApp"}})
            client = AsyncOpenAI(**kwargs)
            model = (os.getenv("OPENROUTER_MODEL") or "openrouter/auto") if is_openrouter else (os.getenv("OPENAI_MODEL") or "gpt-5-mini")
            stream = await asyncio.wait_for(client.chat.completions.create(model=model, messages=messages, stream=True), timeout=20)
            iterator = stream.__aiter__()
            while True:
                if time.monotonic() - started > 60:
                    raise TimeoutError("El proveedor externo tardó demasiado.")
                try:
                    chunk = await asyncio.wait_for(iterator.__anext__(), timeout=15)
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    raise TimeoutError("El proveedor externo dejó de responder.")
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    full += delta
                    yield f"data: {json.dumps({'c': delta}, ensure_ascii=False)}\n\n"
            if not full:
                raise RuntimeError("El proveedor externo no devolvió contenido.")
        except Exception:
            logger.exception("[assistant] external AI provider error; using native Cubi fallback")
            full = native_reply
            yield f"data: {json.dumps({'c': full, 'fallback': True}, ensure_ascii=False)}\n\n"
        finally:
            try:
                await db.assistant_messages.insert_one({"id": new_id(), "business_id": bid, "role": "assistant", "content": full, "created_at": now_iso()})
            except Exception:
                logger.exception("[assistant] persist failed")
            if client:
                try:
                    await client.close()
                except Exception:
                    pass
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"})
