import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, Store, Users, CreditCard, Receipt, CalendarDays, BarChart3, AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { fmtDate, fmtMoney, fmtNum } from "../lib/format";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Switch } from "../components/ui/switch";

export default function Plataforma() {
  const [data, setData] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [plans, setPlans] = useState([]);
  const [pending, setPending] = useState([]);
  const [tab, setTab] = useState("resumen");
  const [selectedBusiness, setSelectedBusiness] = useState("");
  const [score, setScore] = useState(null);
  const [scoreDays, setScoreDays] = useState("90");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [overview, plansRes, pendingRes, metricsRes] = await Promise.all([
        api.get("/platform/overview"),
        api.get("/platform/plans"),
        api.get("/platform/pending-users"),
        api.get("/platform/billing-metrics"),
      ]);
      setData(overview.data);
      setPlans(plansRes.data.plans || []);
      setPending(pendingRes.data.users || []);
      setMetrics(metricsRes.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const loadScore = async (businessId, days = scoreDays) => {
    if (!businessId) return;
    try {
      const res = await api.get(`/platform/platia-score/${businessId}?days=${Number(days)}`);
      setScore(res.data);
    } catch (e) {
      setScore(null);
      toast.error(apiError(e));
    }
  };

  const toggleBusiness = async (business, active) => {
    try {
      await api.put(`/platform/businesses/${business.id}/status`, { active });
      toast.success(active ? "Cuenta habilitada" : "Cuenta deshabilitada");
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const approve = async (user) => {
    try {
      await api.put(`/platform/users/${user.id}/approval`, { approved: true });
      toast.success("Cuenta aprobada");
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  if (!data) return <div className="p-8 text-sm text-muted-foreground">Cargando plataforma…</div>;

  const stats = data.stats || {};
  const businesses = data.businesses || [];
  const tabs = [
    ["resumen", "Resumen"],
    ["clientes", "Clientes"],
    ["score", "PLATIA Score"],
    ["planes", "Planes y precios"],
  ];

  return (
    <div className="space-y-5" data-testid="plataforma-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-heading text-3xl font-extrabold flex items-center gap-2"><ShieldCheck className="w-7 h-7 text-primary" />Plataforma</h1>
          <p className="text-sm text-muted-foreground">Gobernanza, clientes, planes, vencimientos, cobros y costos.</p>
        </div>
        <Button variant="outline" onClick={load} disabled={loading}><RefreshCw className="w-4 h-4 mr-2" />Actualizar</Button>
      </div>

      <div className="flex gap-1 p-1 bg-secondary rounded-xl overflow-x-auto">
        {tabs.map(([value, label]) => <button key={value} onClick={() => setTab(value)} className={`px-4 py-2 rounded-lg text-sm whitespace-nowrap ${tab === value ? "bg-background shadow-sm" : ""}`}>{label}</button>)}
      </div>

      {tab === "resumen" && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <Kpi title="Negocios" value={fmtNum(stats.total)} icon={<Store className="w-5 h-5" />} />
            <Kpi title="Activos" value={fmtNum(stats.activos)} icon={<Users className="w-5 h-5" />} />
            <Kpi title="MRR" value={fmtMoney(stats.mrr_usd || 0, "USD")} icon={<CreditCard className="w-5 h-5" />} />
            <Kpi title="Cobrado este mes" value={fmtMoney(stats.cobrado_mes_usd || 0, "USD")} icon={<Receipt className="w-5 h-5" />} />
            <Kpi title="Nuevos 30 días" value={fmtNum(stats.nuevos_30 || 0)} icon={<CalendarDays className="w-5 h-5" />} />
          </div>
          <div className="bg-card border rounded-2xl p-5">
            <h3 className="font-heading font-bold mb-3">Próximos vencimientos</h3>
            {(metrics?.due_soon || []).length ? metrics.due_soon.map(item => <div key={item.id} className="py-3 border-b flex justify-between"><span>{item.plan_name || "Sin plan"}</span><b>{fmtDate(item.due_date)}</b></div>) : <p className="text-sm text-muted-foreground">No hay cuentas por vencer en los próximos 7 días.</p>}
          </div>
        </>
      )}

      {tab === "clientes" && (
        <div className="space-y-4">
          <div className="bg-card border rounded-2xl overflow-hidden">
            <div className="px-5 py-4 border-b"><h3 className="font-heading font-bold">Cuentas y suscripciones</h3></div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm"><thead><tr className="text-left text-xs uppercase text-muted-foreground bg-secondary/50"><th className="px-5 py-3">Negocio</th><th>Alta</th><th>Plan</th><th>Estado</th><th>Cuenta</th></tr></thead>
                <tbody className="divide-y">{businesses.map(b => <tr key={b.id}><td className="px-5 py-3"><b>{b.name}</b><div className="text-xs text-muted-foreground">{b.owner_email}</div></td><td>{fmtDate(b.created_at)}</td><td>{b.plan_name || "Sin plan"}</td><td>{b.subscription_status || "sin plan"}</td><td><Switch checked={!!b.active} onCheckedChange={value => toggleBusiness(b, value)} /></td></tr>)}</tbody>
              </table>
            </div>
          </div>
          <div className="bg-card border rounded-2xl p-5"><h3 className="font-heading font-bold mb-3">Solicitudes pendientes ({pending.length})</h3>{pending.map(u => <div key={u.id} className="flex items-center gap-3 py-3 border-b"><div className="flex-1"><b>{u.name || u.email}</b><div className="text-xs text-muted-foreground">{u.email} · Alta {fmtDate(u.created_at)}</div></div><Button size="sm" onClick={() => approve(u)}>Aprobar</Button></div>)}</div>
        </div>
      )}

      {tab === "score" && (
        <div className="bg-card border rounded-2xl p-5 space-y-5">
          <div className="flex items-center justify-between flex-wrap gap-3"><div><h3 className="font-heading font-bold flex items-center gap-2"><BarChart3 className="w-5 h-5 text-primary" />PLATIA Score</h3><p className="text-sm text-muted-foreground">Indicador interno de salud y riesgo empresarial.</p></div><div className="flex gap-2"><Select value={scoreDays} onValueChange={value => { setScoreDays(value); if (selectedBusiness) loadScore(selectedBusiness, value); }}><SelectTrigger className="w-28"><SelectValue /></SelectTrigger><SelectContent>{["30", "60", "90", "180", "365"].map(v => <SelectItem key={v} value={v}>{v} días</SelectItem>)}</SelectContent></Select></div></div>
          <Select value={selectedBusiness} onValueChange={value => { setSelectedBusiness(value); setScore(null); loadScore(value, scoreDays); }}><SelectTrigger><SelectValue placeholder="Selecciona un negocio" /></SelectTrigger><SelectContent>{businesses.map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent></Select>
          {!score ? <div className="border rounded-2xl p-8 text-center text-sm text-muted-foreground">Selecciona un negocio para consultar su score.</div> : <div className="space-y-4"><div className="grid md:grid-cols-3 gap-3"><Kpi title="Score" value={`${score.score}/1000`} /><Kpi title="Banda" value={score.band || "—"} /><Kpi title="Período" value={`${score.period_days || scoreDays} días`} /></div><div className="border rounded-2xl p-4"><h4 className="font-bold mb-3">Componentes</h4>{(score.components || []).map(component => <div key={component.name} className="mb-4"><div className="flex justify-between text-sm"><span>{component.name}</span><b>{component.score}</b></div><div className="h-2 bg-secondary rounded-full mt-2"><div className="h-2 bg-primary rounded-full" style={{ width: `${Math.max(0, Math.min(100, Number(component.score || 0) / 10))}%` }} /></div></div>)}</div><div className="grid md:grid-cols-2 gap-4"><List title="Fortalezas" icon={<CheckCircle2 className="w-4 h-4" />} items={score.strengths} /><List title="Alertas de riesgo" icon={<AlertTriangle className="w-4 h-4" />} items={score.risk_alerts} /></div><div className="border rounded-2xl p-4"><h4 className="font-bold mb-2">Acciones recomendadas</h4><ListItems items={score.actions} /></div><p className="text-xs text-muted-foreground">{score.disclaimer}</p></div>}
        </div>
      )}

      {tab === "planes" && <div className="grid md:grid-cols-3 gap-4">{plans.map(plan => <div key={plan.id} className="bg-card border rounded-2xl p-5"><div className="flex justify-between"><h3 className="text-xl font-bold">{plan.name}</h3><span className="text-xs px-2 py-1 rounded-full bg-secondary">{plan.active ? "Activo" : "Inactivo"}</span></div><p className="text-sm text-muted-foreground mt-2">{plan.description}</p><p className="text-3xl font-bold mt-5">{fmtMoney(plan.monthly_price_usd, "USD")}<span className="text-sm font-normal"> / mes</span></p></div>)}</div>}
    </div>
  );
}

function Kpi({ title, value, icon }) {
  return <div className="bg-card border border-border rounded-2xl p-5"><div className="flex items-center justify-between"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>{icon && <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary">{icon}</div>}</div><p className="text-2xl font-extrabold mt-2">{value ?? "0"}</p></div>;
}

function List({ title, icon, items }) {
  return <div className="border rounded-2xl p-4"><h4 className="font-bold flex items-center gap-2 mb-3">{icon}{title}</h4><ListItems items={items} /></div>;
}

function ListItems({ items }) {
  return (items || []).length ? <ul className="space-y-2 text-sm">{items.map(item => <li key={item}>• {item}</li>)}</ul> : <p className="text-sm text-muted-foreground">Sin elementos.</p>;
}
