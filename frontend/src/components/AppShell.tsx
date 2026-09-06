import { NavLink, Outlet } from "react-router-dom";
import { useTheme } from "../useTheme";
import { ThemeToggle } from "./ThemeToggle";

/** Values the shell shares with every routed page. */
export type ShellContext = { dark: boolean };

const SECTIONS = [
  { to: "/game", label: "Game" },
  { to: "/analyze", label: "Analyze" },
  { to: "/explore", label: "Explore" },
];

export function AppShell() {
  const { dark, toggle } = useTheme();

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <header className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2">
        <NavLink to="/game" className="text-lg font-medium text-ink">
          baseball-sim
        </NavLink>
        <nav className="flex gap-0.5" aria-label="Sections">
          {SECTIONS.map((section) => (
            <NavLink
              key={section.to}
              to={section.to}
              className={({ isActive }) =>
                `rounded-md px-2.5 py-1.5 text-[13px] transition-colors ${
                  isActive ? "bg-raised font-medium text-ink" : "text-muted hover:text-ink"
                }`
              }
            >
              {section.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto">
          <ThemeToggle dark={dark} onToggle={toggle} />
        </div>
      </header>

      <Outlet context={{ dark } satisfies ShellContext} />
    </div>
  );
}
