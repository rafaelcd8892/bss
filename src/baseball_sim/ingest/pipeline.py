from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from baseball_sim.config import Settings, get_settings
from baseball_sim.ingest.mlb_stats_client import create_default_mlb_stats_client
from baseball_sim.ingest.normalize import (
    PlayerRecord,
    normalize_games,
    normalize_players,
    normalize_teams,
)
from baseball_sim.ingest.repository import IngestRepository, PostgresIngestRepository
from baseball_sim.ingest.snapshot_store import SnapshotStore, StoredSnapshot
from baseball_sim.ingest.stats import PlayerSeasonStatRecord, normalize_player_stats

SOURCE_SYSTEM = "mlb_stats_api"
STAT_GROUPS = ("hitting", "pitching")


class SupportsMLBClient(Protocol):
    async def get_teams(
        self, *, sport_id: int = 1, season: int | None = None
    ) -> list[dict[str, Any]]: ...

    async def get_schedule(
        self,
        *,
        start_date: str,
        end_date: str,
        sport_id: int = 1,
    ) -> list[dict[str, Any]]: ...

    async def get_team_roster(
        self, *, team_id: int, roster_type: str = "active"
    ) -> list[dict[str, Any]]: ...


class SupportsPlayerStatsClient(SupportsMLBClient, Protocol):
    async def get_player_season_stats(
        self, *, player_id: int, season: int, group: str
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class IngestionResult:
    teams_snapshot_id: str
    rosters_snapshot_id: str
    schedule_snapshot_id: str
    teams_upserted: int
    players_upserted: int
    games_upserted: int
    stats_snapshot_id: str | None = None
    player_stats_upserted: int = 0


async def ingest_mlb_window(
    *,
    start_date: str,
    end_date: str,
    season: int,
    include_player_stats: bool = False,
    settings: Settings | None = None,
    repository: IngestRepository | None = None,
    client: SupportsMLBClient | None = None,
    snapshot_store: SnapshotStore | None = None,
) -> IngestionResult:
    app_settings = settings if settings is not None else get_settings()
    store = (
        snapshot_store if snapshot_store is not None else SnapshotStore(app_settings.raw_data_dir)
    )
    owned_repo = repository is None
    repo = (
        repository if repository is not None else PostgresIngestRepository(dsn=app_settings.db_dsn)
    )

    try:
        if client is None:
            async with create_default_mlb_stats_client(app_settings) as default_client:
                result = await _ingest_with_client(
                    client=default_client,
                    repository=repo,
                    snapshot_store=store,
                    start_date=start_date,
                    end_date=end_date,
                    season=season,
                    sport_id=app_settings.mlb_stats_sport_id,
                    include_player_stats=include_player_stats,
                )
        else:
            result = await _ingest_with_client(
                client=client,
                repository=repo,
                snapshot_store=store,
                start_date=start_date,
                end_date=end_date,
                season=season,
                sport_id=app_settings.mlb_stats_sport_id,
                include_player_stats=include_player_stats,
            )
        repo.commit()
        return result
    except Exception:
        repo.rollback()
        raise
    finally:
        if owned_repo and isinstance(repo, PostgresIngestRepository):
            repo.close()


async def _ingest_with_client(
    *,
    client: SupportsMLBClient,
    repository: IngestRepository,
    snapshot_store: SnapshotStore,
    start_date: str,
    end_date: str,
    season: int,
    sport_id: int,
    include_player_stats: bool,
) -> IngestionResult:
    teams_payload = await client.get_teams(sport_id=sport_id, season=season)
    rosters_payload = await _fetch_rosters(client=client, teams_payload=teams_payload)
    schedule_dates = await client.get_schedule(
        start_date=start_date,
        end_date=end_date,
        sport_id=sport_id,
    )

    teams_snapshot = snapshot_store.write_snapshot(
        source_system=SOURCE_SYSTEM,
        category="teams",
        payload=teams_payload,
    )
    rosters_snapshot = snapshot_store.write_snapshot(
        source_system=SOURCE_SYSTEM,
        category="rosters",
        payload=rosters_payload,
    )
    schedule_snapshot = snapshot_store.write_snapshot(
        source_system=SOURCE_SYSTEM,
        category="schedule",
        payload=schedule_dates,
    )

    _record_snapshot(
        repository=repository,
        snapshot=teams_snapshot,
        notes=f"season={season};entity=teams",
    )
    _record_snapshot(
        repository=repository,
        snapshot=rosters_snapshot,
        notes=f"season={season};entity=rosters",
    )
    _record_snapshot(
        repository=repository,
        snapshot=schedule_snapshot,
        notes=f"season={season};window={start_date}..{end_date};entity=schedule",
    )

    teams = normalize_teams(teams_payload)
    players = normalize_players(rosters_payload)
    games = normalize_games(schedule_dates)

    teams_upserted = repository.upsert_teams(snapshot_id=teams_snapshot.snapshot_id, teams=teams)
    players_upserted = repository.upsert_players(
        snapshot_id=rosters_snapshot.snapshot_id, players=players
    )
    games_upserted = repository.upsert_games(snapshot_id=schedule_snapshot.snapshot_id, games=games)

    stats_snapshot_id: str | None = None
    player_stats_upserted = 0
    if include_player_stats and _client_supports_stats(client):
        stats_snapshot_id, player_stats_upserted = await _ingest_player_stats(
            client=cast(SupportsPlayerStatsClient, client),
            repository=repository,
            snapshot_store=snapshot_store,
            players=players,
            season=season,
        )

    return IngestionResult(
        teams_snapshot_id=teams_snapshot.snapshot_id,
        rosters_snapshot_id=rosters_snapshot.snapshot_id,
        schedule_snapshot_id=schedule_snapshot.snapshot_id,
        teams_upserted=teams_upserted,
        players_upserted=players_upserted,
        games_upserted=games_upserted,
        stats_snapshot_id=stats_snapshot_id,
        player_stats_upserted=player_stats_upserted,
    )


def _client_supports_stats(client: SupportsMLBClient) -> bool:
    return callable(getattr(client, "get_player_season_stats", None))


async def _ingest_player_stats(
    *,
    client: SupportsPlayerStatsClient,
    repository: IngestRepository,
    snapshot_store: SnapshotStore,
    players: Sequence[PlayerRecord],
    season: int,
) -> tuple[str, int]:
    player_ids = sorted({player.player_id for player in players})
    raw_payloads: dict[str, dict[str, Any]] = {}
    records: list[PlayerSeasonStatRecord] = []

    tasks = [
        client.get_player_season_stats(player_id=player_id, season=season, group=group)
        for player_id in player_ids
        for group in STAT_GROUPS
    ]
    payloads = await asyncio.gather(*tasks)

    index = 0
    for player_id in player_ids:
        for group in STAT_GROUPS:
            payload = payloads[index]
            index += 1
            raw_payloads[f"{player_id}:{group}"] = payload
            records.extend(
                normalize_player_stats(player_id=player_id, season=season, payload=payload)
            )

    stats_snapshot = snapshot_store.write_snapshot(
        source_system=SOURCE_SYSTEM,
        category="player_season_stats",
        payload=raw_payloads,
    )
    _record_snapshot(
        repository=repository,
        snapshot=stats_snapshot,
        notes=f"season={season};entity=player_season_stats",
    )
    upserted = repository.upsert_player_season_stats(
        snapshot_id=stats_snapshot.snapshot_id, records=records
    )
    return stats_snapshot.snapshot_id, upserted


def _record_snapshot(
    *,
    repository: IngestRepository,
    snapshot: StoredSnapshot,
    notes: str,
) -> None:
    repository.upsert_data_snapshot(snapshot=snapshot, notes=notes)


async def _fetch_rosters(
    *,
    client: SupportsMLBClient,
    teams_payload: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    team_ids = sorted(team["id"] for team in teams_payload if isinstance(team.get("id"), int))
    roster_tasks = [client.get_team_roster(team_id=team_id) for team_id in team_ids]
    roster_results = await asyncio.gather(*roster_tasks)
    return {str(team_id): roster for team_id, roster in zip(team_ids, roster_results, strict=True)}
