from pathlib import Path

import pytest

from baseball_sim.ingest.normalize import GameRecord, PlayerRecord, TeamRecord
from baseball_sim.ingest.pipeline import ingest_mlb_window
from baseball_sim.ingest.snapshot_store import SnapshotStore, StoredSnapshot


class FakeMLBClient:
    async def get_teams(self, *, sport_id: int = 1, season: int | None = None) -> list[dict]:
        del sport_id, season
        return [
            {
                "id": 147,
                "name": "New York Yankees",
                "abbreviation": "NYY",
                "league": {"name": "American League"},
                "division": {"name": "AL East"},
            }
        ]

    async def get_team_roster(self, *, team_id: int, roster_type: str = "active") -> list[dict]:
        del roster_type
        if team_id != 147:
            return []
        return [
            {
                "person": {"id": 592450, "fullName": "Aaron Judge"},
                "position": {"abbreviation": "RF"},
            }
        ]

    async def get_schedule(
        self,
        *,
        start_date: str,
        end_date: str,
        sport_id: int = 1,
    ) -> list[dict]:
        del start_date, end_date, sport_id
        return [
            {
                "date": "2026-04-01",
                "games": [
                    {
                        "gamePk": 990001,
                        "season": "2026",
                        "gameType": "R",
                        "status": {"detailedState": "Scheduled"},
                        "teams": {
                            "home": {"team": {"id": 147}, "score": 0},
                            "away": {"team": {"id": 121}, "score": 0},
                        },
                    }
                ],
            }
        ]


class FakeRepository:
    def __init__(self) -> None:
        self.snapshots: list[StoredSnapshot] = []
        self.teams: list[TeamRecord] = []
        self.players: list[PlayerRecord] = []
        self.games: list[GameRecord] = []
        self.memberships: list = []
        self.committed = False
        self.rolled_back = False

    def upsert_data_snapshot(self, *, snapshot: StoredSnapshot, notes: str | None = None) -> None:
        del notes
        self.snapshots.append(snapshot)

    def upsert_teams(self, *, snapshot_id: str, teams: list[TeamRecord]) -> int:
        del snapshot_id
        self.teams = teams
        return len(teams)

    def upsert_players(self, *, snapshot_id: str, players: list[PlayerRecord]) -> int:
        del snapshot_id
        self.players = players
        return len(players)

    def upsert_games(self, *, snapshot_id: str, games: list[GameRecord]) -> int:
        del snapshot_id
        self.games = games
        return len(games)

    def upsert_roster_memberships(
        self, *, snapshot_id: str, season: int, memberships: list
    ) -> int:
        del snapshot_id, season
        self.memberships = list(memberships)
        return len(self.memberships)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


@pytest.mark.asyncio
async def test_ingest_pipeline_writes_snapshots_and_upserts(tmp_path: Path) -> None:
    repository = FakeRepository()
    client = FakeMLBClient()
    store = SnapshotStore(tmp_path / "raw")

    result = await ingest_mlb_window(
        start_date="2026-04-01",
        end_date="2026-04-02",
        season=2026,
        repository=repository,
        client=client,
        snapshot_store=store,
    )

    assert repository.committed is True
    assert repository.rolled_back is False
    assert len(repository.snapshots) == 3
    assert result.teams_upserted == 1
    assert result.players_upserted == 1
    assert result.games_upserted == 1
    assert result.memberships_upserted == 1
    assert repository.memberships[0].player_id == 592450
