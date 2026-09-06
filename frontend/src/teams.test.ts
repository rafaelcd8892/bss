import { describe, expect, it } from "vitest";
import { matchupAccents, pairAccents, teamAccent, teamLabel } from "./teams";

const NYY = 147; // primary #0C2340, a near-black navy
const NYM = 121; // primary #002D72, also navy
const HOU = 117; // primary #EB6E1F, orange
const LAD = 119; // primary #005A9C, blue

describe("teamAccent", () => {
  it("keeps a club's primary colour when it has enough contrast", () => {
    expect(teamAccent(HOU, false)).toBe(teamLabel(HOU).primary);
    expect(teamAccent(HOU, true)).toBe(teamLabel(HOU).primary);
  });

  it("drops a near-black primary on a dark surface, where it would vanish", () => {
    expect(teamAccent(NYY, false)).toBe(teamLabel(NYY).primary);
    expect(teamAccent(NYY, true)).not.toBe(teamLabel(NYY).primary);
  });

  it("falls back to a neutral for an unknown club", () => {
    expect(teamAccent(999999, false)).toMatch(/^#[0-9a-f]{6}$/i);
  });
});

describe("pairAccents", () => {
  it("separates two clubs whose primaries are both navy", () => {
    // Without disambiguation these render as the same colour on a shared bar.
    const { first, second } = pairAccents(NYY, NYM, false);
    expect(first).not.toBe(second);
  });

  it("separates two clubs that both resolve to orange on a dark surface", () => {
    // NYM's navy falls back to its orange secondary in dark mode, colliding with
    // Houston's orange primary — the case that shipped broken in Compare.
    const { first, second } = pairAccents(NYM, HOU, true);
    expect(first).not.toBe(second);
  });

  it("leaves already-distinct clubs on their own colours", () => {
    const { first, second } = pairAccents(HOU, LAD, false);
    expect(first).toBe(teamAccent(HOU, false));
    expect(second).toBe(teamAccent(LAD, false));
  });

  it("is stable for a given pair and theme", () => {
    expect(pairAccents(NYY, NYM, true)).toEqual(pairAccents(NYY, NYM, true));
  });
});

describe("matchupAccents", () => {
  it("maps the generic pair onto home and away", () => {
    const pair = pairAccents(NYY, NYM, true);
    expect(matchupAccents(NYY, NYM, true)).toEqual({ home: pair.first, away: pair.second });
  });
});
