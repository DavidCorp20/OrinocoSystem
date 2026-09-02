import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api, { clearAuthToken } from "../lib/api";

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: "loading", user: null, business: null });
  const [rate, setRate] = useState(null);
  const [plan, setPlan] = useState(null);

  const refreshRate = useCallback(async () => {
    try { const { data } = await api.get("/rates/current"); setRate(data.rate || data.auto_rate_usd ? data : null); }
    catch { setRate(null); }
  }, []);

  const refreshPlan = useCallback(async () => {
    try {
      const { data } = await api.get("/subscription/me");
      setPlan({ name: data.plan?.name || "Básico", entitlements: data.entitlements || {}, subscription: data.subscription, price: data.plan?.monthly_price_usd });
    } catch {
      // Platform superadmins do not have a tenant subscription.
      setPlan({ name: "Plataforma", entitlements: { basic_operations: true, max_users: 999, cash_closure: true, exports: "full", cubi: "advanced" } });
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    api.get("/auth/me")
      .then((r) => { if (mounted) setState({ status: "authed", user: r.data.user, business: r.data.business }); })
      .catch(() => { if (mounted) setState({ status: "guest", user: null, business: null }); });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (state.status !== "authed") return;
    refreshRate();
    // Tenant plans are optional for superadmins, but refreshing is harmless and
    // gives the platform shell a consistent context.
    refreshPlan();
    const timer = window.setInterval(refreshRate, 30 * 60 * 1000);
    const planTimer = window.setInterval(refreshPlan, 5 * 60 * 1000);
    return () => { window.clearInterval(timer); window.clearInterval(planTimer); };
  }, [state.status, refreshRate, refreshPlan]);

  const apply = (data) => setState({ status: "authed", user: data.user, business: data.business });

  const login = useCallback(async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    apply(data);
    return data;
  }, []);

  const register = useCallback(async (name, email, password) => {
    const { data } = await api.post("/auth/register", { name, email, password });
    apply(data);
    return data;
  }, []);

  const logout = useCallback(async () => {
    await api.post("/auth/logout").catch(() => {});
    clearAuthToken();
    setState({ status: "guest", user: null, business: null });
    setPlan(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const { data } = await api.get("/auth/me");
    setState({ status: "authed", user: data.user, business: data.business });
    return data;
  }, []);

  return (
    <AuthCtx.Provider value={{
      status: state.status,
      user: state.user,
      business: state.business,
      role: state.user?.role || "propietario",
      isOwner: (state.user?.role || "propietario") === "propietario",
      isAdmin: ["propietario", "administrador"].includes(state.user?.role || "propietario"),
      isSuper: state.user?.platform_role === "superadmin",
      rate,
      refreshRate,
      planName: plan?.name || "Básico",
      entitlements: plan?.entitlements || {},
      subscription: plan?.subscription,
      planPrice: plan?.price,
      refreshPlan,
      login,
      register,
      logout,
      refreshUser
    }}>{children}</AuthCtx.Provider>
  );
}
