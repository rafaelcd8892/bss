import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";

/**
 * Render a routed view the way the app does: inside a router, under a layout that
 * supplies the shell context, so `useSearchParams` and `useOutletContext` both work.
 */
export function renderRouted(ui: ReactElement, { route = "/", dark = false } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route element={<Outlet context={{ dark }} />}>
          <Route path="*" element={ui} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}
