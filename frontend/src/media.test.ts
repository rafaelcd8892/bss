import { describe, expect, it } from "vitest";
import { playerHeadshotUrl, teamCapUrl, teamLogoUrl } from "./media";

describe("media urls", () => {
  it("derives a club logo from the id we already hold", () => {
    expect(teamLogoUrl(147)).toBe("https://www.mlbstatic.com/team-logos/147.svg");
  });

  it("picks a cap variant that reads on the current theme", () => {
    expect(teamCapUrl(147, false)).toContain("team-cap-on-light");
    expect(teamCapUrl(147, true)).toContain("team-cap-on-dark");
  });

  it("derives a headshot from the player id", () => {
    expect(playerHeadshotUrl(592450)).toBe(
      "https://midfield.mlbstatic.com/v1/people/592450/spots/120",
    );
  });

  it("only offers sizes the service actually renders", () => {
    expect(playerHeadshotUrl(1, 60)).toMatch(/\/spots\/60$/);
    expect(playerHeadshotUrl(1, 240)).toMatch(/\/spots\/240$/);
  });

  it("never points anywhere but MLB's own static hosts", () => {
    // These are MLBAM's materials, referenced rather than copied (ADR-025). A URL
    // built anywhere else would mean we started serving them ourselves.
    for (const url of [teamLogoUrl(147), teamCapUrl(147, true), playerHeadshotUrl(1)]) {
      expect(new URL(url).hostname).toMatch(/\.mlbstatic\.com$/);
    }
  });
});
