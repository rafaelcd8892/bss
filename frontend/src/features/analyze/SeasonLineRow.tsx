import type { components } from "../../api/schema";
import { formatMetric, METRIC_HINTS, METRIC_LABELS, type AnyMetric } from "./metrics";

type Line = components["schemas"]["PlayerSeasonLine"];

/** The descriptive stat line, beside the five the simulator actually consumes. */
const HITTING: AnyMetric[] = ["obp", "slg", "ops", "iso", "babip", "x_slg"];
const PITCHING: AnyMetric[] = ["era", "whip", "strikeout_rate", "walk_rate", "ground_ball_rate"];

const READ: Record<string, (line: Line) => number | null | undefined> = {
  obp: (l) => l.obp,
  slg: (l) => l.slg,
  ops: (l) => l.ops,
  iso: (l) => l.iso,
  babip: (l) => l.babip,
  x_slg: (l) => l.x_slg,
  era: (l) => l.era,
  whip: (l) => l.whip,
  strikeout_rate: (l) => l.strikeout_rate,
  walk_rate: (l) => l.walk_rate,
  ground_ball_rate: (l) => l.ground_ball_rate,
};

/**
 * A side-by-side season line.
 *
 * Deliberately separate from the head-to-head table above it. Those five metrics carry
 * provenance and decide a verdict; these are descriptive, all measured, and nobody
 * wins them — mixing the two would imply a verdict the numbers were never asked for.
 */
export function SeasonLineRow({
  left,
  right,
  group,
}: {
  left: Line | null;
  right: Line | null;
  group: "hitting" | "pitching";
}) {
  const metrics = group === "hitting" ? HITTING : PITCHING;
  const rows = metrics.filter(
    (metric) =>
      typeof READ[metric](left ?? ({} as Line)) === "number" ||
      typeof READ[metric](right ?? ({} as Line)) === "number",
  );
  if (rows.length === 0) return null;

  return (
    <div className="border-t border-line">
      <div className="px-3.5 pb-1 pt-2.5 text-[11px] text-faint">
        {group === "hitting" ? "hitting" : "pitching"} line · not scored
      </div>
      {rows.map((metric) => {
        const leftValue = left ? READ[metric](left) : null;
        const rightValue = right ? READ[metric](right) : null;
        return (
          <div
            key={metric}
            className="grid grid-cols-[minmax(0,1fr)_78px_minmax(0,1fr)] items-center gap-2 px-3.5 py-1"
          >
            <span className="text-right font-mono text-xs text-muted">
              {typeof leftValue === "number" ? formatMetric(metric, leftValue) : "—"}
            </span>
            <span
              className="text-center text-[11px] text-faint"
              title={METRIC_HINTS[metric]}
            >
              {METRIC_LABELS[metric]}
            </span>
            <span className="font-mono text-xs text-muted">
              {typeof rightValue === "number" ? formatMetric(metric, rightValue) : "—"}
            </span>
          </div>
        );
      })}
    </div>
  );
}
