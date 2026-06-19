from __future__ import annotations

import argparse
import asyncio
import json

from baseball_sim.ingest.pipeline import ingest_mlb_window


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MLB data ingestion window sync.")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--season", type=int, required=True, help="MLB season year")
    parser.add_argument(
        "--include-player-stats",
        action="store_true",
        help="Also ingest per-player season stats and compute sabermetrics.",
    )
    return parser.parse_args()


async def _main() -> None:
    args = parse_args()
    result = await ingest_mlb_window(
        start_date=args.start_date,
        end_date=args.end_date,
        season=args.season,
        include_player_stats=args.include_player_stats,
    )
    print(
        json.dumps(
            {
                "teams_snapshot_id": result.teams_snapshot_id,
                "rosters_snapshot_id": result.rosters_snapshot_id,
                "schedule_snapshot_id": result.schedule_snapshot_id,
                "stats_snapshot_id": result.stats_snapshot_id,
                "teams_upserted": result.teams_upserted,
                "players_upserted": result.players_upserted,
                "memberships_upserted": result.memberships_upserted,
                "games_upserted": result.games_upserted,
                "player_stats_upserted": result.player_stats_upserted,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(_main())
