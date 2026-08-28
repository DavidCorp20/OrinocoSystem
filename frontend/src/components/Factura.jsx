import { Printer } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { fmtBs, fmtDateTime, fmtMoney, fmtNum } from "../lib/format";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const f2 = (n) => Number(n || 0).toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function totals(doc) {
  const total = doc.total || 0;
  const subtotal = doc.subtotal ?? Math.round((total / 1.16) * 100) / 100;
  const iva = doc.iva_amount ?? Math.round((total - subtotal) * 100) / 100;
  return { total, subtotal, iva };
}

export function printFactura({ kind, doc, business }) {
  const isVenta = kind === "venta";
  const { total, subtotal, iva } = totals(doc);
  const title = isVenta ? "FACTURA" : "COMPROBANTE DE COMPRA";
  const rows = (doc.items || [])
    .map((it) => {
      const unit = it.unit_price ?? it.unit_cost ?? 0;
      return `<tr><td>${esc(it.name)}</td><td style="text-align:center">${fmtNum(it.quantity)}</td><td style="text-align:right">${f2(unit)}</td><td style="text-align:right">${f2(it.line_total)}</td></tr>`;
    })
    .join("");
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>${title} ${esc(doc.invoice_number || "")}</title>
<style>body{font-family:Arial,sans-serif;width:300px;margin:0 auto;padding:16px;color:#111;font-size:12px}h1{font-size:15px;text-align:center;margin:6px 0}.c{text-align:center}.r{text-align:right}table{width:100%;border-collapse:collapse}td,th{padding:2px 0;font-size:12px}hr{border:none;border-top:1px dashed #999;margin:8px 0}.tot{font-size:14px;font-weight:bold}</style></head>
<body>
<p class="c"><b>${esc(business?.name || "")}</b></p>
${business?.rif ? `<p class="c">RIF: ${esc(business.rif)}</p>` : ""}
${business?.address ? `<p class="c">${esc(business.address)}</p>` : ""}
${business?.phone ? `<p class="c">Telf: ${esc(business.phone)}</p>` : ""}
<hr>
<h1>${title}</h1>
<p class="c">Nº ${esc(doc.invoice_number || "—")}</p>
<p>Fecha: ${esc(fmtDateTime(doc.created_at))}</p>
${isVenta ? `<p>Cliente: ${esc(doc.customer_name || "Cliente general")}</p><p>RIF/CI: ${esc(doc.customer_rif || "S/N")}</p>` : `<p>Proveedor: ${esc(doc.supplier || "—")}</p><p>RIF: ${esc(doc.supplier_rif || "S/N")}</p>`}
<hr>
<table><thead><tr><th style="text-align:left">Descripción</th><th>Cant</th><th class="r">P.Unit</th><th class="r">Importe</th></tr></thead><tbody>${rows}</tbody></table>
<hr>
<table>
<tr><td>Subtotal (base imponible)</td><td class="r">${f2(subtotal)}</td></tr>
<tr><td>IVA (16%) incluido</td><td class="r">${f2(iva)}</td></tr>
<tr class="tot"><td>TOTAL USD</td><td class="r">$${f2(total)}</td></tr>
${doc.exchange_rate ? `<tr><td>Tasa BCV del día</td><td class="r">${f2(doc.exchange_rate)}</td></tr><tr class="tot"><td>TOTAL Bs</td><td class="r">Bs ${f2(doc.total_bs)}</td></tr>` : ""}
<tr><td>Método de pago</td><td class="r">${esc(doc.payment_method || "")}</td></tr>
</table>
<hr>
<p class="c">¡Gracias por su ${isVenta ? "compra" : "atención"}!</p>
<p class="c" style="color:#777;font-size:10px">Generado con ControlPyme</p>
<script>window.onload=function(){window.print()}</script>
</body></html>`;
  const w = window.open("", "_blank", "width=400,height=640");
  if (!w) return;
  w.document.write(html);
  w.document.close();
}

export default function FacturaModal({ open, onClose, kind, doc, business }) {
  if (!doc) return null;
  const isVenta = kind === "venta";
  const { total, subtotal, iva } = totals(doc);
  const currency = business?.currency || "USD";

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent aria-describedby={undefined} className="max-w-md" data-testid="factura-modal">
        <DialogHeader>
          <DialogTitle className="font-heading text-center pr-6">
            {isVenta ? "Factura" : "Comprobante de compra"} {doc.invoice_number || ""}
          </DialogTitle>
          {!doc.invoice_number && (
            <p className="text-center text-xs text-muted-foreground">Sin número de factura (registro anterior a la facturación)</p>
          )}
        </DialogHeader>
        <div className="bg-secondary/40 rounded-xl p-4 text-sm">
          <p className="text-center font-bold">{business?.name}</p>
          {business?.rif && <p className="text-center text-xs text-muted-foreground">RIF: {business.rif}</p>}
          {business?.address && <p className="text-center text-xs text-muted-foreground">{business.address}</p>}
          <p className="text-xs text-muted-foreground mt-2">{fmtDateTime(doc.created_at)}</p>
          <p className="text-xs">
            {isVenta
              ? `Cliente: ${doc.customer_name || "Cliente general"} · RIF/CI: ${doc.customer_rif || "S/N"}`
              : `Proveedor: ${doc.supplier || "—"} · RIF: ${doc.supplier_rif || "S/N"}`}
          </p>
          <div className="border-t border-dashed border-slate-300 my-2.5" />
          <div className="space-y-1">
            {(doc.items || []).map((it, i) => (
              <div key={i} className="flex justify-between gap-2 text-xs">
                <span className="truncate">{fmtNum(it.quantity)} x {it.name}</span>
                <span className="font-num shrink-0">{fmtMoney(it.line_total, currency)}</span>
              </div>
            ))}
          </div>
          <div className="border-t border-dashed border-slate-300 my-2.5" />
          <div className="flex justify-between text-xs"><span>Subtotal (base imponible)</span><span className="font-num">{fmtMoney(subtotal, currency)}</span></div>
          <div className="flex justify-between text-xs"><span>IVA (16%) incluido</span><span className="font-num">{fmtMoney(iva, currency)}</span></div>
          <div className="flex justify-between font-bold mt-1"><span>TOTAL</span><span className="font-num" data-testid="factura-total">{fmtMoney(total, currency)}</span></div>
          {doc.exchange_rate ? (
            <>
              <div className="flex justify-between text-xs text-muted-foreground"><span>Tasa BCV del día</span><span className="font-num">{f2(doc.exchange_rate)}</span></div>
              <div className="flex justify-between font-bold text-emerald-800"><span>TOTAL Bs</span><span className="font-num" data-testid="factura-total-bs">{fmtBs(doc.total_bs)}</span></div>
            </>
          ) : null}
          <div className="flex justify-between text-xs text-muted-foreground"><span>Método de pago</span><span className="capitalize">{doc.payment_method}</span></div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="flex-1 rounded-xl" data-testid="factura-close-btn" onClick={onClose}>Cerrar</Button>
          <Button className="flex-1 rounded-xl" data-testid="factura-print-btn" onClick={() => printFactura({ kind, doc, business })}>
            <Printer className="w-4 h-4 mr-1.5" /> Imprimir
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
