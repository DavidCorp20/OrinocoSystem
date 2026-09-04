import Dashboard from "./Dashboard";
import FinancialInsightsCard from "../components/FinancialInsightsCard";
import FinancialHealthCard from "../components/FinancialHealthCard";
import { useAuth } from "../context/AuthContext";

export default function DashboardWithInsights() {
  const { business } = useAuth();
  return (
    <div className="space-y-5">
      <Dashboard />
      <FinancialInsightsCard currency={business?.currency || "USD"} />
      <FinancialHealthCard />
    </div>
  );
}
