import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "../lib/api";

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: "loading", user: null, business: null });
  const [rate, setRate] = useState(null);

  const refreshRate = useCallback(async () => {
    try {
      const { data } = await api.get("/rates/current");
      setRate(data.rate ? data : null);
    } catch {
      setRate(null);
    }
  }, []);

  useEffect(() => {
    api
      .get("/auth/me")
      .then((r) => setState({ status: "authed", user: r.data.user, business: r.data.business }))
      .catch(() => setState({ status: "guest", user: null, business: null }));
  }, []);

  useEffect(() => {
    if (state.status === "authed" && state.business) refreshRate();
  }, [state.status, state.business, refreshRate]);

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
    setState({ status: "guest", user: null, business: null });
  }, []);

  const refreshUser = useCallback(async () => {
    const { data } = await api.get("/auth/me");
    setState({ status: "authed", user: data.user, business: data.business });
    return data;
  }, []);

  return (
    <AuthCtx.Provider
      value={{
        status: state.status,
        user: state.user,
        business: state.business,
        role: state.user?.role || "propietario",
        isOwner: (state.user?.role || "propietario") === "propietario",
        isAdmin: ["propietario", "administrador"].includes(state.user?.role || "propietario"),
        isSuper: state.user?.platform_role === "superadmin",
        rate,
        refreshRate,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthCtx.Provider>
  );
}
