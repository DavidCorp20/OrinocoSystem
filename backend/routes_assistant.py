import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from config import settings
from database import db
from models import ChatIn
from security import new_id, now_iso, require_business
from stats import build_assistant_context

try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
except ModuleNotFoundError:  # pragma: no cover - optional dependency for local/dev without secrets
    LlmChat = UserMessage = TextDelta = StreamDone = None

router = APIRouter(tags=["assistant"])


async def _ensure_local_history_seed(business_id: str):
    count = await db.assistant_messages.count_documents({"business_id": business_id})
    if count > 0:
        return
    await db.assistant_messages.insert_many([
        {
            "id": new_id(),
            "business_id": business_id,
            "role": "user",
            "content": "Consulta inicial del negocio",
            "created_at": now_iso(),
        },
        {
            "id": new_id(),
            "business_id": business_id,
            "role": "assistant",
            "content": "Estoy listo para ayudarte a revisar el negocio. Cuando la IA esté disponible, podré darte análisis más concretos.",
            "created_at": now_iso(),
        },
    ])


SYSTEM_TEMPLATE = """Eres "Pyme", el asesor inteligente del negocio "{name}".
Tu misión: responder la pregunta "¿Cómo está mi negocio y qué debería hacer ahora?".

Reglas estrictas:
- Responde SIEMPRE en español, con frases cortas y tono cercano, práctico y directo.
- Usa EXCLUSIVAMENTE los datos del negocio que aparecen abajo. No inventes cifras.
- Si te preguntan algo que no está en los datos, dilo con honestidad y sugiere qué registrar en la app para saberlo.
- Explica el porqué de cada recomendación y termina con una acción concreta cuando aplique.
- Evita tecnicismos contables. Habla como un asesor de confianza, no como un contador.
- La moneda del negocio es {currency}. Usa montos con 2 decimales como máximo.
- NO uses formato markdown (nada de ** ni # ni tablas): escribe texto plano. Para listas usa guiones simples (-).
- Respuestas breves: máximo ~150 palabras.

DATOS ACTUALES DEL NEGOCIO:
{context}
"""


@router.get("/assistant/history")
async def assistant_history(user: dict = Depends(require_business)):
    await _ensure_local_history_seed(user["business_id"])
    messages = await db.assistant_messages.find(
        {"business_id": user["business_id"]}, {"_id": 0}
    ).sort("created_at", 1).to_list(40)
    return {"messages": messages[-30:]}


@router.post("/assistant/chat")
async def assistant_chat(data: ChatIn, user: dict = Depends(require_business)):
    bid = user["business_id"]
    business = await db.businesses.find_one({"id": bid}, {"_id": 0})
    context = await build_assistant_context(bid, business or {})

    history = await db.assistant_messages.find({"business_id": bid}, {"_id": 0}).sort("created_at", -1).to_list(8)
    history.reverse()
    transcript = "\n".join(f"{'Usuario' if m['role'] == 'user' else 'Pyme'}: {m['content']}" for m in history)

    await db.assistant_messages.insert_one({
        "id": new_id(), "business_id": bid, "role": "user", "content": data.message, "created_at": now_iso(),
    })

    system = SYSTEM_TEMPLATE.format(name=(business or {}).get("name", "tu negocio"), currency=(business or {}).get("currency", "USD"), context=context)
    prompt = (f"Conversación reciente:\n{transcript}\n\n" if transcript else "") + f"Usuario: {data.message}"

    async def event_generator():
        full = ""
        try:
            if not settings.EMERGENT_LLM_KEY or LlmChat is None:
                raise RuntimeError("EMERGENT_LLM_KEY no está configurada o la dependencia de IA no está disponible en este entorno local.")
            chat = LlmChat(
                api_key=settings.EMERGENT_LLM_KEY,
                session_id=f"pyme-{bid}",
                system_message=system,
            ).with_model("openai", "gpt-5.4-mini")
            async for ev in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(ev, TextDelta):
                    full += ev.content
                    yield f"data: {json.dumps({'c': ev.content})}\n\n"
                elif isinstance(ev, StreamDone):
                    break
        except Exception:
            if not full:
                full = "Lo siento, no pude procesar tu consulta en este momento. Intenta de nuevo en unos segundos."
                yield f"data: {json.dumps({'c': full})}\n\n"
        await db.assistant_messages.insert_one({
            "id": new_id(), "business_id": bid, "role": "assistant", "content": full, "created_at": now_iso(),
        })
        if not settings.EMERGENT_LLM_KEY or LlmChat is None:
            await db.assistant_messages.insert_one({
                "id": new_id(),
                "business_id": bid,
                "role": "assistant",
                "content": "El proveedor de IA no está configurado en este entorno local; la sesión queda persistida para la revisión del negocio.",
                "created_at": now_iso(),
            })
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
