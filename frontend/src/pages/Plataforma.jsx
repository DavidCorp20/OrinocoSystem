import { useCallback, useEffect, useState } from "react";
import { Plus, ShieldCheck, Store, Trash2, TrendingUp, Users, Wallet } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { fmtDate, fmtMoney, fmtNum } from "../lib/format";
import StatCard from "../components/StatCard";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Switch } from "../components/ui/switch";

const PLATFORM_CATEGORIES = [
  { value: "infraestructura", label: "Infraestructura (servidores)" },
  { value: "marketing", label: "Marketing" },
  { value: "soporte", label: "Soporte" },
  { value: "licencias", label: "Licencias y herramientas" },
  { value: "otros", label: "Otros" },
];
const CAT_LABELS = Object.fromEntries(PLATFORM_CATEGORIES.map((c) => [c.value, c.label]));

export default function Plataforma() {
  const [data, setData] = useState(null);
  const [expenses, setExpenses] = useState([]);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ category: "infraestructura", description: "", amount: "", date: "" });

  const load = useCallback(() => {
    api.get("/platform/overview").then((r) => setData(r.data)).catch((e) => toast.error(apiError(e)));
    api.get("/platform/expenses").then((r) => setExpenses(r.data.expenses)).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = async (b, active) => {
    try {
      await api.put(`/platform/businesses/${b.id}/status`, { active });
      toast.success(active ? `"${b.name}" habilitado` : `"${b.name}" deshabilitado`);
      load();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const addExpense = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post("/platform/expenses", { ...form, amount: Number(form.amount), date: form.date || null });
      toast.success("Gasto de plataforma registrado");
      setOpen(false);
      setForm({ category: "infraestructura", description: "", amount: "", date: "" });
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSaving(false);
    }
  };

  const removeExpense = async (exp) => {
    try {
      await api.delete(`/platform/expenses/${exp.id}`);
      toast.success("Gasto eliminado");
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  if (!data) {
    return <div className="grid grid-cols-1 md:grid-cols-4 gap-4">{[...Array(4)].map((_, i) => <div key={i} className="h-32 bg-card border border-border rounded-2xl animate-pulse" />)}</div>;
  }
  const s = data.stats;

  return (
    <div className="space-y-5" data-testid="plataforma-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-slate-900 flex items-center gap-2">
            <ShieldCheck className="w-7 h-7 text-primary" /> Plataforma
          </h1>
          <p className="text-sm text-muted-foreground mt-1">Control de los negocios registrados y los gastos de operación de ControlPyme.</p>
        </div>
        <Button data-testid="platform-new-expense-btn" onClick={() => setOpen(true)} className="rounded-xl">
          <Plus className="w-4 h-4 mr-1.5" /> Gasto de plataforma
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard testid="plat-total" title="Negocios registrados" value={fmtNum(s.total)} icon={Store} />
        <StatCard testid="plat-activos" title="Cuentas activas" value={fmtNum(s.activos)} icon={Users} delay={60}
          hint={s.inactivos ? `${s.inactivos} deshabilitada(s)` : "Todas habilitadas"} />
        <StatCard testid="plat-nuevos" title="Nuevos (30 días)" value={fmtNum(s.nuevos_30)} icon={TrendingUp} delay={120} />
        <StatCard testid="plat-gastos" title="Gastos plataforma (mes)" value={fmtMoney(s.gastos_mes, "USD")} icon={Wallet} delay={180}
          hint={Object.entries(s.gastos_por_categoria).map(([c, v]) => `${CAT_LABELS[c] || c}: ${fmtMoney(v, "USD")}`).join(" · ") || "Sin gastos este mes"} />
      </div>

      <div className="bg-card border border-border rounded-2xl overflow-hidden" data-testid="platform-businesses-card">
        <div className="px-5 py-4 border-b border-border">
          <h3 className="font-heading font-bold text-slate-800">Negocios registrados</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="platform-businesses-table">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground border-b border-border bg-secondary/50">
                <th className="px-5 py-3 font-semibold">Negocio</th>
                <th className="px-4 py-3 font-semibold">Dueño</th>
                <th className="px-4 py-3 font-semibold">Registrado</th>
                <th className="px-4 py-3 font-semibold text-right">Productos</th>
                <th className="px-4 py-3 font-semibold text-right">Ventas</th>
                <th className="px-4 py-3 font-semibold text-center">Cuenta activa</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.businesses.map((b) => (
                <tr key={b.id} data-testid={`platform-business-${b.id}`} className="hover:bg-secondary/40 transition-colors">
                  <td className="px-5 py-3">
                    <p className="font-medium text-slate-800">{b.name}</p>
                    <p className="text-xs text-muted-foreground capitalize">{b.type}</p>
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    <p className="text-sm">{b.owner_name}</p>
                    <p className="text-xs text-muted-foreground">{b.owner_email}</p>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">{fmtDate(b.created_at)}</td>
                  <td className="px-4 py-3 text-right font-num">{fmtNum(b.products_count)}</td>
                  <td className="px-4 py-3 text-right font-num">{fmtNum(b.sales_count)}</td>
                  <td className="px-4 py-3 text-center">
                    <Switch
                      data-testid={`platform-toggle-${b.id}`}
                      checked={b.active}
                      onCheckedChange={(v) => toggle(b, v)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-card border border-border rounded-2xl overflow-hidden" data-testid="platform-expenses-card">
        <div className="px-5 py-4 border-b border-border">
          <h3 className="font-heading font-bold text-slate-800">Gastos de la plataforma</h3>
        </div>
        {expenses.length === 0 ? (
          <p className="p-10 text-center text-sm text-muted-foreground">Aún no registras gastos de operación (servidores, marketing, herramientas…).</p>
        ) : (
          <div className="divide-y divide-border">
            {expenses.map((e) => (
              <div key={e.id} className="px-5 py-3 flex items-center gap-3" data-testid={`platform-expense-${e.id}`}>
                <span className="text-xs bg-secondary px-2 py-0.5 rounded-full shrink-0">{CAT_LABELS[e.category] || e.category}</span>
                <span className="flex-1 text-sm text-slate-700 truncate">{e.description}</span>
                <span className="text-xs text-muted-foreground whitespace-nowrap">{fmtDate(e.created_at)}</span>
                <span className="font-num font-semibold text-rose-700">−{fmtMoney(e.amount, "USD")}</span>
                <button data-testid={`platform-expense-delete-${e.id}`} onClick={() => removeExpense(e)} className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 transition-colors">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent aria-describedby={undefined} className="max-w-md" data-testid="platform-expense-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">Gasto de la plataforma</DialogTitle>
          </DialogHeader>
          <form onSubmit={addExpense} className="space-y-4">
            <div className="space-y-1.5">
              <Label>Categoría *</Label>
              <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                <SelectTrigger data-testid="platform-expense-category-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PLATFORM_CATEGORIES.map((c) => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Descripción *</Label>
              <Input data-testid="platform-expense-description-input" required value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Ej. Servidor cloud, mes de junio" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Monto (USD) *</Label>
                <Input data-testid="platform-expense-amount-input" type="number" min="0.01" step="any" required
                  value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label>Fecha</Label>
                <Input data-testid="platform-expense-date-input" type="date" value={form.date}
                  onChange={(e) => setForm({ ...form, date: e.target.value })} />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" data-testid="platform-expense-cancel" onClick={() => setOpen(false)}>Cancelar</Button>
              <Button type="submit" data-testid="platform-expense-submit" disabled={saving} className="rounded-xl">
                {saving ? "Guardando…" : "Registrar"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
