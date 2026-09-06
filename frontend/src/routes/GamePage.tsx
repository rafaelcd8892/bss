import { useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/AppShell";
import { GameViewer } from "../features/game/GameViewer";

export function GamePage() {
  const { dark } = useOutletContext<ShellContext>();
  return (
    <>
      <p className="mb-3 text-sm text-muted">
        Deterministic live game viewer — same seed, same game, every time.
      </p>
      <GameViewer dark={dark} />
    </>
  );
}
