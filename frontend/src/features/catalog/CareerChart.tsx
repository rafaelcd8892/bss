import { useMemo, useState } from "react";
import type { components } from "../../api/schema";
import { Card } from "../../components/Card";
import { METRIC_HINTS, METRIC_LABELS, formatMetric, type AnyMetric } from "../analyze/metrics";

type Line = components["schemas"]["PlayerSeasonLine"];
type SeasonLines = components["schemas"]["SeasonLines"];

/** Metrics worth tracking across a career, per stat group. */
const HITTING: AnyMetric[] = ["woba", "wrc_plus", "ops", "obp", "slg", "iso", "babip"];
const PITCHING: AnyMetric[] = ["fip", "era", "whip", "k_bb_ratio", "strikeout_rate"];

/** Metrics where a lower number is the better one, so the axis reads inverted. */
const LOWER_IS_BETTER = new Set<AnyMetric>(["fip", "era", "whip", "walk_rate"]);

type Point = { season: number; value: number };

function series(seasons: SeasonLines[], group: Line["stat_group"], metric: AnyMetric): Point[] {
  const points: Point[] = [];
  for (const entry of seasons) {
    const line = entry.lines.find((candidate) => candidate.stat_group === group);
    const value = line?.[metric as keyof Line];
    if (typeof value === "number") points.push({ season: entry.season, value });
  }
  // Oldest first: a career reads left to right.
  return points.sort((a, b) => a.season - b.season);
}

export function CareerChart({
  seasons,
  accent,
}: {
  seasons: SeasonLines[];
  accent: string;
}) {
  const groups = useMemo(() => {
    const present = new Set(seasons.flatMap((s) => s.lines.map((l) => l.stat_group)));
    return (["hitting", "pitching"] as const).filter((g) => present.has(g));
  }, [seasons]);
  const [group, setGroup] = useState<Line["stat_group"]>(() => groups[0] ?? "hitting");
  const available = group === "hitting" ? HITTING : PITCHING;
  const [metric, setMetric] = useState<AnyMetric>(available[0]);

  const points = useMemo(() => series(seasons, group, metric), [seasons, group, metric]);

  // A single season is a dot, not a trajectory. Say so rather than drawing a flat line
  // that looks like a finding.
  if (seasons.length < 2) {
    return (
      <Card className="px-4 py-4">
        <p className="text-[13px] text-muted">
          Only one ingested season, so there is no career to plot yet.
        </p>
        <p className="mt-1.5 text-xs text-faint">
          Run the ingestion with <span className="font-mono">--history</span> to backfill
          whole careers.
        </p>
      </Card>
    );
  }

  return (
    <Card padded={false}>
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-3.5 py-2.5">
        <span className="text-sm font-medium text-ink">Career</span>
        {groups.length > 1 && (
          <div className="flex gap-1">
            {groups.map((name) => (
              <button
                key={name}
                onClick={() => {
                  setGroup(name);
                  setMetric((name === "hitting" ? HITTING : PITCHING)[0]);
                }}
                aria-pressed={group === name}
                className={`rounded-md border border-line px-2 py-0.5 text-[11px] transition-colors hover:text-ink ${
                  group === name ? "border-ink bg-ink text-app hover:text-app" : "text-muted"
                }`}
              >
                {name}
              </button>
            ))}
          </div>
        )}
        <div className="ml-auto flex flex-wrap gap-1">
          {available.map((name) => (
            <button
              key={name}
              onClick={() => setMetric(name)}
              aria-pressed={metric === name}
              title={METRIC_HINTS[name]}
              className={`rounded-md border border-line px-1.5 py-0.5 text-[11px] transition-colors hover:text-ink ${
                metric === name ? "border-ink bg-ink text-app hover:text-app" : "text-muted"
              }`}
            >
              {METRIC_LABELS[name]}
            </button>
          ))}
        </div>
      </div>
      {points.length < 2 ? (
        <p className="px-3.5 py-5 text-[13px] text-muted">
          No {METRIC_LABELS[metric]} recorded across enough seasons to plot.
        </p>
      ) : (
        <Trajectory points={points} metric={metric} accent={accent} />
      )}
    </Card>
  );
}

const WIDTH = 640;
const HEIGHT = 180;
const PAD = { top: 14, right: 14, bottom: 24, left: 44 };

function Trajectory({
  points,
  metric,
  accent,
}: {
  points: Point[];
  metric: AnyMetric;
  accent: string;
}) {
  const values = points.map((p) => p.value);
  const low = Math.min(...values);
  const high = Math.max(...values);
  // A flat career would divide by zero; give it a band so the line sits mid-height.
  const span = high - low || Math.abs(high) || 1;
  const inverted = LOWER_IS_BETTER.has(metric);

  const plotW = WIDTH - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const x = (index: number) =>
    PAD.left + (points.length === 1 ? plotW / 2 : (index / (points.length - 1)) * plotW);
  const y = (value: number) => {
    const fraction = (value - low) / span;
    // Better is always higher on the chart, whichever direction the metric runs.
    return PAD.top + (inverted ? fraction : 1 - fraction) * plotH;
  };

  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.value)}`).join(" ");
  const best = inverted ? low : high;

  return (
    <div className="overflow-x-auto px-2 py-2">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="w-full min-w-[420px]"
        role="img"
        aria-label={`${METRIC_LABELS[metric]} by season, ${points[0].season} to ${points[points.length - 1].season}`}
      >
        <line
          x1={PAD.left} x2={WIDTH - PAD.right}
          y1={y(best)} y2={y(best)}
          stroke="var(--color-line)" strokeDasharray="3 3"
        />
        <text x={PAD.left - 6} y={y(best) + 3} textAnchor="end"
              className="fill-[var(--color-faint)] text-[9px] font-mono">
          {formatMetric(metric, best)}
        </text>
        <path d={path} fill="none" stroke={accent} strokeWidth={2} strokeLinejoin="round" />
        {points.map((point, index) => (
          <g key={point.season}>
            <circle cx={x(index)} cy={y(point.value)} r={3} fill={accent}>
              <title>{`${point.season}: ${formatMetric(metric, point.value)}`}</title>
            </circle>
            {/* Label only the ends and the best year: a twenty-year career would
                otherwise stack unreadable text along the axis. */}
            {(index === 0 || index === points.length - 1 || point.value === best) && (
              <text x={x(index)} y={HEIGHT - 8} textAnchor="middle"
                    className="fill-[var(--color-faint)] text-[9px] font-mono">
                {point.season}
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}
