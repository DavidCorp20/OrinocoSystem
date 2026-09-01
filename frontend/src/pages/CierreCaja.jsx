import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Calculator, History, Save, WalletCards } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { fmtNum } from "../lib/format";

const DENOMINATIONS = [500, 200, 100, 50, 20, 10, 5, 1, 0.5];
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`; };
const money = n => `Bs ${fmtNum(Number(n || 0))}`;

export default function CierreCaja() {
  const [date, setDate] = useState(today());
  const [summary, setSummary] = useState(null);
  const [closures, setClosures] = useState([]);
  const [opening, setOpening] = useState(0);
  const [usePrevious, setUsePrevious] = useState(false);
  const [otherIn, setOtherIn] = useState(0);
  const [otherOut, setOtherOut] = useState(0);
  const [observations, setObservations] = useState("");
  const [denoms, setDenoms] = useState(Object.fromEntries(DENOMINATIONS.map(v => [String(v), "0"])));
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async target => {
    setLoading(true);
    try {
      const [{ data: s }, { data: h }] = await Promise.all([api.get(`/cash-closures/summary?date=${target}`), api.get("/cash-closures?limit=30")]);
      setSummary(s); setClosures(h.closures || []);
      if (s.last_closure?.counted_cash != null) setOpening(Number(s.last_closure.counted_cash));
      else if (s.previous_closing_cash != null) setOpening(Number(s.previous_closing_cash));
    } catch (e) { toast.error(apiError(e, "No pude cargar el cierre de caja.")); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(date); }, [date]);
  const denominationTotal = useMemo(() => DENOMINATIONS.reduce((sum, value) => sum + value * Number(denoms[String(value)] || 0), 0), [denoms]);
  const counted = Math.round(denominationTotal * 100) / 100;
  const effectiveOpening = usePrevious && summary?.previous_closing_cash != null ? Number(summary.previous_closing_cash) : Number(opening || 0);
  const expected = Math.round((effectiveOpening + Number(summary?.expected_before_opening || 0) + Number(otherIn || 0) - Number(otherOut || 0)) * 100) / 100;
  const difference = Math.round((counted - expected) * 100) / 100;

  const save = async () => {
    setSaving(true);
    try {
      const denominations = DENOMINATIONS.map(value => ({ value, quantity: Number(denoms[String(value)] || 0) })).filter(x => x.quantity > 0);
      await api.post("/cash-closures", { date, opening_cash: effectiveOpening, denominations, counted_cash: counted, other_cash_in: Number(otherIn || 0), other_cash_out: Number(otherOut || 0), observations: observations || null, use_previous_closing: usePrevious });
      toast.success("Cierre de caja guardado correctamente"); await load(date);
    } catch (e) { toast.error(apiError(e, "No pude guardar el cierre.")); }
    finally { setSaving(false); }
  };

  return <div className="space-y-5 max-w-6xl" data-testid="cierre-caja-page">
    <div><h1 className="font-heading text-3xl font-extrabold">Cierre de caja</h1><p className="text-sm text-muted-foreground mt-1">Reconcilia el efectivo esperado contra el efectivo contado, con detalle de cada movimiento.</p></div>
    <div className="bg-card border rounded-2xl p-5"><div className="flex flex-wrap items-end gap-4"><div><Label>Fecha de cierre</Label><Input type="date" value={date} onChange={e => setDate(e.target.value)} className="mt-1.5 w-44" /></div><div className="flex items-center gap-2 h-10"><input id="previous" type="checkbox" checked={usePrevious} onChange={e => setUsePrevious(e.target.checked)} /><Label htmlFor="previous">Usar cierre anterior como apertura</Label></div>{!usePrevious && <div><Label>Efectivo inicial</Label><Input type="number" min="0" step="0.01" value={opening} onChange={e => setOpening(e.target.value)} className="mt-1.5 w-44" /></div>}</div></div>
    <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4"><Metric title="Ventas en efectivo" value={money(summary?.cash_sales)} detail={`${summary?.sales_count || 0} ventas registradas`} /><Metric title="Cobros en efectivo" value={money(summary?.cash_receivables)} detail="Cuentas por cobrar" /><Metric title="Compras en efectivo" value={money(summary?.cash_purchases)} detail={`${summary?.purchases_count || 0} compras registradas`} negative /><Metric title="Gastos en efectivo" value={money(summary?.cash_expenses)} detail={`${summary?.expenses_count || 0} gastos registrados`} negative /></div>
    <div className="grid lg:grid-cols-2 gap-5">
      <div className="bg-card border rounded-2xl p-5"><div className="flex items-center gap-2 mb-4"><Calculator className="w-5 h-5 text-primary"/><h2 className="font-heading font-bold">Conciliación</h2></div><div className="space-y-3 text-sm"><Row label="Efectivo inicial" value={money(effectiveOpening)} /><Row label="+ Ventas en efectivo" value={money(summary?.cash_sales)} /><Row label="+ Cobros en efectivo" value={money(summary?.cash_receivables)} /><Row label="− Compras en efectivo" value={money(summary?.cash_purchases)} /><Row label="− Pagos de cuentas por pagar" value={money(summary?.cash_payables)} /><Row label="− Gastos en efectivo" value={money(summary?.cash_expenses)} /><div className="border-t pt-3"><Row label="Efectivo esperado" value={money(expected)} strong /></div><div className="grid grid-cols-2 gap-3 pt-2"><div><Label>+ Otros ingresos</Label><Input type="number" min="0" step="0.01" value={otherIn} onChange={e => setOtherIn(e.target.value)} className="mt-1.5" /></div><div><Label>− Otros retiros</Label><Input type="number" min="0" step="0.01" value={otherOut} onChange={e => setOtherOut(e.target.value)} className="mt-1.5" /></div></div></div></div>
      <div className="bg-card border rounded-2xl p-5"><div className="flex items-center gap-2 mb-4"><WalletCards className="w-5 h-5 text-primary"/><h2 className="font-heading font-bold">Conteo físico</h2></div><div className="grid grid-cols-2 sm:grid-cols-3 gap-3">{DENOMINATIONS.map(value => <div key={value}><Label>{value < 1 ? `${value.toFixed(2)} Bs` : `${value} Bs`}</Label><Input type="number" min="0" step="1" value={denoms[String(value)]} onChange={e => setDenoms({...denoms, [String(value)]: e.target.value})} className="mt-1.5" /></div>)}</div><div className="mt-4 rounded-xl bg-secondary/60 p-4 flex justify-between"><span className="font-semibold">Efectivo contado</span><span className="font-heading font-extrabold">{money(counted)}</span></div><div className={`mt-3 rounded-xl p-4 flex items-center justify-between border ${difference === 0 ? "bg-emerald-50 border-emerald-200" : difference > 0 ? "bg-blue-50 border-blue-200" : "bg-rose-50 border-rose-200"}`}><div className="flex items-center gap-2 font-semibold">{difference === 0 ? <CheckCircle2 className="w-5 h-5"/> : <AlertTriangle className="w-5 h-5"/>}<span>{difference === 0 ? "Caja cuadrada" : difference > 0 ? "Sobrante" : "Faltante"}</span></div><span className="font-heading font-extrabold">{money(Math.abs(difference))}</span></div></div>
    </div>
    <div className="bg-card border rounded-2xl p-5"><Label>Observaciones</Label><textarea value={observations} onChange={e => setObservations(e.target.value)} rows={3} placeholder="Explica faltantes, sobrantes, retiros u otra incidencia…" className="mt-1.5 w-full rounded-xl border bg-background px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"/><Button onClick={save} disabled={saving || loading} className="mt-4 rounded-xl"><Save className="w-4 h-4 mr-1.5"/>{saving ? "Guardando…" : "Guardar cierre"}</Button></div>
    <div className="bg-card border rounded-2xl p-5"><div className="flex items-center gap-2 mb-4"><History className="w-5 h-5 text-primary"/><h2 className="font-heading font-bold">Historial de cierres</h2></div>{closures.length === 0 ? <p className="text-sm text-muted-foreground">Todavía no hay cierres registrados.</p> : <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left border-b"><th className="py-2 pr-4">Fecha</th><th className="py-2 pr-4">Esperado</th><th className="py-2 pr-4">Contado</th><th className="py-2 pr-4">Diferencia</th><th className="py-2 pr-4">Usuario</th></tr></thead><tbody>{closures.map(c => <tr key={c.id} className="border-b last:border-0"><td className="py-3 pr-4">{c.date}</td><td className="py-3 pr-4">{money(c.expected_cash)}</td><td className="py-3 pr-4">{money(c.counted_cash)}</td><td className={`py-3 pr-4 font-semibold ${Number(c.difference) < 0 ? "text-rose-600" : Number(c.difference) > 0 ? "text-blue-600" : "text-emerald-700"}`}>{money(c.difference)}</td><td className="py-3 pr-4 text-muted-foreground">{c.user_email}</td></tr>)}</tbody></table></div>}</div>
  </div>;
}
function Metric({ title, value, detail, negative }) { return <div className="bg-card border rounded-2xl p-4"><p className="text-xs text-muted-foreground">{title}</p><p className={`font-heading text-xl font-extrabold mt-1 ${negative ? "text-rose-700" : ""}`}>{value}</p><p className="text-xs text-muted-foreground mt-1">{detail}</p></div>; }
function Row({ label, value, strong }) { return <div className={`flex justify-between gap-4 ${strong ? "font-heading font-extrabold text-base" : ""}`}><span>{label}</span><span>{value}</span></div>; }
