import { GameViewer } from "./components/GameViewer";
import { ThemeToggle } from "./components/ThemeToggle";
import { useTheme } from "./useTheme";

export function App() {
  const { dark, toggle } = useTheme();

  return (
    <div className="mx-auto max-w-4xl px-4 py-7">
      <header className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-medium text-ink">baseball-sim</h1>
          <p className="text-sm text-muted">
            Deterministic live game viewer — same seed, same game, every time.
          </p>
        </div>
        <ThemeToggle dark={dark} onToggle={toggle} />
      </header>
      <GameViewer dark={dark} />
    </div>
  );
}
