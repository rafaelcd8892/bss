import { NavLink, Outlet, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/AppShell";
import { CompareView } from "../features/analyze/CompareView";
import { LeadersView } from "../features/analyze/LeadersView";
import { TeamsView } from "../features/analyze/TeamsView";

const TABS = [
  { to: "/analyze/compare", label: "Compare" },
  { to: "/analyze/leaders", label: "Leaders" },
  { to: "/analyze/teams", label: "Teams" },
];

export function AnalyzePage() {
  // Forward the shell context so nested views still receive the theme.
  const context = useOutletContext<ShellContext>();
  return (
    <div className="flex flex-col gap-3">
      <nav className="flex gap-0.5" aria-label="Analyze views">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              `rounded-md px-2.5 py-1 text-xs transition-colors ${
                isActive
                  ? "border border-line bg-surface font-medium text-ink"
                  : "text-muted hover:text-ink"
              }`
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <Outlet context={context} />
    </div>
  );
}

export function AnalyzeCompare() {
  return <CompareView />;
}

export function AnalyzeLeaders() {
  return <LeadersView />;
}

export function AnalyzeTeams() {
  return <TeamsView />;
}
