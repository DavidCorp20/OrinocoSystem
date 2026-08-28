import { useCallback, useEffect, useState } from "react";
import { Trash2, UserPlus, Users } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { fmtDate, ROLE_LABELS } from "../lib/format";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const ROLE_HELP = [
  { role: "propietario", desc: "Acceso total: ventas, compras, finanzas, reportes, equipo y configuración." },
  { role: "administrador", desc: "Gestiona la operación completa: productos, compras, finanzas y reportes. No gestiona el equipo." },
  { role: "vendedor", desc: "Registra ventas y movimientos de inventario. Ve productos y el dashboard, sin finanzas ni compras." },
];

export default function Equipo() {
  const [team, setTeam] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "vendedor" });

  const load = useCallback(() => {
    api.get("/team").then((r) => setTeam(r.data.team)).catch((e) => toast.error(apiError(e)));
  }, []);

  useEffect(() => { load(); }, [load]);

  const add = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post("/team", form);
      toast.success(`${form.name} ya puede entrar con su correo y contraseña`);
      setForm({ name: "", email: "", password: "", role: "vendedor" });
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (m) => {
    try {
      await api.delete(`/team/${m.id}`);
      toast.success(`${m.name} fue eliminado del equipo`);
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  return (
    <div className="space-y-5" data-testid="equipo-page">
      <div>
        <h1 className="font-heading text-3xl font-extrabold tracking-tight text-slate-900">Equipo</h1>
        <p className="text-sm text-muted-foreground mt-1">Crea cuentas para quienes trabajan contigo y decide qué puede hacer cada uno.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-card border border-border rounded-2xl p-5" data-testid="team-add-card">
          <div className="flex items-center gap-2 mb-4">
            <UserPlus className="w-5 h-5 text-primary" />
            <h3 className="font-heading font-bold text-slate-800">Agregar persona</h3>
          </div>
          <form onSubmit={add} className="space-y-3.5">
            <div className="space-y-1.5">
              <Label>Nombre *</Label>
              <Input data-testid="team-name-input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Ej. Ana Ruiz" />
            </div>
            <div className="space-y-1.5">
              <Label>Correo *</Label>
              <Input data-testid="team-email-input" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="ana@tunegocio.com" />
            </div>
            <div className="space-y-1.5">
              <Label>Contraseña temporal *</Label>
              <Input data-testid="team-password-input" type="text" required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Mín. 8 caracteres" />
            </div>
            <div className="space-y-1.5">
              <Label>Rol *</Label>
              <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                <SelectTrigger data-testid="team-role-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="vendedor" data-testid="team-role-vendedor">Vendedor</SelectItem>
                  <SelectItem value="administrador" data-testid="team-role-administrador">Administrador</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" data-testid="team-add-btn" disabled={saving} className="w-full rounded-xl">
              {saving ? "Creando…" : "Crear cuenta"}
            </Button>
          </form>
        </div>

        <div className="lg:col-span-2 bg-card border border-border rounded-2xl overflow-hidden" data-testid="team-table-card">
          <div className="px-5 py-4 border-b border-border flex items-center gap-2">
            <Users className="w-5 h-5 text-primary" />
            <h3 className="font-heading font-bold text-slate-800">Personas con acceso</h3>
          </div>
          {!team ? (
            <div className="p-6 space-y-3">{[...Array(3)].map((_, i) => <div key={i} className="h-10 bg-secondary rounded-xl animate-pulse" />)}</div>
          ) : (
            <div className="divide-y divide-border">
              {team.map((m) => (
                <div key={m.id} className="px-5 py-3.5 flex items-center gap-3" data-testid={`team-row-${m.id}`}>
                  <div className="w-9 h-9 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-bold shrink-0">
                    {(m.name || "U")[0].toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-800 truncate">{m.name}</p>
                    <p className="text-xs text-muted-foreground truncate">{m.email} · desde {fmtDate(m.created_at)}</p>
                  </div>
                  <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full ${
                    m.role === "propietario" ? "bg-slate-900 text-white" : m.role === "administrador" ? "bg-primary/10 text-primary" : "bg-secondary text-slate-600"
                  }`} data-testid={`team-role-badge-${m.id}`}>
                    {ROLE_LABELS[m.role] || m.role}
                  </span>
                  {m.role !== "propietario" && (
                    <button data-testid={`team-remove-${m.id}`} onClick={() => remove(m)} className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="bg-card border border-border rounded-2xl p-5" data-testid="roles-help-card">
        <h3 className="font-heading font-bold text-slate-800 mb-3">¿Qué puede hacer cada rol?</h3>
        <ul className="space-y-2.5">
          {ROLE_HELP.map((r) => (
            <li key={r.role} className="flex items-start gap-3 text-sm">
              <span className="text-xs font-bold bg-secondary px-2.5 py-1 rounded-full shrink-0">{ROLE_LABELS[r.role]}</span>
              <span className="text-slate-600">{r.desc}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
