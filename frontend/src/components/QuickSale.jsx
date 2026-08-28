import { useEffect, useState } from "react";
import { Minus, Plus, Trash2, Zap } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { fmtBs, fmtMoney, fmtNum, PAYMENT_METHODS } from "../lib/format";
import ProductCombobox from "./ProductCombobox";
import FacturaModal from "./Factura";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

export default function QuickSale({ open, onClose }) {
  const { business } = useAuth();
  const currency = business?.currency || "USD";
  const [products, setProducts] = useState([]);
  const [rate, setRate] = useState(null);
  const [cart, setCart] = useState([]);
  const [payment, setPayment] = useState("efectivo");
  const [customerName, setCustomerName] = useState("");
  const [customerRif, setCustomerRif] = useState("");
  const [saving, setSaving] = useState(false);
  const [facturaDoc, setFacturaDoc] = useState(null);

  const load = () => {
    api.get("/products").then((r) => setProducts(r.data.products)).catch(() => {});
    api.get("/rates/current").then((r) => setRate(r.data.rate)).catch(() => {});
  };

  useEffect(() => {
    if (open) {
      setCart([]);
      setCustomerName("");
      setCustomerRif("");
      load();
    }
  }, [open]);

  const add = (p) => {
    if (p.stock <= 0) {
      toast.warning(`"${p.name}" está agotado`);
      return;
    }
    setCart((c) => {
      const i = c.findIndex((x) => x.product.id === p.id);
      if (i >= 0) {
        const copy = [...c];
        copy[i] = { ...copy[i], quantity: copy[i].quantity + 1 };
        return copy;
      }
      return [...c, { product: p, quantity: 1, price: p.sale_price }];
    });
  };

  const setQty = (id, q) =>
    setCart((c) => c.map((x) => (x.product.id === id ? { ...x, quantity: q } : x)).filter((x) => x.quantity > 0));

  const total = cart.reduce((a, x) => a + x.price * x.quantity, 0);
  const totalBs = rate ? total * rate : null;

  const cobrar = async () => {
    if (!cart.length || saving) return;
    setSaving(true);
    try {
      const { data } = await api.post("/sales", {
        items: cart.map((x) => ({ product_id: x.product.id, quantity: x.quantity, unit_price: x.price, discount: 0 })),
        payment_method: payment,
        customer_name: customerName || null,
        customer_rif: customerRif || null,
      });
      toast.success(`Venta ${data.sale.invoice_number || ""} registrada por ${fmtMoney(data.sale.total, currency)}`);
      (data.low_stock || []).forEach((a) =>
        toast.warning(`"${a.nombre}" quedó con ${fmtNum(a.stock)} unidades (mínimo ${fmtNum(a.min_stock)})`)
      );
      setFacturaDoc(data.sale);
      setCart([]);
      setCustomerName("");
      setCustomerRif("");
      onClose();
      load();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent aria-describedby={undefined} className="max-w-3xl max-h-[92vh] overflow-y-auto" data-testid="quick-sale-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary" /> Venta rápida
            </DialogTitle>
          </DialogHeader>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-5">
            <div className="md:col-span-3 space-y-3">
              <div>
                <ProductCombobox
                  products={products}
                  currency={currency}
                  testid="quick-sale-search"
                  autoFocus
                  placeholder="Escanea el código de barras o escribe el producto…"
                  onSelect={add}
                />
                <p className="text-[11px] text-muted-foreground mt-1.5">
                  Conecta tu lector de códigos: al escanear, el producto se agrega solo al carrito.
                </p>
              </div>

              {cart.length === 0 ? (
                <div className="border-2 border-dashed border-border rounded-2xl p-10 text-center text-sm text-muted-foreground" data-testid="quick-sale-empty">
                  El carrito está vacío. Escanea o busca un producto para comenzar.
                </div>
              ) : (
                <div className="space-y-2" data-testid="quick-sale-cart">
                  {cart.map((x, i) => (
                    <div key={x.product.id} className="flex items-center gap-3 bg-secondary/50 rounded-xl px-3.5 py-2.5" data-testid={`quick-sale-cart-row-${i}`}>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-800 truncate">{x.product.name}</p>
                        <p className="text-xs text-muted-foreground font-num">{fmtMoney(x.price, currency)} c/u · stock: {fmtNum(x.product.stock)}</p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button type="button" data-testid={`quick-sale-minus-${i}`} onClick={() => setQty(x.product.id, x.quantity - 1)}
                          className="w-7 h-7 rounded-lg bg-card border border-border flex items-center justify-center hover:bg-secondary transition-colors">
                          <Minus className="w-3.5 h-3.5" />
                        </button>
                        <span className="w-8 text-center font-num font-bold text-sm" data-testid={`quick-sale-qty-${i}`}>{fmtNum(x.quantity)}</span>
                        <button type="button" data-testid={`quick-sale-plus-${i}`} onClick={() => setQty(x.product.id, x.quantity + 1)}
                          className="w-7 h-7 rounded-lg bg-card border border-border flex items-center justify-center hover:bg-secondary transition-colors">
                          <Plus className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <span className="w-20 text-right font-num font-semibold text-sm">{fmtMoney(x.price * x.quantity, currency)}</span>
                      <button type="button" data-testid={`quick-sale-remove-${i}`} onClick={() => setQty(x.product.id, 0)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="md:col-span-2 space-y-3.5">
              <div className="grid grid-cols-2 gap-2.5">
                <div className="space-y-1">
                  <Label className="text-xs">Cliente (opcional)</Label>
                  <Input data-testid="quick-sale-customer-name" value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Nombre" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">RIF / CI</Label>
                  <Input data-testid="quick-sale-customer-rif" value={customerRif} onChange={(e) => setCustomerRif(e.target.value)} placeholder="V-12345678" />
                </div>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Método de pago</Label>
                <Select value={payment} onValueChange={setPayment}>
                  <SelectTrigger data-testid="quick-sale-payment-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {[...PAYMENT_METHODS, { value: "pago móvil", label: "Pago móvil" }].map((m) => (
                      <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="bg-slate-900 text-white rounded-2xl p-5 space-y-1.5">
                <div className="flex justify-between items-end">
                  <span className="text-sm text-slate-400">Total a cobrar</span>
                  <span className="font-heading font-extrabold text-3xl font-num" data-testid="quick-sale-total">{fmtMoney(total, currency)}</span>
                </div>
                {totalBs !== null && (
                  <div className="flex justify-between items-center text-emerald-300">
                    <span className="text-xs">Equivalente (tasa {fmtNum(rate)})</span>
                    <span className="font-num font-bold" data-testid="quick-sale-total-bs">{fmtBs(totalBs)}</span>
                  </div>
                )}
                <p className="text-[11px] text-slate-500 pt-1">Precios con IVA (16%) incluido. Se emite factura automáticamente.</p>
              </div>

              <Button
                data-testid="quick-sale-charge-btn"
                onClick={cobrar}
                disabled={!cart.length || saving}
                className="w-full h-13 py-3.5 rounded-2xl text-base font-heading font-extrabold"
              >
                {saving ? "Cobrando…" : `Cobrar ${fmtMoney(total, currency)}`}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <FacturaModal open={!!facturaDoc} onClose={() => setFacturaDoc(null)} kind="venta" doc={facturaDoc} business={business} />
    </>
  );
}
