"""Backfill a past season with every player who appeared in it.

    python -m baseball_sim.ingest.run_backfill --season 2019

The career backfill (`run_sync --history`) follows the players clubs roster today, so a
past season it produces is missing everyone since retired. A 2019 leaderboard built
from it is the best 2019 among today's players, which looks like a leaderboard and is
not one. This closes that gap for a named season.

It is deliberately per-season rather than a sweep: ADR-025 asks that bulk ingestion be
a decision rather than a habit. The cost is low — two requests a season, since the
league-wide endpoint returns everyone at once — but the choice of which seasons to hold
is still the operator's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from baseball_sim.config import Settings, get_settings
from baseball_sim.ingest.league_stats import normalize_league_stats
from baseball_sim.ingest.mlb_stats_client import create_default_mlb_stats_client
from baseball_sim.ingest.normalize import PlayerRecord
from baseball_sim.ingest.repository import IngestRepository, PostgresIngestRepository
from baseball_sim.ingest.snapshot_store import SnapshotStore
from baseball_sim.ingest.stats import PlayerSeasonStatRecord

SOURCE_SYSTEM = "mlb_stats_api"
BACKFILL_GROUPS = ("hitting", "pitching")


class SupportsLeagueStatsClient(Protocol):
    async def get_league_season_stats(
        self, *, season: int, group: str, limit: int = 2000, offset: int = 0
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class BackfillResult:
    season: int
    snapshot_id: str
    players_upserted: int
    stats_upserted: int


async def backfill_season(
    *,
    season: int,
    repository: IngestRepository | None = None,
    client: SupportsLeagueStatsClient | None = None,
    snapshot_store: SnapshotStore | None = None,
    settings: Settings | None = None,
) -> BackfillResult:
    app_settings = settings if settings is not None else get_settings()
    store = (
        snapshot_store
        if snapshot_store is not None
        else SnapshotStore(app_settings.raw_data_dir)
    )

    if repository is not None and client is not None:
        return await _backfill(
            season=season, repository=repository, client=client, snapshot_store=store
        )

    async with create_default_mlb_stats_client(settings=app_settings) as default_client:
        with PostgresIngestRepository(dsn=app_settings.db_dsn) as repo:
            try:
                result = await _backfill(
                    season=season,
                    repository=repository or repo,
                    client=client or default_client,
                    snapshot_store=store,
                )
            except Exception:
                repo.rollback()
                raise
            repo.commit()
            return result


async def _backfill(
    *,
    season: int,
    repository: IngestRepository,
    client: SupportsLeagueStatsClient,
    snapshot_store: SnapshotStore,
) -> BackfillResult:
    raw: dict[str, Any] = {}
    players: dict[int, PlayerRecord] = {}
    records: list[PlayerSeasonStatRecord] = []

    for group in BACKFILL_GROUPS:
        payload = await client.get_league_season_stats(season=season, group=group)
        raw[group] = payload
        group_players, group_records = normalize_league_stats(season=season, payload=payload)
        for player in group_players:
            players.setdefault(player.player_id, player)
        records.extend(group_records)

    snapshot = snapshot_store.write_snapshot(
        source_system=SOURCE_SYSTEM,
        category="league_season_stats",
        payload=raw,
    )
    repository.upsert_data_snapshot(
        snapshot=snapshot, notes=f"season={season};entity=league_season_stats"
    )

    # Players first: a stat row's foreign key needs the player to exist, and a retired
    # player has no row from any roster ingest.
    players_upserted = repository.upsert_players(
        snapshot_id=snapshot.snapshot_id, players=list(players.values())
    )
    stats_upserted = repository.upsert_player_season_stats(
        snapshot_id=snapshot.snapshot_id, records=records
    )

    return BackfillResult(
        season=season,
        snapshot_id=snapshot.snapshot_id,
        players_upserted=players_upserted,
        stats_upserted=stats_upserted,
    )
