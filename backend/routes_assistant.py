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


async def _native_cubi_reply(business_id: str, user_message: str) -> str:
    """Deterministic Cubi response. It never requires an external LLM."""
    insights = await build_business_insights(db, business_id)
    history = insights.get("history", {})
    forecast = insights.get("forecast", {})
    inventory = insights.get("inventory_recommendations", [])
    anomaly = insights.get("anomaly", {})
    top = insights.get("top_products", [])

    sales_count = history.get("sales_count", 0)
    observed_days = history.get("observed_days", 0)
    forecast_value = forecast.get("predicted_period_revenue")
    trend = forecast.get("trend_percent")
    urgent = [x for x in inventory if x.get("suggested_purchase", 0) > 0]

    normalized = (user_message or "").strip().lower()
    if normalized in {"hola", "buenas", "buenos días", "buenas tardes", "buenas noches", "hello", "hey"}:
        reply = "Hola. Soy Cubi. Ya puedo analizar tu negocio sin depender de una IA externa."
    else:
        reply = "Puedo analizar ventas, inventario, rentabilidad, productos y alertas directamente con los datos de CuadraApp."

    if sales_count == 0:
        reply += " Todavía no encuentro ventas suficientes para generar un pronóstico confiable."
    else:
        reply += f" En el período analizado encuentro {sales_count} ventas y {observed_days} días con actividad."
        if forecast_value is not None:
            reply += f" Mi proyección para los próximos {forecast.get('horizon_days', 7)} días es de {forecast_value:.2f}."
        if trend is not None:
            direction = "al alza" if trend > 0 else "a la baja" if trend < 0 else "estable"
            reply += f" La tendencia reciente está {direction} ({trend:.1f}%)."

    if urgent:
        reply += f" Hay {len(urgent)} producto(s) con recomendación de reposición."
    if anomaly.get("is_anomaly"):
        reply += " También detecté una anomalía reciente en los ingresos que conviene revisar."
    if top:
        reply += f" Tu producto con mayor desempeño reciente es {top[0].get('name', 'uno de tus productos')}."

    reply += " Puedes preguntarme, por ejemplo, qué productos debes reponer o cómo están evolucionando tus ventas."
    return reply


@router.get("/assistant/status")
async def assistant_status(user: dict = Depends(require_business)):
    key = bool(os.getenv("OPENROUTER_API_KEY") or settings.OPENAI_API_KEY)
    openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
    model = (os.getenv("OPENROUTER_MODEL") or "openrouter/auto") if openrouter else (os.getenv("OPENAI_MODEL") or "gpt-5-mini")
    return {
        "configured": True,
        "native_cubi": True,
        "external_ai_configured": key,
        "provider": "openrouter" if openrouter else "openai" if settings.OPENAI_API_KEY else "native",
        "model": model if key else None,
        "message": "Cubi está disponible con inteligencia nativa." if not key else "Cubi está configurado con inteligencia nativa y un proveedor externo opcional.",
    }


@router.get("/assistant/history")
async def assistant_history(user: dict = Depends(require_business)):
    await _ensure_local_history_seed(user["business_id"])
    messages = await db.assistant_messages.find({"business_id": user["business_id"]}, {"_id": 0}).sort("created_at", 1).to_list(40)
    return {"messages": messages[-30:]}


@router.post("/assistant/chat")
async def assistant_chat(data: ChatIn, user: dict = Depends(require_business)):
    bid = user["business_id"]
    business = await db.businesses.find_one({"id": bid}, {"_id": 0})

    # Build the native Cubi answer first. This guarantees the chat works even
    # when OpenRouter/OpenAI is unavailable or rate-limited.
    try:
        native_reply = await _native_cubi_reply(bid, data.message)
    except Exception:
        logger.exception("[assistant] native Cubi failed")
        native_reply = "Cubi está disponible, pero no pudo calcular los indicadores en este momento. Revisa que existan datos de ventas e inventario."

    await db.assistant_messages.insert_one({
        "id": new_id(),
        "business_id": bid,
        "role": "user",
        "content": data.message,
        "created_at": now_iso(),
    })

    # External AI remains optional. It is only used when explicitly enabled.
    # A 429/error automatically falls back to the native Cubi response.
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

    system_template = f'''Eres "Cubi", el asesor inteligente del negocio "{(business or {}).get("name", "tu negocio")}". Responde SIEMPRE en español, con frases cortas, tono cercano, práctico y directo. Usa EXCLUSIVAMENTE los datos del negocio. No inventes cifras. Si falta un dato, dilo. La moneda es {(business or {}).get("currency", "USD")}.\n\nDATOS:\n{context}'''
    history = await db.assistant_messages.find({"business_id": bid}, {"_id": 0}).sort("created_at", -1).to_list(12)
    history.reverse()
    messages = [{"role": "system", "content": system_template}]
    for item in history:
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
