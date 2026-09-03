import asyncio, json, logging, os, time, unicodedata
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

CUBI_SYSTEM = """Eres CUBI, el asesor inteligente de PLATIA. Piensa como un profesional senior de finanzas, economía, Business Intelligence, estadística y gestión de negocios, pero habla como un humano: claro, sencillo, directo, tranquilo y cercano.

OBJETIVO: ayudar al propietario a entender qué está pasando, qué significa, qué riesgo u oportunidad existe y qué acción conviene considerar.

REGLAS:
1. Usa solo los datos del contexto para afirmar cifras o hechos. Nunca inventes.
2. Separa HECHOS, INTERPRETACIONES e HIPÓTESIS. Una posible causa no es una causa demostrada.
3. Si faltan datos, dilo y explica qué dato hace falta.
4. Para preguntas simples responde simple; para preguntas profundas analiza más.
5. Si usas un término financiero, tradúcelo inmediatamente a lenguaje cotidiano.
6. Si preguntas por qué, explica qué datos apuntan a la conclusión sin inventar causalidad.
7. Si preguntan qué hacer, prioriza hasta 3 acciones concretas y explica por qué.
8. Si preguntan cómo está el negocio, entrega una lectura ejecutiva: situación, positivo, qué vigilar y qué haría primero.
9. Señala riesgos sin alarmismo y oportunidades sin prometer resultados.
10. No te presentes como contador, abogado, auditor certificado o asesor fiscal.
11. Confianza: ALTA = dato directo; MEDIA = patrón que requiere contexto; HIPÓTESIS = explicación posible; INSUFICIENTE = faltan datos.
12. Normalmente responde en 2 a 6 párrafos cortos o viñetas. No hagas informes largos salvo que el usuario los pida.
13. Cuando sea útil, enseña brevemente cómo funciona el concepto. Ejemplo: margen bruto = lo que queda de una venta después de pagar el costo del producto.
14. Piensa siempre: DATOS -> COMPARACIÓN -> INTERPRETACIÓN -> RIESGO/OPORTUNIDAD -> RECOMENDACIÓN.
15. La inteligencia se mantiene constante; cambia la forma de comunicarla.
"""

async def _ensure_local_history_seed(business_id):
    if await db.assistant_messages.count_documents({"business_id": business_id}) > 0: return
    await db.assistant_messages.insert_many([
        {"id": new_id(), "business_id": business_id, "role": "user", "content": "Consulta inicial del negocio", "created_at": now_iso()},
        {"id": new_id(), "business_id": business_id, "role": "assistant", "content": "Estoy listo para ayudarte a revisar el negocio.", "created_at": now_iso()},
    ])

def _norm(value):
    return "".join(c for c in unicodedata.normalize("NFD", (value or "").lower()) if unicodedata.category(c) != "Mn").strip()

def _money(value, currency="USD"):
    try: n=float(value)
    except (TypeError,ValueError): return None
    return f"{n:,.2f}".replace(",","X").replace(".",",").replace("X",".")+ (f" {currency}" if currency else "")

def _num(value):
    try: return f"{float(value):,.0f}".replace(",",".")
    except (TypeError,ValueError): return "0"

def _pct(value):
    try: return f"{float(value):.1f}%"
    except (TypeError,ValueError): return "0%"

def _pname(p): return (p or {}).get("product_name") or (p or {}).get("name") or "ese producto"

def _intent(message):
    t=_norm(message)
    if not t:return "unknown"
    if t in {"hola","buenas","hello","hey","holi","buen dia","buenos dias","buenas tardes","buenas noches"} or t.startswith(("hola ","buenas ")):return "greeting"
    groups={
      "improve_sales":("mejorar ventas","vender mas","aumentar ventas","subir ventas","mas ventas","como vendo","que hago para vender","mas clientes","conseguir clientes"),
      "sales_detail":("que tanto","cuanto subieron","cuanto crecieron","que porcentaje","porcentaje de ventas","cuanto crecimiento","cuanto aumento"),
      "sales":("ventas","vendi","vendiendo","vendido","como van","como estoy vendiendo","resultado de ventas"),
      "top_products":("producto mas vendido","productos mas vendidos","que se vende mas","mejores productos","que productos venden","que producto debo vender","que deberia vender","cual producto","que producto"),
      "restock":("reponer","reposicion","que compro","que debo comprar","que comprar","stock","inventario","se va a acabar","se acaba","falta producto"),
      "profit":("ganancia","ganancias","utilidad","margen","rentable","rentabilidad","que me deja mas","mas ganancia","producto rentable"),
      "anomaly":("alerta","anomalia","raro","extrano","caida","problema con ventas","que paso"),
      "forecast":("proyeccion","pronostico","futuro","proximos dias","cuanto vendre","que espero vender","proximo mes"),
      "customers":("clientes","compradores","cliente que mas compra")}
    for k,words in groups.items():
        if any(w in t for w in words):return k
    return "unknown"

def _cubi_chat_context(insights, business, margin_data=None):
    history=insights.get("history",{}) or {}; summary=insights.get("summary",{}) or {}
    context={
        "negocio":{"name":(business or {}).get("name","tu negocio"),"currency":(business or {}).get("currency","USD")},
        "salud":insights.get("health",{}) or {},
        "resumen":summary,
        "historial":history,
        "proyeccion":insights.get("forecast",{}) or {},
        "productos_top":(insights.get("top_products") or [])[:8],
        "abc":(insights.get("abc_analysis") or [])[:8],
        "inventario":(insights.get("inventory_recommendations") or [])[:10],
        "anomalia":insights.get("anomaly",{}) or {},
        "diagnostico":insights.get("diagnosis",[]) or [],
        "riesgos":insights.get("risks",[]) or [],
        "oportunidades":insights.get("opportunities",[]) or [],
        "recomendaciones":insights.get("recommendations",[]) or [],
        "conceptos":insights.get("teaching_points",[]) or [],
    }
    if margin_data:
        context["analisis_financiero"]={"summary":margin_data.get("summary",{}),"alerts":(margin_data.get("alerts") or [])[:10]}
    return json.dumps(context,ensure_ascii=False,default=str)

async def _native_cubi_reply(business_id,user_message,previous_messages=None):
    insights=await build_business_insights(db,business_id)
    history=insights.get("history",{}); forecast=insights.get("forecast",{}); inventory=insights.get("inventory_recommendations",[]); anomaly=insights.get("anomaly",{})
    top=insights.get("top_products",[]); abc=insights.get("abc_analysis",[]); summary=insights.get("summary",{})
    sales_count=history.get("sales_count",0); observed_days=history.get("observed_days",0)
    business=await db.businesses.find_one({"id":business_id},{"_id":0,"currency":1}) or {}; currency=business.get("currency","USD")
    urgent=[x for x in inventory if float(x.get("suggested_purchase",0) or 0)>0]
    previous=[x for x in (previous_messages or []) if x.get("content") and x.get("content") not in SEED_CONTENT]
    last_assistant=_norm(next((x.get("content","") for x in reversed(previous) if x.get("role")=="assistant"),""))
    intent=_intent(user_message); short=_norm(user_message)
    if intent=="unknown":
        if short in {"si","claro","dale","ok","okay"}:
            if "producto" in last_assistant or "vend" in last_assistant:intent="top_products"
            elif "ganancia" in last_assistant or "margen" in last_assistant:intent="profit"
            elif "compr" in last_assistant or "reponer" in last_assistant:intent="restock"
            elif "crec" in last_assistant or "ventas" in last_assistant:intent="sales_detail"
        elif short in {"que tanto","cuanto","y cuanto","que porcentaje"} : intent="sales_detail"
    if intent=="greeting":
        return f"¡Hola! 👋 Tengo {sales_count} ventas para analizar. ¿Quieres ver ventas, productos, inventario o ganancias?" if sales_count else "¡Hola! 👋 Estoy listo. Puedo revisar tus ventas, productos, inventario y ganancias. ¿Por dónde empezamos?"
    if sales_count==0 and intent in {"sales","sales_detail","improve_sales","top_products","profit","forecast","anomaly"}:
        return "Todavía no tengo suficientes ventas para darte una conclusión útil."
    if intent=="improve_sales":
        if top:
            p=top[0]; return f"Empezaría por {_pname(p)}: {_num(p.get('units'))} unidades vendidas. Podemos buscar cómo aumentar su venta y qué producto combinar con él."
        return "Empezaría por tus productos más vendidos y los que dejan más ganancia. Así sabemos dónde concentrar el esfuerzo."
    if intent=="sales_detail":
        trend=forecast.get("trend_percent")
        if trend is None:return f"Tienes {sales_count} ventas. Todavía no tengo una comparación suficientemente sólida."
        if trend>0:return f"Tus ventas crecieron aproximadamente {_pct(trend)}. 📈 Ahora podemos identificar qué producto está impulsando ese crecimiento."
        if trend<0:return f"Tus ventas bajaron aproximadamente {_pct(abs(trend))}. ⚠️ Podemos revisar qué productos perdieron movimiento."
        return "Tus ventas están prácticamente estables. Podemos buscar dónde crecer."
    if intent=="sales":
        trend=forecast.get("trend_percent")
        if trend is None:return f"Tienes {sales_count} ventas en {observed_days} días con actividad."
        if trend>0:return f"Van bien: la tendencia reciente es de +{_pct(trend)}. 📈 ¿Quieres ver qué producto está aportando más?"
        if trend<0:return f"Hay una caída reciente de {_pct(abs(trend))}. ⚠️ ¿Quieres que busque qué productos están bajando?"
        return "Tus ventas están estables. ¿Quieres que busquemos oportunidades para crecer?"
    if intent=="top_products":
        if not top:return "Todavía no tengo suficientes datos para identificar tus productos más vendidos."
        rows=[f"{i}. {_pname(p)} — {_num(p.get('units'))} unidades" for i,p in enumerate(top[:3],1)]
        return "Los que más vendes son:\n"+"\n".join(rows)+"\n¿Quieres que los compare por ganancia?"
    if intent=="restock":
        if not urgent:return "No veo reposiciones urgentes ahora mismo. También puedo revisar productos con poco stock."
        p=urgent[0]; return f"Primero revisaría {_pname(p)}: comprar unas {_num(p.get('suggested_purchase'))} unidades. Tengo {len(urgent)} productos para revisar."
    if intent=="profit":
        candidates=[p for p in abc if p.get("profit") is not None]
        if not candidates:return "Todavía no tengo costos suficientes para calcular la ganancia por producto."
        p=max(candidates,key=lambda x:float(x.get("profit") or 0)); return f"El que más ganancia te deja es {_pname(p)}: {_money(p.get('profit'),currency)}, con margen de {_pct(p.get('margin_percent'))}. ¿Quieres comparar los 3 mejores?"
    if intent=="forecast":
        if not forecast.get("available"):return "Todavía no tengo suficientes datos para hacer una buena proyección."
        return f"Para los próximos {forecast.get('horizon_days',7)} días estimo unas ventas de {_money(forecast.get('predicted_period_revenue'),currency)}."
    if intent=="anomaly":return "Sí, detecté un cambio fuera de lo habitual en tus ingresos." if anomaly.get("is_anomaly") else "No veo un comportamiento especialmente fuera de lo normal en tus ingresos recientes."
    if intent=="customers":return "Todavía estoy aprendiendo a medir clientes. Por ahora puedo analizar ventas, productos, inventario y ganancias."
    if top:return f"Puedo revisar tus ventas y productos. Por ejemplo, {_pname(top[0])} es el que más unidades mueve. ¿Qué quieres saber de él?"
    return "Puedo revisar ventas, productos, inventario y ganancias. ¿Qué quieres saber?"

@router.get("/assistant/status")
async def assistant_status(user:dict=Depends(require_business)):
    key=bool(os.getenv("OPENROUTER_API_KEY") or settings.OPENAI_API_KEY); openrouter=bool(os.getenv("OPENROUTER_API_KEY")); model=(os.getenv("OPENROUTER_MODEL") or "openrouter/auto") if openrouter else (os.getenv("OPENAI_MODEL") or "gpt-5-mini")
    return {"configured":True,"native_cubi":True,"external_ai_configured":key,"provider":"openrouter" if openrouter else "openai" if settings.OPENAI_API_KEY else "native","model":model if key else None,"message":"Cubi está disponible con inteligencia nativa." if not key else "Cubi está configurado con inteligencia nativa y un proveedor externo opcional."}

@router.get("/assistant/history")
async def assistant_history(user:dict=Depends(require_business)):
    await _ensure_local_history_seed(user["business_id"]); messages=await db.assistant_messages.find({"business_id":user["business_id"]},{"_id":0}).sort("created_at",1).to_list(40); return {"messages":messages[-30:]}

@router.post("/assistant/chat")
async def assistant_chat(data:ChatIn,user:dict=Depends(require_business)):
    bid=user["business_id"]; business=await db.businesses.find_one({"id":bid},{"_id":0}); previous=await db.assistant_messages.find({"business_id":bid},{"_id":0}).sort("created_at",-1).to_list(12); previous.reverse()
    try:native_reply=await _native_cubi_reply(bid,data.message,previous)
    except Exception:logger.exception("[assistant] native Cubi failed"); native_reply="Cubi no pudo revisar los datos en este momento. Inténtalo de nuevo en unos segundos."
    await db.assistant_messages.insert_one({"id":new_id(),"business_id":bid,"role":"user","content":data.message,"created_at":now_iso()})
    if os.getenv("CUBI_EXTERNAL_AI","false").lower()!="true":
        async def native_generator():
            yield f"data: {json.dumps({'c':native_reply},ensure_ascii=False)}\n\n"; await db.assistant_messages.insert_one({"id":new_id(),"business_id":bid,"role":"assistant","content":native_reply,"created_at":now_iso()}); yield "data: [DONE]\n\n"
        return StreamingResponse(native_generator(),media_type="text/event-stream",headers={"Cache-Control":"no-cache, no-transform","X-Accel-Buffering":"no","Connection":"keep-alive"})
    try:
        insights=await build_business_insights(db,bid)
        margin_data=await margin_analysis(user)
        context=await build_assistant_context(bid,business or {})
        rich_context=_cubi_chat_context(insights,business or {},margin_data)
        s=(margin_data.get("summary") or {})
        context+=f"\n\nCUBI INTELLIGENCE STRUCTURED:\n{rich_context}"
        context+=f"\n\nANÁLISIS FINANCIERO AI-01 (90 días):\nIngresos: {s.get('revenue_90d')} | Costo: {s.get('realized_cost_90d')} | Utilidad: {s.get('realized_profit_90d')} | Margen: {s.get('realized_margin_percent')}%"
        alerts=(margin_data.get("alerts") or [])[:10]
        if alerts:context+="\nAlertas: "+" | ".join(a.get("message","") for a in alerts)
    except Exception:logger.exception("[assistant] context failed"); context="No se pudo cargar parte del contexto operativo."
    system_template=CUBI_SYSTEM+f"\nNegocio: {(business or {}).get('name','tu negocio')}\nMoneda: {(business or {}).get('currency','USD')}\n\nDATOS DISPONIBLES:\n{context}"
    history_messages=await db.assistant_messages.find({"business_id":bid},{"_id":0}).sort("created_at",-1).to_list(12); history_messages.reverse(); messages=[{"role":"system","content":system_template}]
    for item in history_messages:
        if item.get("role") in {"user","assistant"} and item.get("content") and item.get("content") not in SEED_CONTENT:messages.append({"role":item["role"],"content":item["content"]})
    messages.append({"role":"user","content":data.message})
    async def event_generator():
        full=""; client=None; started=time.monotonic()
        try:
            api_key=os.getenv("OPENROUTER_API_KEY") or settings.OPENAI_API_KEY; is_openrouter=bool(os.getenv("OPENROUTER_API_KEY"))
            if not api_key:raise RuntimeError("proveedor externo no configurado")
            kwargs={"api_key":api_key,"timeout":15.0}
            if is_openrouter:kwargs.update({"base_url":"https://openrouter.ai/api/v1","default_headers":{"HTTP-Referer":"https://cuadrapp.up.railway.app","X-Title":"PLATIA"}})
            client=AsyncOpenAI(**kwargs); model=(os.getenv("OPENROUTER_MODEL") or "openrouter/auto") if is_openrouter else (os.getenv("OPENAI_MODEL") or "gpt-5-mini"); stream=await asyncio.wait_for(client.chat.completions.create(model=model,messages=messages,stream=True),timeout=20); iterator=stream.__aiter__()
            while True:
                if time.monotonic()-started>60:raise TimeoutError("proveedor externo tardó demasiado")
                try:chunk=await asyncio.wait_for(iterator.__anext__(),timeout=15)
                except StopAsyncIteration:break
                except asyncio.TimeoutError:raise TimeoutError("proveedor externo dejó de responder")
                if not chunk.choices:continue
                delta=chunk.choices[0].delta.content
                if delta:full+=delta;yield f"data: {json.dumps({'c':delta},ensure_ascii=False)}\n\n"
            if not full:raise RuntimeError("proveedor externo no devolvió contenido")
        except Exception:logger.exception("[assistant] external AI provider error; using native Cubi fallback");full=native_reply;yield f"data: {json.dumps({'c':full,'fallback':True},ensure_ascii=False)}\n\n"
        finally:
            try:await db.assistant_messages.insert_one({"id":new_id(),"business_id":bid,"role":"assistant","content":full,"created_at":now_iso()})
            except Exception:logger.exception("[assistant] persist failed")
            if client:
                try:await client.close()
                except Exception:pass
            yield "data: [DONE]\n\n"
    return StreamingResponse(event_generator(),media_type="text/event-stream",headers={"Cache-Control":"no-cache, no-transform","X-Accel-Buffering":"no","Connection":"keep-alive"})