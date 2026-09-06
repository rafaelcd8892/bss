import type { Play } from "../../api/client";

/**
 * Baseline win-probability model — explainable, not calibrated.
 *
 * Follows ADR-004 (explainable baselines before complex models). The estimate is a
 * logistic on the projected final run differential:
 *
 *   1. Each team's expected remaining runs = league scoring rate x outs they have left.
 *   2. The batting team additionally gets the run expectancy of the current base/out
 *      state (a simplified RE24 table), which covers the rest of the current inning.
 *   3. margin = (home runs + home projection) - (away runs + away projection)
 *   4. Uncertainty shrinks as outs run out: sigma scales with sqrt(outs remaining).
 *   5. wp(home) = logistic(margin / sigma)
 *
 * It is deterministic and derived only from the play state, so it replays exactly.
 * It is NOT a trained model: treat it as a readable heuristic, not a forecast.
 */

/** League-average scoring: ~4.5 runs per 27 outs. */
const RUNS_PER_OUT = 4.5 / 27;

/** Spread of remaining-run differential, per out remaining. */
const RUN_SD_PER_OUT = 0.41;

/** Simplified RE24: expected runs for the rest of the inning, by base state and outs. */
const RUN_EXPECTANCY: Record<string, [number, number, number]> = {
  "000": [0.48, 0.25, 0.1],
  "100": [0.85, 0.5, 0.22],
  "010": [1.06, 0.65, 0.31],
  "110": [1.43, 0.88, 0.42],
  "001": [1.35, 0.94, 0.36],
  "101": [1.78, 1.14, 0.51],
  "011": [1.96, 1.36, 0.6],
  "111": [2.29, 1.54, 0.75],
};

export type WinProbability = {
  /** Home win probability in [0, 1]. */
  home: number;
  /** True once the game is decided, so the bar can show a settled result. */
  final: boolean;
};

function runExpectancy(bases: string, outs: number): number {
  const row = RUN_EXPECTANCY[bases] ?? RUN_EXPECTANCY["000"];
  return row[Math.min(Math.max(outs, 0), 2)] ?? 0;
}

export function winProbability(play: Play | null, scheduledInnings: number): WinProbability {
  if (!play) return { home: 0.5, final: false };

  const homeScore = play.home_score_after_play;
  const awayScore = play.away_score_after_play;
  const homeBatting = play.half === "bottom";

  // Full innings each side still bats after the current one.
  const inningsAfter = Math.max(scheduledInnings - play.inning, 0);
  const outsThisInning = Math.max(3 - play.outs_after, 0);

  // The batting team's current inning is covered by run expectancy, not by the rate.
  const battingOutsLater = inningsAfter * 3;
  const fieldingOutsLater = homeBatting ? inningsAfter * 3 : (inningsAfter + 1) * 3;

  const battingProjection =
    runExpectancy(play.bases_after, play.outs_after) + RUNS_PER_OUT * battingOutsLater;
  const fieldingProjection = RUNS_PER_OUT * fieldingOutsLater;

  const homeProjection = homeBatting ? battingProjection : fieldingProjection;
  const awayProjection = homeBatting ? fieldingProjection : battingProjection;

  const outsRemaining = outsThisInning + battingOutsLater + fieldingOutsLater;
  if (outsRemaining <= 0 || play.event === "tiebreaker") {
    return { home: homeScore > awayScore ? 1 : 0, final: true };
  }

  const margin = homeScore + homeProjection - (awayScore + awayProjection);
  const sigma = Math.max(0.8, RUN_SD_PER_OUT * Math.sqrt(outsRemaining));
  const home = 1 / (1 + Math.exp(-margin / sigma));

  return { home: Math.min(0.99, Math.max(0.01, home)), final: false };
}
