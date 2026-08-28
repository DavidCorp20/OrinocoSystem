export default function StatCard({ title, value, hint, icon: Icon, badge, testid, bs, delay = 0 }) {
  return (
    <div
      data-testid={testid}
      className="bg-card border border-border rounded-2xl p-5 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 animate-rise"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>
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
