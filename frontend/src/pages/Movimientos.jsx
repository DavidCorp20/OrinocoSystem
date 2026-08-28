import { useCallback, useEffect, useState } from "react";
import { ArrowDownLeft, ArrowUpRight, Download, Plus } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadCsv } from "../lib/api";
import { fmtDateTime, fmtNum, REASON_LABELS, ENTRY_REASONS, EXIT_REASONS } from "../lib/format";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

export default function Movimientos() {
  const [movements, setMovements] = useState(null);
  const [products, setProducts] = useState([]);
  const [typeFilter, setTypeFilter] = useState("todos");
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ product_id: "", type: "entrada", reason: "reposicion", quantity: "", notes: "" });

  const load = useCallback(() => {
    const params = {};
    if (typeFilter !== "todos") params.type = typeFilter;
    api.get("/movements", { params }).then((r) => setMovements(r.data.movements)).catch((e) => toast.error(apiError(e)));
  }, [typeFilter]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/products").then((r) => setProducts(r.data.products)).catch(() => {}); }, []);

  const reasons = form.type === "entrada" ? ENTRY_REASONS : EXIT_REASONS;

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const { data } = await api.post("/movements", { ...form, quantity: Number(form.quantity) });
      toast.success(`Movimiento registrado. Nuevo stock: ${fmtNum(data.stock)}`);
      setOpen(false);
      setForm({ product_id: "", type: "entrada", reason: "reposicion", quantity: "", notes: "" });
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5" data-testid="movimientos-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-slate-900">Movimientos</h1>
          <p className="text-sm text-muted-foreground mt-1">Historial de entradas y salidas de tu mercancía.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" data-testid="export-movements-csv-btn" onClick={() => downloadCsv("/movements/export/csv", "movimientos.csv")} className="rounded-xl">
            <Download className="w-4 h-4 mr-1.5" /> Exportar CSV
          </Button>
          <Button data-testid="new-movement-btn" onClick={() => setOpen(true)} className="rounded-xl">
            <Plus className="w-4 h-4 mr-1.5" /> Nuevo movimiento
          </Button>
        </div>
      </div>

      <Select value={typeFilter} onValueChange={setTypeFilter}>
        <SelectTrigger data-testid="select-movement-type-filter" className="w-52 rounded-xl">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="todos">Entradas y salidas</SelectItem>
          <SelectItem value="entrada">Solo entradas</SelectItem>
          <SelectItem value="salida">Solo salidas</SelectItem>
        </SelectContent>
      </Select>

      <div className="bg-card border border-border rounded-2xl overflow-hidden" data-testid="movements-table-card">
        {!movements ? (
          <div className="p-6 space-y-3">{[...Array(6)].map((_, i) => <div key={i} className="h-10 bg-secondary rounded-xl animate-pulse" />)}</div>
        ) : movements.length === 0 ? (
          <p className="p-10 text-center text-sm text-muted-foreground">Aún no hay movimientos. Registra uno o haz tu primera venta.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="movements-table">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground border-b border-border bg-secondary/50">
                  <th className="px-5 py-3 font-semibold">Fecha</th>
                  <th className="px-4 py-3 font-semibold">Producto</th>
                  <th className="px-4 py-3 font-semibold">Tipo</th>
                  <th className="px-4 py-3 font-semibold">Motivo</th>
                  <th className="px-4 py-3 font-semibold text-right">Cantidad</th>
                  <th className="px-4 py-3 font-semibold text-right">Stock resultante</th>
                  <th className="px-4 py-3 font-semibold">Usuario</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {movements.map((m) => (
                  <tr key={m.id} data-testid={`movement-row-${m.id}`} className="hover:bg-secondary/40 transition-colors">
                    <td className="px-5 py-3 text-muted-foreground whitespace-nowrap">{fmtDateTime(m.created_at)}</td>
                    <td className="px-4 py-3 font-medium text-slate-800">{m.product_name}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full ${
                        m.type === "entrada" ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"}`}>
                        {m.type === "entrada" ? <ArrowDownLeft className="w-3 h-3" /> : <ArrowUpRight className="w-3 h-3" />}
                        {m.type === "entrada" ? "Entrada" : "Salida"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{REASON_LABELS[m.reason] || m.reason}</td>
                    <td className={`px-4 py-3 text-right font-num font-semibold ${m.type === "entrada" ? "text-emerald-700" : "text-rose-700"}`}>
                      {m.type === "entrada" ? "+" : "−"}{fmtNum(m.quantity)}
                    </td>
                    <td className="px-4 py-3 text-right font-num text-muted-foreground">{fmtNum(m.stock_after)}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{m.user_email}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent aria-describedby={undefined} className="max-w-md" data-testid="movement-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">Registrar movimiento</DialogTitle>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div className="space-y-1.5">
              <Label>Producto *</Label>
              <Select value={form.product_id} onValueChange={(v) => setForm({ ...form, product_id: v })}>
                <SelectTrigger data-testid="movement-product-select"><SelectValue placeholder="Elige un producto" /></SelectTrigger>
                <SelectContent>
                  {products.map((p) => (
                    <SelectItem key={p.id} value={p.id} data-testid={`movement-product-${p.id}`}>
                      {p.name} · stock: {fmtNum(p.stock)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Tipo *</Label>
                <Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v, reason: v === "entrada" ? "reposicion" : "ajuste_negativo" })}>
                  <SelectTrigger data-testid="movement-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="entrada">Entrada</SelectItem>
                    <SelectItem value="salida">Salida</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Motivo *</Label>
                <Select value={form.reason} onValueChange={(v) => setForm({ ...form, reason: v })}>
                  <SelectTrigger data-testid="movement-reason-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {reasons.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Cantidad *</Label>
              <Input data-testid="movement-quantity-input" type="number" min="0.01" step="any" required
                value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Nota (opcional)</Label>
              <Input data-testid="movement-notes-input" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Ej. Se dañaron en transporte" />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" data-testid="movement-form-cancel" onClick={() => setOpen(false)}>Cancelar</Button>
              <Button type="submit" data-testid="movement-form-submit" disabled={saving || !form.product_id} className="rounded-xl">
                {saving ? "Guardando…" : "Registrar"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
