import InfoHelp from "./InfoHelp";

const KPI_HELP = {
  "Ventas de hoy": { description: "Dinero total de las ventas registradas hoy.", formula: "Σ total de ventas del día", example: "3 ventas de $20, $35 y $45 → $100." },
  "Ventas (30 días)": { description: "Suma de las ventas registradas durante los últimos 30 días. Es volumen de ventas, no ganancia.", formula: "Σ total de ventas del período", example: "$1.000 + $2.000 + $2.500 → $5.500." },
  "Ingresos (30 días)": { description: "Total vendido en los últimos 30 días. No representa la ganancia porque todavía deben considerarse costos y gastos.", formula: "Σ total de ventas de los últimos 30 días", example: "Si vendiste $5.000, tus ingresos son $5.000." },
  "Gastos operativos": { description: "Gastos necesarios para funcionar, como alquiler, servicios, personal, transporte y marketing. Las compras de mercancía se muestran aparte.", formula: "Σ gastos operativos registrados en el período", example: "Alquiler $500 + servicios $150 → $650." },
  "Ganancia estimada": { description: "Resultado aproximado después de restar a la utilidad de las ventas los gastos operativos registrados.", formula: "Utilidad de ventas − gastos operativos", example: "Utilidad $3.000 − gastos $1.000 → $2.000." },
  "Margen": { description: "Porcentaje que queda de las ventas después del costo de los productos, antes de gastos operativos.", formula: "Utilidad bruta ÷ ingresos × 100", example: "Ventas $10.000 y utilidad $3.000 → 30%." },
};

export default function StatCard({ title, value, hint, icon: Icon, badge, testid, bs, delay = 0 }) {
  const help = KPI_HELP[title];
  return (
    <div data-testid={testid} className="bg-card border border-border rounded-2xl p-5 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 animate-rise" style={{ animationDelay: `${delay}ms` }}>
      <div className="flex items-start justify-between gap-2"><div className="flex items-center min-w-0"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>{help&&<InfoHelp title={title}>{help.description}<span className="block mt-2 rounded-lg bg-secondary/70 p-2"><b>Fórmula:</b> {help.formula}</span><span className="block mt-1.5"><b>Ejemplo:</b> {help.example}</span></InfoHelp>}</div>{Icon&&<div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center shrink-0"><Icon className="w-5 h-5 text-primary"/></div>}</div>
      <div className="mt-2 flex items-end gap-2 flex-wrap"><span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 font-num">{value}</span>{badge}</div>
      {bs&&<p className="mt-1 text-xs text-muted-foreground font-num" data-testid={`${testid}-bs`}>≈ {bs}</p>}
      {hint&&<p className="mt-2 text-xs text-muted-foreground leading-snug">{hint}</p>}
    </div>
  );
}
