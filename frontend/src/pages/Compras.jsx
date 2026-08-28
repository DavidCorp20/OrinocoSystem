import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Download, Plus, Trash2, Truck } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadCsv } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { fmtDateTime, fmtMoney, fmtNum, PAYMENT_METHODS } from "../lib/format";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const emptyItem = () => ({ product_id: "", quantity: "1", unit_cost: "" });

export default function Compras() {
  const { business } = useAuth();
  const currency = business?.currency || "USD";
  const [params, setParams] = useSearchParams();
  const [purchases, setPurchases] = useState(null);
  const [products, setProducts] = useState([]);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [items, setItems] = useState([emptyItem()]);
  const [supplier, setSupplier] = useState("");
  const [payment, setPayment] = useState("efectivo");

  const load = useCallback(() => {
    api.get("/purchases").then((r) => setPurchases(r.data.purchases)).catch((e) => toast.error(apiError(e)));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/products").then((r) => setProducts(r.data.products)).catch(() => {}); }, []);
  useEffect(() => {
    if (params.get("nueva") === "1") { setOpen(true); setParams({}, { replace: true }); }
  }, [params, setParams]);

  const setItem = (i, patch) => setItems(items.map((it, j) => (j === i ? { ...it, ...patch } : it)));

  const pickProduct = (i, pid) => {
    const p = products.find((x) => x.id === pid);
    setItem(i, { product_id: pid, unit_cost: p ? String(p.purchase_price) : "" });
  };

  const total = items.reduce((acc, it) => acc + (Number(it.unit_cost) || 0) * (Number(it.quantity) || 0), 0);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        supplier: supplier || null,
        items: items.map((it) => ({ product_id: it.product_id, quantity: Number(it.quantity), unit_cost: Number(it.unit_cost) || 0 })),
        payment_method: payment,
      };
      const { data } = await api.post("/purchases", payload);
      toast.success(`Compra registrada por ${fmtMoney(data.purchase.total, currency)}. Tu stock ya fue actualizado.`);
      setOpen(false);
      setItems([emptyItem()]);
      setSupplier("");
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5" data-testid="compras-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-slate-900">Compras</h1>
          <p className="text-sm text-muted-foreground mt-1">Cada compra suma unidades a tu inventario y actualiza el costo del producto.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" data-testid="export-purchases-csv-btn" onClick={() => downloadCsv("/purchases/export/csv", "compras.csv")} className="rounded-xl">
            <Download className="w-4 h-4 mr-1.5" /> Exportar CSV
          </Button>
          <Button data-testid="new-purchase-btn" onClick={() => setOpen(true)} className="rounded-xl">
            <Plus className="w-4 h-4 mr-1.5" /> Registrar compra
          </Button>
        </div>
      </div>

      <div className="bg-card border border-border rounded-2xl overflow-hidden" data-testid="purchases-table-card">
        {!purchases ? (
          <div className="p-6 space-y-3">{[...Array(5)].map((_, i) => <div key={i} className="h-10 bg-secondary rounded-xl animate-pulse" />)}</div>
        ) : purchases.length === 0 ? (
          <div className="p-12 text-center">
            <Truck className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
            <p className="font-semibold text-slate-800">Aún no registras compras</p>
            <p className="text-sm text-muted-foreground mt-1 mb-4">Cuando compres mercancía a tu proveedor, regístrala aquí.</p>
            <Button data-testid="empty-new-purchase-btn" onClick={() => setOpen(true)} className="rounded-xl"><Plus className="w-4 h-4 mr-1.5" /> Registrar compra</Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="purchases-table">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground border-b border-border bg-secondary/50">
                  <th className="px-5 py-3 font-semibold">Fecha</th>
                  <th className="px-4 py-3 font-semibold">Proveedor</th>
                  <th className="px-4 py-3 font-semibold">Productos</th>
                  <th className="px-4 py-3 font-semibold">Pago</th>
                  <th className="px-4 py-3 font-semibold text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {purchases.map((p) => (
                  <tr key={p.id} data-testid={`purchase-row-${p.id}`} className="hover:bg-secondary/40 transition-colors">
                    <td className="px-5 py-3 text-muted-foreground whitespace-nowrap">{fmtDateTime(p.created_at)}</td>
                    <td className="px-4 py-3 font-medium text-slate-800">{p.supplier || "—"}</td>
                    <td className="px-4 py-3 text-slate-700 max-w-md">
                      <span className="line-clamp-1">{p.items.map((i) => `${i.name} x${fmtNum(i.quantity)}`).join(", ")}</span>
                    </td>
                    <td className="px-4 py-3"><span className="text-xs bg-secondary px-2 py-0.5 rounded-full capitalize">{p.payment_method}</span></td>
                    <td className="px-4 py-3 text-right font-num font-semibold">{fmtMoney(p.total, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent aria-describedby={undefined} className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="purchase-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">Registrar compra</DialogTitle>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Proveedor</Label>
                <Input data-testid="purchase-supplier-input" value={supplier} onChange={(e) => setSupplier(e.target.value)} placeholder="Ej. Distribuidora López" />
              </div>
              <div className="space-y-1.5">
                <Label>Método de pago</Label>
                <Select value={payment} onValueChange={setPayment}>
                  <SelectTrigger data-testid="purchase-payment-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PAYMENT_METHODS.map((m) => <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-3">
              {items.map((it, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-end bg-secondary/50 rounded-xl p-3" data-testid={`purchase-item-row-${i}`}>
                  <div className="col-span-12 sm:col-span-6 space-y-1">
                    <Label className="text-xs">Producto</Label>
                    <Select value={it.product_id} onValueChange={(v) => pickProduct(i, v)}>
                      <SelectTrigger data-testid={`purchase-item-product-${i}`}><SelectValue placeholder="Elige producto" /></SelectTrigger>
                      <SelectContent>
                        {products.map((pr) => (
                          <SelectItem key={pr.id} value={pr.id}>{pr.name} · stock actual: {fmtNum(pr.stock)}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="col-span-5 sm:col-span-2 space-y-1">
                    <Label className="text-xs">Cantidad</Label>
                    <Input data-testid={`purchase-item-qty-${i}`} type="number" min="0.01" step="any" required
                      value={it.quantity} onChange={(e) => setItem(i, { quantity: e.target.value })} />
                  </div>
                  <div className="col-span-5 sm:col-span-3 space-y-1">
                    <Label className="text-xs">Costo unitario</Label>
                    <Input data-testid={`purchase-item-cost-${i}`} type="number" min="0" step="any" required
                      value={it.unit_cost} onChange={(e) => setItem(i, { unit_cost: e.target.value })} />
                  </div>
                  <div className="col-span-2 sm:col-span-1 flex justify-end">
                    <button type="button" data-testid={`purchase-item-remove-${i}`} disabled={items.length === 1}
                      onClick={() => setItems(items.filter((_, j) => j !== i))}
                      className="p-2 rounded-lg text-slate-400 hover:text-rose-600 disabled:opacity-30 transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
              <Button type="button" variant="outline" size="sm" data-testid="purchase-add-item-btn"
                onClick={() => setItems([...items, emptyItem()])} className="rounded-xl">
                <Plus className="w-3.5 h-3.5 mr-1" /> Agregar otro producto
              </Button>
            </div>

            <div className="bg-secondary/60 rounded-xl p-4 flex justify-between items-center">
              <span className="font-heading font-extrabold text-lg text-slate-900">Total de la compra</span>
              <span className="font-num font-extrabold text-lg" data-testid="purchase-total">{fmtMoney(total, currency)}</span>
            </div>

            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" data-testid="purchase-form-cancel" onClick={() => setOpen(false)}>Cancelar</Button>
              <Button type="submit" data-testid="purchase-form-submit" disabled={saving || items.some((it) => !it.product_id)} className="rounded-xl">
                {saving ? "Registrando…" : "Registrar compra"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
