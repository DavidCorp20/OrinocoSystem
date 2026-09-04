import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Lightbulb, TrendingDown, TrendingUp } from "lucide-react";
import api from "../lib/api";
import { fmtMoney, fmtPct } from "../lib/format";

function tone(level) {
  if (level === "high" || level === "urgent" || level === "warning" || level === "rojo") return "border-rose-200 bg-rose-50 text-rose-900";
  if (level === "medium" || level === "attention" || level === "yellow" || level === "amarillo") return "border-amber-200 bg-amber-50 text-amber-900";
  return "border-emerald-200 bg-emerald-50 text-emerald-900";
}

export default function FinancialInsightsCard({ currency = "USD" }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    api.get("/financial-insights?days=30")
      .then((r) => { if (alive) setData(r.data); })
      .catch(() => { if (alive) setError(true); });
    return () => { alive = false; };
  }, []);

  if (error) return null;
  if (!data) return <div className="h-40 bg-card border border-border rounded-2xl animate-pulse" data-testid="financial-insights-loading" />;

  const summary = data.summary || {};
  const insights = data.insights || [];
  const warnings = data.warnings || [];
  const actions = data.actions || [];

  return (
    <section className="bg-card border border-border rounded-2xl p-5 md:p-6 space-y-5" data-testid="financial-insights-card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-9 h-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center text-lg">🧠</span>
            <h2 className="font-heading text-xl font-extrabold text-slate-900">¿Qué está pasando con tu negocio?</h2>
          </div>
          {summary.headline && <p className="mt-2 text-sm text-slate-600 max-w-3xl">{summary.headline}</p>}
        </div>
        <span className="text-xs font-semibold text-muted-foreground whitespace-nowrap">Últimos 30 días</span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Metric label="Ventas" value={fmtMoney(summary.revenue, currency)} />
        <Metric label="Utilidad bruta" value={fmtMoney(summary.gross_profit, currency)} />
        <Metric label="Margen bruto" value={fmtPct(summary.gross_margin)} />
        <Metric label="Utilidad operativa" value={fmtMoney(summary.operating_profit, currency)} />
      </div>

      {insights.length > 0 && <div className="space-y-2">
        {insights.slice(0, 4).map((item, i) => (
          <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-slate-50 border border-slate-100" data-testid={`financial-insight-${i}`}>
            {item.type === "fact" || item.type === "margin" ? <TrendingUp className="w-4 h-4 mt-0.5 text-emerald-600 shrink-0" /> : <TrendingDown className="w-4 h-4 mt-0.5 text-slate-500 shrink-0" />}
            <div><p className="text-sm font-semibold text-slate-800">{item.title}</p><p className="text-sm text-slate-600 mt-0.5">{item.explanation}</p></div>
          </div>
        ))}
      </div>}

      {warnings.length > 0 && <div className="space-y-2" data-testid="financial-warnings">
        <h3 className="font-heading font-bold text-slate-800 flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-amber-600" /> Atención</h3>
        {warnings.slice(0, 3).map((item, i) => <div key={i} className={`border rounded-xl p-3 text-sm ${tone(item.severity)}`}><p className="font-semibold">{item.title}</p><p className="mt-0.5">{item.explanation}</p></div>)}
      </div>}

      {actions.length > 0 && <div className="space-y-2" data-testid="financial-actions">
        <h3 className="font-heading font-bold text-slate-800 flex items-center gap-2"><Lightbulb className="w-4 h-4 text-accent" /> Qué hacer ahora</h3>
        {actions.slice(0, 3).map((item, i) => <div key={i} className="flex items-start gap-3 text-sm text-slate-700"><CheckCircle2 className="w-4 h-4 mt-0.5 text-emerald-600 shrink-0" /><span>{item}</span></div>)}
      </div>}
    </section>
  );
}

function Metric({ label, value }) {
  return <div className="rounded-xl border border-border bg-background p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 font-num font-extrabold text-slate-900 text-lg truncate">{value}</p></div>;
}
