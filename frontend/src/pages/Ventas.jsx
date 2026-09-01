import { useCallback, useEffect, useMemo, useState } from "react";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";

const emptyItem = () => ({
  product_id: "",
  quantity: "1",
  unit_price: "",
  discount: "0",
});

const emptyPart = (method = "efectivo") => ({
  method,
  amount: "",
});

const FOREIGN = new Set(["divisas", "tarjeta_divisa", "zelle"]);

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
  const [combined, setCombined] = useState(false);
  const [paymentParts, setPaymentParts] = useState([
    emptyPart("efectivo"),
    emptyPart("tarjeta"),
  ]);
  const [customerName, setCustomerName] = useState("");
  const [customerRif, setCustomerRif] = useState("");
  const [facturaDoc, setFacturaDoc] = useState(null);

  const load = useCallback(() => {
    api
      .get("/sales")
      .then((r) => setSales(r.data.sales))
      .catch((e) => toast.error(apiError(e)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api
      .get("/products")
      .then((r) => setProducts(r.data.products))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (params.get("nueva") === "1") {
      setOpen(true);
      setParams({}, { replace: true });
    }
  }, [params, setParams]);

  const setItem = (index, patch) => {
    setItems((current) =>
      current.map((item, i) => (i === index ? { ...item, ...patch } : item))
    );
  };

  const addProductLine = (product) => {
    const existingIndex = items.findIndex(
      (item) => item.product_id === product.id
    );

    if (existingIndex >= 0) {
      setItem(existingIndex, {
        quantity: String((Number(items[existingIndex].quantity) || 0) + 1),
      });
      return;
    }

    const line = {
      product_id: product.id,
      quantity: "1",
      unit_price: String(product.sale_price),
      discount: "0",
    };
    const emptyIndex = items.findIndex((item) => !item.product_id);

    if (emptyIndex >= 0) {
      setItem(emptyIndex, line);
    } else {
      setItems((current) => [...current, line]);
    }
  };

  const totals = useMemo(
    () =>
      items.reduce(
        (acc, item) => {
          const product = products.find((x) => x.id === item.product_id);
          const price = Number(item.unit_price) || 0;
          const quantity = Number(item.quantity) || 0;
          const discount = Math.min(
            Number(item.discount) || 0,
            price * quantity
          );

          acc.subtotal += price * quantity;
          acc.discounts += discount;
          acc.total += price * quantity - discount;
          acc.profit +=
            (price - (product?.purchase_price || 0)) * quantity - discount;
          return acc;
        },
        { subtotal: 0, discounts: 0, total: 0, profit: 0 }
      ),
    [items, products]
  );

  const paymentTarget = useMemo(() => {
    const base =
      totals.total +
      (business?.delivery_enabled
        ? Number(business?.delivery_amount || 0)
        : 0);
    const igtf = Number(business?.igtf_percent || 3) / 100;

    if (!business?.igtf_enabled) return base;

    const foreign = combined
      ? paymentParts
          .filter((part) => FOREIGN.has(part.method))
          .reduce((sum, part) => sum + (Number(part.amount) || 0), 0)
      : FOREIGN.has(payment)
        ? base
        : 0;

    return base + foreign * igtf;
  }, [business, combined, payment, paymentParts, totals.total]);

  const paid = paymentParts.reduce(
    (sum, part) => sum + (Number(part.amount) || 0),
    0
  );
  const difference = Number((paymentTarget - paid).toFixed(2));

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);

    try {
      const payload = {
        items: items.map((item) => ({
          product_id: item.product_id,
          quantity: Number(item.quantity),
          unit_price:
            item.unit_price === "" ? null : Number(item.unit_price),
          discount: Number(item.discount) || 0,
        })),
        payment_method: combined ? "combinado" : payment,
        payment_parts: combined
          ? paymentParts
              .filter((part) => Number(part.amount) > 0)
              .map((part) => ({
                method: part.method,
                amount: Number(part.amount),
              }))
          : [],
        customer_name: customerName || null,
        customer_rif: customerRif || null,
      };

      const { data } = await api.post("/sales", payload);
      toast.success(
        `Venta ${data.sale.invoice_number || ""} registrada por ${fmtMoney(
          data.sale.total,
          currency
        )}`
      );

      (data.low_stock || []).forEach((alert) => {
        toast.warning(
          `"${alert.nombre}" quedó con ${fmtNum(alert.stock)} unidades (mínimo ${fmtNum(
            alert.min_stock
          )})`
        );
      });

      setOpen(false);
      setItems([emptyItem()]);
      setCustomerName("");
      setCustomerRif("");
      setCombined(false);
      setPaymentParts([emptyPart("efectivo"), emptyPart("tarjeta")]);
      setFacturaDoc(data.sale);
      load();
      api
        .get("/products")
        .then((r) => setProducts(r.data.products))
        .catch(() => {});
    } catch (error) {
      toast.error(apiError(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5" data-testid="ventas-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-slate-900">
            Ventas
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Cada venta descuenta inventario y registra ingresos automáticamente.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => downloadCsv("/sales/export/csv", "ventas.csv")}
            className="rounded-xl"
          >
            <Download className="w-4 h-4 mr-1.5" />
            Exportar CSV
          </Button>
          <Button onClick={() => setOpen(true)} className="rounded-xl">
            <Plus className="w-4 h-4 mr-1.5" />
            Registrar venta
          </Button>
        </div>
      </div>

      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        {!sales ? (
          <div className="p-6 space-y-3">
            {[...Array(5)].map((_, index) => (
              <div
                key={index}
                className="h-10 bg-secondary rounded-xl animate-pulse"
              />
            ))}
          </div>
        ) : sales.length === 0 ? (
          <div className="p-12 text-center">
            <ShoppingCart className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
            <p className="font-semibold text-slate-800">Aún no registras ventas</p>
            <p className="text-sm text-muted-foreground mt-1 mb-4">
              Haz tu primera venta y mira cómo baja tu stock.
            </p>
            <Button onClick={() => setOpen(true)} className="rounded-xl">
              <Plus className="w-4 h-4 mr-1.5" />
              Registrar venta
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground border-b border-border bg-secondary/50">
                  <th className="px-5 py-3">Fecha</th>
                  <th className="px-4 py-3">Factura</th>
                  <th className="px-4 py-3">Productos</th>
                  <th className="px-4 py-3">Pago</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  <th className="px-4 py-3 text-right">Ganancia</th>
                  <th />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sales.map((sale) => (
                  <tr key={sale.id} className="hover:bg-secondary/40">
                    <td className="px-5 py-3 text-muted-foreground whitespace-nowrap">
                      {fmtDateTime(sale.created_at)}
                    </td>
                    <td className="px-4 py-3 font-num text-xs font-semibold">
                      {sale.invoice_number || "—"}
                    </td>
                    <td className="px-4 py-3 max-w-md">
                      <span className="line-clamp-1">
                        {sale.items
                          .map(
                            (item) =>
                              `${item.name} x${fmtNum(item.quantity)}`
                          )
                          .join(", ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs bg-secondary px-2 py-0.5 rounded-full capitalize">
                        {sale.payment_method}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-num font-semibold">
                      {fmtMoney(sale.total, currency)}
                    </td>
                    <td className="px-4 py-3 text-right font-num font-semibold text-emerald-700">
                      {fmtMoney(sale.profit, currency)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        title="Ver factura"
                        onClick={() => setFacturaDoc(sale)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-primary"
                      >
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
        <DialogContent
          aria-describedby={undefined}
          className="max-w-2xl max-h-[90vh] overflow-y-auto"
        >
          <DialogHeader>
            <DialogTitle className="font-heading">Registrar venta</DialogTitle>
          </DialogHeader>

          <form onSubmit={save} className="space-y-4">
            <div>
              <Label className="text-xs mb-1.5 block">
                Escanear o buscar producto
              </Label>
              <ProductCombobox
                products={products}
                currency={currency}
                autoFocus
                placeholder="Escanea el código de barras o escribe el nombre…"
                onSelect={addProductLine}
              />
            </div>

            <div className="space-y-3">
              {items.map((item, index) => {
                const product = products.find(
                  (candidate) => candidate.id === item.product_id
                );

                return (
                  <div
                    key={index}
                    className="grid grid-cols-12 gap-2 items-end bg-secondary/50 rounded-xl p-3"
                  >
                    <div className="col-span-12 sm:col-span-5 space-y-1">
                      <Label className="text-xs">Producto</Label>
                      {product ? (
                        <div className="flex items-center gap-2 bg-card border border-border rounded-lg px-2.5 py-2">
                          <span className="text-sm flex-1 truncate font-medium">
                            {product.name}
                          </span>
                          <button
                            type="button"
                            onClick={() => setItem(index, { product_id: "" })}
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <ProductCombobox
                          products={products}
                          currency={currency}
                          placeholder="Buscar producto…"
                          onSelect={(selected) =>
                            setItem(index, {
                              product_id: selected.id,
                              unit_price: String(selected.sale_price),
                            })
                          }
                        />
                      )}
                      {product && Number(item.quantity) > product.stock && (
                        <p className="text-[11px] text-rose-600">
                          Solo hay {fmtNum(product.stock)} disponibles
                        </p>
                      )}
                    </div>

                    <div className="col-span-4 sm:col-span-2 space-y-1">
                      <Label className="text-xs">Cantidad</Label>
                      <Input
                        type="number"
                        min="0.01"
                        step="any"
                        required
                        value={item.quantity}
                        onChange={(event) =>
                          setItem(index, { quantity: event.target.value })
                        }
                      />
                    </div>

                    <div className="col-span-4 sm:col-span-2 space-y-1">
                      <Label className="text-xs">Precio</Label>
                      <Input
                        type="number"
                        min="0"
                        step="any"
                        required
                        value={item.unit_price}
                        onChange={(event) =>
                          setItem(index, { unit_price: event.target.value })
                        }
                      />
                    </div>

                    <div className="col-span-3 sm:col-span-2 space-y-1">
                      <Label className="text-xs">Descuento</Label>
                      <Input
                        type="number"
                        min="0"
                        step="any"
                        value={item.discount}
                        onChange={(event) =>
                          setItem(index, { discount: event.target.value })
                        }
                      />
                    </div>

                    <div className="col-span-1 flex justify-end">
                      <button
                        type="button"
                        disabled={items.length === 1}
                        onClick={() =>
                          setItems((current) =>
                            current.filter((_, i) => i !== index)
                          )
                        }
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                );
              })}

              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setItems((current) => [...current, emptyItem()])}
                className="rounded-xl"
              >
                <Plus className="w-3.5 h-3.5 mr-1" />
                Agregar otro producto
              </Button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Método de pago</Label>
                <Select
                  value={payment}
                  onValueChange={(value) => {
                    setPayment(value);
                    setCombined(false);
                  }}
                  disabled={combined}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PAYMENT_METHODS.map((method) => (
                      <SelectItem key={method.value} value={method.value}>
                        {method.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-end">
                <Button
                  type="button"
                  variant={combined ? "default" : "outline"}
                  className="w-full"
                  onClick={() => setCombined((value) => !value)}
                >
                  {combined ? "Pago combinado activo" : "Dividir el pago"}
                </Button>
              </div>

              <div className="space-y-1.5">
                <Label>Cliente (opcional)</Label>
                <Input
                  value={customerName}
                  onChange={(event) => setCustomerName(event.target.value)}
                  placeholder="Nombre o razón social"
                />
              </div>

              <div className="space-y-1.5">
                <Label>RIF / CI</Label>
                <Input
                  value={customerRif}
                  onChange={(event) => setCustomerRif(event.target.value)}
                  placeholder="V-12345678"
                />
              </div>
            </div>

            {combined && (
              <div className="border border-primary/20 bg-primary/5 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-sm">Pago dividido</p>
                    <p className="text-xs text-muted-foreground">
                      Ej.: parte en efectivo y parte con tarjeta.
                    </p>
                  </div>
                  <span
                    className={`text-xs font-semibold ${
                      Math.abs(difference) <= 0.01
                        ? "text-emerald-700"
                        : "text-amber-700"
                    }`}
                  >
                    {Math.abs(difference) <= 0.01
                      ? "Completo"
                      : `Faltan ${fmtMoney(Math.max(difference, 0), currency)}`}
                  </span>
                </div>

                {paymentParts.map((part, index) => (
                  <div key={index} className="grid grid-cols-2 gap-2">
                    <Select
                      value={part.method}
                      onValueChange={(value) =>
                        setPaymentParts((current) =>
                          current.map((entry, i) =>
                            i === index ? { ...entry, method: value } : entry
                          )
                        )
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {PAYMENT_METHODS.map((method) => (
                          <SelectItem key={method.value} value={method.value}>
                            {method.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      value={part.amount}
                      onChange={(event) =>
                        setPaymentParts((current) =>
                          current.map((entry, i) =>
                            i === index
                              ? { ...entry, amount: event.target.value }
                              : entry
                          )
                        )
                      }
                      placeholder="Monto"
                    />
                  </div>
                ))}

                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    setPaymentParts((current) => [
                      ...current,
                      emptyPart("efectivo"),
                    ])
                  }
                >
                  + Agregar otro método
                </Button>

                <p className="text-xs text-muted-foreground">
                  Total estimado: <strong>{fmtMoney(paymentTarget, currency)}</strong>
                  {" · "}
                  Registrado: <strong>{fmtMoney(paid, currency)}</strong>
                  {business?.igtf_enabled && (
                    <span>
                      {" · "}IGTF aplicado según la porción en divisas.
                    </span>
                  )}
                </p>
              </div>
            )}

            <div className="bg-secondary/60 rounded-xl p-4 space-y-1.5 text-sm">
              <div className="flex justify-between text-muted-foreground">
                <span>Subtotal</span>
                <span className="font-num">
                  {fmtMoney(totals.subtotal, currency)}
                </span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>Descuentos</span>
                <span className="font-num">
                  −{fmtMoney(totals.discounts, currency)}
                </span>
              </div>
              <div className="flex justify-between font-heading font-extrabold text-lg pt-1 border-t border-border">
                <span>Total base</span>
                <span className="font-num">
                  {fmtMoney(totals.total, currency)}
                </span>
              </div>
              <div className="flex justify-between text-xs text-emerald-700 font-semibold">
                <span>Ganancia estimada</span>
                <span className="font-num">
                  {fmtMoney(totals.profit, currency)}
                </span>
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={
                  saving ||
                  items.some((item) => !item.product_id) ||
                  (combined && Math.abs(difference) > 0.01)
                }
                className="rounded-xl"
              >
                {saving ? "Registrando…" : "Cobrar y registrar"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <FacturaModal
        open={!!facturaDoc}
        onClose={() => setFacturaDoc(null)}
        kind="venta"
        doc={facturaDoc}
        business={business}
      />
    </div>
  );
}
