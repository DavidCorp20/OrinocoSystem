import { Navigate, useLocation } from "react-router-dom";
import { Store } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import FirstRunTour from "./FirstRunTour";

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

export function NoAccess() {
  return (
    <div className="bg-card border border-border rounded-2xl p-12 text-center" data-testid="no-access">
      <p className="font-heading font-bold text-lg text-slate-800">No tienes acceso a esta sección</p>
      <p className="text-sm text-muted-foreground mt-1">Pídele al propietario del negocio que ajuste tu rol en la sección Equipo.</p>
    </div>
  );
}

export default function Protected({ children, requireBusiness = true }) {
  const { status, user, business, isSuper } = useAuth();
  const loc = useLocation();

  if (status === "loading") return <LoadingScreen />;
  if (status === "guest") return <Navigate to="/auth" replace state={{ from: loc.pathname }} />;

  // A platform superadmin is not a tenant and therefore does not need a business.
  if (isSuper) return <>{children}</>;

  // The authenticated user carries the durable business_id. Do not send a user
  // back to onboarding just because the business object has not hydrated yet.
  const hasBusiness = Boolean(business || user?.business_id);

  if (requireBusiness && !hasBusiness) return <Navigate to="/onboarding" replace />;
  if (!requireBusiness && hasBusiness) return <Navigate to="/dashboard" replace />;

  return (
    <>
      {children}
      {requireBusiness && hasBusiness && <FirstRunTour />}
    </>
  );
}
