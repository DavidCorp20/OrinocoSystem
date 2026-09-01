import React from "react";

export default function NuevaVenta() {
  return (
    <div className="space-y-5" data-testid="nueva-venta-page">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="font-heading text-3xl font-extrabold flex items-center gap-2">
            <span>🛒</span> Punto de venta
          </h1>
          <p className="text-sm text-muted-foreground mt-1">Selecciona productos y prepara el cobro.</p>
        </div>
      </div>
      <div className="bg-card border rounded-2xl p-6">
        <p className="font-semibold">Punto de venta</p>
        <p className="text-sm text-muted-foreground mt-1">El módulo está listo para continuar con el flujo de productos y pago.</p>
      </div>
    </div>
  );
}
