import {useEffect,useRef,useState} from "react";
import {Bot,Send,X,Sparkles,RotateCcw} from "lucide-react";
import api,{apiError,streamChat} from "../lib/api";
const QUICK_PROMPTS=["Ventas","Productos","Inventario","Ganancias","Proyección"];
const renderMd=text=>(text||"").split(/(\*\*[^*]+\*\*)/g).map((part,i)=>part.startsWith("**")?<strong key={i}>{part.slice(2,-2)}</strong>:part);
const normalize=s=>(s||"").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"").trim();
const isGreeting=s=>/^(hola|hol|buenas|hello|hey|holi)[!. ,]*$/i.test((s||"").trim());
const isLegacyBroken=s=>/\{'term'\s*:\s*['\"]Margen bruto['\"]/.test(s||"")||/^En simple:\s*Margen bruto:/i.test((s||"").trim());
const menuFor=(text,isFirst=false)=>{
 const t=normalize(text);
 if(isFirst)return QUICK_PROMPTS;
 if(/quieres ver que producto|que producto esta aportando|producto esta aportando/.test(t)) return ["Qué producto vende más","Cuánto crecieron","Ver ganancias"];
 if(/quieres que los compare por ganancia|comparar por ganancia/.test(t)) return ["Comparar por ganancia","Revisar inventario","Ver ventas"];
 if(/comparar los 3 mejores|mayor ganancia/.test(t)) return ["Comparar los 3 mejores","Ver productos más vendidos","Ver inventario"];
 if(/revisar que productos|productos estan bajando|productos perdieron/.test(t)) return ["Producto que más bajó","Producto que más vende","Ver ganancias"];
 if(/quieres revisar los faltantes|quieres revisar inventario|quieres ver el inventario/.test(t)) return ["Ver faltantes","Ver poco stock","Ver productos"];
 if(/quieres ver la proyeccion|quieres ver la tendencia/.test(t)) return ["Ver tendencia","Ver productos","Ver ventas"];
 if(/si quieres, puedo leerlos tambien desde el margen|puedo leerlos tambien desde el margen/.test(t)) return ["Comparar por ganancia","Ver inventario","Ver ventas"];
 return [];
};
export default function AIAssistant({open,onClose}){
 const[messages,setMessages]=useState([]),[input,setInput]=useState(""),[sending,setSending]=useState(false),[error,setError]=useState(""),loadedRef=useRef(false),bottomRef=useRef(null);
 useEffect(()=>{if(!open||loadedRef.current)return;loadedRef.current=true;setError("");api.get("/assistant/history").then(r=>setMessages((r.data.messages||[]).filter(m=>!isLegacyBroken(m.content)))).catch(e=>setError(apiError(e,"No pude cargar el historial.")))},[open]);
 const send=async text=>{let msg=(text??input).trim();if(!msg||sending)return;
   const n=normalize(msg);
   // Greetings are conversational and never need analytics or the AI provider.
   if(isGreeting(msg)){
     setInput("");setError("");setMessages(m=>[...m,{role:"user",content:msg},{role:"assistant",content:"Hola. Soy Cubi, tu asesor de negocio. Puedo ayudarte con ventas, productos, inventario, ganancias y proyecciones. ¿Qué quieres revisar?"}]);
     return;
   }
   const lastAssistant=[...messages].reverse().find(m=>m.role==="assistant")?.content||"";
   if(["si","sí","claro","dale","ok","okay"].includes(n)){
     const q=normalize(lastAssistant);
     if(q.includes("compare")&&q.includes("ganancia"))msg="Comparar por ganancia";
     else if(q.includes("producto")&&q.includes("aporta"))msg="Qué producto vende más";
     else if(q.includes("crecimiento")||q.includes("crecieron"))msg="Cuánto crecieron";
     else if(q.includes("inventario")||q.includes("reponer"))msg="Ver inventario";
     else msg="Ventas";
   }
   setInput("");setError("");setSending(true);setMessages(m=>[...m,{role:"user",content:msg},{role:"assistant",content:"",pending:true}]);
   try{await streamChat(msg,token=>setMessages(m=>{const c=[...m],i=c.length-1;c[i]={...c[i],content:(c[i].content||"")+token,pending:false};return c}),()=>setMessages(m=>{const c=[...m],i=c.length-1;if(c[i]?.role==="assistant")c[i]={...c[i],pending:false};return c}))}catch(e){setError(e.message||"No pude conectar con Cubi");setMessages(m=>{const c=[...m],i=c.length-1;if(c[i]?.role==="assistant")c[i]={...c[i],content:"No pude procesar tu consulta. Revisa la conexión del asistente e inténtalo nuevamente.",pending:false,error:true};return c})}finally{setSending(false)}};
 useEffect(()=>{bottomRef.current?.scrollIntoView({behavior:"smooth"})},[messages]);
 if(!open)return null;
 const lastAssistantIndex=[...messages].map((m,i)=>({m,i})).reverse().find(x=>x.m.role==="assistant"&&x.m.content)?.i;
 return <div data-testid="ai-assistant-panel" className="fixed bottom-4 right-4 z-50 w-[calc(100vw-2rem)] sm:w-96 h-[70vh] sm:h-[560px] bg-card border rounded-2xl shadow-2xl flex flex-col overflow-hidden" onClick={e=>e.stopPropagation()}><div className="bg-primary text-white px-4 py-3 flex items-center gap-2.5"><div className="w-8 h-8 rounded-full bg-white/15 flex items-center justify-center"><Bot className="w-4 h-4"/></div><div className="flex-1"><p className="font-heading font-bold text-sm">Cubi, tu asesor</p><p className="text-[11px] text-white/70">Ventas · inventario · gastos · rentabilidad</p></div><button type="button" onClick={onClose}><X className="w-4 h-4"/></button></div>{error&&<div className="mx-3 mt-3 rounded-xl border border-red-200 bg-red-50 p-2.5 text-xs text-red-700 flex gap-2"><span className="flex-1">{error}</span><button type="button" onClick={()=>{const last=messages.filter(m=>m.role==="user").at(-1);if(last){setError("");send(last.content)}}} disabled={sending}><RotateCcw className="w-4 h-4"/></button></div>}<div className="flex-1 overflow-y-auto p-4 space-y-3">{messages.length===0&&<div className="space-y-3"><div className="flex items-start gap-2"><Sparkles className="w-4 h-4 text-accent mt-1"/><p className="text-sm text-slate-600">Hola, soy <b>Cubi</b>. Conozco las operaciones de tu negocio. Pregúntame algo y te responderé con tus datos.</p></div><div className="flex flex-wrap gap-2">{QUICK_PROMPTS.map(q=><button type="button" key={q} onClick={()=>send(q)} disabled={sending} className="text-xs bg-secondary hover:bg-primary hover:text-white px-3 py-1.5 rounded-full border">{q}</button>)}</div></div>}{messages.map((m,i)=>{const options=m.role==="assistant"&&!m.pending&&m.content?menuFor(m.content,i===lastAssistantIndex&&messages.length<=2):[];return <div key={i} className={`flex ${m.role==="user"?"justify-end":"justify-start"}`}><div className="max-w-[90%]"><div data-testid={`ai-message-${m.role}-${i}`} className={`rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${m.role==="user"?"bg-primary text-white rounded-br-md":"bg-secondary text-slate-700 rounded-bl-md"}`}>{renderMd(m.content)}{m.pending&&!m.content&&<span className="flex gap-1 py-1"><span className="w-1.5 h-1.5 rounded-full bg-slate-400 typing-dot"/><span className="w-1.5 h-1.5 rounded-full bg-slate-400 typing-dot"/></span>}</div>{options.length>0&&<div className="flex flex-wrap gap-1.5 mt-2">{options.map(q=><button type="button" key={q} onClick={()=>send(q)} disabled={sending} className="text-[11px] bg-card hover:bg-primary hover:text-white border px-2.5 py-1.5 rounded-full transition-colors">{q}</button>)}</div>}</div></div>})}<div ref={bottomRef}/></div><div className="border-t p-3 flex gap-2"><input data-testid="ai-chat-input" value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&send()} placeholder="Pregunta sobre tu negocio…" className="flex-1 text-sm bg-secondary rounded-xl px-3.5 py-2.5 outline-none focus:ring-2 focus:ring-primary/40"/><button type="button" data-testid="ai-chat-send-button" onClick={()=>send()} disabled={sending||!input.trim()} className="w-10 h-10 rounded-xl bg-primary text-white flex items-center justify-center disabled:opacity-40"><Send className="w-4 h-4"/></button></div></div>;
}
