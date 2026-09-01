import { useEffect, useState } from "react";
import { ArrowRight, X } from "lucide-react";

const STEPS = [
  ["Dashboard", "Aquí ves la salud del negocio: ventas, rentabilidad, stock y alertas importantes."],
  ["Punto de venta", "Registra ventas y sus medios de pago. Las ventas en efectivo alimentan el cierre de caja."],
  ["Inventario y productos", "Inventario controla existencias y movimientos. Productos administra precios, costos y datos del catálogo."],
  ["Reportes y cierre de caja", "Los reportes explican el negocio. El cierre compara el efectivo esperado contra el efectivo contado."],
  ["Configuración", "Define moneda, referencia USD/EUR, tasas, cargos y datos del negocio."],
  ["Cubi", "Cubi analiza los datos reales de tu negocio y responde preguntas sobre ventas, inventario, gastos y rentabilidad."],
];

export default function FirstRunTour() {
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);
  useEffect(() => {
    if (localStorage.getItem("cuadrapp:first-tour:v1") !== "done") setVisible(true);
  }, []);
  if (!visible) return null;
  const finish = () => { localStorage.setItem("cuadrapp:first-tour:v1", "done"); setVisible(false); };
  const [title, text] = STEPS[step];
  return <div className="fixed inset-0 z-[100] bg-slate-950/45 backdrop-blur-[2px] flex items-end sm:items-center justify-center p-4">
    <div className="w-full max-w-lg bg-card border rounded-3xl shadow-2xl p-6 sm:p-7">
      <div className="flex items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-widest text-primary">Primer recorrido · {step + 1}/{STEPS.length}</p><h2 className="font-heading text-2xl font-extrabold mt-2">{title}</h2></div><button onClick={finish} aria-label="Cerrar tutorial" className="p-2 rounded-xl hover:bg-secondary"><X className="w-4 h-4"/></button></div>
      <p className="text-sm text-muted-foreground leading-relaxed mt-3">{text}</p>
      <div className="flex gap-1.5 mt-5">{STEPS.map((_, i) => <span key={i} className={`h-1.5 rounded-full flex-1 ${i === step ? "bg-primary" : "bg-secondary"}`}/>)}</div>
      <div className="flex justify-between items-center mt-5"><button onClick={finish} className="text-sm text-muted-foreground hover:text-foreground">Omitir</button><button onClick={() => step === STEPS.length - 1 ? finish() : setStep(s => s + 1)} className="inline-flex items-center gap-2 bg-primary text-white px-4 py-2.5 rounded-xl text-sm font-semibold">{step === STEPS.length - 1 ? "Empezar" : "Siguiente"}<ArrowRight className="w-4 h-4"/></button></div>
    </div>
  </div>;
}
