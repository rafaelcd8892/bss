from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Protocol, cast

from baseball_sim.config import Settings, get_settings
from baseball_sim.ingest.mlb_stats_client import create_default_mlb_stats_client
from baseball_sim.ingest.normalize import (
    GameRecord,
    PlayerRecord,
    TeamRecord,
    normalize_games,
    normalize_players,
    normalize_roster_memberships,
    normalize_teams,
)
from baseball_sim.ingest.repository import IngestRepository, PostgresIngestRepository
from baseball_sim.ingest.snapshot_store import SnapshotStore, StoredSnapshot
from baseball_sim.ingest.stats import (
    ExpectedStats,
    PlayerSeasonFieldingRecord,
    PlayerSeasonStatRecord,
    normalize_player_expected,
    normalize_player_fielding,
    normalize_player_stats,
)

SOURCE_SYSTEM = "mlb_stats_api"
STAT_GROUPS = ("hitting", "pitching", "fielding")

#: The API stat type carrying Statcast expected outcomes. It is a second view of the
#: same group, not a second source: xwOBA arrives from the endpoint we already call.
EXPECTED_STAT_TYPE = "expectedStatistics"
#: One request returns a player's whole career instead of one season, so a full
#: backfill costs the same number of requests as a single season does.
HISTORY_STAT_TYPE = "yearByYear"
#: Groups that have an expected view. Fielding does not.
_EXPECTED_GROUPS = ("hitting", "pitching")

#: Positions the MLB roster uses for a pitcher and for a declared two-way player.
_PITCHER_POSITIONS = frozenset({"P", "SP", "RP", "LHP", "RHP", "CP"})
_TWO_WAY_POSITION = "TWP"


def stat_requests_for(
    position: str | None,
    *,
    fetch_all: bool,
    include_expected: bool = True,
    history: bool = False,
) -> tuple[tuple[str, str], ...]:
    """The ``(group, stat_type)`` pairs worth requesting for a player.

    Expected stats are a separate request per group because the API returns them
    under a separate stat type. That is roughly a third more requests, so it can be
    turned off for a run that only needs the counting lines.

    ``history`` swaps the counting request from one season to the whole career. It
    costs no extra requests — the career arrives in the same call — but the expected
    stats have no year-by-year view, so those stay pinned to the requested season.
    """

    groups = stat_groups_for(position, fetch_all=fetch_all)
    counting = HISTORY_STAT_TYPE if history else "season"
    requests = [(group, counting) for group in groups]
    if include_expected:
        requests += [
            (group, EXPECTED_STAT_TYPE) for group in groups if group in _EXPECTED_GROUPS
        ]
    return tuple(requests)


def stat_groups_for(position: str | None, *, fetch_all: bool) -> tuple[str, ...]:
    """Which stat groups are worth requesting for a player.

    Asking for both groups for everyone doubles the request count and stores lines
    nobody wants: a position player's mop-up inning becomes a FIP, a reliever's four
    plate appearances become a wOBA. Declared two-way players still get both.

    Position data can be stale, so this is a cost and noise control, not a
    correctness guarantee — team aggregation applies its own playing-time floor.
    """

    if fetch_all or position is None:
        return STAT_GROUPS
    normalized = position.strip().upper()
    if normalized == _TWO_WAY_POSITION:
        return STAT_GROUPS
    if normalized in _PITCHER_POSITIONS:
        # A pitcher's own fielding is a rounding error on team defense, and skipping
        # it keeps the request count down.
        return ("pitching",)
    return ("hitting", "fielding")


async def _gather_limited[T](
    *,
    limit: int,
    factories: Sequence[Callable[[], Awaitable[T]]],
) -> list[T]:
    """Run awaitables with bounded concurrency.

    Season-stats ingestion fans out to two requests per rostered player — well over a
    thousand for a full league — so firing them all at once would hammer the public
    MLB Stats API and invite rate limiting. A semaphore keeps the burst civil while
    preserving result order.
    """

    semaphore = asyncio.Semaphore(max(1, limit))

    async def run(factory: Callable[[], Awaitable[T]]) -> T:
        async with semaphore:
            return await factory()

    return list(await asyncio.gather(*(run(factory) for factory in factories)))


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
        self, *, player_id: int, season: int, group: str, stat_type: str = "season"
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class IngestionResult:
    teams_snapshot_id: str
    rosters_snapshot_id: str
    schedule_snapshot_id: str
    teams_upserted: int
    players_upserted: int
    games_upserted: int
    memberships_upserted: int = 0
    #: Scheduled games dropped because a side is not an ingested club — the All-Star
    #: Game is the usual case.
    games_skipped: int = 0
    stats_snapshot_id: str | None = None
    player_stats_upserted: int = 0
    fielding_upserted: int = 0


async def ingest_mlb_window(
    *,
    start_date: str,
    end_date: str,
    season: int,
    include_player_stats: bool = False,
    all_stat_groups: bool = False,
    history: bool = False,
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
                    all_stat_groups=all_stat_groups,
                    history=history,
                    max_concurrency=app_settings.mlb_stats_max_concurrency,
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
                all_stat_groups=all_stat_groups,
                history=history,
                max_concurrency=app_settings.mlb_stats_max_concurrency,
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
    all_stat_groups: bool = False,
    history: bool = False,
    max_concurrency: int = 8,
) -> IngestionResult:
    teams_payload = await client.get_teams(sport_id=sport_id, season=season)
    rosters_payload = await _fetch_rosters(
        client=client, teams_payload=teams_payload, max_concurrency=max_concurrency
    )
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
    memberships = normalize_roster_memberships(rosters_payload)
    all_games, games_skipped = _games_between_known_clubs(
        normalize_games(schedule_dates), teams
    )
    games = all_games

    teams_upserted = repository.upsert_teams(snapshot_id=teams_snapshot.snapshot_id, teams=teams)
    players_upserted = repository.upsert_players(
        snapshot_id=rosters_snapshot.snapshot_id, players=players
    )
    memberships_upserted = repository.upsert_roster_memberships(
        snapshot_id=rosters_snapshot.snapshot_id, season=season, memberships=memberships
    )
    games_upserted = repository.upsert_games(snapshot_id=schedule_snapshot.snapshot_id, games=games)

    stats_snapshot_id: str | None = None
    player_stats_upserted = 0
    fielding_upserted = 0
    if include_player_stats and _client_supports_stats(client):
        stats_snapshot_id, player_stats_upserted, fielding_upserted = await _ingest_player_stats(
            client=cast(SupportsPlayerStatsClient, client),
            repository=repository,
            snapshot_store=snapshot_store,
            players=players,
            season=season,
            all_stat_groups=all_stat_groups,
            history=history,
            max_concurrency=max_concurrency,
        )

    return IngestionResult(
        teams_snapshot_id=teams_snapshot.snapshot_id,
        rosters_snapshot_id=rosters_snapshot.snapshot_id,
        schedule_snapshot_id=schedule_snapshot.snapshot_id,
        teams_upserted=teams_upserted,
        players_upserted=players_upserted,
        games_upserted=games_upserted,
        memberships_upserted=memberships_upserted,
        games_skipped=games_skipped,
        stats_snapshot_id=stats_snapshot_id,
        player_stats_upserted=player_stats_upserted,
        fielding_upserted=fielding_upserted,
    )


def _games_between_known_clubs(
    games: Sequence[GameRecord], teams: Sequence[TeamRecord]
) -> tuple[list[GameRecord], int]:
    """Drop scheduled games involving anything that is not an ingested club.

    The schedule is not limited to the clubs `/teams?sportId=1` returns: the All-Star
    Game lists the two league squads (ids 159 and 160), which have no roster and no
    row in `teams`. Inserting those violates the games foreign key and rolls back the
    whole run, so they are filtered out and counted rather than allowed to fail it.
    """

    known = {team.team_id for team in teams}
    kept = [
        game
        for game in games
        if game.home_team_id in known and game.away_team_id in known
    ]
    return kept, len(games) - len(kept)


def _client_supports_stats(client: SupportsMLBClient) -> bool:
    return callable(getattr(client, "get_player_season_stats", None))


async def _ingest_player_stats(
    *,
    client: SupportsPlayerStatsClient,
    repository: IngestRepository,
    snapshot_store: SnapshotStore,
    players: Sequence[PlayerRecord],
    season: int,
    all_stat_groups: bool = False,
    include_expected_stats: bool = True,
    history: bool = False,
    max_concurrency: int = 8,
) -> tuple[str, int, int]:
    by_id = {player.player_id: player for player in players}
    requests: list[tuple[int, str, str]] = [
        (player_id, group, stat_type)
        for player_id in sorted(by_id)
        for group, stat_type in stat_requests_for(
            by_id[player_id].primary_position,
            fetch_all=all_stat_groups,
            include_expected=include_expected_stats,
            history=history,
        )
    ]
    raw_payloads: dict[str, dict[str, Any]] = {}
    records: list[PlayerSeasonStatRecord] = []
    fielding: list[PlayerSeasonFieldingRecord] = []
    expected: dict[tuple[int, str], ExpectedStats] = {}

    def stats_factory(
        player_id: int, group: str, stat_type: str
    ) -> Callable[[], Awaitable[dict[str, Any]]]:
        async def call() -> dict[str, Any]:
            return await client.get_player_season_stats(
                player_id=player_id, season=season, group=group, stat_type=stat_type
            )

        return call

    payloads = await _gather_limited(
        limit=max_concurrency,
        factories=[stats_factory(*request) for request in requests],
    )

    for (player_id, group, stat_type), payload in zip(requests, payloads, strict=True):
        raw_payloads[f"{player_id}:{group}:{stat_type}"] = payload
        if stat_type == EXPECTED_STAT_TYPE:
            for parsed_group, parsed in normalize_player_expected(payload=payload).items():
                expected[(player_id, parsed_group)] = parsed
        elif group == "fielding":
            fielding.extend(
                normalize_player_fielding(player_id=player_id, season=season, payload=payload)
            )
        else:
            records.extend(
                normalize_player_stats(player_id=player_id, season=season, payload=payload)
            )

    records = [_with_expected(record, expected, season=season) for record in records]

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
    fielding_upserted = repository.upsert_player_season_fielding(
        snapshot_id=stats_snapshot.snapshot_id, records=fielding
    )
    return stats_snapshot.snapshot_id, upserted, fielding_upserted


def _with_expected(
    record: PlayerSeasonStatRecord,
    expected: Mapping[tuple[int, str], ExpectedStats],
    *,
    season: int,
) -> PlayerSeasonStatRecord:
    """Attach the Statcast view to the counting line it belongs to."""

    measured = expected.get((record.player_id, record.stat_group))
    # Expected stats are only fetched for the requested season, so a career backfill
    # must not stamp 2019's line with 2026's xwOBA.
    if measured is None or record.season != season:
        return record
    return replace(
        record,
        xwoba=measured.x_woba,
        x_batting_average=measured.x_batting_average,
        x_slg=measured.x_slg,
        x_woba_con=measured.x_woba_con,
    )


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
    max_concurrency: int = 8,
) -> dict[str, list[dict[str, Any]]]:
    team_ids = sorted(team["id"] for team in teams_payload if isinstance(team.get("id"), int))

    def roster_factory(team_id: int) -> Callable[[], Awaitable[list[dict[str, Any]]]]:
        async def call() -> list[dict[str, Any]]:
            return await client.get_team_roster(team_id=team_id)

        return call

    roster_results = await _gather_limited(
        limit=max_concurrency,
        factories=[roster_factory(team_id) for team_id in team_ids],
    )
    return {str(team_id): roster for team_id, roster in zip(team_ids, roster_results, strict=True)}
