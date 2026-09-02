import { Lock, ArrowUpRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function PlanGuard({ feature, children }) {
  const { entitlements, planName } = useAuth();
  const navigate = useNavigate();
  if (entitlements?.[feature] && entitlements[feature] !== "none") return children;
  return <div className="min-h-[420px] flex items-center justify-center"><div className="max-w-md text-center bg-card border rounded-2xl p-8 shadow-sm"><div className="mx-auto w-12 h-12 rounded-full bg-secondary flex items-center justify-center mb-4"><Lock className="w-6 h-6"/></div><h1 className="font-heading text-2xl font-extrabold">Función no incluida en tu plan</h1><p className="text-sm text-muted-foreground mt-2">Esta función pertenece a un plan superior. Actualmente tienes <b>{planName || "Básico"}</b>.</p><button onClick={()=>navigate("/suscripcion")} className="mt-6 inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold">Ver planes <ArrowUpRight className="w-4 h-4"/></button></div></div>;
}
