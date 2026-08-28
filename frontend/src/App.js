import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import "@/App.css";
import { AuthProvider } from "@/context/AuthContext";
import Protected from "@/components/Protected";
import Layout from "@/components/Layout";
import AuthPage from "@/pages/AuthPage";
import Onboarding from "@/pages/Onboarding";
import Dashboard from "@/pages/Dashboard";
import Productos from "@/pages/Productos";
import Movimientos from "@/pages/Movimientos";
import Ventas from "@/pages/Ventas";
import Compras from "@/pages/Compras";
import Finanzas from "@/pages/Finanzas";
import Reportes from "@/pages/Reportes";

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/auth" element={<AuthPage />} />
            <Route
              path="/onboarding"
              element={
                <Protected requireBusiness={false}>
                  <Onboarding />
                </Protected>
              }
            />
            <Route
              element={
                <Protected>
                  <Layout />
                </Protected>
              }
            >
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/productos" element={<Productos />} />
              <Route path="/movimientos" element={<Movimientos />} />
              <Route path="/ventas" element={<Ventas />} />
              <Route path="/compras" element={<Compras />} />
              <Route path="/finanzas" element={<Finanzas />} />
              <Route path="/reportes" element={<Reportes />} />
            </Route>
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster richColors position="top-center" />
      </AuthProvider>
    </div>
  );
}

export default App;
