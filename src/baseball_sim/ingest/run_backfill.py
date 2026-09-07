"""Backfill one past season with everyone who played in it.

    python -m baseball_sim.ingest.run_backfill --season 2019
"""

from __future__ import annotations

import argparse
import asyncio
import json

from baseball_sim.ingest.backfill import backfill_season


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill a past season with every player who appeared in it."
    )
    parser.add_argument("--season", type=int, required=True, help="Season to backfill.")
    return parser.parse_args()


async def _main() -> None:
    args = parse_args()
    result = await backfill_season(season=args.season)
    print(
        json.dumps(
            {
                "season": result.season,
                "snapshot_id": result.snapshot_id,
                "players_upserted": result.players_upserted,
                "stats_upserted": result.stats_upserted,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(_main())
