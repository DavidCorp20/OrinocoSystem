import InfoHelp from "./InfoHelp";

const KPI_HELP = {
  "Ventas de hoy": {
    description: "Es el dinero total de las ventas registradas desde el inicio de hoy. Sirve para saber cuánto vendió el negocio en la jornada.",
    formula: "Σ total de cada venta del día",
    example: "Si hiciste 3 ventas de $20, $35 y $45 → ventas de hoy = $100.",
  },
  "Ventas (30 días)": {
    description: "Es la suma de todas las ventas registradas durante los últimos 30 días. Es una medida de volumen de ventas, no de ganancia.",
    formula: "Σ total de ventas de los últimos 30 días",
    example: "Si vendiste $1.000, $2.000 y $2.500 → ventas del período = $5.500.",
  },
  "Ganancia estimada": {
    description: "Muestra una estimación de lo que queda después de descontar el costo de los productos vendidos y los gastos operativos registrados en los últimos 30 días.",
    formula: "Utilidad de las ventas − gastos operativos",
    example: "Ventas $10.000 − costo de productos $6.000 − gastos $1.500 → ganancia estimada = $2.500.",
  },
  "Margen": {
    description: "Indica qué porcentaje de cada venta queda después del costo del producto, antes de descontar los gastos operativos. Te ayuda a saber si tus precios dejan suficiente espacio para cubrir gastos y generar ganancia.",
    formula: "Utilidad de productos vendidos ÷ ventas × 100",
    example: "Si vendes $10.000 y la utilidad antes de gastos es $3.000 → margen = 30%. Por cada $100 vendidos, $30 quedan antes de gastos.",
  },
};

export default function StatCard({ title, value, hint, icon: Icon, badge, testid, bs, delay = 0 }) {
  const help = KPI_HELP[title];
  return (
    <div
      data-testid={testid}
      className="bg-card border border-border rounded-2xl p-5 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 animate-rise"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>
          {help && (
            <InfoHelp title={title}>
              {help.description}
              <span className="block mt-2 rounded-lg bg-secondary/70 p-2">
                <b>Fórmula:</b> {help.formula}
              </span>
              <span className="block mt-1.5"><b>Ejemplo:</b> {help.example}</span>
            </InfoHelp>
          )}
        </div>
        {Icon && (
          <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
            <Icon className="w-4.5 h-4.5 w-5 h-5 text-primary" />
          </div>
        )}
      </div>
      <div className="mt-2 flex items-end gap-2 flex-wrap">
        <span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 font-num">{value}</span>
        {badge}
      </div>
      {bs && <p className="mt-1 text-xs text-muted-foreground font-num" data-testid={`${testid}-bs`}>≈ {bs}</p>}
      {hint && <p className="mt-2 text-xs text-muted-foreground leading-snug">{hint}</p>}
    </div>
  );
}
