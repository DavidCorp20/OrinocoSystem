import {useEffect,useState} from "react";
import {ArrowLeft,Save,ShieldCheck} from "lucide-react";
import {useNavigate} from "react-router-dom";
import {toast} from "sonner";
import api,{apiError} from "../lib/api";
import {Button} from "../components/ui/button";
import {Input} from "../components/ui/input";
import {Label} from "../components/ui/label";
import {Switch} from "../components/ui/switch";
import {Select,SelectContent,SelectItem,SelectTrigger,SelectValue} from "../components/ui/select";

const BOOLS=[
 ["basic_operations","Operación básica"],["finance","Finanzas"],["obligations","Cuentas por cobrar/pagar"],["reports_advanced","Reportes avanzados"],["projections","Proyecciones"],["promotions","Promociones"],["recipes","Recetas y costos"],["abc_xyz","Análisis ABC/XYZ"],["advanced_analytics","Analítica avanzada"],["cash_closure","Cierre de caja"]
];
const DEFAULTS={max_users:1,basic_operations:true,finance:false,obligations:false,reports_advanced:false,projections:false,promotions:false,recipes:false,abc_xyz:false,advanced_analytics:false,cash_closure:true,automations:"none",exports:"basic",cubi:"basic"};

function normalize(p){return {...DEFAULTS,...(p?.entitlements||{})};}
export default function PlanEntitlements(){
 const navigate=useNavigate();const[plans,setPlans]=useState([]);const[selected,setSelected]=useState("");const[form,setForm]=useState(DEFAULTS);const[saving,setSaving]=useState(false);
 useEffect(()=>{api.get("/platform/plans").then(r=>{const ps=r.data.plans||[];setPlans(ps);if(ps[0]){setSelected(ps[0].id);setForm(normalize(ps[0]));}}).catch(e=>toast.error(apiError(e)))},[]);
 const choose=id=>{const p=plans.find(x=>x.id===id);setSelected(id);setForm(normalize(p));};
 const save=async()=>{const p=plans.find(x=>x.id===selected);if(!p)return;setSaving(true);try{await api.put(`/platform/plans/${p.id}`,{name:p.name,description:p.description||"",monthly_price_usd:Number(p.monthly_price_usd),active:p.active!==false,features:p.features||[],entitlements:{...form,max_users:Math.max(1,Number(form.max_users)||1)}});toast.success(`Permisos de ${p.name} actualizados`);const r=await api.get("/platform/plans");setPlans(r.data.plans||[]);setForm(normalize((r.data.plans||[]).find(x=>x.id===p.id)));}catch(e){toast.error(apiError(e))}finally{setSaving(false)}};
 const toggle=k=>setForm(x=>({...x,[k]:!x[k]}));
 return <div className="space-y-5" data-testid="plan-entitlements-page"><div className="flex items-center justify-between gap-3 flex-wrap"><div><div className="flex items-center gap-2"><ShieldCheck className="w-7 h-7 text-primary"/><h1 className="font-heading text-3xl font-extrabold">Permisos por plan</h1></div><p className="text-sm text-muted-foreground mt-1">Define qué puede usar cada suscripción. Los cambios se aplican desde el backend de planes.</p></div><Button variant="outline" onClick={()=>navigate("/plataforma")}><ArrowLeft className="w-4 h-4 mr-2"/>Volver a Plataforma</Button></div>
 <div className="bg-card border rounded-2xl p-5 space-y-5"><div><Label>Plan</Label><Select value={selected} onValueChange={choose}><SelectTrigger className="mt-2 max-w-md"><SelectValue placeholder="Selecciona un plan"/></SelectTrigger><SelectContent>{plans.map(p=><SelectItem key={p.id} value={p.id}>{p.name} · ${Number(p.monthly_price_usd||0).toFixed(2)}/mes</SelectItem>)}</SelectContent></Select></div>
 <div className="grid md:grid-cols-2 gap-3">{BOOLS.map(([k,label])=><div key={k} className="flex items-center justify-between border rounded-xl px-4 py-3"><div><p className="font-medium">{label}</p><p className="text-xs text-muted-foreground">{k}</p></div><Switch checked={Boolean(form[k])} onCheckedChange={()=>toggle(k)}/></div>)}</div>
 <div className="grid md:grid-cols-4 gap-4"><div><Label>Máx. usuarios</Label><Input className="mt-2" type="number" min="1" value={form.max_users} onChange={e=>setForm(x=>({...x,max_users:e.target.value}))}/></div><div><Label>Automatizaciones</Label><Select value={form.automations} onValueChange={v=>setForm(x=>({...x,automations:v}))}><SelectTrigger className="mt-2"><SelectValue/></SelectTrigger><SelectContent>{["none","basic","advanced"].map(v=><SelectItem key={v} value={v}>{v}</SelectItem>)}</SelectContent></Select></div><div><Label>Exportaciones</Label><Select value={form.exports} onValueChange={v=>setForm(x=>({...x,exports:v}))}><SelectTrigger className="mt-2"><SelectValue/></SelectTrigger><SelectContent>{["none","basic","full"].map(v=><SelectItem key={v} value={v}>{v}</SelectItem>)}</SelectContent></Select></div><div><Label>Cubi</Label><Select value={form.cubi} onValueChange={v=>setForm(x=>({...x,cubi:v}))}><SelectTrigger className="mt-2"><SelectValue/></SelectTrigger><SelectContent>{["none","basic","standard","advanced"].map(v=><SelectItem key={v} value={v}>{v}</SelectItem>)}</SelectContent></Select></div></div>
 <div className="flex justify-end"><Button onClick={save} disabled={!selected||saving}><Save className="w-4 h-4 mr-2"/>{saving?"Guardando…":"Guardar permisos"}</Button></div></div></div>
}
