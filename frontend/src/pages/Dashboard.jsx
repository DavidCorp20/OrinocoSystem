import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import {
  ShoppingCart, Wallet, PiggyBank, Percent, AlertTriangle, PackageX,
  Lightbulb, TrendingDown, TrendingUp, Info, CheckCircle2, Package, Zap,
} from "lucide-react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { fmtBs, fmtMoney, fmtNum, fmtPct, fmtDateTime } from "../lib/format";
import StatCard from "../components/StatCard";
import QuickSale from "../components/QuickSale";

const SEMAFORO_STYLES = {
  verde: { dot: "🟢", cls: "bg-emerald-50 border-emerald-300", text: "text-emerald-800" },
  amarillo: { dot: "🟡", cls: "bg-amber-50 border-amber-300", text: "text-amber-800" },
  rojo: { dot: "🔴", cls: "bg-rose-50 border-rose-300", text: "text-rose-800" },
};

const RECO_ICONS = {
  urgente: { icon: PackageX, cls: "text-rose-600 bg-rose-100" },
  atencion: { icon: AlertTriangle, cls: "text-amber-700 bg-amber-100" },
  positivo: { icon: CheckCircle2, cls: "text-emerald-700 bg-emerald-100" },
  info: { icon: Info, cls: "text-sky-700 bg-sky-100" },
};

export default function Dashboard() {
  const { user, business } = useAuth();
  const currency = business?.currency || "USD";
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [quickOpen, setQuickOpen] = useState(false);
  const [rateInfo, setRateInfo] = useState(null);

  const load = useCallback(() => {
    api.get("/dashboard").then((r) => setData(r.data)).catch(() => setError("No pudimos cargar tu panel."));
  }, []);

  useEffect(() => {
    load();
    api.get("/rates/current").then((r) => setRateInfo(r.data)).catch(() => {});
  }, [load]);

  if (error) return <p className="text-sm text-rose-600" data-testid="dashboard-error">{error}</p>;
  if (!data) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="dashboard-loading">
        {[...Array(8)].map((_, i) => <div key={i} className="h-32 bg-card border border-border rounded-2xl animate-pulse" />)}
      </div>
    );
  }

  const sem = SEMAFORO_STYLES[data.semaforo.nivel] || SEMAFORO_STYLES.verde;
  const firstName = (user?.name || "").split(" ")[0];

  return (
    <div className="space-y-5" data-testid="dashboard-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900">
            Hola, {firstName}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Así va {business?.name} hoy.{rateInfo?.rate ? ` Tasa del día: Bs ${fmtNum(rateInfo.rate)} por $1.` : ""}
          </p>
        </div>
        <button
          data-testid="dashboard-quick-sale-btn"
          onClick={() => setQuickOpen(true)}
          className="flex items-center gap-3 bg-primary text-white rounded-2xl px-6 py-3.5 shadow-lg shadow-primary/25 hover:shadow-xl hover:-translate-y-0.5 transition-all"
        >
          <span className="w-10 h-10 rounded-xl bg-white/15 flex items-center justify-center">
            <Zap className="w-5 h-5" />
          </span>
          <span className="text-left">
            <span className="block font-heading font-extrabold text-lg leading-tight">Venta rápida</span>
            <span className="block text-xs text-white/70">Escanea o busca y cobra en segundos</span>
          </span>
        </button>
      </div>

      <div
        data-testid="semaforo-status-card"
        className={`border-2 rounded-2xl p-5 flex items-center gap-4 animate-rise ${sem.cls}`}
      >
        <span className="text-4xl">{sem.dot}</span>
        <div>
          <p className={`font-heading font-extrabold text-lg ${sem.text}`}>{data.semaforo.titulo}</p>
          <p className="text-sm text-slate-600">{data.semaforo.mensaje}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard testid="kpi-ventas-hoy" title="Ventas de hoy" value={fmtMoney(data.ventas_hoy, currency)} icon={ShoppingCart}
          bs={rateInfo?.rate ? fmtBs(data.ventas_hoy * rateInfo.rate) : undefined}
          hint={`${fmtNum(data.num_ventas_hoy)} venta(s) registradas hoy`} delay={0} />
        <StatCard testid="kpi-ventas-mes" title="Ventas (30 días)" value={fmtMoney(data.ventas_30, currency)} icon={Wallet} delay={60}
          bs={rateInfo?.rate ? fmtBs(data.ventas_30 * rateInfo.rate) : undefined}
          badge={
            data.variacion !== null && (
              <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full ${data.variacion >= 0 ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"}`}
                data-testid="kpi-variacion-badge">
                {data.variacion >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {data.variacion >= 0 ? "+" : ""}{fmtNum(data.variacion)}%
              </span>
            )
          }
          hint={`${fmtNum(data.num_ventas_30)} ventas en el período · comparado con los 30 días anteriores`} />
        <StatCard testid="kpi-ganancia" title="Ganancia estimada" value={fmtMoney(data.ganancia_estimada, currency)} icon={PiggyBank} delay={120}
          bs={rateInfo?.rate ? fmtBs(data.ganancia_estimada * rateInfo.rate) : undefined}
          hint="Lo que vendiste, menos el costo de los productos y tus gastos" />
        <StatCard testid="kpi-margen" title="Margen" value={fmtPct(data.margen)} icon={Percent} delay={180}
          hint={`Por cada $100 que vendes, unos $${fmtNum(data.margen)} quedan como margen antes de gastos`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-card border border-border rounded-2xl p-5 animate-rise" style={{ animationDelay: "220ms" }} data-testid="sales-trend-card">
          <h3 className="font-heading font-bold text-slate-800 mb-1">Tus ventas, últimos 14 días</h3>
          <p className="text-xs text-muted-foreground mb-4">Ticket promedio: {fmtMoney(data.ticket_promedio, currency)}</p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.trend} margin={{ top: 5, right: 8, left: -14, bottom: 0 }}>
                <defs>
                  <linearGradient id="ventas" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#0D5C3A" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#0D5C3A" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="fecha" tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
                <Tooltip formatter={(v) => [fmtMoney(v, currency), "Ventas"]} />
                <Area type="monotone" dataKey="ventas" stroke="#0D5C3A" strokeWidth={2.5} fill="url(#ventas)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-card border border-border rounded-2xl p-5 animate-rise" style={{ animationDelay: "280ms" }} data-testid="recommendations-card">
          <div className="flex items-center gap-2 mb-4">
            <Lightbulb className="w-5 h-5 text-accent" />
            <h3 className="font-heading font-bold text-slate-800">Qué hacer ahora</h3>
          </div>
          {data.recomendaciones.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sin pendientes. Tu negocio va bien.</p>
          ) : (
            <ul className="space-y-3">
              {data.recomendaciones.map((r, i) => {
                const R = RECO_ICONS[r.level] || RECO_ICONS.info;
                return (
                  <li key={i} data-testid={`recommendation-${i}`} className="flex items-start gap-3">
                    <span className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${R.cls}`}>
                      <R.icon className="w-3.5 h-3.5" />
                    </span>
                    <p className="text-sm text-slate-700 leading-snug">{r.text}</p>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-card border border-border rounded-2xl p-5 animate-rise" style={{ animationDelay: "340ms" }} data-testid="low-stock-card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-heading font-bold text-slate-800">Alertas de stock</h3>
            <Link to="/productos" data-testid="low-stock-view-all" className="text-xs font-semibold text-primary hover:underline">Ver productos</Link>
          </div>
          {data.agotados.length === 0 && data.bajos.length === 0 ? (
            <p className="text-sm text-muted-foreground">Todo tu stock está en niveles saludables.</p>
          ) : (
            <ul className="divide-y divide-border">
              {[...data.agotados, ...data.bajos].map((p) => (
                <li key={p.id} className="py-2.5 flex items-center gap-3" data-testid={`low-stock-item-${p.id}`}>
                  <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${p.stock <= 0 ? "bg-rose-500" : "bg-amber-400"}`} />
                  <span className="flex-1 text-sm font-medium text-slate-800 truncate">{p.nombre}</span>
                  <span className="text-xs font-num text-muted-foreground">{fmtNum(p.stock)} / mín {fmtNum(p.min_stock)}</span>
                  <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${p.stock <= 0 ? "bg-rose-100 text-rose-800" : "bg-amber-100 text-amber-800"}`}>
                    {p.stock <= 0 ? "Agotado" : "Bajo"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="bg-card border border-border rounded-2xl p-5 animate-rise" style={{ animationDelay: "400ms" }} data-testid="top-products-card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-heading font-bold text-slate-800">Tus productos estrella (30 días)</h3>
            <Link to="/ventas" data-testid="top-products-view-sales" className="text-xs font-semibold text-primary hover:underline">Ver ventas</Link>
          </div>
          {data.top_vendidos.length === 0 ? (
            <div className="text-sm text-muted-foreground flex items-center gap-2">
              <Package className="w-4 h-4" /> Aún no hay ventas registradas en el período.
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {data.top_vendidos.map((t, i) => (
                <li key={t.nombre} className="py-2.5 flex items-center gap-3" data-testid={`top-product-${i}`}>
                  <span className="w-7 h-7 rounded-lg bg-primary/10 text-primary text-xs font-extrabold flex items-center justify-center shrink-0">{i + 1}</span>
                  <span className="flex-1 text-sm font-medium text-slate-800 truncate">{t.nombre}</span>
                  <span className="text-xs text-muted-foreground font-num">{fmtNum(t.unidades)} uds</span>
                  <span className="text-sm font-bold font-num text-slate-900">{fmtMoney(t.ganancia, currency)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="bg-card border border-border rounded-2xl p-5 animate-rise" style={{ animationDelay: "460ms" }} data-testid="recent-sales-card">
        <h3 className="font-heading font-bold text-slate-800 mb-4">Ventas recientes</h3>
        {data.recent_sales.length === 0 ? (
          <p className="text-sm text-muted-foreground">Cuando registres tu primera venta aparecerá aquí.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground border-b border-border">
                  <th className="pb-2 font-semibold">Fecha</th>
                  <th className="pb-2 font-semibold">Productos</th>
                  <th className="pb-2 font-semibold">Pago</th>
                  <th className="pb-2 font-semibold text-right">Total</th>
                  <th className="pb-2 font-semibold text-right">Ganancia</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.recent_sales.map((s) => (
                  <tr key={s.id} data-testid={`recent-sale-${s.id}`}>
                    <td className="py-2.5 text-muted-foreground whitespace-nowrap">{fmtDateTime(s.created_at)}</td>
                    <td className="py-2.5 text-slate-700 max-w-xs truncate">{s.resumen}</td>
                    <td className="py-2.5"><span className="text-xs bg-secondary px-2 py-0.5 rounded-full capitalize">{s.payment_method}</span></td>
                    <td className="py-2.5 text-right font-num font-semibold">{fmtMoney(s.total, currency)}</td>
                    <td className="py-2.5 text-right font-num text-emerald-700 font-semibold">{fmtMoney(s.profit, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <QuickSale open={quickOpen} onClose={() => { setQuickOpen(false); load(); }} />
    </div>
  );
}
