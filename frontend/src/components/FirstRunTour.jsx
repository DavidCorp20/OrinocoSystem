import { useEffect, useState } from "react";
import { ArrowRight, X, BarChart3, ShoppingCart, Package, FileText, Settings, Bot, Wallet } from "lucide-react";

const STEPS = [
  ["Dashboard", "Aquí entiendes la salud del negocio: ventas, margen, ganancia, tendencia, stock y recomendaciones. Los indicadores tienen un icono i para ver qué significan, su fórmula y un ejemplo."],
  ["Punto de venta", "Registra una venta, elige cómo te pagaron y CuadraApp actualiza la información del negocio. Las ventas en efectivo también alimentan el cierre de caja.", ShoppingCart],
  ["Productos e inventario", "Productos guarda precios y costos. Inventario muestra existencias y movimientos. El stock bajo y los productos por agotarse aparecen como alertas para ayudarte a decidir cuándo reponer.", Package],
  ["Ventas, compras y gastos", "Estas operaciones construyen la información financiera del negocio. Registrar correctamente costos, compras y gastos es clave para que los indicadores sean útiles.", BarChart3],
  ["Reportes y cierre de caja", "Los reportes convierten tus movimientos en información para decidir. El cierre de caja compara cuánto efectivo debería haber contra cuánto efectivo contaste y deja trazabilidad.", Wallet],
  ["Configuración", "Aquí defines las preferencias del negocio, moneda y referencia de comparación USD/EUR. Las tasas automáticas se muestran para ayudarte a interpretar valores en bolívares.", Settings],
  ["Cubi", "Cubi puede analizar los datos reales del negocio y ayudarte a entender qué está pasando y qué acción conviene tomar. No reemplaza tu decisión: te ayuda a tomarla con datos.", Bot],
  ["Ahora sí: empieza", "No necesitas memorizar todo. Usa el icono i cuando tengas una duda. En los indicadores verás qué mide, cómo se calcula y un ejemplo sencillo. CuadraApp debe ayudarte a entender el negocio, no solo a mostrar números.", FileText],
];

let claimedInThisSession = false;

export default function FirstRunTour() {
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (claimedInThisSession) return;
    const seen = localStorage.getItem("cuadrapp:first-tour:v2");
    if (seen !== "done") {
      claimedInThisSession = true;
      setVisible(true);
    }
  }, []);

  if (!visible) return null;
  const finish = () => {
    localStorage.setItem("cuadrapp:first-tour:v2", "done");
    localStorage.removeItem("cuadrapp:first-tour:v1");
    setVisible(false);
  };
  const [title, text, Icon] = STEPS[step];

  return (
    <div className="fixed inset-0 z-[100] bg-slate-950/45 backdrop-blur-[2px] flex items-end sm:items-center justify-center p-4">
      <div className="w-full max-w-lg bg-card border rounded-3xl shadow-2xl p-6 sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <div className="flex gap-3">
            {Icon && <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0"><Icon className="w-5 h-5" /></div>}
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-primary">Primer recorrido · {step + 1}/{STEPS.length}</p>
              <h2 className="font-heading text-2xl font-extrabold mt-2">{title}</h2>
            </div>
          </div>
          <button onClick={finish} aria-label="Cerrar tutorial" className="p-2 rounded-xl hover:bg-secondary"><X className="w-4 h-4"/></button>
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed mt-4">{text}</p>
        <div className="flex gap-1.5 mt-5">{STEPS.map((_, i) => <span key={i} className={`h-1.5 rounded-full flex-1 ${i === step ? "bg-primary" : "bg-secondary"}`}/>)}</div>
        <div className="flex justify-between items-center mt-5">
          <button onClick={finish} className="text-sm text-muted-foreground hover:text-foreground">Omitir</button>
          <button onClick={() => step === STEPS.length - 1 ? finish() : setStep(s => s + 1)} className="inline-flex items-center gap-2 bg-primary text-white px-4 py-2.5 rounded-xl text-sm font-semibold">{step === STEPS.length - 1 ? "Empezar" : "Siguiente"}<ArrowRight className="w-4 h-4"/></button>
        </div>
      </div>
    </div>
  );
}
