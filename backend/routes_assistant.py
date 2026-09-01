import asyncio,json,logging,os,time
from fastapi import APIRouter,Depends
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from config import settings
from database import db
from models import ChatIn
from security import new_id,now_iso,require_business
from stats import build_assistant_context
from routes_ai import margin_analysis
router=APIRouter(tags=["assistant"]);logger=logging.getLogger(__name__);SEED_CONTENT={"Consulta inicial del negocio","Estoy listo para ayudarte a revisar el negocio."}
async def _ensure_local_history_seed(business_id:str):
    if await db.assistant_messages.count_documents({"business_id":business_id})>0:return
    await db.assistant_messages.insert_many([{"id":new_id(),"business_id":business_id,"role":"user","content":"Consulta inicial del negocio","created_at":now_iso()},{"id":new_id(),"business_id":business_id,"role":"assistant","content":"Estoy listo para ayudarte a revisar el negocio.","created_at":now_iso()}])
SYSTEM_TEMPLATE="""Eres \"Cubi\", el asesor inteligente del negocio \"{name}\". Responde SIEMPRE en español, con frases cortas, tono cercano, práctico y directo. Usa EXCLUSIVAMENTE los datos del negocio que aparecen abajo. No inventes cifras. Si falta un dato, dilo. Explica el porqué de cada recomendación y termina con una acción concreta cuando aplique. Evita tecnicismos contables. NO uses markdown. Máximo ~150 palabras. La moneda del negocio es {currency}.\n\nDATOS ACTUALES DEL NEGOCIO:\n{context}\n"""
@router.get("/assistant/status")
async def assistant_status(user:dict=Depends(require_business)):
    key=bool(os.getenv("OPENROUTER_API_KEY") or settings.OPENAI_API_KEY);openrouter=bool(os.getenv("OPENROUTER_API_KEY"));model=(os.getenv("OPENROUTER_MODEL") or "openrouter/auto") if openrouter else (os.getenv("OPENAI_MODEL") or "gpt-5-mini")
    return {"configured":key,"provider":"openrouter" if openrouter else "openai" if settings.OPENAI_API_KEY else None,"model":model,"message":"Cubi está configurado." if key else "Falta configurar OPENROUTER_API_KEY u OPENAI_API_KEY en Railway."}
@router.get("/assistant/history")
async def assistant_history(user:dict=Depends(require_business)):
    await _ensure_local_history_seed(user["business_id"]);messages=await db.assistant_messages.find({"business_id":user["business_id"]},{"_id":0}).sort("created_at",1).to_list(40);return {"messages":messages[-30:]}
@router.post("/assistant/chat")
async def assistant_chat(data:ChatIn,user:dict=Depends(require_business)):
    bid=user["business_id"];business=await db.businesses.find_one({"id":bid},{"_id":0})
    try:context=await build_assistant_context(bid,business or {})
    except Exception:logger.exception("[assistant] context failed");context="No se pudo cargar parte del contexto operativo. Responde solo con los datos disponibles."
    try:
        margin_data=await margin_analysis(user);summary=margin_data["summary"];alerts=margin_data["alerts"][:10];context+=f"\n\nANÁLISIS FINANCIERO AI-01 (90 días):\nIngresos: {summary['revenue_90d']} | Costo realizado: {summary['realized_cost_90d']} | Utilidad realizada: {summary['realized_profit_90d']} | Margen realizado: {summary['realized_margin_percent']}%\nAlertas detectadas: {summary['alerts_count']}";context+=(("\nAlertas: "+" | ".join(a["message"] for a in alerts)) if alerts else "")
    except Exception:logger.exception("[assistant] AI-01 failed");context+="\n\nANÁLISIS FINANCIERO AI-01: temporalmente no disponible."
    history=await db.assistant_messages.find({"business_id":bid},{"_id":0}).sort("created_at",-1).to_list(12);history.reverse();messages=[{"role":"system","content":SYSTEM_TEMPLATE.format(name=(business or {}).get("name","tu negocio"),currency=(business or {}).get("currency","USD"),context=context)}]
    for item in history:
        if item.get("role") in {"user","assistant"} and item.get("content") and item.get("content") not in SEED_CONTENT:messages.append({"role":item["role"],"content":item["content"]})
    messages.append({"role":"user","content":data.message});await db.assistant_messages.insert_one({"id":new_id(),"business_id":bid,"role":"user","content":data.message,"created_at":now_iso()})
    async def event_generator():
        full="";client=None;started=time.monotonic()
        try:
            api_key=os.getenv("OPENROUTER_API_KEY") or settings.OPENAI_API_KEY;is_openrouter=bool(os.getenv("OPENROUTER_API_KEY"))
            if not api_key:raise RuntimeError("Cubi no está configurado en el servidor: falta OPENROUTER_API_KEY u OPENAI_API_KEY.")
            kwargs={"api_key":api_key,"timeout":15.0}
            if is_openrouter:kwargs.update({"base_url":"https://openrouter.ai/api/v1","default_headers":{"HTTP-Referer":"https://cuadrapp.up.railway.app","X-Title":"CuadraApp"}})
            client=AsyncOpenAI(**kwargs);model=(os.getenv("OPENROUTER_MODEL") or "openrouter/auto") if is_openrouter else (os.getenv("OPENAI_MODEL") or "gpt-5-mini")
            stream=await asyncio.wait_for(client.chat.completions.create(model=model,messages=messages,stream=True),timeout=20);iterator=stream.__aiter__()
            while True:
                if time.monotonic()-started>60:raise TimeoutError("Cubi tardó demasiado en responder.")
                try:chunk=await asyncio.wait_for(iterator.__anext__(),timeout=15)
                except StopAsyncIteration:break
                except asyncio.TimeoutError:raise TimeoutError("El proveedor de IA dejó de responder.")
                if not chunk.choices:continue
                delta=chunk.choices[0].delta.content
                if delta:full+=delta;yield f"data: {json.dumps({'c':delta},ensure_ascii=False)}\n\n"
            if not full:full="No recibí contenido del proveedor de IA. Inténtalo nuevamente.";yield f"data: {json.dumps({'c':full,'error':True},ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("[assistant] AI provider error");msg=str(exc)[:300]
            if not full:full=f"Cubi no pudo responder. {msg}";yield f"data: {json.dumps({'c':full,'error':True},ensure_ascii=False)}\n\n"
        finally:
            try:await db.assistant_messages.insert_one({"id":new_id(),"business_id":bid,"role":"assistant","content":full,"created_at":now_iso()})
            except Exception:logger.exception("[assistant] persist failed")
            if client:
                try:await client.close()
                except Exception:pass
            yield "data: [DONE]\n\n"
    return StreamingResponse(event_generator(),media_type="text/event-stream",headers={"Cache-Control":"no-cache, no-transform","X-Accel-Buffering":"no","Connection":"keep-alive"})
