import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Store, CheckCircle2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { apiError } from "../lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

const VALUE_PROPS = [
  "Controla tu inventario sin ser experto",
  "Sabe qué productos te dejan más ganancia",
  "Recibe alertas antes de quedarte sin stock",
  "Pregúntale a Pyme, tu asesor con IA",
];

export default function AuthPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [regForm, setRegForm] = useState({ name: "", email: "", password: "", confirm: "" });

  const go = (data) => navigate(data.business ? "/dashboard" : "/onboarding", { replace: true });

  const doLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      go(await login(loginForm.email, loginForm.password));
    } catch (err) {
      setError(apiError(err, "No pudimos iniciar sesión."));
    } finally {
      setLoading(false);
    }
  };

  const doRegister = async (e) => {
    e.preventDefault();
    setError("");
    if (regForm.password !== regForm.confirm) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setLoading(true);
    try {
      go(await register(regForm.name, regForm.email, regForm.password));
    } catch (err) {
      setError(apiError(err, "No pudimos crear tu cuenta."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">
      <div className="hidden lg:flex relative flex-col justify-between p-10 bg-[#0F172A] text-white overflow-hidden">
        <img
          src="https://images.unsplash.com/photo-1648824572347-517357c9c44e?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NzN8MHwxfHNlYXJjaHwxfHxzbWFsbCUyMGJ1c2luZXNzJTIwb3duZXIlMjByZXRhaWwlMjBzdG9yZSUyMHNob3BrZWVwZXIlMjBpbnZlbnRvcnl8ZW58MHx8fHwxNzg3ODg0NTgyfDA&ixlib=rb-4.1.0&q=85"
          alt="Dueño de negocio controlando su inventario"
          className="absolute inset-0 w-full h-full object-cover opacity-25"
        />
        <div className="relative flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-primary flex items-center justify-center">
            <Store className="w-6 h-6 text-white" />
          </div>
          <span className="font-heading font-extrabold text-2xl">ControlPyme</span>
        </div>
        <div className="relative space-y-6">
          <h1 className="font-heading text-4xl xl:text-5xl font-extrabold leading-tight tracking-tight">
            Entiende tu negocio<br />en un vistazo.
          </h1>
          <p className="text-slate-300 text-lg max-w-md">
            Inventario, ventas, compras y finanzas en un solo lugar. Simple para ti, profesional por dentro.
          </p>
          <ul className="space-y-3">
            {VALUE_PROPS.map((v) => (
              <li key={v} className="flex items-center gap-3 text-sm text-slate-200">
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" /> {v}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-slate-500">Hecho para tiendas, bodegas, ferreterías, papelerías y emprendimientos.</p>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-2.5 mb-8 justify-center">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <Store className="w-5 h-5 text-white" />
            </div>
            <span className="font-heading font-extrabold text-xl">ControlPyme</span>
          </div>

          <Tabs defaultValue="login" className="w-full">
            <TabsList className="grid grid-cols-2 w-full mb-6">
              <TabsTrigger value="login" data-testid="tab-login">Iniciar sesión</TabsTrigger>
              <TabsTrigger value="register" data-testid="tab-register">Crear cuenta</TabsTrigger>
            </TabsList>

            {error && (
              <div data-testid="auth-error" className="mb-4 text-sm bg-rose-50 border border-rose-200 text-rose-700 rounded-xl px-4 py-3">
                {error}
              </div>
            )}

            <TabsContent value="login">
              <form onSubmit={doLogin} className="space-y-4" data-testid="login-form">
                <div className="space-y-1.5">
                  <Label htmlFor="login-email">Correo electrónico</Label>
                  <Input
                    id="login-email" data-testid="login-email-input" type="email" required
                    placeholder="tucorreo@ejemplo.com" value={loginForm.email}
                    onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="login-password">Contraseña</Label>
                  <Input
                    id="login-password" data-testid="login-password-input" type="password" required
                    placeholder="••••••••" value={loginForm.password}
                    onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                  />
                </div>
                <Button data-testid="login-submit-button" type="submit" disabled={loading} className="w-full rounded-xl h-11 font-semibold">
                  {loading ? "Entrando…" : "Entrar a mi negocio"}
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="register">
              <form onSubmit={doRegister} className="space-y-4" data-testid="register-form">
                <div className="space-y-1.5">
                  <Label htmlFor="reg-name">Tu nombre</Label>
                  <Input
                    id="reg-name" data-testid="register-name-input" required placeholder="Ej. María Pérez"
                    value={regForm.name} onChange={(e) => setRegForm({ ...regForm, name: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="reg-email">Correo electrónico</Label>
                  <Input
                    id="reg-email" data-testid="register-email-input" type="email" required
                    placeholder="tucorreo@ejemplo.com" value={regForm.email}
                    onChange={(e) => setRegForm({ ...regForm, email: e.target.value })}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="reg-pass">Contraseña</Label>
                    <Input
                      id="reg-pass" data-testid="register-password-input" type="password" required minLength={8}
                      placeholder="Mín. 8 caracteres" value={regForm.password}
                      onChange={(e) => setRegForm({ ...regForm, password: e.target.value })}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="reg-confirm">Confirmar</Label>
                    <Input
                      id="reg-confirm" data-testid="register-confirm-input" type="password" required
                      placeholder="Repite la contraseña" value={regForm.confirm}
                      onChange={(e) => setRegForm({ ...regForm, confirm: e.target.value })}
                    />
                  </div>
                </div>
                <Button data-testid="register-submit-button" type="submit" disabled={loading} className="w-full rounded-xl h-11 font-semibold">
                  {loading ? "Creando cuenta…" : "Crear mi cuenta gratis"}
                </Button>
                <p className="text-xs text-muted-foreground text-center">En menos de 2 minutos tendrás tu negocio configurado.</p>
              </form>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
