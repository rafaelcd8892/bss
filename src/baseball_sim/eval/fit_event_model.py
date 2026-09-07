"""Fit the event model against what really happened.

    python -m baseball_sim.eval.fit_event_model --season 2026

ADR-020 recorded the engine's constants as documented starting points rather than
fitted ones, and ADR-004 asks that the difference be closed by measurement. Season
simulation (ADR-027) supplied the measurement; this closes it.

Two targets, both taken from the ingested games rather than from memory:

- **run environment** — runs per team per game across the real season.
- **talent spread** — the standard deviation of team win%, with binomial luck removed.
  Observed spread includes luck; the model's spread, averaged over many seasons, does
  not. Comparing them directly would ask the model to reproduce noise as if it were
  skill.

Two knobs, because the targets are close to independent:

- `sensitivity` scales every outcome's response to the matchup. It moves the spread and
  barely touches the run environment.
- `out_base_shift` moves the league-average out rate. It moves the run environment and
  barely touches the spread.

The search is a coarse sweep, not an optimizer. With two nearly independent knobs and
targets known to a few percent, anything cleverer would be false precision.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
from collections.abc import Sequence
from dataclasses import replace

from baseball_sim.config import get_settings
from baseball_sim.domain.catalog import PostgresCatalogRepository
from baseball_sim.domain.postgres_stats import build_stat_line_provider
from baseball_sim.sim.profiles import TeamProfile
from baseball_sim.sim.rulesets import (
    DEFAULT_RULESET,
    EventModel,
    EventRates,
    SimulationRuleset,
)
from baseball_sim.sim.season import ScheduledGame, project_seasons, simulate_season

_SENSITIVITY_GRID = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5)
_OUT_SHIFT_GRID = (0.0, -0.005, -0.010, -0.015, -0.020, -0.025)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit the event model to real results.")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--seasons",
        type=int,
        default=25,
        help="Seasons per grid point. More is slower and less noisy.",
    )
    return parser.parse_args()


def scaled_model(
    model: EventModel, *, sensitivity: float, out_base_shift: float
) -> EventModel:
    """Scale every sensitivity, and shift the out base.

    Scaling leaves each base rate alone, so the league average is untouched and only
    the gap between clubs narrows. The bounds scale with it: a clamp sized for the old
    sensitivity would bite at the wrong place under the new one.
    """

    def tune(rates: EventRates, *, shift: float = 0.0) -> EventRates:
        base = rates.base + shift
        span_low = (rates.base - rates.minimum) * sensitivity
        span_high = (rates.maximum - rates.base) * sensitivity
        return replace(
            rates,
            base=base,
            sensitivity=rates.sensitivity * sensitivity,
            minimum=max(0.0, base - span_low),
            maximum=min(1.0, base + span_high),
        )

    return replace(
        model,
        out=tune(model.out, shift=out_base_shift),
        walk=tune(model.walk),
        single=tune(model.single),
        double=tune(model.double),
        triple=tune(model.triple),
        home_run=tune(model.home_run),
    )


def real_targets(*, dsn: str, season: int) -> tuple[float, float, int]:
    """Runs per team per game, talent spread, and games per club — all measured."""

    import psycopg

    with psycopg.connect(dsn) as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT home_team_id, away_team_id, home_score, away_score
            FROM games
            WHERE season = %s AND status_text = 'Final'
              AND home_score IS NOT NULL AND away_score IS NOT NULL
            """,
            (season,),
        )
        rows = cursor.fetchall()

    runs: dict[int, int] = {}
    wins: dict[int, int] = {}
    played: dict[int, int] = {}
    total_runs = 0
    for home, away, home_score, away_score in rows:
        total_runs += home_score + away_score
        for team, scored, allowed in (
            (home, home_score, away_score),
            (away, away_score, home_score),
        ):
            runs[team] = runs.get(team, 0) + scored
            played[team] = played.get(team, 0) + 1
            wins[team] = wins.get(team, 0) + (1 if scored > allowed else 0)

    games_per_club = round(st.mean(played.values()))
    runs_per_game = total_runs / len(rows) / 2 if rows else 0.0
    win_pcts = [wins[t] / played[t] for t in played]
    observed_sd = st.pstdev(win_pcts)
    # Observed spread is talent and luck together. Luck over n games is binomial at
    # .500, so removing it in quadrature leaves what the model should reproduce.
    luck_sd = math.sqrt(0.25 / games_per_club) if games_per_club else 0.0
    talent_sd = math.sqrt(max(observed_sd**2 - luck_sd**2, 0.0))
    return runs_per_game, talent_sd, games_per_club


def measure(
    *,
    ruleset: SimulationRuleset,
    schedule: Sequence[ScheduledGame],
    profiles: dict[int, TeamProfile],
    seeds: Sequence[int],
    games_per_club: int,
) -> tuple[float, float]:
    """Simulated runs per game and talent spread under one candidate model."""

    one = simulate_season(seed=seeds[0], schedule=schedule, profiles=profiles, ruleset=ruleset)
    runs_per_game = (
        sum(s.runs_scored for s in one.standings) / sum(s.games for s in one.standings)
        if one.standings
        else 0.0
    )
    projections = project_seasons(
        seeds=list(seeds), schedule=schedule, profiles=profiles, ruleset=ruleset
    )
    talent_sd = st.pstdev([p.mean_wins / games_per_club for p in projections])
    return runs_per_game, talent_sd


def main() -> None:
    args = parse_args()
    settings = get_settings()
    dsn = args.dsn or settings.db_dsn
    season = args.season or settings.stats_season
    seed = args.seed if args.seed is not None else settings.default_seed

    target_runs, target_sd, games_per_club = real_targets(dsn=dsn, season=season)

    repository = PostgresCatalogRepository(dsn=dsn)
    try:
        schedule = repository.get_season_schedule(season=season)
    finally:
        repository.close()

    provider = build_stat_line_provider(dsn=dsn, season=season)
    team_ids = {g.home_team_id for g in schedule} | {g.away_team_id for g in schedule}
    profiles = {t: provider.team_profile(team_id=t, seed=seed) for t in sorted(team_ids)}
    seeds = [seed + offset for offset in range(args.seasons)]

    # Sensitivity first: it moves the spread and barely touches the run environment,
    # so fitting it before the base rate keeps the two searches from chasing each other.
    grid = []
    for sensitivity in _SENSITIVITY_GRID:
        candidate = replace(
            DEFAULT_RULESET,
            event_model=scaled_model(
                DEFAULT_RULESET.event_model, sensitivity=sensitivity, out_base_shift=0.0
            ),
        )
        runs, sd = measure(
            ruleset=candidate,
            schedule=schedule,
            profiles=profiles,
            seeds=seeds,
            games_per_club=games_per_club,
        )
        grid.append({"sensitivity": sensitivity, "runs_per_game": round(runs, 3),
                     "talent_sd": round(sd, 4), "sd_ratio": round(sd / target_sd, 2)})
    best_sensitivity = min(
        _SENSITIVITY_GRID,
        key=lambda s: abs(
            next(row["talent_sd"] for row in grid if row["sensitivity"] == s) - target_sd
        ),
    )

    shift_grid = []
    for shift in _OUT_SHIFT_GRID:
        candidate = replace(
            DEFAULT_RULESET,
            event_model=scaled_model(
                DEFAULT_RULESET.event_model,
                sensitivity=best_sensitivity,
                out_base_shift=shift,
            ),
        )
        runs, sd = measure(
            ruleset=candidate,
            schedule=schedule,
            profiles=profiles,
            seeds=seeds,
            games_per_club=games_per_club,
        )
        shift_grid.append({"out_base_shift": shift, "runs_per_game": round(runs, 3),
                           "talent_sd": round(sd, 4)})
    best_shift = min(
        _OUT_SHIFT_GRID,
        key=lambda s: abs(
            next(row["runs_per_game"] for row in shift_grid if row["out_base_shift"] == s)
            - target_runs
        ),
    )

    print(
        json.dumps(
            {
                "season": season,
                "games_per_club": games_per_club,
                "target_runs_per_game": round(target_runs, 3),
                "target_talent_sd": round(target_sd, 4),
                "seasons_per_grid_point": args.seasons,
                "sensitivity_sweep": grid,
                "out_shift_sweep": shift_grid,
                "fitted": {
                    "sensitivity": best_sensitivity,
                    "out_base_shift": best_shift,
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
