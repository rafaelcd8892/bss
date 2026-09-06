import { NavLink, Outlet } from "react-router-dom";
import { Placeholder } from "../components/Placeholder";

const TABS = [
  { to: "/analyze/compare", label: "Compare" },
  { to: "/analyze/leaders", label: "Leaders" },
  { to: "/analyze/teams", label: "Teams" },
];

export function AnalyzePage() {
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
      <Outlet />
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
  return (
    <Placeholder
      ready
      title="Leaders"
      description="Top players by an ingested sabermetric, with the playing-time qualifier
        visible and adjustable. FIP is ranked ascending because lower is better."
      endpoint="GET /api/v1/stats/leaders"
    />
  );
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
