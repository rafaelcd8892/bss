import type { LeaderMetric } from "../../api/client";

export const METRIC_LABELS: Record<LeaderMetric, string> = {
  woba: "wOBA",
  wrc_plus: "wRC+",
  fip: "FIP",
  k_bb_ratio: "K/BB",
};

/** Playing-time unit each metric qualifies on, used to label the control. */
export const QUALIFIER_UNIT: Record<LeaderMetric, "PA" | "IP"> = {
  woba: "PA",
  wrc_plus: "PA",
  fip: "IP",
  k_bb_ratio: "IP",
};

export const METRIC_ORDER: LeaderMetric[] = ["woba", "wrc_plus", "fip", "k_bb_ratio"];

/** Render a metric the way a baseball reader expects to see it. */
export function formatMetric(metric: LeaderMetric, value: number): string {
  switch (metric) {
    case "woba":
      // Rate stats below 1 are written without the leading zero: .423
      return value.toFixed(3).replace(/^0\./, ".");
    case "wrc_plus":
      return Math.round(value).toString();
    default:
      return value.toFixed(2);
  }
}
