import { describe, expect, it } from "vitest";
import { METRIC_HINTS, METRIC_LABELS, METRIC_ORDER, QUALIFIER_UNIT, formatMetric } from "./metrics";

describe("formatMetric", () => {
  it("writes rate stats the way a baseball reader does", () => {
    expect(formatMetric("woba", 0.4231)).toBe(".423");
    expect(formatMetric("obp", 0.3985)).toBe(".399");
  });

  it("keeps the leading digit when a rate clears 1.000", () => {
    // OPS regularly does; dropping the zero would print ".031" for a 1.031 season.
    expect(formatMetric("ops", 1.031)).toBe("1.031");
  });

  it("reads proportions stored as fractions as percentages", () => {
    expect(formatMetric("strikeout_rate", 0.2785)).toBe("27.9%");
    expect(formatMetric("ground_ball_rate", 0.358)).toBe("35.8%");
  });

  it("rounds wRC+ to a whole number, because it is an index", () => {
    expect(formatMetric("wrc_plus", 149.87)).toBe("150");
  });

  it("gives ERA-scale metrics two decimals", () => {
    expect(formatMetric("era", 3.0543)).toBe("3.05");
    expect(formatMetric("whip", 1.2317)).toBe("1.23");
  });
});

describe("metric metadata", () => {
  it("labels and explains every metric a leaderboard offers", () => {
    for (const metric of METRIC_ORDER) {
      expect(METRIC_LABELS[metric]).toBeTruthy();
      expect(METRIC_HINTS[metric]).toBeTruthy();
      expect(QUALIFIER_UNIT[metric]).toMatch(/^(PA|IP)$/);
    }
  });

  it("qualifies hitting metrics on plate appearances and pitching on innings", () => {
    expect(QUALIFIER_UNIT.ops).toBe("PA");
    expect(QUALIFIER_UNIT.whip).toBe("IP");
  });
});
