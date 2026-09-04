import React, { useEffect, useState } from "react";
import api from "../api";

export default function FinancialHealthCard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    api.get("/financial-health?days=90")
      .then((res) => alive && setData(res.data))
      .catch(() => alive && setError("No se pudo calcular la salud financiera."));
    return () => { alive = false; };
  }, []);

  if (error) return <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>;
  if (!data) return <div className="rounded-2xl border bg-white p-5 text-sm text-gray-500 animate-pulse">Calculando salud financiera…</div>;

  const score = Number(data.score || 0);
  const ring = score >= 80 ? "border-emerald-500 text-emerald-600" : score >= 65 ? "border-blue-500 text-blue-600" : score >= 50 ? "border-amber-500 text-amber-600" : "border-red-500 text-red-600";

  return (
    <section className="rounded-2xl border bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-5 md:flex-row md:items-center">
        <div className="flex items-center gap-4 md:w-1/3">
          <div className={`flex h-24 w-24 shrink-0 items-center justify-center rounded-full border-8 ${ring}`}>
            <div className="text-center"><div className="text-2xl font-bold">{score}</div><div className="text-[10px]">/ 100</div></div>
          </div>
          <div><h2 className="text-lg font-bold text-gray-900">Salud financiera</h2><p className="capitalize text-sm text-gray-500">Estado: {data.band}</p><p className="mt-1 text-xs text-gray-400">Últimos {data.period?.days || 90} días</p></div>
        </div>
        <div className="grid flex-1 grid-cols-2 gap-3 md:grid-cols-5">
          {(data.components || []).map((c) => (
            <div key={c.name} className="rounded-xl bg-gray-50 p-3"><div className="text-xs text-gray-500">{c.name}</div><div className="mt-1 text-lg font-bold">{c.score}</div><div className="mt-1 text-[11px] leading-tight text-gray-400">{c.explanation}</div></div>
          ))}
        </div>
      </div>
      {(data.alerts || []).length > 0 && <div className="mt-5 rounded-xl bg-amber-50 p-4"><div className="font-semibold text-amber-800">Atención</div><ul className="mt-1 list-disc pl-5 text-sm text-amber-700">{data.alerts.map((a) => <li key={a}>{a}</li>)}</ul></div>}
      <p className="mt-4 text-[11px] text-gray-400">Indicador interno de PLATIA; no constituye un credit score ni una decisión crediticia.</p>
    </section>
  );
}
