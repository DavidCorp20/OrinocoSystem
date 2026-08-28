import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "../lib/api";

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: "loading", user: null, business: null });

  useEffect(() => {
    api
      .get("/auth/me")
      .then((r) => setState({ status: "authed", user: r.data.user, business: r.data.business }))
      .catch(() => setState({ status: "guest", user: null, business: null }));
  }, []);

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
