import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import {
  AnalyzeCompare,
  AnalyzeLeaders,
  AnalyzePage,
  AnalyzeTeams,
} from "./routes/AnalyzePage";
import { ExplorePage } from "./routes/ExplorePage";
import { GamePage } from "./routes/GamePage";
import { NotFoundPage } from "./routes/NotFoundPage";

/**
 * The viewer used to live at the root, so replay links look like
 * `/?home=147&away=121&seed=1234`. Carry the query across the redirect or every
 * link shared before routing existed would silently lose its matchup.
 */
function RootRedirect() {
  const { search } = useLocation();
  return <Navigate to={{ pathname: "/game", search }} replace />;
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/game" element={<GamePage />} />
          <Route path="/analyze" element={<AnalyzePage />}>
            <Route index element={<Navigate to="compare" replace />} />
            <Route path="compare" element={<AnalyzeCompare />} />
            <Route path="leaders" element={<AnalyzeLeaders />} />
            <Route path="teams" element={<AnalyzeTeams />} />
          </Route>
          <Route path="/explore" element={<ExplorePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
