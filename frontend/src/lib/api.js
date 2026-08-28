import axios from "axios";

export const API_URL = `${process.env.REACT_APP_BACKEND_URL}/api`;

const api = axios.create({ baseURL: API_URL, withCredentials: true });

let refreshing = null;
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config || {};
    if (error.response?.status === 401 && !original._retry && !(original.url || "").startsWith("/auth/")) {
      original._retry = true;
      try {
        refreshing = refreshing || api.post("/auth/refresh");
        await refreshing;
        refreshing = null;
        return api(original);
      } catch (e) {
        refreshing = null;
      }
    }
    return Promise.reject(error);
  }
);

export function apiError(e, fallback = "Ocurrió un error. Intenta de nuevo.") {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => (x && x.msg) || "").filter(Boolean).join(" ");
  return fallback;
}

export async function downloadCsv(path, filename) {
  const res = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function streamChat(message, onToken) {
  const doFetch = () =>
    fetch(`${API_URL}/assistant/chat`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
  let res = await doFetch();
  if (res.status === 401) {
    await fetch(`${API_URL}/auth/refresh`, { method: "POST", credentials: "include" });
    res = await doFetch();
  }
  if (!res.ok || !res.body) throw new Error("chat failed");
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop();
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6);
      if (payload === "[DONE]") return;
      try {
        onToken(JSON.parse(payload).c || "");
      } catch {}
    }
  }
}

export default api;
