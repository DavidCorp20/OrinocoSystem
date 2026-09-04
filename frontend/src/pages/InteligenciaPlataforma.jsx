import { useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, BarChart3, Boxes, Building2, ChevronRight,
  CircleDollarSign, Database, Package, RefreshCw, Search, ShoppingCart,
  Truck, TrendingDown, TrendingUp, Wallet, X
} from "lucide-react";
import { toast } from "sonner";
import { useLocation, useNavigate } from "react-router-dom";
import {
  BarChart, Bar, CartesianGrid, Cell, PieChart, Pie, ResponsiveContainer,
  Tooltip, XAxis, YAxis
} from "recharts";
import api, { apiError } from "../lib/api";
import { fmtDate, fmtMoney, fmtNum } from "../lib/format";
import { Button } from "../components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "../components/ui/select";

const money = (value) => fmtMoney(Number(value || 0), "USD");

const scoreLabel = (value) => {
  const score = Number(value || 0);
  if (score >= 800) return "Excelente";
  if (score >= 700) return "Bueno";
  if (score >= 600) return "Moderado";
  if (score >= 500) return "Elevado";
  return "Alto";
};

const moduleByPath = (path) => {
  if (path.includes("/proveedores")) return "proveedores";
  if (path.includes("/benchmarks")) return "benchmarks";
  if (path.includes("/financiera")) return "financiera";
  if (path.includes("/data")) return "data";
  if (path.includes("/negocios")) return "negocios";
  return "resumen";
};

function Metric({ label, value, icon: Icon, sub }) {
  return (
    <div className="min-w-0 overflow-hidden rounded-2xl border bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-xs font-medium text-muted-foreground">{label}</p>
        {Icon && <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />}
      </div>
      <p className="mt-2 truncate text-xl font-extrabold tracking-tight sm:text-2xl" title={String(value)}>{value}</p>
      {sub && <p className="mt-1 truncate text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

function Section({ title, description, children, className = "" }) {
  return (
    <section className={`overflow-hidden rounded-2xl border bg-card shadow-sm ${className}`}>
      <div className="border-b px-5 py-4">
        <h2 className="font-heading text-base font-bold">{title}</h2>
        {description && <p className="mt-1 text-xs text-muted-foreground">{description}</p>}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function ChartBox({ children, height = 280 }) {
  return <div className="w-full min-w-0" style={{ height }}>{children}</div>;
}

function EmptyChart({ text }) {
  return <div className="flex h-full items-center justify-center rounded-xl border border-dashed text-sm text-muted-foreground">{text}</div>;
}

function ScoreBadge({ score }) {
  const value = Number(score || 0);
  return (
    <div className="flex items-center gap-2 whitespace-nowrap">
      <span className="font-extrabold">{fmtNum(value)}</span>
      <span className="rounded-full bg-secondary px-2 py-1 text-xs">{scoreLabel(value)}</span>
    </div>
  );
}

export default function InteligenciaPlataforma() {
  const location = useLocation();
  const navigate = useNavigate();
  const [days, setDays] = useState("90");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [scoreBand, setScoreBand] = useState("all");
  const [sortBy, setSortBy] = useState("sales");
  const [sortDir, setSortDir] = useState("desc");
  const tab = moduleByPath(location.pathname);

  const load = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/platform/intelligence?days=${Number(days)}`);
      setData(response.data);
      if (selected) {
        const updated = (response.data.businesses || []).find((item) => item.id === selected.id);
        setSelected(updated || null);
      }
    } catch (error) {
      toast.error(apiError(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [days]);

  const businesses = useMemo(() => data?.businesses || [], [data]);
  const suppliers = useMemo(() => data?.suppliers || [], [data]);
  const summary = data?.summary || {};

  const filteredBusinesses = useMemo(() => {
    const query = search.trim().toLowerCase();
    const rows = businesses.filter((business) => {
      const text = `${business.name || ""} ${business.owner_name || ""} ${business.owner_email || ""}`.toLowerCase();
      const matchesSearch = !query || text.includes(query);
      const matchesStatus = status === "all" || (status === "active" ? business.active : !business.active);
      const matchesBand = scoreBand === "all" || scoreLabel(business.score).toLowerCase() === scoreBand;
      return matchesSearch && matchesStatus && matchesBand;
    });

    rows.sort((a, b) => {
      if (sortBy === "name") {
        const result = String(a.name || "").localeCompare(String(b.name || ""), "es");
        return sortDir === "asc" ? result : -result;
      }
      const result = Number(a[sortBy] || 0) - Number(b[sortBy] || 0);
      return sortDir === "asc" ? result : -result;
    });
    return rows;
  }, [businesses, search, status, scoreBand, sortBy, sortDir]);

  const topBusinesses = useMemo(
    () => businesses.slice().sort((a, b) => Number(b.sales || 0) - Number(a.sales || 0)).slice(0, 8),
    [businesses]
  );

  const topSuppliers = useMemo(
    () => suppliers.slice().sort((a, b) => Number(b.purchase_amount || 0) - Number(a.purchase_amount || 0)).slice(0, 8),
    [suppliers]
  );

  const scoreBands = useMemo(() => [
    { name: "Excelente", value: businesses.filter((b) => b.score >= 800).length },
    { name: "Bueno", value: businesses.filter((b) => b.score >= 700 && b.score < 800).length },
    { name: "Moderado", value: businesses.filter((b) => b.score >= 600 && b.score < 700).length },
    { name: "Elevado", value: businesses.filter((b) => b.score >= 500 && b.score < 600).length },
    { name: "Alto", value: businesses.filter((b) => b.score < 500).length }
  ].filter((item) => item.value > 0), [businesses]);

  const quality = useMemo(() => businesses.reduce((result, business) => ({
    costs: result.costs + Number(business.data_quality?.missing_sale_costs || 0),
    dates: result.dates + Number(business.data_quality?.missing_date_records || 0),
    products: result.products + Number(business.data_quality?.missing_inventory_cost_products || 0)
  }), { costs: 0, dates: 0, products: 0 }), [businesses]);

  const selectBusiness = (business) => {
    setSelected(business);
    setTimeout(() => {
      document.getElementById("business-detail")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  };

  const go = (module) => navigate(module === "resumen" ? "/inteligencia" : `/inteligencia/${module}`);
  const clearFilters = () => {
    setSearch("");
    setStatus("all");
    setScoreBand("all");
    setSortBy("sales");
    setSortDir("desc");
  };

  if (!data) return <div className="p-8 text-sm text-muted-foreground">Cargando inteligencia de negocios…</div>;

  const tooltip = {
    contentStyle: {
      borderRadius: 12,
      border: "1px solid hsl(var(--border))",
      background: "hsl(var(--card))"
    }
  };

  return (
    <div className="space-y-6" data-testid="platform-intelligence-page">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-7 w-7 shrink-0 text-primary" />
            <h1 className="font-heading text-3xl font-extrabold tracking-tight">Inteligencia</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">El centro analítico de PLATIA para entender negocios, proveedores, riesgo y datos.</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Select value={days} onValueChange={setDays}>
            <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
            <SelectContent>{[30, 60, 90, 180, 365].map((value) => <SelectItem key={value} value={String(value)}>{value} días</SelectItem>)}</SelectContent>
          </Select>
          <Button variant="outline" onClick={load} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />Actualizar
          </Button>
        </div>
      </div>

      <div className="flex w-full gap-1 overflow-x-auto rounded-xl bg-secondary/70 p-1">
        {["resumen", "negocios", "proveedores", "benchmarks", "financiera", "data"].map((module) => {
          const labels = { resumen: "Resumen", negocios: "Negocios", proveedores: "Proveedores", benchmarks: "Benchmarks", financiera: "Financial Intelligence", data: "Data / Analytics" };
          return <button key={module} onClick={() => go(module)} className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm transition ${tab === module ? "bg-background font-semibold shadow-sm" : "text-muted-foreground hover:text-foreground"}`}>{labels[module]}</button>;
        })}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Negocios" value={fmtNum(summary.businesses)} icon={Building2} sub={`${fmtNum(summary.active_businesses)} activos`} />
        <Metric label="Ventas" value={money(summary.sales)} icon={CircleDollarSign} sub={`${fmtNum(summary.sales_count || 0)} operaciones`} />
        <Metric label="Utilidad operativa" value={money(summary.operating_profit)} icon={Number(summary.operating_profit || 0) < 0 ? TrendingDown : TrendingUp} sub={`${summary.operating_margin || 0}% margen`} />
        <Metric label="PLATIA Score promedio" value={fmtNum(summary.average_score)} icon={BarChart3} sub={`${fmtNum(summary.scored_businesses)} negocios evaluados`} />
      </div>

      {tab === "resumen" && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-5">
          <Section title="Ventas por negocio" description={`Top ${topBusinesses.length} por ventas · últimos ${days} días`} className="xl:col-span-3">
            {topBusinesses.length ? <ChartBox><ResponsiveContainer width="100%" height="100%"><BarChart data={topBusinesses} margin={{ top: 8, right: 8, left: 0, bottom: 35 }}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" angle={-25} textAnchor="end" height={65} interval={0} tick={{ fontSize: 11 }} /><YAxis tickFormatter={(value) => `$${Number(value || 0).toLocaleString("es-VE", { notation: "compact" })}`} tick={{ fontSize: 11 }} /><Tooltip {...tooltip} formatter={(value) => [money(value), "Ventas"]} /><Bar dataKey="sales" name="Ventas" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></ChartBox> : <EmptyChart text="No hay ventas suficientes para graficar." />}
          </Section>
          <Section title="Distribución del Score" description="Distribución del portafolio por nivel" className="xl:col-span-2">
            {scoreBands.length ? <ChartBox><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={scoreBands} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={65} outerRadius={100} paddingAngle={3} label={({ name, value }) => `${name}: ${value}`}><Cell /><Cell /><Cell /><Cell /><Cell /></Pie><Tooltip {...tooltip} /></PieChart></ResponsiveContainer></ChartBox> : <EmptyChart text="No hay scores disponibles." />}
          </Section>
          <Section title="Lectura rápida" description="Principales magnitudes del período" className="xl:col-span-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"><Metric label="Compras" value={money(summary.purchases)} icon={Truck} /><Metric label="Gastos operativos" value={money(summary.operating_expenses)} icon={Wallet} /><Metric label="Inventario" value={money(summary.inventory)} icon={Boxes} /><Metric label="Proveedores" value={fmtNum(summary.suppliers)} icon={Truck} /></div>
          </Section>
        </div>
      )}

      {tab === "negocios" && (
        <div className="space-y-5">
          <Section title="Portafolio de negocios" description="Busca, filtra y ordena. Haz clic en un comercio o en la flecha para abrir su ficha completa.">
            <div className="mb-4 grid grid-cols-1 gap-3 lg:grid-cols-4">
              <div className="relative lg:col-span-2">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar negocio, propietario o correo…" className="h-10 w-full rounded-lg border bg-background pl-9 pr-9 text-sm outline-none focus:ring-2 focus:ring-primary/30" />
                {search && <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2"><X className="h-4 w-4 text-muted-foreground" /></button>}
              </div>
              <Select value={status} onValueChange={setStatus}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Todos los estados</SelectItem><SelectItem value="active">Activos</SelectItem><SelectItem value="inactive">Inactivos</SelectItem></SelectContent></Select>
              <Select value={scoreBand} onValueChange={setScoreBand}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Todos los scores</SelectItem><SelectItem value="excelente">Excelente</SelectItem><SelectItem value="bueno">Bueno</SelectItem><SelectItem value="moderado">Moderado</SelectItem><SelectItem value="elevado">Elevado</SelectItem><SelectItem value="alto">Alto</SelectItem></SelectContent></Select>
            </div>
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">Ordenar por</span>
              <Select value={sortBy} onValueChange={setSortBy}><SelectTrigger className="w-40"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="sales">Ventas</SelectItem><SelectItem value="score">Score</SelectItem><SelectItem value="operating_profit">Utilidad</SelectItem><SelectItem value="operating_margin">Margen</SelectItem><SelectItem value="purchase_amount">Compras</SelectItem><SelectItem value="inventory_value">Inventario</SelectItem><SelectItem value="cash_balance">Caja</SelectItem><SelectItem value="name">Nombre</SelectItem></SelectContent></Select>
              <Button variant="outline" size="sm" onClick={() => setSortDir((value) => value === "desc" ? "asc" : "desc")}>{sortDir === "desc" ? "Mayor → menor" : "Menor → mayor"}</Button>
              <Button variant="ghost" size="sm" onClick={clearFilters}>Limpiar filtros</Button>
              <span className="ml-auto text-xs text-muted-foreground">{filteredBusinesses.length} de {businesses.length} negocios</span>
            </div>
            <div className="overflow-x-auto -mx-1">
              <table className="w-full min-w-[1000px] text-sm">
                <thead><tr className="bg-secondary/50 text-left text-[11px] uppercase tracking-wide text-muted-foreground"><th className="px-4 py-3">Negocio</th><th>Score</th><th>Ventas</th><th>Utilidad</th><th>Margen</th><th>Compras</th><th>Inventario</th><th>Caja</th><th className="pr-4 text-right">Ficha</th></tr></thead>
                <tbody className="divide-y">
                  {filteredBusinesses.map((business) => (
                    <tr key={business.id} className={`cursor-pointer hover:bg-secondary/40 ${selected?.id === business.id ? "bg-secondary/30" : ""}`} onClick={() => selectBusiness(business)}>
                      <td className="px-4 py-3"><b>{business.name}</b><div className="text-xs text-muted-foreground">{business.owner_email} · {business.active ? "Activo" : "Inactivo"}</div></td>
                      <td><ScoreBadge score={business.score} /></td>
                      <td>{money(business.sales)}</td>
                      <td className={Number(business.operating_profit) < 0 ? "font-semibold text-red-600" : "font-semibold"}>{money(business.operating_profit)}</td>
                      <td>{business.operating_margin}%</td><td>{money(business.purchase_amount)}</td><td>{money(business.inventory_value)}</td><td>{money(business.cash_balance)}</td>
                      <td className="pr-4 text-right"><button aria-label={`Abrir ficha de ${business.name}`} onClick={(event) => { event.stopPropagation(); selectBusiness(business); }} className="rounded-lg p-2 hover:bg-secondary"><ChevronRight className="h-5 w-5 text-muted-foreground" /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!filteredBusinesses.length && <div className="py-10 text-center text-sm text-muted-foreground">No hay negocios que coincidan con los filtros.</div>}
          </Section>

          {selected && (
            <Section title={selected.name} description={`Ficha completa · propietario: ${selected.owner_name || "—"}`} className="scroll-mt-6" id="business-detail">
              <div id="business-detail" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Metric label="Ventas" value={money(selected.sales)} icon={ShoppingCart} sub={`${fmtNum(selected.sales_count)} operaciones`} />
                <Metric label="Ticket promedio" value={money(selected.average_ticket)} icon={CircleDollarSign} />
                <Metric label="Utilidad bruta" value={money(selected.gross_profit)} icon={TrendingUp} sub={`${selected.gross_margin}% margen`} />
                <Metric label="Utilidad operativa" value={money(selected.operating_profit)} icon={Number(selected.operating_profit) < 0 ? TrendingDown : TrendingUp} sub={`${selected.operating_margin}% margen`} />
                <Metric label="Compras" value={money(selected.purchase_amount)} icon={Truck} sub={`${fmtNum(selected.purchases_count)} compras`} />
                <Metric label="Inventario" value={money(selected.inventory_value)} icon={Boxes} />
                <Metric label="Capital de trabajo" value={money(selected.working_capital)} icon={TrendingUp} />
                <Metric label="Flujo de caja" value={money(selected.cash_flow)} icon={Number(selected.cash_flow) < 0 ? TrendingDown : TrendingUp} />
                <Metric label="Cuentas por cobrar" value={money(selected.receivables)} icon={CircleDollarSign} />
                <Metric label="Cuentas por pagar" value={money(selected.payables)} icon={Wallet} />
                <Metric label="Productos" value={fmtNum(selected.products_count)} icon={Package} />
                <Metric label="Usuarios" value={fmtNum(selected.users_count)} icon={Building2} />
              </div>
              <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
                <div className="rounded-xl border p-4">
                  <h3 className="mb-4 font-bold">PLATIA Score</h3>
                  <div className="mb-5 flex items-end gap-2"><span className="text-5xl font-extrabold">{fmtNum(selected.score)}</span><span className="mb-2 text-sm text-muted-foreground">/1000 · {scoreLabel(selected.score)}</span></div>
                  {(selected.score_components || []).map((component) => <div key={component.name} className="mb-4"><div className="mb-1 flex justify-between text-sm"><span>{component.name}</span><b>{component.score}</b></div><div className="h-2 overflow-hidden rounded-full bg-secondary"><div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(0, Math.min(100, Number(component.score || 0) / 10))}%` }} /></div><p className="mt-1 text-xs text-muted-foreground">Peso {component.weight}%</p></div>)}
                </div>
                <div className="rounded-xl border p-4">
                  <h3 className="mb-3 flex items-center gap-2 font-bold"><AlertTriangle className="h-4 w-4" />Alertas y acciones</h3>
                  {(selected.score_alerts || []).length ? <ul className="mb-5 space-y-2 text-sm">{selected.score_alerts.map((item) => <li key={item} className="rounded-lg bg-secondary/60 p-3">{item}</li>)}</ul> : <p className="mb-5 text-sm text-muted-foreground">Sin alertas de riesgo.</p>}
                  <h4 className="mb-2 text-sm font-semibold">Acciones sugeridas</h4>
                  {(selected.score_actions || []).length ? <ul className="space-y-2 text-sm">{selected.score_actions.map((item) => <li key={item} className="rounded-lg border p-3">{item}</li>)}</ul> : <p className="text-sm text-muted-foreground">No hay acciones específicas.</p>}
                </div>
              </div>
              <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3"><div className="rounded-xl border p-4"><p className="text-xs text-muted-foreground">Calidad de datos</p><p className="mt-1 font-bold">{fmtNum(Number(selected.data_quality?.missing_sale_costs || 0) + Number(selected.data_quality?.missing_date_records || 0) + Number(selected.data_quality?.missing_inventory_cost_products || 0))} incidencias</p></div><div className="rounded-xl border p-4"><p className="text-xs text-muted-foreground">Período analizado</p><p className="mt-1 font-bold">Últimos {days} días</p></div><div className="rounded-xl border p-4"><p className="text-xs text-muted-foreground">Estado</p><p className="mt-1 font-bold">{selected.active ? "Activo" : "Inactivo"}</p></div></div>
            </Section>
          )}
        </div>
      )}

      {tab === "proveedores" && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Proveedores" value={fmtNum(summary.suppliers)} icon={Truck} /><Metric label="Compras" value={money(summary.purchases)} icon={ShoppingCart} /><Metric label="Proveedor principal" value={topSuppliers[0]?.name || "—"} icon={Truck} sub={topSuppliers[0] ? money(topSuppliers[0].purchase_amount) : "Sin datos"} /><Metric label="Dependencia máxima" value={topSuppliers[0] ? `${topSuppliers[0].purchase_share_pct}%` : "—"} icon={BarChart3} sub="participación en compras" /></div>
          <Section title="Concentración de proveedores" description={`Principales proveedores por monto · últimos ${days} días`}>{topSuppliers.length ? <ChartBox><ResponsiveContainer width="100%" height="100%"><BarChart data={topSuppliers} layout="vertical" margin={{ top: 5, right: 20, left: 100, bottom: 5 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" tickFormatter={(value) => `$${Number(value || 0).toLocaleString("es-VE", { notation: "compact" })}`} /><YAxis type="category" dataKey="name" width={95} tick={{ fontSize: 11 }} /><Tooltip {...tooltip} formatter={(value) => [money(value), "Compras"]} /><Bar dataKey="purchase_amount" name="Compras" radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer></ChartBox> : <EmptyChart text="Aún no hay compras con proveedor registradas." />}</Section>
          <Section title="Detalle de proveedores"><div className="overflow-x-auto"><table className="w-full min-w-[850px] text-sm"><thead><tr className="bg-secondary/50 text-left text-[11px] uppercase tracking-wide text-muted-foreground"><th className="px-4 py-3">Proveedor</th><th>Negocio</th><th>Compras</th><th>Monto</th><th>% compras</th><th>Actividad</th><th>Última compra</th></tr></thead><tbody className="divide-y">{suppliers.map((item) => <tr key={`${item.business_id}-${item.supplier_id}`}><td className="px-4 py-3"><b>{item.name}</b>{item.rif && <div className="text-xs text-muted-foreground">{item.rif}</div>}</td><td>{item.business_name}</td><td>{fmtNum(item.purchases)}</td><td className="font-semibold">{money(item.purchase_amount)}</td><td>{item.purchase_share_pct}%</td><td><span className="rounded-full bg-secondary px-2 py-1 text-xs">{item.activity_score}/100</span></td><td>{item.last_purchase ? fmtDate(item.last_purchase) : "—"}</td></tr>)}</tbody></table></div>{!suppliers.length && <div className="py-8 text-center text-sm text-muted-foreground">Aún no hay compras con proveedor registradas.</div>}</Section>
        </div>
      )}

      {tab === "benchmarks" && (
        <div className="space-y-5">
          <Section title="Benchmark interno" description="Compara el portafolio usando los negocios disponibles.">
            <div className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Score promedio" value={fmtNum(summary.average_score)} icon={BarChart3} /><Metric label="Margen operativo" value={`${summary.operating_margin || 0}%`} icon={TrendingUp} /><Metric label="Ventas totales" value={money(summary.sales)} icon={CircleDollarSign} /><Metric label="Inventario" value={money(summary.inventory)} icon={Boxes} /></div>
            {topBusinesses.length ? <ChartBox height={330}><ResponsiveContainer width="100%" height="100%"><BarChart data={topBusinesses} margin={{ top: 10, right: 10, left: 0, bottom: 35 }}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" angle={-25} textAnchor="end" height={70} interval={0} tick={{ fontSize: 11 }} /><YAxis domain={[0, 1000]} /><Tooltip {...tooltip} formatter={(value) => [fmtNum(value), "Score"]} /><Bar dataKey="score" name="Score" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></ChartBox> : <EmptyChart text="No hay negocios evaluados." />}
          </Section>
          <Section title="Ranking del portafolio" description="Ordenado por PLATIA Score."><div className="grid grid-cols-1 gap-x-8 md:grid-cols-2">{businesses.slice().sort((a, b) => Number(b.score || 0) - Number(a.score || 0)).map((business, index) => <button key={business.id} onClick={() => selectBusiness(business)} className="flex items-center gap-3 rounded-lg border-b px-2 py-3 text-left hover:bg-secondary/30"><span className="w-7 text-center text-sm font-bold text-muted-foreground">{index + 1}</span><div className="min-w-0 flex-1"><p className="truncate font-semibold">{business.name}</p><p className="text-xs text-muted-foreground">Margen {business.operating_margin}% · Ventas {money(business.sales)}</p></div><ScoreBadge score={business.score} /></button>)}</div></Section>
        </div>
      )}

      {tab === "financiera" && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Ventas" value={money(summary.sales)} icon={CircleDollarSign} /><Metric label="Utilidad bruta" value={money(summary.gross_profit)} icon={TrendingUp} /><Metric label="Utilidad operativa" value={money(summary.operating_profit)} icon={Number(summary.operating_profit) < 0 ? TrendingDown : TrendingUp} /><Metric label="Margen operativo" value={`${summary.operating_margin || 0}%`} icon={BarChart3} /></div>
          <Section title="Estructura financiera del portafolio" description="Ventas, compras y gastos durante el período."><ChartBox height={330}><ResponsiveContainer width="100%" height="100%"><BarChart data={[{ name: "Portafolio", ventas: Number(summary.sales || 0), compras: Number(summary.purchases || 0), gastos: Number(summary.operating_expenses || 0) }]}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" /><YAxis tickFormatter={(value) => `$${Number(value || 0).toLocaleString("es-VE", { notation: "compact" })}`} /><Tooltip {...tooltip} formatter={(value, name) => [money(value), name]} /><Bar dataKey="ventas" name="Ventas" radius={[6, 6, 0, 0]} /><Bar dataKey="compras" name="Compras" radius={[6, 6, 0, 0]} /><Bar dataKey="gastos" name="Gastos" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></ChartBox></Section>
          <Section title="Salud por negocio" description="Selecciona un comercio para abrir su ficha."><div className="space-y-2">{businesses.slice().sort((a, b) => Number(b.operating_margin || 0) - Number(a.operating_margin || 0)).map((business) => <button key={business.id} onClick={() => selectBusiness(business)} className="grid w-full grid-cols-[minmax(0,1fr)_100px_90px] items-center gap-3 rounded-lg p-2 text-left hover:bg-secondary/30"><div className="min-w-0"><p className="truncate font-semibold">{business.name}</p><div className="mt-2 h-2 overflow-hidden rounded-full bg-secondary"><div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(0, Math.min(100, Number(business.operating_margin || 0) + 50))}%` }} /></div></div><span className={`text-right text-sm ${Number(business.operating_margin) < 0 ? "font-semibold text-red-600" : ""}`}>{business.operating_margin}%</span><ScoreBadge score={business.score} /></button>)}</div></Section>
        </div>
      )}

      {tab === "data" && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Negocios analizados" value={fmtNum(businesses.length)} icon={Database} /><Metric label="Costos de venta faltantes" value={fmtNum(quality.costs)} icon={AlertTriangle} /><Metric label="Registros sin fecha" value={fmtNum(quality.dates)} icon={Activity} /><Metric label="Productos sin costo" value={fmtNum(quality.products)} icon={Package} /></div>
          <Section title="Calidad de datos" description="Indicadores que afectan la confiabilidad de la inteligencia."><div className="grid grid-cols-1 gap-4 md:grid-cols-3">{[["Costos de venta faltantes", quality.costs, "Sin costo asociado a ventas"], ["Registros sin fecha", quality.dates, "Movimientos que no pueden ubicarse en el período"], ["Productos sin costo", quality.products, "Inventario sin costo utilizable"]].map(([label, value, description]) => <div key={label} className="rounded-xl border p-4"><div className="flex items-center justify-between gap-3"><span className="text-sm font-semibold">{label}</span><span className={`text-2xl font-extrabold ${Number(value) > 0 ? "text-amber-600" : ""}`}>{fmtNum(value)}</span></div><p className="mt-2 text-xs text-muted-foreground">{description}</p></div>)}</div></Section>
          <Section title="Cobertura del portafolio" description="Cantidad de negocios con información suficiente para cada lectura."><div className="space-y-4">{[["Con PLATIA Score", businesses.filter((b) => b.score != null).length], ["Con ventas", businesses.filter((b) => Number(b.sales_count || 0) > 0).length], ["Con inventario", businesses.filter((b) => Number(b.inventory_value || 0) > 0).length], ["Con compras", businesses.filter((b) => Number(b.purchases_count || 0) > 0).length]].map(([label, value]) => <div key={label}><div className="mb-1 flex justify-between text-sm"><span>{label}</span><b>{fmtNum(value)} / {fmtNum(businesses.length)}</b></div><div className="h-2 overflow-hidden rounded-full bg-secondary"><div className="h-full rounded-full bg-primary" style={{ width: `${businesses.length ? (value / businesses.length) * 100 : 0}%` }} /></div></div>)}</div></Section>
        </div>
      )}
    </div>
  );
}
