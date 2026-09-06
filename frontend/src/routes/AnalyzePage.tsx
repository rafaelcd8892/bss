import { NavLink, Outlet, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/AppShell";
import { Placeholder } from "../components/Placeholder";
import { LeadersView } from "../features/analyze/LeadersView";

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
  return (
    <Placeholder
      ready
      title="Compare players"
      description="Two players side by side across wOBA, xwOBA, wRC+, FIP and K/BB, with each
        metric marked as measured or seeded so a placeholder is never mistaken for data."
      endpoint="POST /api/v1/compare/players"
    />
  );
}

export function AnalyzeLeaders() {
  return <LeadersView />;
}

export function AnalyzeTeams() {
  return (
    <Placeholder
      ready
      title="Team profiles"
      description="The seven matchup factors the simulator actually consumes, alongside the
        aggregate wOBA and FIP behind them, so a team rating can be audited."
      endpoint="GET /api/v1/teams/{id}/profile"
    />
  );
}
