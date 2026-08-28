import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, PackagePlus, Store, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { BUSINESS_TYPES, CURRENCIES } from "../lib/format";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const STEPS = ["Tu negocio", "Rubro", "Moneda", "Productos", "Listo"];

export default function Onboarding() {
  const { refreshUser } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", type: "", currency: "USD" });
  const [products, setProducts] = useState([]);
  const [draft, setDraft] = useState({ name: "", sale_price: "", purchase_price: "", stock: "" });

  const addProduct = () => {
    if (!draft.name.trim()) return;
    setProducts([...products, {
      name: draft.name.trim(),
      sale_price: Number(draft.sale_price) || 0,
      purchase_price: Number(draft.purchase_price) || 0,
      stock: Number(draft.stock) || 0,
    }]);
    setDraft({ name: "", sale_price: "", purchase_price: "", stock: "" });
  };

  const finish = async () => {
    setSaving(true);
    try {
      await api.post("/business", { ...form, initial_products: products });
      await refreshUser();
      toast.success("¡Tu negocio está listo!");
      navigate("/dashboard", { replace: true });
    } catch (e) {
      toast.error(apiError(e, "No pudimos guardar tu negocio."));
    } finally {
      setSaving(false);
    }
  };

  const canNext = step === 0 ? form.name.trim().length >= 2 : step === 1 ? !!form.type : true;

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        <div className="flex items-center gap-2.5 mb-8 justify-center">
          <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
            <Store className="w-5 h-5 text-white" />
          </div>
          <span className="font-heading font-extrabold text-xl">ControlPyme</span>
        </div>

        <div className="flex items-center justify-center gap-2 mb-6">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div
                data-testid={`onboarding-step-dot-${i}`}
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                  i < step ? "bg-primary text-white" : i === step ? "bg-primary text-white ring-4 ring-primary/20" : "bg-secondary text-muted-foreground"
                }`}
              >
                {i + 1}
              </div>
              {i < STEPS.length - 1 && <div className={`w-6 h-0.5 ${i < step ? "bg-primary" : "bg-border"}`} />}
            </div>
          ))}
        </div>

        <div className="bg-card border border-border rounded-3xl p-6 sm:p-8 shadow-sm animate-rise" data-testid="onboarding-card">
          {step === 0 && (
            <div className="space-y-4">
              <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight">¿Cómo se llama tu negocio?</h1>
              <p className="text-sm text-muted-foreground">Ej. Ferretería El Candado, Bodega Don José, Salón Bella.</p>
              <div className="space-y-1.5">
                <Label htmlFor="biz-name">Nombre del negocio</Label>
                <Input
                  id="biz-name" data-testid="onboarding-business-name-input" autoFocus
                  value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Mi negocio" className="h-12 text-base"
                />
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight">¿Qué tipo de negocio tienes?</h1>
              <p className="text-sm text-muted-foreground">Esto nos ayuda a hablarte en tu idioma, sin tecnicismos.</p>
              <Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v })}>
                <SelectTrigger data-testid="onboarding-business-type-select" className="h-12">
                  <SelectValue placeholder="Elige tu rubro" />
                </SelectTrigger>
                <SelectContent>
                  {BUSINESS_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value} data-testid={`onboarding-type-${t.value}`}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight">¿En qué moneda trabajas?</h1>
              <p className="text-sm text-muted-foreground">La usaremos en todos tus reportes e indicadores.</p>
              <Select value={form.currency} onValueChange={(v) => setForm({ ...form, currency: v })}>
                <SelectTrigger data-testid="onboarding-currency-select" className="h-12">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CURRENCIES.map((c) => (
                    <SelectItem key={c.code} value={c.code} data-testid={`onboarding-currency-${c.code}`}>{c.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight">Agrega tus primeros productos</h1>
              <p className="text-sm text-muted-foreground">Opcional. Solo nombre, precio, costo y cuántas unidades tienes. Luego podrás importar desde Excel/CSV.</p>

              {products.length > 0 && (
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {products.map((p, i) => (
                    <div key={i} className="flex items-center gap-3 bg-secondary rounded-xl px-3.5 py-2.5 text-sm" data-testid={`onboarding-product-${i}`}>
                      <PackagePlus className="w-4 h-4 text-primary shrink-0" />
                      <span className="flex-1 font-medium truncate">{p.name}</span>
                      <span className="font-num text-xs text-muted-foreground">${p.sale_price} · {p.stock} uds</span>
                      <button onClick={() => setProducts(products.filter((_, j) => j !== i))} className="text-slate-400 hover:text-rose-600 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="grid grid-cols-2 gap-2.5">
                <Input data-testid="onboarding-product-name" placeholder="Nombre del producto" className="col-span-2"
                  value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
                <Input data-testid="onboarding-product-price" type="number" min="0" step="any" placeholder="Precio de venta"
                  value={draft.sale_price} onChange={(e) => setDraft({ ...draft, sale_price: e.target.value })} />
                <Input data-testid="onboarding-product-cost" type="number" min="0" step="any" placeholder="Costo de compra"
                  value={draft.purchase_price} onChange={(e) => setDraft({ ...draft, purchase_price: e.target.value })} />
                <Input data-testid="onboarding-product-stock" type="number" min="0" step="any" placeholder="Unidades en stock"
                  value={draft.stock} onChange={(e) => setDraft({ ...draft, stock: e.target.value })} />
                <Button type="button" variant="outline" data-testid="onboarding-add-product-btn" onClick={addProduct} disabled={!draft.name.trim()}>
                  Agregar
                </Button>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4 text-center py-4">
              <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto">
                <Store className="w-8 h-8 text-primary" />
              </div>
              <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight">¡Todo listo, {form.name}!</h1>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                Tu panel inteligente está activado. Registra tu primera venta y Pyme empezará a darte recomendaciones.
              </p>
            </div>
          )}

          <div className="flex items-center justify-between mt-8">
            <Button variant="ghost" data-testid="onboarding-back-btn" onClick={() => setStep(step - 1)} disabled={step === 0 || saving}>
              <ArrowLeft className="w-4 h-4 mr-1.5" /> Atrás
            </Button>
            {step < STEPS.length - 1 ? (
              <div className="flex gap-2">
                {step === 3 && (
                  <Button variant="ghost" data-testid="onboarding-skip-btn" onClick={() => setStep(step + 1)}>Omitir</Button>
                )}
                <Button data-testid="onboarding-next-step-btn" onClick={() => setStep(step + 1)} disabled={!canNext} className="rounded-xl">
                  Continuar <ArrowRight className="w-4 h-4 ml-1.5" />
                </Button>
              </div>
            ) : (
              <Button data-testid="onboarding-finish-btn" onClick={finish} disabled={saving} className="rounded-xl">
                {saving ? "Guardando…" : "Ir a mi Dashboard"} <ArrowRight className="w-4 h-4 ml-1.5" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
