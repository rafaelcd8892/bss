import { GameViewer } from "./components/GameViewer";

export function App() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <header className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-medium">baseball-sim</h1>
          <p className="text-sm text-neutral-500">
            Deterministic live game viewer — same seed, same game, every time.
          </p>
        </div>
        <span className="rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700">
          live sim
        </span>
      </header>
      <GameViewer />
    </div>
  );
}
