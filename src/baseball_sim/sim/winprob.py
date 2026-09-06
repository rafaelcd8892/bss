"""Baseline win probability — one model for both the pregame forecast and the
in-game number shown while a simulated game plays.

Explainable, not calibrated (ADR-004). The estimate is a logistic on the projected
final run differential:

1. Team quality becomes an expected runs-per-game rate: the offense factor of the
   batting side and the run-prevention factor of the opposing side each move the
   league average within a documented band.
2. Before first pitch there is no game state, so the projection is just those two
   rates plus a home-field allowance.
3. Once play starts, each side's projection is the runs it has already scored plus
   its rate applied to the outs it has left. The batting team additionally gets the
   run expectancy of the current base/out state, which covers the rest of its inning.
4. Uncertainty shrinks as outs run out: sigma scales with the square root of the outs
   remaining.

Every constant below is an initial value, not a fitted one. Step 2b measures them.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, sqrt
from typing import Literal

from baseball_sim.sim.profiles import TeamProfile

#: League-average team scoring, used as the centre of the run-rate band.
LEAGUE_RUNS_PER_GAME = 4.5

#: How far a maximal offense or defense factor moves a team off the league average.
#: Factors sit in [0, 1] with 0.5 as average, so each contributes at most +/-11%,
#: putting the extremes near 3.5 and 5.5 runs per game — the observed league spread.
OFFENSE_SWING = 0.22
PREVENTION_SWING = 0.22

#: Runs of advantage credited to the home side before first pitch.
HOME_FIELD_RUNS = 0.25

#: Spread of the remaining-run differential, per out still to be played.
RUN_SD_PER_OUT = 0.41

#: Floor so a one-run lead in the final out does not read as a coin flip.
MIN_SIGMA = 0.8

OUTS_PER_INNING = 3
OUTS_PER_GAME = 27

#: Simplified RE24: expected runs for the rest of the inning, by base state and outs.
#: Keys are on_first/on_second/on_third, matching the simulator's base encoding.
RUN_EXPECTANCY: dict[str, tuple[float, float, float]] = {
    "000": (0.48, 0.25, 0.10),
    "100": (0.85, 0.50, 0.22),
    "010": (1.06, 0.65, 0.31),
    "110": (1.43, 0.88, 0.42),
    "001": (1.35, 0.94, 0.36),
    "101": (1.78, 1.14, 0.51),
    "011": (1.96, 1.36, 0.60),
    "111": (2.29, 1.54, 0.75),
}


@dataclass(frozen=True)
class GameSituation:
    """Where a game stands after a play. Omit it entirely for a pregame forecast."""

    inning: int
    half: Literal["top", "bottom"]
    outs: int
    bases: str
    home_score: int
    away_score: int


@dataclass(frozen=True)
class WinProbability:
    home: float
    away: float
    #: Expected runs per game for each side, the inputs behind the number.
    home_expected_runs: float
    away_expected_runs: float
    #: True once the result can no longer change.
    final: bool


def expected_runs(*, offense: float, opposing_prevention: float) -> float:
    """Runs per game a team is expected to score against a given defense."""

    offense_effect = OFFENSE_SWING * (_clamp_unit(offense) - 0.5)
    prevention_effect = PREVENTION_SWING * (_clamp_unit(opposing_prevention) - 0.5)
    return LEAGUE_RUNS_PER_GAME * (1.0 + offense_effect - prevention_effect)


def team_run_rates(
    *, home_profile: TeamProfile, away_profile: TeamProfile
) -> tuple[float, float]:
    """Expected runs per game for (home, away) in this matchup."""

    home_rate = expected_runs(
        offense=home_profile.offense, opposing_prevention=away_profile.prevention
    )
    away_rate = expected_runs(
        offense=away_profile.offense, opposing_prevention=home_profile.prevention
    )
    return home_rate, away_rate


def run_expectancy(bases: str, outs: int) -> float:
    row = RUN_EXPECTANCY.get(bases, RUN_EXPECTANCY["000"])
    return row[min(max(outs, 0), 2)]


def win_probability(
    *,
    home_rate: float,
    away_rate: float,
    scheduled_innings: int = 9,
    situation: GameSituation | None = None,
) -> WinProbability:
    if situation is None:
        margin = home_rate - away_rate + HOME_FIELD_RUNS
        sigma = max(MIN_SIGMA, RUN_SD_PER_OUT * sqrt(OUTS_PER_GAME * 2))
        home = _logistic(margin / sigma)
        return WinProbability(
            home=round(home, 4),
            away=round(1.0 - home, 4),
            home_expected_runs=round(home_rate, 3),
            away_expected_runs=round(away_rate, 3),
            final=False,
        )

    home_batting = situation.half == "bottom"
    innings_after = max(scheduled_innings - situation.inning, 0)
    outs_this_inning = max(OUTS_PER_INNING - situation.outs, 0)

    # The batting team's current inning is covered by run expectancy, not by its rate.
    batting_outs_later = innings_after * OUTS_PER_INNING
    fielding_outs_later = (
        innings_after if home_batting else innings_after + 1
    ) * OUTS_PER_INNING

    batting_rate = home_rate if home_batting else away_rate
    fielding_rate = away_rate if home_batting else home_rate

    batting_projection = run_expectancy(situation.bases, situation.outs) + (
        batting_rate / OUTS_PER_GAME
    ) * batting_outs_later
    fielding_projection = (fielding_rate / OUTS_PER_GAME) * fielding_outs_later

    home_projection = batting_projection if home_batting else fielding_projection
    away_projection = fielding_projection if home_batting else batting_projection

    outs_remaining = outs_this_inning + batting_outs_later + fielding_outs_later
    if outs_remaining <= 0:
        decided = 1.0 if situation.home_score > situation.away_score else 0.0
        return WinProbability(
            home=decided,
            away=1.0 - decided,
            home_expected_runs=round(home_rate, 3),
            away_expected_runs=round(away_rate, 3),
            final=True,
        )

    margin = (situation.home_score + home_projection) - (
        situation.away_score + away_projection
    )
    sigma = max(MIN_SIGMA, RUN_SD_PER_OUT * sqrt(outs_remaining))
    home = min(0.99, max(0.01, _logistic(margin / sigma)))
    return WinProbability(
        home=round(home, 4),
        away=round(1.0 - home, 4),
        home_expected_runs=round(home_rate, 3),
        away_expected_runs=round(away_rate, 3),
        final=False,
    )


def _logistic(value: float) -> float:
    return 1.0 / (1.0 + exp(-value))


def _clamp_unit(value: float) -> float:
    return min(1.0, max(0.0, value))
