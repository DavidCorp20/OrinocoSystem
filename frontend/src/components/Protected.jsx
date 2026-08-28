import { Navigate, useLocation } from "react-router-dom";
import { Store } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export function LoadingScreen() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-3 bg-background" data-testid="loading-screen">
      <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center animate-pulse">
        <Store className="w-6 h-6 text-white" />
      </div>
      <p className="text-sm text-muted-foreground font-medium">Cargando tu negocio…</p>
    </div>
  );
}

export default function Protected({ children, requireBusiness = true }) {
  const { status, business } = useAuth();
  const loc = useLocation();
  if (status === "loading") return <LoadingScreen />;
  if (status === "guest") return <Navigate to="/auth" replace state={{ from: loc.pathname }} />;
  if (requireBusiness && !business) return <Navigate to="/onboarding" replace />;
  if (!requireBusiness && business) return <Navigate to="/dashboard" replace />;
  return children;
}
