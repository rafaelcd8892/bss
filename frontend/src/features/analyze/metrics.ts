import type { LeaderMetric } from "../../api/client";

/** Every metric the compare endpoint reports. Leaderboards use a subset. */
export type CompareMetric = "woba" | "xwoba" | "wrc_plus" | "fip" | "k_bb_ratio";

export const METRIC_LABELS: Record<CompareMetric, string> = {
  woba: "wOBA",
  xwoba: "xwOBA",
  wrc_plus: "wRC+",
  fip: "FIP",
  k_bb_ratio: "K/BB",
};

/** One-line reminder of what each metric measures, shown on hover. */
export const METRIC_HINTS: Record<CompareMetric, string> = {
  woba: "Weighted on-base average — offensive value per plate appearance.",
  xwoba: "Expected wOBA from batted-ball quality (needs Statcast).",
  wrc_plus: "Weighted runs created, league-relative. 100 is average.",
  fip: "Fielding independent pitching, on the ERA scale. Lower is better.",
  k_bb_ratio: "Strikeouts per walk.",
};

/** Playing-time unit each metric qualifies on, used to label the control. */
export const QUALIFIER_UNIT: Record<LeaderMetric, "PA" | "IP"> = {
  woba: "PA",
  wrc_plus: "PA",
  fip: "IP",
  k_bb_ratio: "IP",
};

export const METRIC_ORDER: LeaderMetric[] = ["woba", "wrc_plus", "fip", "k_bb_ratio"];
export const COMPARE_METRIC_ORDER: CompareMetric[] = [
  "woba",
  "xwoba",
  "wrc_plus",
  "fip",
  "k_bb_ratio",
];

/** Render a metric the way a baseball reader expects to see it. */
export function formatMetric(metric: CompareMetric, value: number): string {
  switch (metric) {
    case "woba":
    case "xwoba":
      // Rate stats below 1 are written without the leading zero: .423
      return value.toFixed(3).replace(/^0\./, ".");
    case "wrc_plus":
      return Math.round(value).toString();
    default:
      return value.toFixed(2);
  }
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
