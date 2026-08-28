import { useCallback, useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { Download, HelpCircle, Plus, Trash2, TrendingUp, Wallet, PiggyBank, Percent, Truck } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadCsv } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { fmtDate, fmtMoney, fmtPct, fmtNum, EXPENSE_CATEGORIES } from "../lib/format";
import StatCard from "../components/StatCard";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Tooltip as InfoTooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../components/ui/tooltip";

const CAT_LABELS = Object.fromEntries(EXPENSE_CATEGORIES.map((c) => [c.value, c.label]));

export default function Finanzas() {
  const { business } = useAuth();
  const currency = business?.currency || "USD";
  const [summary, setSummary] = useState(null);
  const [expenses, setExpenses] = useState(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ category: "otros", description: "", amount: "", date: "" });

  const load = useCallback(() => {
    api.get("/finances/summary").then((r) => setSummary(r.data)).catch((e) => toast.error(apiError(e)));
    api.get("/expenses").then((r) => setExpenses(r.data.expenses)).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post("/expenses", { ...form, amount: Number(form.amount), date: form.date || null });
      toast.success("Gasto registrado");
      setOpen(false);
      setForm({ category: "otros", description: "", amount: "", date: "" });
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (exp) => {
    try {
      await api.delete(`/expenses/${exp.id}`);
      toast.success("Gasto eliminado");
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  return (
    <div className="space-y-5" data-testid="finanzas-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-slate-900">Finanzas</h1>
          <p className="text-sm text-muted-foreground mt-1">Cuánto entra, cuánto sale y cuánto te queda. Sin contabilidad complicada.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" data-testid="export-expenses-csv-btn" onClick={() => downloadCsv("/expenses/export/csv", "gastos.csv")} className="rounded-xl">
            <Download className="w-4 h-4 mr-1.5" /> Exportar CSV
          </Button>
          <Button data-testid="new-expense-btn" onClick={() => setOpen(true)} className="rounded-xl">
            <Plus className="w-4 h-4 mr-1.5" /> Registrar gasto
          </Button>
        </div>
      </div>

      {!summary ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">{[...Array(4)].map((_, i) => <div key={i} className="h-32 bg-card border border-border rounded-2xl animate-pulse" />)}</div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard testid="fin-ingresos" title="Ingresos (30 días)" value={fmtMoney(summary.ingresos_30, currency)} icon={Wallet}
              hint="Todo lo que vendiste en el período" />
            <StatCard testid="fin-gastos" title="Gastos operativos" value={fmtMoney(summary.gastos_operativos_30, currency)} icon={TrendingUp} delay={60}
              hint="Alquiler, servicios, personal y otros gastos del día a día" />
            <StatCard testid="fin-ganancia" title="Ganancia estimada" value={fmtMoney(summary.ganancia_estimada_30, currency)} icon={PiggyBank} delay={120}
              hint="Lo que ganaste por ventas menos tus gastos operativos" />
            <StatCard testid="fin-margen" title="Margen" value={fmtPct(summary.margen)} icon={Percent} delay={180}
              hint={`Por cada $100 que vendes, unos $${fmtNum(summary.margen)} quedan como margen antes de gastos`} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 bg-card border border-border rounded-2xl p-5" data-testid="cashflow-card">
              <h3 className="font-heading font-bold text-slate-800 mb-1">Ingresos vs gastos, últimas 8 semanas</h3>
              <p className="text-xs text-muted-foreground mb-4 flex items-center gap-1">
                Compras de mercancía del período: {fmtMoney(summary.compras_30, currency)}
                <TooltipProvider>
                  <InfoTooltip>
                    <TooltipTrigger asChild><HelpCircle className="w-3.5 h-3.5 cursor-help" /></TooltipTrigger>
                    <TooltipContent className="max-w-xs text-xs">Las compras no son un gasto perdido: se convierten en inventario. El costo se descuenta de tu ganancia cuando vendes el producto.</TooltipContent>
                  </InfoTooltip>
                </TooltipProvider>
              </p>
              <div className="h-60">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={summary.flujo_semanal} margin={{ top: 5, right: 8, left: -14, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="semana" tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
                    <Tooltip formatter={(v, name) => [fmtMoney(v, currency), name === "ingresos" ? "Ingresos" : "Gastos"]} />
                    <Legend formatter={(v) => (v === "ingresos" ? "Ingresos" : "Gastos")} />
                    <Bar dataKey="ingresos" fill="#0D5C3A" radius={[6, 6, 0, 0]} />
                    <Bar dataKey="gastos" fill="#D97706" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-card border border-border rounded-2xl p-5" data-testid="expenses-by-category-card">
              <h3 className="font-heading font-bold text-slate-800 mb-4">¿En qué se va tu dinero?</h3>
              {Object.keys(summary.gastos_por_categoria).length === 0 ? (
                <p className="text-sm text-muted-foreground">Sin gastos registrados en los últimos 30 días.</p>
              ) : (
                <ul className="space-y-3">
                  {Object.entries(summary.gastos_por_categoria).sort((a, b) => b[1] - a[1]).map(([cat, amount]) => {
                    const pct = summary.gastos_operativos_30 ? Math.round((amount / summary.gastos_operativos_30) * 100) : 0;
                    return (
                      <li key={cat} data-testid={`expense-category-${cat}`}>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="font-medium text-slate-700">{CAT_LABELS[cat] || cat}</span>
                          <span className="font-num font-semibold">{fmtMoney(amount, currency)} · {pct}%</span>
                        </div>
                        <div className="h-2 bg-secondary rounded-full overflow-hidden">
                          <div className="h-full bg-accent rounded-full" style={{ width: `${pct}%` }} />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        </>
      )}

      <div className="bg-card border border-border rounded-2xl overflow-hidden" data-testid="expenses-table-card">
        <div className="px-5 py-4 border-b border-border">
          <h3 className="font-heading font-bold text-slate-800">Gastos registrados</h3>
        </div>
        {!expenses ? (
          <div className="p-6 space-y-3">{[...Array(4)].map((_, i) => <div key={i} className="h-10 bg-secondary rounded-xl animate-pulse" />)}</div>
        ) : expenses.length === 0 ? (
          <p className="p-10 text-center text-sm text-muted-foreground">Registra tus gastos (alquiler, servicios, personal…) para conocer tu ganancia real.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="expenses-table">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground border-b border-border bg-secondary/50">
                  <th className="px-5 py-3 font-semibold">Fecha</th>
                  <th className="px-4 py-3 font-semibold">Categoría</th>
                  <th className="px-4 py-3 font-semibold">Descripción</th>
                  <th className="px-4 py-3 font-semibold text-right">Monto</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {expenses.map((e) => (
                  <tr key={e.id} data-testid={`expense-row-${e.id}`} className="hover:bg-secondary/40 transition-colors">
                    <td className="px-5 py-3 text-muted-foreground whitespace-nowrap">{fmtDate(e.created_at)}</td>
                    <td className="px-4 py-3"><span className="text-xs bg-secondary px-2 py-0.5 rounded-full">{CAT_LABELS[e.category] || e.category}</span></td>
                    <td className="px-4 py-3 text-slate-700">{e.description}</td>
                    <td className="px-4 py-3 text-right font-num font-semibold text-rose-700">−{fmtMoney(e.amount, currency)}</td>
                    <td className="px-4 py-3 text-right">
                      <button data-testid={`expense-delete-${e.id}`} onClick={() => remove(e)} className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent aria-describedby={undefined} className="max-w-md" data-testid="expense-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">Registrar gasto</DialogTitle>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div className="space-y-1.5">
              <Label>Categoría *</Label>
              <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                <SelectTrigger data-testid="expense-category-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {EXPENSE_CATEGORIES.map((c) => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Descripción *</Label>
              <Input data-testid="expense-description-input" required value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Ej. Alquiler del local, mes de junio" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Monto *</Label>
                <Input data-testid="expense-amount-input" type="number" min="0.01" step="any" required
                  value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label>Fecha</Label>
                <Input data-testid="expense-date-input" type="date" value={form.date}
                  onChange={(e) => setForm({ ...form, date: e.target.value })} />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" data-testid="expense-form-cancel" onClick={() => setOpen(false)}>Cancelar</Button>
              <Button type="submit" data-testid="expense-form-submit" disabled={saving} className="rounded-xl">
                {saving ? "Guardando…" : "Registrar gasto"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
