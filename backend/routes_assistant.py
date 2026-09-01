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


def _percent(value):
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return None


def _first_name(product):
    return (product or {}).get("name") or "ese producto"


def _classify_intent(message: str) -> str:
    text = (message or "").strip().lower()
    if not text:
        return "unknown"
    greetings = {"hola", "buenas", "hello", "hey", "holi", "buen día", "buenos días", "buenas tardes", "buenas noches"}
    if text in greetings or text.startswith(("hola ", "buenas ")):
        return "greeting"
    groups = {
        "improve_sales": ("mejorar ventas", "vender más", "vender mas", "aumentar ventas", "subir ventas", "más ventas", "mas ventas", "cómo vendo", "como vendo", "qué hago para vender", "que hago para vender"),
        "sales": ("ventas", "vendí", "vendi", "vendiendo", "vendido", "cómo van", "como van", "cómo estoy vendiendo", "como estoy vendiendo"),
        "top_products": ("producto más vendido", "producto mas vendido", "productos más vendidos", "productos mas vendidos", "qué se vende más", "que se vende mas", "mejores productos", "qué productos venden", "que productos venden"),
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
    currency = (await db.businesses.find_one({"id": business_id}, {"_id": 0, "currency": 1}) or {}).get("currency", "USD")
    urgent = [x for x in inventory if x.get("suggested_purchase", 0) > 0]
    intent = _classify_intent(user_message)

    if intent == "greeting":
        return "¡Hola! 👋 ¿Cómo va el negocio? Puedo ayudarte a revisar ventas, productos, inventario o ganancias. ¿Qué quieres revisar?"

    if sales_count == 0:
        if intent in {"sales", "improve_sales", "top_products", "profit", "forecast", "anomaly"}:
            return "Todavía no tengo suficientes ventas registradas para analizar esa parte. Cuando tengas más movimiento, puedo ayudarte a encontrar qué está funcionando y qué mejorar."

    if intent == "improve_sales":
        if top:
            names = ", ".join(_first_name(p) for p in top[:3])
            return f"Sí. Empezaría por aprovechar lo que ya funciona: {names}. También podemos revisar cuáles te dejan más ganancia. ¿Quieres que los compare?"
        return "Sí. Podemos empezar revisando qué productos se venden más y cuáles te dejan mejor ganancia. ¿Quieres que lo haga?"

    if intent == "sales":
        if not forecast:
            return f"Tienes {sales_count} ventas registradas. Todavía estoy reuniendo suficiente información para darte una lectura más completa."
        trend = forecast.get("trend_percent")
        if trend is not None:
            direction = "subiendo" if trend > 0 else "bajando" if trend < 0 else "bastante estables"
            return f"Tus ventas vienen {direction}. 📈" if trend > 0 else f"Tus ventas vienen {direction}. Vale la pena revisar qué está pasando." if trend < 0 else "Tus ventas vienen bastante estables. Podemos buscar oportunidades para hacerlas crecer."
        return f"Tienes {sales_count} ventas registradas. ¿Quieres que revise cuáles productos están moviendo más el negocio?"

    if intent == "top_products":
        if not top:
            return "Todavía no tengo suficiente información para decirte cuáles son tus productos más vendidos."
        names = ", ".join(_first_name(p) for p in top[:5])
        return f"Los que más movimiento tienen son: {names}. ¿Quieres que revise cuáles de ellos te dejan más ganancia?"

    if intent == "restock":
        if not urgent:
            return "Por ahora no veo productos que necesiten una reposición urgente. Si quieres, también puedo revisar cuáles tienen poco stock."
        names = ", ".join(_first_name(x) for x in urgent[:5])
        extra = f" y {len(urgent) - 5} más" if len(urgent) > 5 else ""
        return f"Yo revisaría primero estos: {names}{extra}. Son los que conviene tener disponibles para evitar quedarte sin producto."

    if intent == "profit":
        candidates = [p for p in top if p.get("profit") is not None]
        if not candidates:
            candidates = [p for p in abc if p.get("profit") is not None]
        if not candidates:
            return "Todavía no tengo suficiente información de costos para decirte qué productos te dejan más ganancia."
        best = max(candidates, key=lambda p: float(p.get("profit") or 0))
        profit = _money(best.get("profit"), currency)
        margin = _percent(best.get("margin_percent"))
        detail = f" con un margen de {margin}" if margin else ""
        return f"El producto que más ganancia te está dejando es {_first_name(best)}: aproximadamente {profit}{detail}. ¿Quieres que revise otros productos para comparar?"

    if intent == "forecast":
        if not forecast.get("available"):
            return "Todavía no tengo suficientes datos para hacer una buena proyección. Con más ventas registradas podré darte una estimación más útil."
        value = _money(forecast.get("predicted_period_revenue"), currency)
        days = forecast.get("horizon_days", 7)
        return f"Para los próximos {days} días, estimo unas ventas de alrededor de {value}. Tómalo como una guía, no como una garantía. ¿Quieres que revisemos qué productos pueden sostener ese resultado?"

    if intent == "anomaly":
        if anomaly.get("is_anomaly"):
            return "Sí, encontré un cambio fuera de lo habitual en tus ingresos. Conviene revisar qué pasó en esos días y si estuvo relacionado con algún producto o venta puntual."
        return "No veo un cambio especialmente fuera de lo normal en tus ingresos recientes. Si quieres, podemos revisar la evolución de las ventas."

    if intent == "unknown":
        return "Todavía estoy aprendiendo sobre esa parte del negocio. Por ahora puedo ayudarte con ventas, productos, inventario, ganancias y reposición."

    # Generic fallback keeps the conversation short and invites the next useful topic.
    if top:
        return f"Puedo ayudarte a revisar tus ventas y productos. Por ejemplo, ahora mismo puedo decirte cuáles se están vendiendo más, como {_first_name(top[0])}. ¿Qué quieres saber?"
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
