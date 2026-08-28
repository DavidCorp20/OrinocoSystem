import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Package, ArrowLeftRight, ShoppingCart, Truck, TrendingUp,
  FileText, Store, LogOut, Menu, Plus, Bot,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import AIAssistant from "./AIAssistant";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "./ui/sheet";

const NAV = [
  { label: "Dashboard", path: "/dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { label: "Productos", path: "/productos", icon: Package, testid: "nav-productos" },
  { label: "Movimientos", path: "/movimientos", icon: ArrowLeftRight, testid: "nav-movimientos" },
  { label: "Ventas", path: "/ventas", icon: ShoppingCart, testid: "nav-ventas" },
  { label: "Compras", path: "/compras", icon: Truck, testid: "nav-compras" },
  { label: "Finanzas", path: "/finanzas", icon: TrendingUp, testid: "nav-finanzas" },
  { label: "Reportes", path: "/reportes", icon: FileText, testid: "nav-reportes" },
];

function NavItems({ onNavigate, mobile = false }) {
  return (
    <nav className="flex-1 px-3 py-4 space-y-1">
      {NAV.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          data-testid={mobile ? `${item.testid}-mobile` : item.testid}
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors ${
              isActive ? "bg-white/10 text-white border-l-2 border-emerald-400" : "text-slate-400 hover:text-white hover:bg-white/5"
            }`
          }
        >
          <item.icon className="w-4.5 h-4.5 w-5 h-5 shrink-0" />
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

function SidebarContent({ onNavigate, mobile = false }) {
  const { user, business, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="flex flex-col h-full bg-[#0F172A]">
      <div className="px-5 py-5 flex items-center gap-3 border-b border-white/10">
        <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center shrink-0">
          <Store className="w-5 h-5 text-white" />
        </div>
        <div className="min-w-0">
          <p className="font-heading font-extrabold text-white text-base leading-tight">ControlPyme</p>
          <p className="text-xs text-slate-400 truncate" data-testid="sidebar-business-name">{business?.name}</p>
        </div>
      </div>
      <NavItems onNavigate={onNavigate} mobile={mobile} />
      <div className="p-4 border-t border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-emerald-700 flex items-center justify-center text-white text-sm font-bold shrink-0">
            {(user?.name || "U")[0].toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-white truncate">{user?.name}</p>
            <p className="text-xs text-slate-400 truncate">{user?.email}</p>
          </div>
          <button
            data-testid="logout-btn"
            title="Cerrar sesión"
            onClick={async () => { await logout(); navigate("/auth"); }}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Layout() {
  const { business } = useAuth();
  const [aiOpen, setAiOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      <aside className="hidden lg:block fixed inset-y-0 left-0 w-64 z-40">
        <SidebarContent />
      </aside>

      <div className="lg:pl-64 flex flex-col min-h-screen">
        <header className="sticky top-0 z-30 bg-background/85 backdrop-blur-md border-b border-border">
          <div className="px-4 sm:px-6 lg:px-8 h-16 flex items-center gap-3">
            <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
              <SheetTrigger asChild>
                <button data-testid="mobile-menu-btn" className="lg:hidden p-2 rounded-lg hover:bg-secondary transition-colors">
                  <Menu className="w-5 h-5" />
                </button>
              </SheetTrigger>
              <SheetContent side="left" aria-describedby={undefined} className="p-0 w-64 border-0 [&>button]:text-white/70 [&>button]:hover:text-white">
                <SheetTitle className="sr-only">Menú de navegación</SheetTitle>
                <SidebarContent mobile onNavigate={() => setMenuOpen(false)} />
              </SheetContent>
            </Sheet>

            <div className="flex-1 min-w-0">
              <p className="font-heading font-bold text-slate-900 truncate" data-testid="header-business-name">{business?.name}</p>
              <p className="text-xs text-muted-foreground">Moneda: {business?.currency || "USD"}</p>
            </div>

            <button
              data-testid="ai-assistant-launcher"
              onClick={() => setAiOpen(true)}
              className="hidden sm:flex items-center gap-2 text-xs font-semibold bg-slate-900 text-white px-3.5 py-2 rounded-full hover:bg-slate-800 transition-colors"
            >
              <Bot className="w-3.5 h-3.5" /> Preguntar a Pyme
            </button>
            <Link
              to="/compras?nueva=1"
              data-testid="quick-add-purchase-btn"
              className="hidden sm:flex items-center gap-1.5 text-xs font-semibold border border-border bg-card px-3.5 py-2 rounded-full hover:bg-secondary transition-colors"
            >
              <Plus className="w-3.5 h-3.5" /> Compra
            </Link>
            <Link
              to="/ventas?nueva=1"
              data-testid="quick-add-sale-btn"
              className="flex items-center gap-1.5 text-xs font-semibold bg-primary text-white px-3.5 py-2 rounded-full hover:bg-primary/90 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" /> Venta
            </Link>
          </div>
        </header>

        <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>

      {!aiOpen && (
        <button
          data-testid="ai-assistant-fab"
          onClick={() => setAiOpen(true)}
          className="fixed bottom-5 right-5 z-40 w-14 h-14 rounded-full bg-slate-900 text-white shadow-xl flex items-center justify-center hover:scale-105 transition-transform"
        >
          <Bot className="w-6 h-6" />
        </button>
      )}
      <AIAssistant open={aiOpen} onClose={() => setAiOpen(false)} />
    </div>
  );
}
