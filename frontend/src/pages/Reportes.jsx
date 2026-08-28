import { useState } from "react";
import { ArrowLeftRight, Download, FileText, Package, ShoppingCart, Truck, Wallet } from "lucide-react";
import { toast } from "sonner";
import { downloadCsv } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

const REPORTS = [
  { key: "ventas", title: "Ventas", desc: "Fecha, productos, método de pago, total y ganancia de cada venta.", icon: ShoppingCart, path: "/sales/export/csv", dated: true },
  { key: "compras", title: "Compras", desc: "Proveedor, productos, cantidades y total de cada compra.", icon: Truck, path: "/purchases/export/csv", dated: true },
  { key: "movimientos", title: "Movimientos de inventario", desc: "Historial completo de entradas y salidas con usuario y motivo.", icon: ArrowLeftRight, path: "/movements/export/csv", dated: false },
  { key: "productos", title: "Productos e inventario", desc: "Catálogo completo con precios, costos y stock actual.", icon: Package, path: "/products/export/csv", dated: false },
  { key: "gastos", title: "Gastos", desc: "Gastos operativos por categoría, descripción y monto.", icon: Wallet, path: "/expenses/export/csv", dated: true },
];

export default function Reportes() {
  const [range, setRange] = useState({});
  const [downloading, setDownloading] = useState("");

  const getRange = (key) => range[key] || { from: "", to: "" };
  const setRangeKey = (key, patch) => setRange({ ...range, [key]: { ...getRange(key), ...patch } });

  const doExport = async (r) => {
    setDownloading(r.key);
    try {
      const rg = getRange(r.key);
      const qs = [];
      if (r.dated && rg.from) qs.push(`from_date=${rg.from}`);
      if (r.dated && rg.to) qs.push(`to_date=${rg.to}`);
      await downloadCsv(`${r.path}${qs.length ? `?${qs.join("&")}` : ""}`, `${r.key}.csv`);
      toast.success(`Reporte de ${r.title.toLowerCase()} descargado`);
    } catch {
      toast.error("No pudimos generar el reporte.");
    } finally {
      setDownloading("");
    }
  };

  return (
    <div className="space-y-5" data-testid="reportes-page">
      <div>
        <h1 className="font-heading text-3xl font-extrabold tracking-tight text-slate-900">Reportes</h1>
        <p className="text-sm text-muted-foreground mt-1">Descarga tu información en CSV para abrirla en Excel o compartirla con quien quieras.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {REPORTS.map((r, i) => (
          <div key={r.key} data-testid={`report-card-${r.key}`}
            className="bg-card border border-border rounded-2xl p-5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 animate-rise"
            style={{ animationDelay: `${i * 60}ms` }}>
            <div className="flex items-start gap-3.5">
              <div className="w-11 h-11 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                <r.icon className="w-5 h-5 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-heading font-bold text-slate-800">{r.title}</h3>
                <p className="text-xs text-muted-foreground mt-0.5">{r.desc}</p>
              </div>
            </div>
            {r.dated && (
              <div className="grid grid-cols-2 gap-3 mt-4">
                <div className="space-y-1">
                  <Label className="text-xs">Desde</Label>
                  <Input data-testid={`report-${r.key}-from`} type="date" value={getRange(r.key).from}
                    onChange={(e) => setRangeKey(r.key, { from: e.target.value })} />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Hasta</Label>
                  <Input data-testid={`report-${r.key}-to`} type="date" value={getRange(r.key).to}
                    onChange={(e) => setRangeKey(r.key, { to: e.target.value })} />
                </div>
              </div>
            )}
            <Button data-testid={`report-${r.key}-export-btn`} onClick={() => doExport(r)} disabled={downloading === r.key}
              className="w-full mt-4 rounded-xl" variant="outline">
              {downloading === r.key ? <FileText className="w-4 h-4 mr-1.5 animate-pulse" /> : <Download className="w-4 h-4 mr-1.5" />}
              {downloading === r.key ? "Generando…" : "Exportar CSV"}
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
