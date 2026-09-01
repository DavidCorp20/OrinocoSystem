import asyncio
import json
import os
import logging
import time
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from config import settings
from database import db
from models import ChatIn
from security import new_id, now_iso, require_business
from stats import build_assistant_context
from routes_ai import margin_analysis
router=APIRouter(tags=["assistant"]);logger=logging.getLogger(__name__)
SEED_CONTENT={"Consulta inicial del negocio","Estoy listo para ayudarte a revisar el negocio."}
async def _ensure_local_history_seed(business_id:str):
 count=await db.assistant_messages.count_documents({"business_id":business_id})
 if count>0:return
 await db.assistant_messages.insert_many([{"id":new_id(),"business_id":business_id,"role":"user","content":"Consulta inicial del negocio","created_at":now_iso()},{"id":new_id(),"business_id":business_id,"role":"assistant","content":"Estoy listo para ayudarte a revisar el negocio.","created_at":now_iso()}])
SYSTEM_TEMPLATE="""Eres \"Pyme\", el asesor inteligente del negocio \"{name}\".\nTu misión: responder la pregunta del comerciante de forma útil y accionable.\n\nReglas estrictas:\n- Responde SIEMPRE en español, con frases cortas y tono cercano, práctico y directo.\n- Usa EXCLUSIVAMENTE los datos del negocio que aparecen abajo. No inventes cifras.\n- Si te preguntan algo que no está en los datos, dilo con honestidad.\n- Explica el porqué de cada recomendación y termina con una acción concreta cuando aplique.\n- Evita tecnicismos contables. Habla como un asesor de confianza.\n- La moneda del negocio es {currency}. Usa montos con 2 decimales como máximo.\n- NO uses formato markdown. Para listas usa guiones simples (-).\n- Respuestas breves: máximo ~150 palabras.\n\nDATOS ACTUALES DEL NEGOCIO:\n{context}\n"""
@router.get("/assistant/history")
async def assistant_history(user:dict=Depends(require_business)):
 await _ensure_local_history_seed(user["business_id"]);messages=await db.assistant_messages.find({"business_id":user["business_id"]},{"_id":0}).sort("created_at",1).to_list(40);return {"messages":messages[-30:]}
@router.post("/assistant/chat")
async def assistant_chat(data:ChatIn,user:dict=Depends(require_business)):
 bid=user["business_id"];business=await db.businesses.find_one({"id":bid},{"_id":0})
 try:context=await build_assistant_context(bid,business or {})
 except Exception:logger.exception("[assistant] context failed");context="No se pudo cargar parte del contexto operativo. Responde solo con los datos disponibles."
 try:
  margin_data=await margin_analysis(user);summary=margin_data["summary"];alerts=margin_data["alerts"][:10];context+=f"\n\nANÁLISIS FINANCIERO AI-01 (90 días):\nIngresos: {summary['revenue_90d']} | Costo realizado: {summary['realized_cost_90d']} | Utilidad realizada: {summary['realized_profit_90d']} | Margen realizado: {summary['realized_margin_percent']}%\nAlertas detectadas: {summary['alerts_count']}"
  if alerts:context+="\nAlertas: "+" | ".join(a["message"] for a in alerts)
 except Exception:logger.exception("[assistant] AI-01 failed");context+="\n\nANÁLISIS FINANCIERO AI-01: temporalmente no disponible."
 history=await db.assistant_messages.find({"business_id":bid},{"_id":0}).sort("created_at",-1).to_list(12);history.reverse();messages=[{"role":"system","content":SYSTEM_TEMPLATE.format(name=(business or {}).get("name","tu negocio"),currency=(business or {}).get("currency","USD"),context=context)}]
 for item in history:
  role=item.get("role");content=item.get("content");
  if role in {"user","assistant"} and content and content not in SEED_CONTENT:messages.append({"role":role,"content":content})
 messages.append({"role":"user","content":data.message})
 await db.assistant_messages.insert_one({"id":new_id(),"business_id":bid,"role":"user","content":data.message,"created_at":now_iso()})
 async def event_generator():
  full="";client=None;started=time.monotonic()
  try:
   api_key=os.getenv("OPENROUTER_API_KEY") or settings.OPENAI_API_KEY
   is_openrouter=bool(os.getenv("OPENROUTER_API_KEY"))
   if not api_key:raise RuntimeError("No hay OPENROUTER_API_KEY ni OPENAI_API_KEY configurada")
   kwargs={"api_key":api_key,"timeout":15.0}
   if is_openrouter:kwargs.update({"base_url":"https://openrouter.ai/api/v1","default_headers":{"HTTP-Referer":"https://cuadrapp.up.railway.app","X-Title":"CuadraApp"}})
   client=AsyncOpenAI(**kwargs);model=(os.getenv("OPENROUTER_MODEL") or "openai/gpt-5-mini") if is_openrouter else (os.getenv("OPENAI_MODEL") or "gpt-5-mini")
   stream=await asyncio.wait_for(client.chat.completions.create(model=model,messages=messages,stream=True),timeout=20)
   iterator=stream.__aiter__()
   while True:
    if time.monotonic()-started>60:raise TimeoutError("Tiempo máximo de respuesta excedido")
    try:chunk=await asyncio.wait_for(iterator.__anext__(),timeout=15)
    except StopAsyncIteration:break
    except asyncio.TimeoutError:raise TimeoutError("El proveedor de IA dejó de enviar datos")
    if not chunk.choices:continue
    delta=chunk.choices[0].delta.content
    if delta:full+=delta;yield f"data: {json.dumps({'c':delta},ensure_ascii=False)}\n\n"
   if not full:full="No pude generar una respuesta en este momento.";yield f"data: {json.dumps({'c':full},ensure_ascii=False)}\n\n"
  except Exception as exc:
   logger.exception("[assistant] AI provider error")
   if not full:full="Pyme no pudo responder en este momento. Inténtalo nuevamente.";yield f"data: {json.dumps({'c':full,'error':str(exc)},ensure_ascii=False)}\n\n"
  finally:
   try:await db.assistant_messages.insert_one({"id":new_id(),"business_id":bid,"role":"assistant","content":full,"created_at":now_iso()})
   except Exception:logger.exception("[assistant] persist failed")
   if client is not None:
    try:await client.close()
    except Exception:pass
   yield "data: [DONE]\n\n"
 return StreamingResponse(event_generator(),media_type="text/event-stream",headers={"Cache-Control":"no-cache, no-transform","X-Accel-Buffering":"no","Connection":"keep-alive"})
