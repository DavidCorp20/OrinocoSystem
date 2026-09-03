import axios from "axios";

// CRA replaces REACT_APP_* at build time. PLATIA frontend and API are deployed
// on separate Railway services, so never fall back to the frontend origin.
const configuredBackend = (process.env.REACT_APP_BACKEND_URL || "").trim().replace(/\/$/, "");
const productionBackend = "https://orinocosystem-production.up.railway.app";
export const API_URL = `${configuredBackend || productionBackend}/api`;

const TOKEN_KEY = "cuadra_access_token";
const readToken = () => {
  try { return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY) || ""; } catch { return ""; }
};
const saveToken = (token) => {
  if (!token) return;
  try { localStorage.setItem(TOKEN_KEY, token); } catch {}
};
const clearToken = () => {
  try { localStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(TOKEN_KEY); } catch {}
};

const api = axios.create({ baseURL: API_URL, withCredentials: true });
api.interceptors.request.use((config) => {
  const token = readToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing = null;
api.interceptors.response.use(
  (response) => {
    if (response.config?.url === "/auth/login" && response.data?.access_token) saveToken(response.data.access_token);
    return response;
  },
  async (error) => {
    const original = error.config || {};
    const url = original.url || "";
    if (error.response?.status === 401 && !original._retry && !url.startsWith("/auth/")) {
      original._retry = true;
      try {
        refreshing = refreshing || api.post("/auth/refresh");
        const refreshResponse = await refreshing;
        refreshing = null;
        if (refreshResponse.data?.access_token) saveToken(refreshResponse.data.access_token);
        return api(original);
      } catch (e) {
        refreshing = null;
        clearToken();
      }
    }
    return Promise.reject(error);
  }
);

export function clearAuthToken() { clearToken(); }

export function apiError(e, fallback = "Ocurrió un error. Intenta de nuevo.") {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(x => x?.msg || "").filter(Boolean).join(" ");
  if (typeof e?.message === "string" && e.message) return e.message;
  return fallback;
}

export async function downloadCsv(path, filename) {
  const res = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a"); a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}

export async function streamChat(message, onToken, onDone) {
  const doFetch = () => fetch(`${API_URL}/assistant/chat`, {
    method: "POST", credentials: "include",
    headers: { "Content-Type": "application/json", "Accept": "text/event-stream", ...(readToken() ? { Authorization: `Bearer ${readToken()}` } : {}) },
    body: JSON.stringify({ message })
  });
  let res = await doFetch();
  if (res.status === 401) {
    const refresh = await fetch(`${API_URL}/auth/refresh`, { method: "POST", credentials: "include" });
    if (!refresh.ok) throw new Error("La sesión expiró. Vuelve a iniciar sesión.");
    const data = await refresh.json().catch(() => ({}));
    if (data.access_token) saveToken(data.access_token);
    res = await doFetch();
  }
  if (!res.ok || !res.body) {
    let detail = ""; try { detail = (await res.json()).detail || ""; } catch {}
    throw new Error(detail || `El asistente devolvió un error (${res.status})`);
  }
  const reader = res.body.getReader(), dec = new TextDecoder();
  let buf = "", received = false, doneSignal = false, lastData = Date.now();
  const consume = part => {
    const line = part.trim(); if (!line.startsWith("data:")) return;
    const payload = line.slice(5).trim(); if (payload === "[DONE]") { doneSignal = true; return; }
    let data; try { data = JSON.parse(payload); } catch { throw new Error("Respuesta inválida del asistente"); }
    if (data.c) { received = true; onToken(data.c); lastData = Date.now(); return; }
    if (data.error) throw new Error(typeof data.error === "string" ? data.error : "El asistente encontró un error");
  };
  try {
    for (;;) {
      if (Date.now() - lastData > 20000) { try { await reader.cancel(); } catch {} throw new Error("Pyme tardó demasiado en responder. Puedes reintentar."); }
      const { done, value } = await reader.read(); if (done) break;
      lastData = Date.now(); buf += dec.decode(value, { stream: true });
      const parts = buf.split(/\r?\n\r?\n/); buf = parts.pop() || ""; for (const part of parts) consume(part);
    }
    buf += dec.decode(); if (buf.trim()) consume(buf);
  } finally { reader.releaseLock(); }
  if (!received) throw new Error("Pyme no devolvió contenido. Puedes reintentar.");
  onDone?.(doneSignal);
}

export default api;
