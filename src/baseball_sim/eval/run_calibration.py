"""Score the pregame forecast against games that have already been played.

    python -m baseball_sim.eval.run_calibration --season 2026

IMPORTANT — what this measurement is and is not.

Team profiles are built from full-season aggregates, and the games being scored happened
inside that same season. The model therefore already "knows" how the season turned out:
this is an in-sample check with look-ahead bias, not an out-of-sample backtest. A clean
backtest needs stats as they stood before each game, which requires game-level history
we do not ingest yet.

Read the result as a sanity check on the model's shape — is it systematically biased,
is it better than a coin flip — and not as a measure of forecasting skill.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from baseball_sim.config import get_settings
from baseball_sim.domain.catalog import PostgresCatalogRepository
from baseball_sim.domain.postgres_stats import build_stat_line_provider
from baseball_sim.eval.calibration import Observation, calibration_report
from baseball_sim.sim.winprob import team_run_rates, win_probability


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score the pregame win-probability model.")
    parser.add_argument("--season", type=int, default=None, help="Season to evaluate.")
    parser.add_argument("--dsn", default=None, help="Override the database DSN.")
    parser.add_argument("--bins", type=int, default=5, help="Reliability bin count.")
    parser.add_argument("--seed", type=int, default=None, help="Seed for fallback profiles.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    dsn = args.dsn or settings.db_dsn
    season = args.season or settings.stats_season
    seed = args.seed if args.seed is not None else settings.default_seed

    provider = build_stat_line_provider(dsn=dsn, season=season)
    repository = PostgresCatalogRepository(dsn=dsn)
    try:
        games = repository.get_completed_games(season=season)
    finally:
        repository.close()

    observations: list[Observation] = []
    for game in games:
        home_rate, away_rate = team_run_rates(
            home_profile=provider.team_profile(team_id=game.home_team_id, seed=seed),
            away_profile=provider.team_profile(team_id=game.away_team_id, seed=seed),
        )
        forecast = win_probability(home_rate=home_rate, away_rate=away_rate)
        observations.append(
            Observation(predicted_home_win=forecast.home, home_won=game.home_won)
        )

    report = calibration_report(observations, bin_count=args.bins)
    payload = asdict(report)
    payload["observed_interval"] = list(report.observed_interval)
    payload["conclusive"] = report.conclusive
    payload["season"] = season
    payload["caveat"] = (
        "In-sample: profiles come from full-season aggregates covering these same "
        "games, so this carries look-ahead bias and is not a backtest."
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
