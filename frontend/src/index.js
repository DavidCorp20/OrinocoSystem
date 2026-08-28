import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";

// Suprime el falso positivo de ResizeObserver (Recharts/Radix) que dispara el overlay de errores de CRA
const RO_PATTERN = /ResizeObserver loop/;
window.addEventListener("error", (e) => {
  if (RO_PATTERN.test(e.message || "")) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
});
const _consoleError = console.error;
console.error = (...args) => {
  if (args.some((a) => RO_PATTERN.test(String(a)))) return;
  _consoleError(...args);
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
