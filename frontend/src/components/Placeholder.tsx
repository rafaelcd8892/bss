import { Card } from "./Card";

type PlaceholderProps = {
  title: string;
  description: string;
  /** The API this screen will read from, so the gap is concrete rather than vague. */
  endpoint?: string;
  ready?: boolean;
};

/** Honest empty state for a screen that is routed but not built yet. */
export function Placeholder({ title, description, endpoint, ready = false }: PlaceholderProps) {
  return (
    <Card className="px-4 py-6">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-medium text-ink">{title}</h2>
        <span
          className={`rounded px-1.5 py-0.5 text-[11px] ${
            ready ? "bg-raised text-muted" : "bg-raised text-faint"
          }`}
        >
          {ready ? "data ready" : "not built yet"}
        </span>
      </div>
      <p className="mt-1.5 max-w-prose text-[13px] leading-relaxed text-muted">{description}</p>
      {endpoint && (
        <p className="mt-2 font-mono text-[11px] text-faint">
          backed by <span className="text-muted">{endpoint}</span>
        </p>
      )}
    </Card>
  );
}
