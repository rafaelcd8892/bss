"""The ingestion upserts, against a real PostgreSQL.

PostgresIngestRepository had no coverage at all: every pipeline test used a fake, so
the ON CONFLICT clauses and the composite keys were never executed.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from baseball_sim.ingest.normalize import (
    PlayerRecord,
    RosterMembershipRecord,
    TeamRecord,
)
from baseball_sim.ingest.pipeline import ingest_mlb_window
from baseball_sim.ingest.repository import PostgresIngestRepository
from baseball_sim.ingest.snapshot_store import SnapshotStore
from baseball_sim.ingest.stats import PlayerSeasonStatRecord
from baseball_sim.sim.sabermetrics import RawBattingLine, RawPitchingLine

from .conftest import SEASON

SNAPSHOT = "ingest:snapshot:0001"


@pytest.fixture
def repository(postgres_dsn: str, db: Any) -> Any:
    del db  # the db fixture truncates before the test
    repo = PostgresIngestRepository(dsn=postgres_dsn)
    try:
        yield repo
    finally:
        repo.close()


class _Snapshot:
    snapshot_id = SNAPSHOT
    source_system = "test"
    payload_sha256 = "cafebabe"


def _prepare(repo: PostgresIngestRepository) -> None:
    repo.upsert_data_snapshot(snapshot=_Snapshot())  # type: ignore[arg-type]
    repo.upsert_teams(
        snapshot_id=SNAPSHOT,
        teams=[TeamRecord(500, "Ingest Club", "ING", "L", "D")],
    )
    repo.upsert_players(
        snapshot_id=SNAPSHOT,
        players=[
            PlayerRecord(50, "Ingest Hitter", "RF", "L", "R", None, None),
            PlayerRecord(51, "Ingest Twoway", "TWP", "L", "L", None, None),
        ],
    )


def _count(repo: PostgresIngestRepository, table: str) -> int:
    with repo._conn.cursor() as cursor:  # noqa: SLF001 - inspecting the test database
        cursor.execute(f"SELECT count(*) FROM {table}")
        return int(cursor.fetchone()[0])


class TestUpserts:
    def test_writes_the_core_entities(self, repository: PostgresIngestRepository) -> None:
        _prepare(repository)
        repository.commit()

        assert _count(repository, "teams") == 1
        assert _count(repository, "players") == 2

    def test_reingesting_updates_instead_of_duplicating(
        self, repository: PostgresIngestRepository
    ) -> None:
        _prepare(repository)
        repository.upsert_teams(
            snapshot_id=SNAPSHOT,
            teams=[TeamRecord(500, "Renamed Club", "RNM", "L", "D")],
        )
        repository.commit()

        assert _count(repository, "teams") == 1
        with repository._conn.cursor() as cursor:  # noqa: SLF001
            cursor.execute("SELECT name, abbreviation FROM teams WHERE team_id = 500")
            assert cursor.fetchone() == ("Renamed Club", "RNM")

    def test_roster_membership_is_keyed_per_snapshot(
        self, repository: PostgresIngestRepository
    ) -> None:
        _prepare(repository)
        memberships = [RosterMembershipRecord(500, 50, "RF")]
        repository.upsert_roster_memberships(
            snapshot_id=SNAPSHOT, season=SEASON, memberships=memberships
        )
        repository.upsert_roster_memberships(
            snapshot_id=SNAPSHOT, season=SEASON, memberships=memberships
        )
        repository.commit()

        assert _count(repository, "roster_memberships") == 1

    def test_two_way_player_keeps_both_stat_lines(
        self, repository: PostgresIngestRepository
    ) -> None:
        """Regression guard for migration 0002.

        Before stat_group joined the primary key, a player's hitting and pitching rows
        for the same season and snapshot collided and one silently overwrote the other.
        """
        _prepare(repository)
        batting = RawBattingLine(400, 350, 70, 20, 2, 18, 45, 3, 5, 3, 90, 6)
        pitching = RawPitchingLine(90.0, 100, 25, 3, 9)
        repository.upsert_player_season_stats(
            snapshot_id=SNAPSHOT,
            records=[
                PlayerSeasonStatRecord(
                    51, SEASON, 500, "hitting", batting, None,
                    400, None, 0.36, None, 130.0, None, None,
                ),
                PlayerSeasonStatRecord(
                    51, SEASON, 500, "pitching", None, pitching,
                    None, 90.0, None, None, None, 3.1, 4.0,
                ),
            ],
        )
        repository.commit()

        assert _count(repository, "player_season_stats") == 2
        with repository._conn.cursor() as cursor:  # noqa: SLF001
            cursor.execute(
                "SELECT stat_group FROM player_season_stats WHERE player_id = 51 "
                "ORDER BY stat_group"
            )
            assert [row[0] for row in cursor.fetchall()] == ["hitting", "pitching"]

    def test_a_failed_run_rolls_back(self, repository: PostgresIngestRepository) -> None:
        _prepare(repository)
        repository.rollback()
        assert _count(repository, "teams") == 0


class FakeClient:
    """Enough of the MLB API to drive a full ingestion run."""

    async def get_teams(self, *, sport_id: int = 1, season: int | None = None) -> list[dict]:
        del sport_id, season
        return [{"id": 600, "name": "Pipeline Club", "abbreviation": "PIP"}]

    async def get_team_roster(self, *, team_id: int, roster_type: str = "active") -> list[dict]:
        del roster_type
        if team_id != 600:
            return []
        return [
            {"person": {"id": 60, "fullName": "Pipe Hitter"}, "position": {"abbreviation": "CF"}}
        ]

    async def get_schedule(
        self, *, start_date: str, end_date: str, sport_id: int = 1
    ) -> list[dict]:
        del start_date, end_date, sport_id
        return [
            {
                "date": "2026-09-01",
                "games": [
                    {
                        "gamePk": 777001,
                        "season": str(SEASON),
                        "gameType": "R",
                        "status": {"detailedState": "Final"},
                        "teams": {
                            "home": {"team": {"id": 600}, "score": 4},
                            "away": {"team": {"id": 600}, "score": 2},
                        },
                    }
                ],
            }
        ]


@pytest.mark.asyncio
async def test_full_pipeline_writes_and_is_idempotent(
    postgres_dsn: str, db: Any, tmp_path: Path
) -> None:
    del db
    store = SnapshotStore(tmp_path / "raw")

    async def run() -> Any:
        repo = PostgresIngestRepository(dsn=postgres_dsn)
        try:
            return await ingest_mlb_window(
                start_date="2026-09-01",
                end_date="2026-09-02",
                season=SEASON,
                repository=repo,
                client=FakeClient(),
                snapshot_store=store,
            )
        finally:
            repo.close()

    first = await run()
    assert first.teams_upserted == 1
    assert first.players_upserted == 1
    assert first.memberships_upserted == 1
    assert first.games_upserted == 1

    # The same window ingested twice must not duplicate anything: identical payloads
    # hash to the same snapshot id, and every write is an upsert.
    await run()

    inspect = PostgresIngestRepository(dsn=postgres_dsn)
    try:
        assert _count(inspect, "teams") == 1
        assert _count(inspect, "players") == 1
        assert _count(inspect, "roster_memberships") == 1
        assert _count(inspect, "games") == 1
        with inspect._conn.cursor() as cursor:  # noqa: SLF001
            cursor.execute("SELECT game_date, home_score FROM games WHERE game_pk = 777001")
            assert cursor.fetchone() == (date(2026, 9, 1), 4)
    finally:
        inspect.close()
