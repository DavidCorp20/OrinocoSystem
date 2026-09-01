import { useEffect, useState } from "react";
import { Building2, RefreshCw, Save, Receipt, Truck } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { fmtNum } from "../lib/format";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

export default function Configuracion() {
  const { business, refreshUser, refreshRate } = useAuth();
  const [fiscal, setFiscal] = useState({ rif: "", address: "", phone: "" });
  const [charges, setCharges] = useState({ iva_enabled: false, iva_percent: "16", igtf_enabled: false, igtf_percent: "3", delivery_enabled: false, delivery_amount: "0" });
  const [rateInfo, setRateInfo] = useState(null);
  const [mode, setMode] = useState("auto");
  const [manualRate, setManualRate] = useState("");
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (business) {
      setFiscal({ rif: business.rif || "", address: business.address || "", phone: business.phone || "" });
      setMode(business.bcv_mode || "auto");
      setManualRate(business.bcv_rate ? String(business.bcv_rate) : "");
      setCharges({
        iva_enabled: Boolean(business.iva_enabled), iva_percent: String(business.iva_percent ?? 16),
        igtf_enabled: Boolean(business.igtf_enabled), igtf_percent: String(business.igtf_percent ?? 3),
        delivery_enabled: Boolean(business.delivery_enabled), delivery_amount: String(business.delivery_amount ?? 0),
      });
    }
  }, [business]);

  const loadRate = () => api.get("/rates/current").then((r) => setRateInfo(r.data)).catch(() => {});
  useEffect(() => { loadRate(); }, []);

  const save = async (patch) => {
    setSaving(true);
    try { await api.put("/business/settings", patch); await refreshUser(); await refreshRate(); loadRate(); toast.success("Configuración guardada"); }
    catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };
  const saveCharges = () => save({ iva_enabled: charges.iva_enabled, iva_percent: Number(charges.iva_percent) || 0, igtf_enabled: charges.igtf_enabled, igtf_percent: Number(charges.igtf_percent) || 0, delivery_enabled: charges.delivery_enabled, delivery_amount: Number(charges.delivery_amount) || 0 });
  const refreshBcv = async () => {
    setRefreshing(true);
    try { const { data } = await api.post("/rates/refresh"); if (data.ok) toast.success(`Tasa BCV actualizada: Bs ${fmtNum(data.rate)}`); else toast.warning(data.detail || "No se pudo actualizar"); loadRate(); refreshRate(); }
    catch (e) { toast.error(apiError(e, "No se pudo actualizar la tasa.")); } finally { setRefreshing(false); }
  };

  return (
    <div className="space-y-5 max-w-3xl" data-testid="configuracion-page">
      <div><h1 className="font-heading text-3xl font-extrabold tracking-tight text-slate-900">Configuración</h1><p className="text-sm text-muted-foreground mt-1">Controla datos fiscales, moneda, tasa y cargos que se aplican a tus operaciones.</p></div>
      <div className="bg-card border border-border rounded-2xl p-5" data-testid="fiscal-card">
        <div className="flex items-center gap-2 mb-4"><Building2 className="w-5 h-5 text-primary" /><h3 className="font-heading font-bold text-slate-800">Datos fiscales</h3></div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
          <div className="space-y-1.5"><Label>RIF</Label><Input data-testid="settings-rif-input" value={fiscal.rif} onChange={(e) => setFiscal({ ...fiscal, rif: e.target.value })} placeholder="J-12345678-9" /></div>
          <div className="space-y-1.5"><Label>Teléfono</Label><Input data-testid="settings-phone-input" value={fiscal.phone} onChange={(e) => setFiscal({ ...fiscal, phone: e.target.value })} placeholder="0414-1234567" /></div>
          <div className="space-y-1.5"><Label>Dirección</Label><Input data-testid="settings-address-input" value={fiscal.address} onChange={(e) => setFiscal({ ...fiscal, address: e.target.value })} placeholder="Av. Principal, Local 4" /></div>
        </div>
        <Button data-testid="settings-fiscal-save-btn" onClick={() => save({ rif: fiscal.rif || null, address: fiscal.address || null, phone: fiscal.phone || null })} disabled={saving} className="mt-4 rounded-xl"><Save className="w-4 h-4 mr-1.5" /> Guardar datos fiscales</Button>
      </div>
      <div className="bg-card border border-border rounded-2xl p-5" data-testid="charges-card">
        <div className="flex items-center gap-2 mb-1"><Receipt className="w-5 h-5 text-primary" /><h3 className="font-heading font-bold text-slate-800">Cargos de operaciones</h3></div>
        <p className="text-sm text-muted-foreground mb-4">Activa solo los cargos que realmente uses. Puedes modificarlos sin cambiar los precios de tus productos.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="rounded-xl border border-border p-4"><div className="flex justify-between items-center mb-3"><Label>IVA</Label><input type="checkbox" checked={charges.iva_enabled} onChange={(e) => setCharges({ ...charges, iva_enabled: e.target.checked })} /></div><Input type="number" min="0" max="100" step="0.01" value={charges.iva_percent} onChange={(e) => setCharges({ ...charges, iva_percent: e.target.value })} disabled={!charges.iva_enabled} /><p className="text-xs text-muted-foreground mt-1">Porcentaje de IVA.</p></div>
          <div className="rounded-xl border border-border p-4"><div className="flex justify-between items-center mb-3"><Label>IGTF</Label><input type="checkbox" checked={charges.igtf_enabled} onChange={(e) => setCharges({ ...charges, igtf_enabled: e.target.checked })} /></div><Input type="number" min="0" max="100" step="0.01" value={charges.igtf_percent} onChange={(e) => setCharges({ ...charges, igtf_percent: e.target.value })} disabled={!charges.igtf_enabled} /><p className="text-xs text-muted-foreground mt-1">Se calcula sobre la parte pagada en divisas.</p></div>
          <div className="rounded-xl border border-border p-4 sm:col-span-2"><div className="flex items-center gap-2 mb-3"><Truck className="w-4 h-4" /><Label>Delivery</Label><input className="ml-auto" type="checkbox" checked={charges.delivery_enabled} onChange={(e) => setCharges({ ...charges, delivery_enabled: e.target.checked })} /></div><Input type="number" min="0" step="0.01" value={charges.delivery_amount} onChange={(e) => setCharges({ ...charges, delivery_amount: e.target.value })} disabled={!charges.delivery_enabled} placeholder="Monto por operación" /></div>
        </div>
        <Button data-testid="settings-charges-save-btn" onClick={saveCharges} disabled={saving} className="mt-4 rounded-xl"><Save className="w-4 h-4 mr-1.5" /> Guardar cargos</Button>
      </div>
      <div className="bg-card border border-border rounded-2xl p-5" data-testid="bcv-card">
        <div className="flex items-center justify-between flex-wrap gap-3 mb-4"><h3 className="font-heading font-bold text-slate-800">Tasa del dólar (Bs / USD)</h3>{rateInfo?.rate && <span className="text-sm font-num font-bold bg-emerald-50 text-emerald-800 border border-emerald-200 px-3 py-1.5 rounded-full" data-testid="settings-current-rate">1 USD = Bs {fmtNum(rateInfo.rate)} {rateInfo.source === "manual" ? "(manual)" : "(BCV)"}</span>}</div>
        <p className="text-sm text-muted-foreground mb-4">Con una tasa activa puedes mostrar importes equivalentes en dólares y bolívares.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5"><div className="space-y-1.5"><Label>¿De dónde tomar la tasa?</Label><Select value={mode} onValueChange={setMode}><SelectTrigger data-testid="settings-bcv-mode-select"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="auto">Automática (BCV del día)</SelectItem><SelectItem value="manual">Manual (la coloco yo)</SelectItem></SelectContent></Select></div>{mode === "manual" && <div className="space-y-1.5"><Label>Tasa manual (Bs por $1)</Label><Input data-testid="settings-manual-rate-input" type="number" min="0.01" step="any" value={manualRate} onChange={(e) => setManualRate(e.target.value)} placeholder="Ej. 96.50" /></div>}</div>
        {mode === "auto" && rateInfo?.auto_rate && <p className="text-xs text-muted-foreground mt-2">Última tasa BCV obtenida: Bs {fmtNum(rateInfo.auto_rate)} (vigente: {rateInfo.auto_date || "—"})</p>}
        <div className="flex gap-2 mt-4 flex-wrap"><Button data-testid="settings-bcv-save-btn" onClick={() => save({ bcv_mode: mode, bcv_rate: mode === "manual" && manualRate ? Number(manualRate) : undefined })} disabled={saving} className="rounded-xl"><Save className="w-4 h-4 mr-1.5" /> Guardar tasa</Button><Button variant="outline" data-testid="settings-bcv-refresh-btn" onClick={refreshBcv} disabled={refreshing} className="rounded-xl"><RefreshCw className={`w-4 h-4 mr-1.5 ${refreshing ? "animate-spin" : ""}`} /> Actualizar desde BCV ahora</Button></div>
      </div>
    </div>
  );
}
