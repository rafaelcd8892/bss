"""Simulate a full season, or many of them, against the real ingested schedule.

    python -m baseball_sim.eval.run_season --season 2026
    python -m baseball_sim.eval.run_season --season 2026 --seasons 1000

One season gives a standings table. Many give the distribution behind it, which is the
more honest reading: team strength is fixed across runs, so the whole spread is the
model's own noise. If a club's tenth and ninetieth percentile are fifteen wins apart,
then a fifteen-win gap in a single simulated standings table means nothing.

Every club's profile, batting order and staff are resolved once and reused for the
whole season — a club is the same club in April and September — which is what makes a
2,430-game season take about a second (ADR-026).
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping, Sequence

from baseball_sim.config import get_settings
from baseball_sim.domain.catalog import PostgresCatalogRepository
from baseball_sim.domain.lineup_provider import CatalogLineupProvider
from baseball_sim.domain.postgres_stats import build_stat_line_provider
from baseball_sim.sim.lineups import Batter
from baseball_sim.sim.pitching import PitchingStaff
from baseball_sim.sim.profiles import TeamProfile, synthetic_team_profile
from baseball_sim.sim.season import (
    ScheduledGame,
    TeamStanding,
    project_seasons,
    simulate_season,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate one or many seasons.")
    parser.add_argument("--season", type=int, default=None, help="Season to simulate.")
    parser.add_argument("--dsn", default=None, help="Override the database DSN.")
    parser.add_argument("--seed", type=int, default=None, help="Base seed.")
    parser.add_argument(
        "--seasons",
        type=int,
        default=1,
        help="How many seasons to play. More than one reports a projection.",
    )
    parser.add_argument(
        "--innings", type=int, default=9, help="Scheduled innings per game."
    )
    return parser.parse_args()


def _real_profiles(
    *, dsn: str, season: int, seed: int, team_ids: set[int]
) -> tuple[dict[int, TeamProfile], int]:
    """Each club's profile, and how many came from data rather than the seed."""

    provider = build_stat_line_provider(dsn=dsn, season=season)
    profiles: dict[int, TeamProfile] = {}
    real = 0
    for team_id in sorted(team_ids):
        profile = provider.team_profile(team_id=team_id, seed=seed)
        profiles[team_id] = profile
        if profile != synthetic_team_profile(seed=seed, team_id=team_id):
            real += 1
    return profiles, real


def _real_rosters(
    *, dsn: str, season: int, seed: int, team_ids: set[int]
) -> tuple[dict[int, list[Batter]], dict[int, PitchingStaff]]:
    provider = CatalogLineupProvider(dsn=dsn, season=season)
    lineups = {tid: provider.lineup(team_id=tid, seed=seed) for tid in sorted(team_ids)}
    staffs = {tid: provider.staff(team_id=tid, seed=seed) for tid in sorted(team_ids)}
    return lineups, staffs


def _standings_rows(
    result_standings: Sequence[TeamStanding], names: Mapping[int, str]
) -> list[dict[str, object]]:
    return [
        {
            "team": names.get(s.team_id, str(s.team_id)),
            "w": s.wins,
            "l": s.losses,
            "pct": round(s.win_percentage, 3),
            "rs": s.runs_scored,
            "ra": s.runs_allowed,
            "diff": s.run_differential,
        }
        for s in result_standings
    ]


def main() -> None:
    args = parse_args()
    settings = get_settings()
    dsn = args.dsn or settings.db_dsn
    season = args.season or settings.stats_season
    seed = args.seed if args.seed is not None else settings.default_seed

    repository = PostgresCatalogRepository(dsn=dsn)
    try:
        schedule: list[ScheduledGame] = repository.get_season_schedule(season=season)
        names = {team.team_id: team.abbreviation or team.name for team in repository.list_teams()}
    finally:
        repository.close()

    team_ids = {game.home_team_id for game in schedule} | {
        game.away_team_id for game in schedule
    }
    profiles, real_profiles = _real_profiles(
        dsn=dsn, season=season, seed=seed, team_ids=team_ids
    )
    lineups, staffs = _real_rosters(dsn=dsn, season=season, seed=seed, team_ids=team_ids)

    started = time.perf_counter()
    if args.seasons == 1:
        result = simulate_season(
            seed=seed,
            schedule=schedule,
            profiles=profiles,
            lineups=lineups,
            staffs=staffs,
            scheduled_innings=args.innings,
        )
        payload: dict[str, object] = {
            "mode": "single_season",
            "games_played": result.games_played,
            "standings": _standings_rows(result.standings, names),
        }
    else:
        projections = project_seasons(
            seeds=[seed + offset for offset in range(args.seasons)],
            schedule=schedule,
            profiles=profiles,
            lineups=lineups,
            staffs=staffs,
            scheduled_innings=args.innings,
        )
        payload = {
            "mode": "projection",
            "seasons": args.seasons,
            "teams": [
                {
                    "team": names.get(p.team_id, str(p.team_id)),
                    "mean_w": p.mean_wins,
                    "p10": p.wins_p10,
                    "p50": p.wins_p50,
                    "p90": p.wins_p90,
                    "spread": p.wins_p90 - p.wins_p10,
                    "best_record_pct": round(p.best_record_share * 100, 1),
                }
                for p in projections
            ],
        }

    payload |= {
        "season": season,
        "base_seed": seed,
        "scheduled_games": len(schedule),
        "clubs": len(team_ids),
        "clubs_with_real_profiles": real_profiles,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
