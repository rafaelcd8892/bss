import { describe, expect, it } from "vitest";
import type { Play } from "../../api/client";
import { winProbability } from "./winprob";

function play(overrides: Partial<Play> = {}): Play {
  return {
    play_index: 1,
    inning: 1,
    half: "top",
    batting_team_id: 121,
    fielding_team_id: 147,
    event: "out",
    outs_before: 0,
    outs_after: 1,
    bases_before: "000",
    bases_after: "000",
    runs_scored_on_play: 0,
    home_score_after_play: 0,
    away_score_after_play: 0,
    description: "",
    ...overrides,
  };
}

describe("winProbability", () => {
  it("is an even split before the first play", () => {
    expect(winProbability(null, 9)).toEqual({ home: 0.5, final: false });
  });

  it("settles to a decided result once no outs remain", () => {
    const walkoff = play({
      inning: 9,
      half: "bottom",
      outs_after: 3,
      home_score_after_play: 5,
      away_score_after_play: 3,
    });
    expect(winProbability(walkoff, 9)).toEqual({ home: 1, final: true });
  });

  it("does not call the game after the top of the ninth — the home team still bats", () => {
    const topNinth = play({ inning: 9, half: "top", outs_after: 3 });
    expect(winProbability(topNinth, 9).final).toBe(false);
  });

  it("moves toward the team that is ahead", () => {
    const homeAhead = winProbability(
      play({ inning: 7, half: "bottom", home_score_after_play: 6, away_score_after_play: 1 }),
      9,
    );
    const awayAhead = winProbability(
      play({ inning: 7, half: "bottom", home_score_after_play: 1, away_score_after_play: 6 }),
      9,
    );
    expect(homeAhead.home).toBeGreaterThan(0.8);
    expect(awayAhead.home).toBeLessThan(0.2);
  });

  it("is less certain about the same lead earlier in the game", () => {
    const early = winProbability(play({ inning: 2, half: "bottom", home_score_after_play: 2 }), 9);
    const late = winProbability(play({ inning: 8, half: "bottom", home_score_after_play: 2 }), 9);
    expect(late.home).toBeGreaterThan(early.home);
  });

  it("credits the batting team for runners on base", () => {
    const empty = winProbability(play({ inning: 5, half: "bottom", bases_after: "000" }), 9);
    const loaded = winProbability(play({ inning: 5, half: "bottom", bases_after: "111" }), 9);
    expect(loaded.home).toBeGreaterThan(empty.home);
  });

  it("never reports absolute certainty while the game is live", () => {
    const blowout = winProbability(
      play({ inning: 3, half: "top", home_score_after_play: 20, away_score_after_play: 0 }),
      9,
    );
    expect(blowout.home).toBeLessThanOrEqual(0.99);
    expect(blowout.final).toBe(false);
  });

  it("is a pure function of the play", () => {
    const sample = play({ inning: 6, half: "bottom", home_score_after_play: 3 });
    expect(winProbability(sample, 9)).toEqual(winProbability(sample, 9));
  });
});
