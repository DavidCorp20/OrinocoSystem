import { useEffect, useState } from "react";
import { Plus, CheckCircle2, Trash2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { fmtMoney, fmtDate } from "../lib/format";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

export default function Cuentas() {
  const { business } = useAuth(); const currency = business?.currency || "USD";
  const [items,setItems]=useState([]); const [open,setOpen]=useState(false);
  const [form,setForm]=useState({kind:"por_cobrar",contact:"",description:"",amount:"",due_date:"",notes:""});
  const load=()=>api.get("/obligations").then(r=>setItems(r.data.obligations)).catch(e=>toast.error(apiError(e)));
  useEffect(()=>{load();},[]);
  const save=async e=>{e.preventDefault();try{await api.post("/obligations",{...form,amount:Number(form.amount)});toast.success("Cuenta registrada");setOpen(false);setForm({kind:"por_cobrar",contact:"",description:"",amount:"",due_date:"",notes:""});load();}catch(e){toast.error(apiError(e));}};
  const status=async(i,s)=>{try{await api.patch(`/obligations/${i.id}/status?status=${s}`);load();}catch(e){toast.error(apiError(e));}};
  const remove=async i=>{try{await api.delete(`/obligations/${i.id}`);load();}catch(e){toast.error(apiError(e));}};
  const pending=items.filter(i=>i.status==="pendiente");
  return <div className="space-y-5" data-testid="cuentas-page">
    <div className="flex justify-between items-center gap-3"><div><h1 className="font-heading text-3xl font-extrabold">Cuentas por cobrar y pagar</h1><p className="text-sm text-muted-foreground mt-1">Controla compromisos y cobros antes de que se conviertan en olvidos.</p></div><Button onClick={()=>setOpen(true)} className="rounded-xl"><Plus className="w-4 h-4 mr-1.5"/>Nueva cuenta</Button></div>
    {pending.length>0&&<div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex gap-3"><AlertCircle className="w-5 h-5 text-amber-700 shrink-0"/><div><b className="text-amber-900">Tienes {pending.length} cuenta(s) pendiente(s).</b><p className="text-sm text-amber-800 mt-1">Revisa las fechas de vencimiento y marca como pagadas o cobradas cuando corresponda.</p></div></div>}
    <div className="bg-card border border-border rounded-2xl overflow-hidden"><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-xs uppercase tracking-wide text-muted-foreground border-b bg-secondary/50"><th className="px-5 py-3">Tipo</th><th className="px-4 py-3">Contacto</th><th className="px-4 py-3">Descripción</th><th className="px-4 py-3">Vencimiento</th><th className="px-4 py-3 text-right">Monto</th><th className="px-4 py-3">Estado</th><th/></tr></thead><tbody className="divide-y">{items.map(i=><tr key={i.id}><td className="px-5 py-3 font-semibold">{i.kind==="por_cobrar"?"Por cobrar":"Por pagar"}</td><td className="px-4 py-3">{i.contact}</td><td className="px-4 py-3">{i.description}</td><td className="px-4 py-3">{i.due_date}</td><td className="px-4 py-3 text-right font-semibold">{fmtMoney(i.amount,currency)}</td><td className="px-4 py-3">{i.status}</td><td className="px-4 py-3 text-right flex gap-1 justify-end">{i.status==="pendiente"&&<button title="Marcar pagada/cobrada" onClick={()=>status(i,"pagada")} className="p-1.5 text-emerald-700"><CheckCircle2 className="w-4 h-4"/></button>}<button onClick={()=>remove(i)} className="p-1.5 text-rose-600"><Trash2 className="w-4 h-4"/></button></td></tr>)}</tbody></table>{!items.length&&<p className="p-10 text-center text-sm text-muted-foreground">No tienes cuentas registradas.</p>}</div></div>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent><DialogHeader><DialogTitle>Nueva cuenta</DialogTitle></DialogHeader><form onSubmit={save} className="space-y-4"><div><Label>Tipo</Label><Select value={form.kind} onValueChange={v=>setForm({...form,kind:v})}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value="por_cobrar">Por cobrar</SelectItem><SelectItem value="por_pagar">Por pagar</SelectItem></SelectContent></Select></div><div><Label>Cliente / proveedor</Label><Input required value={form.contact} onChange={e=>setForm({...form,contact:e.target.value})}/></div><div><Label>Descripción</Label><Input required value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></div><div className="grid grid-cols-2 gap-3"><div><Label>Monto</Label><Input required type="number" min="0.01" step="any" value={form.amount} onChange={e=>setForm({...form,amount:e.target.value})}/></div><div><Label>Vencimiento</Label><Input required type="date" value={form.due_date} onChange={e=>setForm({...form,due_date:e.target.value})}/></div></div><div><Label>Notas</Label><Input value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></div><div className="flex justify-end"><Button type="submit">Guardar</Button></div></form></DialogContent></Dialog>
  </div>;
}
