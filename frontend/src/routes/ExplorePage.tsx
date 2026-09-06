import { Outlet, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/AppShell";

/** Layout for the catalog section; forwards the shell context to nested pages. */
export function ExplorePage() {
  const context = useOutletContext<ShellContext>();
  return <Outlet context={context} />;
}
