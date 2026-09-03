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
16. Nunca muestres objetos Python, diccionarios, JSON, claves internas ni estructuras del contexto al usuario.
17. No repitas el mismo hecho con palabras diferentes dentro de una misma respuesta.
18. Un saludo o mensaje casual debe recibir una respuesta conversacional breve; no descargues automáticamente el diagnóstico del negocio.
19. Las opciones rápidas de la interfaz son consultas directas. Responde exactamente al tema seleccionado y no cambies de tema por palabras coincidentes.
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

def _clean_text(value):
    if isinstance(value, dict):
        term=value.get("term") or value.get("name") or value.get("title")
        meaning=value.get("meaning") or value.get("description") or value.get("message")
        if term and meaning: return f"{term}: {meaning}"
        if meaning: return str(meaning)
        if term: return str(term)
        return ""
    if isinstance(value, (list, tuple, set)):
        return "; ".join(x for x in (_clean_text(v) for v in value) if x)
    return str(value or "").strip()

def _unique(items):
    result=[]; seen=[]
    for item in items:
        text=_clean_text(item)
        if not text: continue
        key=" ".join(_norm(text).split())
        if any(key==old or key in old or old in key for old in seen): continue
        seen.append(key); result.append(text)
    return result

def _intent(message):
    t=_norm(message)
    if not t:return "unknown"

    # Exact UI actions must win over broad substring matching.
    exact={
        "hola":"greeting","hol":"greeting","buenas":"greeting","hello":"greeting","hey":"greeting","holi":"greeting",
        "ventas":"sales","ver ventas":"sales","productos":"top_products","productos mas vendidos":"top_products","que producto vende mas":"top_products",
        "inventario":"restock","ver inventario":"restock","ganancias":"profit","comparar ganancias":"profit","comparar por ganancia":"profit","ver ganancias":"profit","proyeccion":"forecast",
        "cuanto crecieron":"sales_detail","ver tendencia":"sales_detail","revisar inventario":"restock","ver productos":"top_products",
        "producto que mas vende":"top_products","producto que mas bajo":"sales_detail","ver faltantes":"restock","ver poco stock":"restock",
        "comparar los 3 mejores":"profit","ver productos mas vendidos":"top_products","que deberia vender":"top_products"
    }
    if t in exact:return exact[t]
    if t.startswith(("hola ","buenas ")):return "greeting"

    # Specific multi-word intents before generic words such as "ventas" or "vendido".
    groups=[
      ("business_health",("como esta mi negocio","como viene mi negocio","como va mi negocio","como estoy","como estamos","salud del negocio","estado del negocio","como va el negocio","que tal va mi negocio","como esta el negocio")),
      ("top_products",("producto mas vendido","productos mas vendidos","que se vende mas","mejores productos","que productos venden","que producto debo vender","que deberia vender","cual producto","que producto")),
      ("improve_sales",("mejorar ventas","vender mas","aumentar ventas","subir ventas","mas ventas","como vendo","que hago para vender","mas clientes","conseguir clientes")),
      ("sales_detail",("que tanto","cuanto subieron","cuanto crecieron","que porcentaje","porcentaje de ventas","cuanto crecimiento","cuanto aumento")),
      ("restock",("reponer","reposicion","que compro","que debo comprar","que comprar","stock","inventario","se va a acabar","se acaba","falta producto")),
      ("profit",("ganancia","ganancias","utilidad","margen","rentable","rentabilidad","que me deja mas","mas ganancia","producto rentable","estoy ganando","cuanto gano")),
      ("cash",("caja","efectivo","liquidez","dinero disponible","flujo de caja","flujo de efectivo")),
      ("costs",("costos","costes","gastos","donde pierdo dinero","estoy gastando","por que gasto")),
      ("anomaly",("alerta","anomalia","raro","extrano","caida","problema con ventas","que paso")),
      ("forecast",("proyeccion","pronostico","futuro","proximos dias","cuanto vendre","que espero vender","proximo mes")),
      ("customers",("clientes","compradores","cliente que mas compra")),
      ("recommendation",("que deberia hacer","que hago ahora","que hago primero","que me recomiendas","recomendacion","que recomiendas","dame un consejo","consejo")),
      ("why",("por que","porque","por qué","explicame","que significa","significa que")),
      ("sales",("ventas","vendi","vendiendo","vendido","como van","como estoy vendiendo","resultado de ventas"))
    ]
    for k,words in groups:
        if any(w in t for w in words):return k
    return "unknown"

def _cubi_chat_context(insights, business, margin_data=None):
    history=insights.get("history",{}) or {}; summary=insights.get("summary",{}) or {}; analysis=insights.get("analysis",{}) or {}; health=insights.get("health_score",{}) or insights.get("health",{}) or {}
    context={"negocio":{"name":(business or {}).get("name","tu negocio"),"currency":(business or {}).get("currency","USD")},"salud":health,"resumen":summary,"historial":history,"proyeccion":insights.get("forecast",{}) or {},"productos_top":(insights.get("top_products") or [])[:8],"abc":(insights.get("abc_analysis") or [])[:8],"inventario":(insights.get("inventory_recommendations") or [])[:10],"anomalia":insights.get("anomaly",{}) or {},"diagnostico":analysis.get("diagnosis",insights.get("diagnosis",[])) or [],"hechos":analysis.get("facts",[]) or [],"riesgos":analysis.get("risks",insights.get("risks",[])) or [],"oportunidades":analysis.get("opportunities",insights.get("opportunities",[])) or [],"recomendaciones":analysis.get("recommendations",insights.get("recommendations",[])) or [],"conceptos":analysis.get("teaching",insights.get("teaching_points",[])) or [],"confianza":analysis.get("confidence",health.get("confidence")),"motivo_confianza":analysis.get("confidence_reason",health.get("confidence_reason"))}
    if margin_data:context["analisis_financiero"]={"summary":margin_data.get("summary",{}),"alerts":(margin_data.get("alerts") or [])[:10]}
    return json.dumps(context,ensure_ascii=False,default=str)

def _native_expert_reply(insights,user_message,currency="USD"):
    history=insights.get("history",{}) or {}; analysis=insights.get("analysis",{}) or {}; health=insights.get("health_score",{}) or insights.get("health",{}) or {}; forecast=insights.get("forecast",{}) or {}; top=insights.get("top_products",[]) or []; inventory=insights.get("inventory_recommendations",[]) or []; anomaly=insights.get("anomaly",{}) or {}; facts=analysis.get("facts",[]) or []; diagnosis=analysis.get("diagnosis",[]) or []; risks=analysis.get("risks",[]) or []; opportunities=analysis.get("opportunities",[]) or []; recommendations=analysis.get("recommendations",[]) or []; teaching=analysis.get("teaching",[]) or []
    trend=forecast.get("trend_percent"); sales_count=history.get("sales_count",0); observed_days=history.get("observed_days",0)
    def first(items):return _clean_text(items[0]) if items else None
    def bullets(items,limit=2):return "\n".join(f"• {_clean_text(x)}" for x in items[:limit] if _clean_text(x))
    intent=_intent(user_message)
    if intent=="greeting":return "Hola. Soy Cubi, tu asesor de negocio. Puedo ayudarte a entender tus ventas, inventario, gastos, rentabilidad y flujo de caja. ¿Qué quieres revisar?"
    if intent=="business_health":
        parts=[]
        if trend is not None:
            direction="creciendo" if trend>0 else "bajando" if trend<0 else "estable"; parts.append(f"En general, tu negocio viene {direction}. Las ventas recientes están {_pct(abs(trend))} {'por encima' if trend>0 else 'por debajo' if trend<0 else 'muy cerca del nivel del'} período anterior.")
        elif sales_count:parts.append(f"Tengo {sales_count} ventas para analizar en {observed_days} días con actividad.")
        if diagnosis:parts.append(first(diagnosis))
        elif facts:parts.append(first(facts))
        if risks:parts.append(f"Lo que vigilaría: {first(risks)}")
        elif opportunities:parts.append(f"La oportunidad más clara está en: {first(opportunities)}")
        if recommendations:parts.append(f"Mi primera acción sería: {first(recommendations)}")
        elif trend is not None and trend>0:parts.append("Vender más no significa automáticamente ganar más. Lo siguiente que revisaría es margen y gastos.")
        if health:
            score=health.get("score") or health.get("value")
            if score is not None:parts.append(f"Salud estimada: {score}/100.")
        return "\n\n".join(_unique(parts)[:5]) if parts else "Todavía no tengo suficientes datos para darte una lectura seria del negocio. Necesito más actividad registrada."
    if sales_count==0 and intent in {"sales","sales_detail","improve_sales","top_products","profit","forecast","anomaly"}:return "Todavía no tengo suficientes ventas para darte una conclusión útil. Prefiero decirte eso antes que inventar una respuesta."
    if intent=="recommendation":
        if recommendations:return "Si tuviera que priorizar ahora mismo, empezaría por esto:\n"+bullets(recommendations,3)
        if risks:return "Primero atendería esto:\n"+bullets(risks,3)
        return "No quiero darte una recomendación genérica. Necesito una señal más clara en tus datos para decirte qué mover primero."
    if intent=="why":
        if diagnosis:
            response=f"Lo que veo apunta a esto: {first(diagnosis)}"
            if facts:response+=f"\n\nEl dato que más lo respalda es: {first(facts)}"
            if risks:response+=f"\n\nEsto merece atención porque {first(risks)}"
            return response
        return "Puedo explicarte el porqué, pero necesito separar lo que sé de lo que solo sería una hipótesis. Por ahora no tengo suficiente evidencia para atribuir una causa concreta."
    if intent=="sales_detail":
        if trend is None:return f"Tienes {sales_count} ventas. Todavía no tengo una comparación suficientemente sólida."
        if trend>0:return f"Tus ventas crecieron aproximadamente {_pct(trend)}. Eso es positivo, pero quiero comprobar si el crecimiento también está mejorando tu ganancia."
        if trend<0:return f"Tus ventas bajaron aproximadamente {_pct(abs(trend))}. Lo siguiente que revisaría es qué productos explican la caída y si el problema está en volumen, precio o mezcla de ventas."
        return "Tus ventas están prácticamente estables. Aquí buscaría oportunidades de crecimiento sin sacrificar margen."
    if intent=="sales":
        if trend is None:return f"Tienes {sales_count} ventas en {observed_days} días con actividad."
        if trend>0:return f"Las ventas vienen creciendo: +{_pct(trend)} frente al período comparable. La señal es buena; ahora hay que comprobar cuánto de ese crecimiento se convierte realmente en ganancia."
        if trend<0:return f"Las ventas vienen cayendo: {_pct(abs(trend))}. No asumiría todavía una causa; primero revisaría productos, ticket y frecuencia."
        return "Las ventas están estables. Eso no es necesariamente malo: ahora podemos buscar si hay margen para crecer."
    if intent=="improve_sales":
        if opportunities:return "Yo atacaría primero estas oportunidades:\n"+bullets(opportunities,3)
        if top:return f"Empezaría por {_pname(top[0])}: ya tiene movimiento y podemos buscar productos complementarios o mejorar su margen."
        return "Empezaría identificando qué productos tienen mejor combinación de demanda y margen."
    if intent=="top_products":
        if not top:return "Todavía no tengo suficientes datos para identificar tus productos más vendidos."
        rows=[f"{i}. {_pname(p)} — {_num(p.get('units'))} unidades" for i,p in enumerate(top[:5],1)]
        return "Los productos que más movimiento tienen son:\n"+"\n".join(rows)+"\n\nVender mucho no siempre significa ganar más; si quieres, puedo leerlos también desde el margen."
    if intent=="restock":
        urgent=[x for x in inventory if float(x.get("suggested_purchase",0) or 0)>0]
        if not urgent:return "No veo una reposición urgente en los datos disponibles. Eso no significa que todo el inventario esté perfecto; puedo revisar riesgo de capital inmovilizado y productos lentos."
        rows=[f"• {_pname(p)} — sugerencia de compra: {_num(p.get('suggested_purchase'))} unidades" for p in urgent[:3]]
        return "Priorizaría estas reposiciones:\n"+"\n".join(rows)+"\n\nLa idea es evitar quedarte sin productos con movimiento sin comprar de más."
    if intent=="profit":
        candidates=[p for p in (insights.get("abc_analysis",[]) or []) if p.get("profit") is not None]
        if candidates:
            p=max(candidates,key=lambda x:float(x.get("profit") or 0)); response=f"El producto que más ganancia aporta según los datos disponibles es {_pname(p)}: {_money(p.get('profit'),currency)}, con un margen de {_pct(p.get('margin_percent'))}."; response+="\n\nEn simple: el margen bruto es lo que queda de una venta después de pagar el costo del producto."; return response
        if diagnosis:return f"Puedo ver la operación, pero todavía no tengo costos suficientes para afirmar una ganancia por producto. {first(diagnosis)}"
        return "Todavía no tengo costos suficientes para calcular la ganancia con confianza."
    if intent=="cash":
        if risks:return f"En caja, lo primero que vigilaría es: {first(risks)}\n\nLiquidez significa el dinero disponible para cumplir tus pagos y mantener funcionando el negocio."
        return "Puedo revisar la salud de caja, pero necesito datos suficientes de entradas, salidas y compromisos registrados."
    if intent=="costs":
        if risks or diagnosis:
            response="Aquí buscaría el origen de la presión financiera."
            if diagnosis:response+=f"\n\n{first(diagnosis)}"
            if risks:response+=f"\n\nLo que vigilaría: {first(risks)}"
            return response
        return "Todavía no tengo evidencia suficiente para decirte dónde estás perdiendo dinero."
    if intent=="forecast":
        if not forecast.get("available"):return "Todavía no tengo suficientes datos para hacer una buena proyección. Prefiero no darte un número que parezca preciso sin tener una base sólida."
        return f"Para los próximos {forecast.get('horizon_days',7)} días estimo unas ventas de {_money(forecast.get('predicted_period_revenue'),currency)}. Es una proyección basada en el comportamiento registrado, no una garantía."
    if intent=="anomaly":
        if anomaly.get("is_anomaly"):return "Sí, detecté un comportamiento fuera de lo habitual. Lo tomaría como una señal para investigar, no como una explicación automática de lo que ocurrió."
        return "No veo un comportamiento especialmente fuera de lo normal en los ingresos recientes."
    if intent=="customers":return "Todavía no tengo una medición completa del comportamiento de clientes. No quiero fingir precisión donde no la tengo."
    if diagnosis or risks or opportunities or recommendations:
        response=[]
        if diagnosis:response.append(first(diagnosis))
        if risks:response.append(f"Vigilaría: {first(risks)}")
        if opportunities:response.append(f"Oportunidad: {first(opportunities)}")
        if recommendations:response.append(f"Yo haría primero: {first(recommendations)}")
        if teaching:
            teach=first(teaching)
            if teach:response.append(f"En simple: {teach}")
        return "\n\n".join(_unique(response)[:4])
    if top:return f"Estoy viendo tu negocio desde varias perspectivas. {_pname(top[0])} es uno de los productos con mayor movimiento. Si me preguntas algo concreto, puedo analizar el impacto en ventas, margen, inventario o crecimiento."
    return "Todavía necesito más datos para darte una lectura útil del negocio."

async def _native_cubi_reply(business_id,user_message,previous_messages=None):
    insights=await build_business_insights(db,business_id); business=await db.businesses.find_one({"id":business_id},{"_id":0,"name":1,"currency":1}) or {}; currency=business.get("currency","USD"); return _native_expert_reply(insights,user_message,currency)

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
        insights=await build_business_insights(db,bid); margin_data=await margin_analysis(user); context=await build_assistant_context(bid,business or {}); rich_context=_cubi_chat_context(insights,business or {},margin_data); s=(margin_data.get("summary") or {}); context+=f"\n\nCUBI INTELLIGENCE STRUCTURED:\n{rich_context}"; context+=f"\n\nANÁLISIS FINANCIERO AI-01 (90 días):\nIngresos: {s.get('revenue_90d')} | Costo: {s.get('realized_cost_90d')} | Utilidad: {s.get('realized_profit_90d')} | Margen: {s.get('realized_margin_percent')}%"; alerts=(margin_data.get("alerts") or [])[:10]
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