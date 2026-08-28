import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Download, Eye, Plus, ShoppingCart, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadCsv } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { fmtDateTime, fmtMoney, fmtNum, PAYMENT_METHODS } from "../lib/format";
import ProductCombobox from "../components/ProductCombobox";
import FacturaModal from "../components/Factura";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const emptyItem = () => ({ product_id: "", quantity: "1", unit_price: "", discount: "0" });

export default function Ventas() {
  const { business } = useAuth();
  const currency = business?.currency || "USD";
  const [params, setParams] = useSearchParams();
  const [sales, setSales] = useState(null);
  const [products, setProducts] = useState([]);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [items, setItems] = useState([emptyItem()]);
  const [payment, setPayment] = useState("efectivo");
  const [customerName, setCustomerName] = useState("");
  const [customerRif, setCustomerRif] = useState("");
  const [facturaDoc, setFacturaDoc] = useState(null);

  const load = useCallback(() => {
    api.get("/sales").then((r) => setSales(r.data.sales)).catch((e) => toast.error(apiError(e)));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/products").then((r) => setProducts(r.data.products)).catch(() => {}); }, []);
  useEffect(() => {
    if (params.get("nueva") === "1") { setOpen(true); setParams({}, { replace: true }); }
  }, [params, setParams]);

  const setItem = (i, patch) => setItems(items.map((it, j) => (j === i ? { ...it, ...patch } : it)));

  const addProductLine = (prod) => {
    const idx = items.findIndex((it) => it.product_id === prod.id);
    if (idx >= 0) {
      setItem(idx, { quantity: String((Number(items[idx].quantity) || 0) + 1) });
    } else {
      const line = { product_id: prod.id, quantity: "1", unit_price: String(prod.sale_price), discount: "0" };
      const empt = items.findIndex((it) => !it.product_id);
      if (empt >= 0) setItem(empt, line);
      else setItems([...items, line]);
    }
  };

  const totals = items.reduce(
    (acc, it) => {
      const p = products.find((x) => x.id === it.product_id);
      const price = Number(it.unit_price) || 0;
      const qty = Number(it.quantity) || 0;
      const disc = Math.min(Number(it.discount) || 0, price * qty);
      acc.subtotal += price * qty;
      acc.discounts += disc;
      acc.total += price * qty - disc;
      acc.profit += (price - (p?.purchase_price || 0)) * qty - disc;
      return acc;
    },
    { subtotal: 0, discounts: 0, total: 0, profit: 0 }
  );

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        items: items.map((it) => ({
          product_id: it.product_id,
          quantity: Number(it.quantity),
          unit_price: it.unit_price === "" ? null : Number(it.unit_price),
          discount: Number(it.discount) || 0,
        })),
        payment_method: payment,
        customer_name: customerName || null,
        customer_rif: customerRif || null,
      };
      const { data } = await api.post("/sales", payload);
      toast.success(`Venta ${data.sale.invoice_number || ""} registrada por ${fmtMoney(data.sale.total, currency)}`);
      (data.low_stock || []).forEach((a) =>
        toast.warning(`"${a.nombre}" quedó con ${fmtNum(a.stock)} unidades (mínimo ${fmtNum(a.min_stock)})`)
      );
      setOpen(false);
      setItems([emptyItem()]);
      setCustomerName("");
      setCustomerRif("");
      setFacturaDoc(data.sale);
      load();
      api.get("/products").then((r) => setProducts(r.data.products)).catch(() => {});
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5" data-testid="ventas-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-slate-900">Ventas</h1>
          <p className="text-sm text-muted-foreground mt-1">Cada venta descuenta tu inventario y suma a tus ingresos automáticamente.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" data-testid="export-sales-csv-btn" onClick={() => downloadCsv("/sales/export/csv", "ventas.csv")} className="rounded-xl">
            <Download className="w-4 h-4 mr-1.5" /> Exportar CSV
          </Button>
          <Button data-testid="new-sale-btn" onClick={() => setOpen(true)} className="rounded-xl">
            <Plus className="w-4 h-4 mr-1.5" /> Registrar venta
          </Button>
        </div>
      </div>

      <div className="bg-card border border-border rounded-2xl overflow-hidden" data-testid="sales-table-card">
        {!sales ? (
          <div className="p-6 space-y-3">{[...Array(5)].map((_, i) => <div key={i} className="h-10 bg-secondary rounded-xl animate-pulse" />)}</div>
        ) : sales.length === 0 ? (
          <div className="p-12 text-center">
            <ShoppingCart className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
            <p className="font-semibold text-slate-800">Aún no registras ventas</p>
            <p className="text-sm text-muted-foreground mt-1 mb-4">Haz tu primera venta y mira cómo baja tu stock al instante.</p>
            <Button data-testid="empty-new-sale-btn" onClick={() => setOpen(true)} className="rounded-xl"><Plus className="w-4 h-4 mr-1.5" /> Registrar venta</Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="sales-table">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground border-b border-border bg-secondary/50">
                  <th className="px-5 py-3 font-semibold">Fecha</th>
                  <th className="px-4 py-3 font-semibold">Factura</th>
                  <th className="px-4 py-3 font-semibold">Productos</th>
                  <th className="px-4 py-3 font-semibold">Pago</th>
                  <th className="px-4 py-3 font-semibold text-right">Total</th>
                  <th className="px-4 py-3 font-semibold text-right">Ganancia</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sales.map((s) => (
                  <tr key={s.id} data-testid={`sale-row-${s.id}`} className="hover:bg-secondary/40 transition-colors">
                    <td className="px-5 py-3 text-muted-foreground whitespace-nowrap">{fmtDateTime(s.created_at)}</td>
                    <td className="px-4 py-3 font-num text-xs font-semibold text-slate-700">{s.invoice_number || "—"}</td>
                    <td className="px-4 py-3 text-slate-700 max-w-md">
                      <span className="line-clamp-1">{s.items.map((i) => `${i.name} x${fmtNum(i.quantity)}`).join(", ")}</span>
                    </td>
                    <td className="px-4 py-3"><span className="text-xs bg-secondary px-2 py-0.5 rounded-full capitalize">{s.payment_method}</span></td>
                    <td className="px-4 py-3 text-right font-num font-semibold">{fmtMoney(s.total, currency)}</td>
                    <td className="px-4 py-3 text-right font-num font-semibold text-emerald-700">{fmtMoney(s.profit, currency)}</td>
                    <td className="px-4 py-3 text-right">
                      <button data-testid={`sale-invoice-${s.id}`} title="Ver factura" onClick={() => setFacturaDoc(s)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-primary transition-colors">
                        <Eye className="w-4 h-4" />
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
        <DialogContent aria-describedby={undefined} className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="sale-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">Registrar venta</DialogTitle>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div>
              <Label className="text-xs mb-1.5 block">Escanear o buscar producto (agrega directo a la venta)</Label>
              <ProductCombobox products={products} currency={currency} testid="sale-scan-input" autoFocus
                placeholder="Escanea el código de barras o escribe el nombre…" onSelect={addProductLine} />
            </div>
            <div className="space-y-3">
              {items.map((it, i) => {
                const p = products.find((x) => x.id === it.product_id);
                return (
                  <div key={i} className="grid grid-cols-12 gap-2 items-end bg-secondary/50 rounded-xl p-3" data-testid={`sale-item-row-${i}`}>
                    <div className="col-span-12 sm:col-span-5 space-y-1">
                      <Label className="text-xs">Producto</Label>
                      {p ? (
                        <div className="flex items-center gap-2 bg-card border border-border rounded-lg px-2.5 py-2" data-testid={`sale-item-product-${i}`}>
                          <span className="text-sm flex-1 truncate font-medium">{p.name}</span>
                          <button type="button" data-testid={`sale-item-clear-${i}`} onClick={() => setItem(i, { product_id: "" })}
                            className="text-slate-400 hover:text-rose-600 transition-colors">
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <ProductCombobox products={products} currency={currency} testid={`sale-item-search-${i}`}
                          placeholder="Buscar producto…" onSelect={(prod) => setItem(i, { product_id: prod.id, unit_price: String(prod.sale_price) })} />
                      )}
                      {p && Number(it.quantity) > p.stock && (
                        <p className="text-[11px] text-rose-600 font-medium">Solo hay {fmtNum(p.stock)} disponibles</p>
                      )}
                    </div>
                    <div className="col-span-4 sm:col-span-2 space-y-1">
                      <Label className="text-xs">Cantidad</Label>
                      <Input data-testid={`sale-item-qty-${i}`} type="number" min="0.01" step="any" required
                        value={it.quantity} onChange={(e) => setItem(i, { quantity: e.target.value })} />
                    </div>
                    <div className="col-span-4 sm:col-span-2 space-y-1">
                      <Label className="text-xs">Precio</Label>
                      <Input data-testid={`sale-item-price-${i}`} type="number" min="0" step="any" required
                        value={it.unit_price} onChange={(e) => setItem(i, { unit_price: e.target.value })} />
                    </div>
                    <div className="col-span-3 sm:col-span-2 space-y-1">
                      <Label className="text-xs">Descuento</Label>
                      <Input data-testid={`sale-item-discount-${i}`} type="number" min="0" step="any"
                        value={it.discount} onChange={(e) => setItem(i, { discount: e.target.value })} />
                    </div>
                    <div className="col-span-1 flex justify-end">
                      <button type="button" data-testid={`sale-item-remove-${i}`} disabled={items.length === 1}
                        onClick={() => setItems(items.filter((_, j) => j !== i))}
                        className="p-2 rounded-lg text-slate-400 hover:text-rose-600 disabled:opacity-30 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
              <Button type="button" variant="outline" size="sm" data-testid="sale-add-item-btn"
                onClick={() => setItems([...items, emptyItem()])} className="rounded-xl">
                <Plus className="w-3.5 h-3.5 mr-1" /> Agregar otro producto
              </Button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Método de pago</Label>
                <Select value={payment} onValueChange={setPayment}>
                  <SelectTrigger data-testid="sale-payment-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PAYMENT_METHODS.map((m) => <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Cliente (opcional)</Label>
                <Input data-testid="sale-customer-input" value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Nombre o razón social" />
              </div>
              <div className="space-y-1.5">
                <Label>RIF / CI del cliente</Label>
                <Input data-testid="sale-customer-rif-input" value={customerRif} onChange={(e) => setCustomerRif(e.target.value)} placeholder="V-12345678" />
              </div>
            </div>

            <div className="bg-secondary/60 rounded-xl p-4 space-y-1.5 text-sm">
              <div className="flex justify-between text-muted-foreground"><span>Subtotal</span><span className="font-num">{fmtMoney(totals.subtotal, currency)}</span></div>
              <div className="flex justify-between text-muted-foreground"><span>Descuentos</span><span className="font-num">−{fmtMoney(totals.discounts, currency)}</span></div>
              <div className="flex justify-between font-heading font-extrabold text-lg text-slate-900 pt-1 border-t border-border">
                <span>Total a cobrar</span><span className="font-num" data-testid="sale-total">{fmtMoney(totals.total, currency)}</span>
              </div>
              <div className="flex justify-between text-xs text-emerald-700 font-semibold">
                <span>Ganancia estimada de esta venta</span><span className="font-num" data-testid="sale-profit">{fmtMoney(totals.profit, currency)}</span>
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" data-testid="sale-form-cancel" onClick={() => setOpen(false)}>Cancelar</Button>
              <Button type="submit" data-testid="sale-form-submit" disabled={saving || items.some((it) => !it.product_id)} className="rounded-xl">
                {saving ? "Registrando…" : "Cobrar y registrar"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <FacturaModal open={!!facturaDoc} onClose={() => setFacturaDoc(null)} kind="venta" doc={facturaDoc} business={business} />
    </div>
  );
}
