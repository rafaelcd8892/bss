import { describe, expect, it } from "vitest";
import { formatMetric, goodnessRatio } from "./metrics";

describe("formatMetric", () => {
  it("writes rate stats without the leading zero, as baseball does", () => {
    expect(formatMetric("woba", 0.4233)).toBe(".423");
    expect(formatMetric("xwoba", 0.281)).toBe(".281");
  });

  it("rounds wRC+ to a whole number", () => {
    expect(formatMetric("wrc_plus", 174.6)).toBe("175");
    expect(formatMetric("wrc_plus", 100)).toBe("100");
  });

  it("shows ERA-scale and ratio stats to two places", () => {
    expect(formatMetric("fip", 3.291)).toBe("3.29");
    expect(formatMetric("k_bb_ratio", 7.227)).toBe("7.23");
  });
});

describe("goodnessRatio", () => {
  it("gives the full bar to the higher value when higher is better", () => {
    expect(goodnessRatio("higher_is_better", 10, 5)).toBe(1);
    expect(goodnessRatio("higher_is_better", 5, 10)).toBe(0.5);
  });

  it("gives the full bar to the LOWER value when lower is better", () => {
    // Without this, FIP would draw the worse pitcher with the longer bar.
    expect(goodnessRatio("lower_is_better", 2, 4)).toBe(1);
    expect(goodnessRatio("lower_is_better", 4, 2)).toBe(0.5);
  });

  it("never returns a negative or infinite width", () => {
    expect(goodnessRatio("higher_is_better", 0, 0)).toBe(0);
    expect(goodnessRatio("lower_is_better", 0, 5)).toBe(0);
    expect(goodnessRatio("lower_is_better", 5, 0)).toBe(0);
  });
});
