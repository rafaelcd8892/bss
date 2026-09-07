import type { LeaderMetric } from "../../api/client";

/** Every metric the compare endpoint reports. Leaderboards use a wider set. */
export type CompareMetric = "woba" | "xwoba" | "wrc_plus" | "fip" | "k_bb_ratio";

/** Every metric with a stored value, whether or not it has a leaderboard. */
export type AnyMetric = LeaderMetric | CompareMetric | "ground_ball_rate" | "x_slg";

export const METRIC_LABELS: Record<AnyMetric, string> = {
  woba: "wOBA",
  xwoba: "xwOBA",
  wrc_plus: "wRC+",
  fip: "FIP",
  k_bb_ratio: "K/BB",
  obp: "OBP",
  slg: "SLG",
  ops: "OPS",
  iso: "ISO",
  babip: "BABIP",
  era: "ERA",
  whip: "WHIP",
  strikeout_rate: "K%",
  walk_rate: "BB%",
  ground_ball_rate: "GB%",
  x_slg: "xSLG",
};

/** One-line reminder of what each metric measures, shown on hover. */
export const METRIC_HINTS: Record<AnyMetric, string> = {
  woba: "Weighted on-base average — offensive value per plate appearance.",
  xwoba: "Expected wOBA from batted-ball quality, measured by Statcast.",
  wrc_plus: "Weighted runs created, league-relative. 100 is average.",
  fip: "Fielding independent pitching, on the ERA scale. Lower is better.",
  k_bb_ratio: "Strikeouts per walk.",
  obp: "On-base percentage.",
  slg: "Slugging — total bases per at-bat.",
  ops: "On-base plus slugging.",
  iso: "Isolated power: slugging minus batting average, so extra bases only.",
  babip: "Batting average on balls in play. Swings a lot with luck.",
  era: "Earned runs per nine innings. Lower is better.",
  whip: "Walks and hits per inning pitched. Lower is better.",
  strikeout_rate: "Share of batters faced struck out.",
  walk_rate: "Share of batters faced walked. Lower is better.",
  ground_ball_rate: "Ground outs as a share of batted-ball outs.",
  x_slg: "Expected slugging from batted-ball quality.",
};

/** Playing-time unit each leaderboard qualifies on, used to label the control. */
export const QUALIFIER_UNIT: Record<LeaderMetric, "PA" | "IP"> = {
  woba: "PA",
  xwoba: "PA",
  wrc_plus: "PA",
  obp: "PA",
  slg: "PA",
  ops: "PA",
  iso: "PA",
  babip: "PA",
  fip: "IP",
  era: "IP",
  whip: "IP",
  k_bb_ratio: "IP",
  strikeout_rate: "IP",
  walk_rate: "IP",
};

/** Hitting leaderboards first, then pitching, each in the order a reader scans them. */
export const METRIC_ORDER: LeaderMetric[] = [
  "woba",
  "xwoba",
  "wrc_plus",
  "obp",
  "slg",
  "ops",
  "iso",
  "babip",
  "era",
  "fip",
  "whip",
  "k_bb_ratio",
  "strikeout_rate",
  "walk_rate",
];

export const COMPARE_METRIC_ORDER: CompareMetric[] = [
  "woba",
  "xwoba",
  "wrc_plus",
  "fip",
  "k_bb_ratio",
];

/** Metrics written as a bare decimal, the way a baseball reader expects: .423 */
const RATE_METRICS = new Set<AnyMetric>([
  "woba",
  "xwoba",
  "obp",
  "slg",
  "ops",
  "iso",
  "babip",
  "x_slg",
]);

/** Metrics stored as a proportion but read as a percentage. */
const PERCENT_METRICS = new Set<AnyMetric>([
  "strikeout_rate",
  "walk_rate",
  "ground_ball_rate",
]);

/** Render a metric the way a baseball reader expects to see it. */
export function formatMetric(metric: AnyMetric, value: number): string {
  if (metric === "wrc_plus") return Math.round(value).toString();
  if (PERCENT_METRICS.has(metric)) return `${(value * 100).toFixed(1)}%`;
  // Anchored to the leading zero, so OPS keeps its digit when it clears 1.000.
  if (RATE_METRICS.has(metric)) return value.toFixed(3).replace(/^0\./, ".");
  return value.toFixed(2);
}

/**
 * Bar length as "how good", so a longer bar always means better regardless of
 * whether the metric rewards high or low values. Without this, FIP would draw the
 * worse pitcher with the longer bar.
 */
export function goodnessRatio(
  direction: "higher_is_better" | "lower_is_better",
  value: number,
  other: number,
): number {
  if (direction === "higher_is_better") {
    const best = Math.max(value, other);
    return best > 0 ? Math.max(value / best, 0) : 0;
  }
  const best = Math.min(value, other);
  return value > 0 && best > 0 ? best / value : 0;
}
