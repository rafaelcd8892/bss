from pathlib import Path
from typing import Any

import pytest

from baseball_sim.ingest.pipeline import ingest_mlb_window
from baseball_sim.ingest.snapshot_store import SnapshotStore
from baseball_sim.ingest.stats import (
    PlayerSeasonStatRecord,
    innings_to_float,
    normalize_player_stats,
)

HITTING_PAYLOAD = {
    "stats": [
        {
            "group": {"displayName": "hitting"},
            "splits": [
                {
                    "stat": {
                        "plateAppearances": 600,
                        "atBats": 540,
                        "hits": 180,
                        "doubles": 30,
                        "triples": 3,
                        "homeRuns": 35,
                        "baseOnBalls": 50,
                        "intentionalWalks": 5,
                        "hitByPitch": 6,
                        "sacFlies": 4,
                        "strikeOuts": 120,
                        "stolenBases": 10,
                    },
                    "team": {"id": 147},
                }
            ],
        }
    ]
}

PITCHING_PAYLOAD = {
    "stats": [
        {
            "group": {"displayName": "pitching"},
            "splits": [
                {
                    "stat": {
                        "inningsPitched": "200.1",
                        "strikeOuts": 230,
                        "baseOnBalls": 45,
                        "hitByPitch": 5,
                        "homeRuns": 17,
                    },
                    "team": {"id": 147},
                }
            ],
        }
    ]
}


def test_innings_to_float_handles_thirds() -> None:
    assert innings_to_float("123.1") == pytest.approx(123 + 1 / 3)
    assert innings_to_float("200.2") == pytest.approx(200 + 2 / 3)
    assert innings_to_float("9") == pytest.approx(9.0)
    assert innings_to_float(None) == 0.0


def test_normalize_hitting_payload_computes_singles_and_woba() -> None:
    records = normalize_player_stats(player_id=592450, season=2026, payload=HITTING_PAYLOAD)
    assert len(records) == 1
    record = records[0]
    assert record.stat_group == "hitting"
    assert record.batting is not None
    assert record.batting.singles == 180 - 30 - 3 - 35
    assert record.team_id == 147
    assert record.woba is not None and record.woba > 0.3
    assert record.wrc_plus is not None
    assert record.fip is None


def test_normalize_pitching_payload_computes_fip() -> None:
    records = normalize_player_stats(player_id=592450, season=2026, payload=PITCHING_PAYLOAD)
    assert len(records) == 1
    record = records[0]
    assert record.stat_group == "pitching"
    assert record.pitching is not None
    assert record.ip == pytest.approx(200.33, abs=0.01)
    assert record.fip is not None
    assert record.k_bb_ratio == pytest.approx(230 / 45, abs=1e-3)


class FakeStatsClient:
    async def get_teams(self, *, sport_id: int = 1, season: int | None = None) -> list[dict]:
        del sport_id, season
        return [{"id": 147, "name": "New York Yankees"}]

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
        self, *, start_date: str, end_date: str, sport_id: int = 1
    ) -> list[dict]:
        del start_date, end_date, sport_id
        return []

    async def get_player_season_stats(
        self, *, player_id: int, season: int, group: str
    ) -> dict[str, Any]:
        del player_id, season
        return HITTING_PAYLOAD if group == "hitting" else PITCHING_PAYLOAD


class FakeStatsRepository:
    def __init__(self) -> None:
        self.player_stats: list[PlayerSeasonStatRecord] = []
        self.committed = False
        self.rolled_back = False

    def upsert_data_snapshot(self, *, snapshot: Any, notes: str | None = None) -> None:
        del snapshot, notes

    def upsert_teams(self, *, snapshot_id: str, teams: Any) -> int:
        del snapshot_id
        return len(list(teams))

    def upsert_players(self, *, snapshot_id: str, players: Any) -> int:
        del snapshot_id
        return len(list(players))

    def upsert_games(self, *, snapshot_id: str, games: Any) -> int:
        del snapshot_id
        return len(list(games))

    def upsert_roster_memberships(
        self, *, snapshot_id: str, season: int, memberships: Any
    ) -> int:
        del snapshot_id, season
        return len(list(memberships))

    def upsert_player_season_stats(
        self, *, snapshot_id: str, records: Any
    ) -> int:
        del snapshot_id
        self.player_stats = list(records)
        return len(self.player_stats)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


@pytest.mark.asyncio
async def test_pipeline_ingests_and_computes_player_stats(tmp_path: Path) -> None:
    repository = FakeStatsRepository()
    store = SnapshotStore(tmp_path / "raw")

    result = await ingest_mlb_window(
        start_date="2026-04-01",
        end_date="2026-04-02",
        season=2026,
        include_player_stats=True,
        repository=repository,
        client=FakeStatsClient(),
        snapshot_store=store,
    )

    assert repository.committed is True
    assert result.stats_snapshot_id is not None
    assert result.player_stats_upserted == 2  # one hitting + one pitching record
    groups = {record.stat_group for record in repository.player_stats}
    assert groups == {"hitting", "pitching"}
    hitting = next(r for r in repository.player_stats if r.stat_group == "hitting")
    assert hitting.woba is not None


@pytest.mark.asyncio
async def test_pipeline_skips_stats_by_default(tmp_path: Path) -> None:
    repository = FakeStatsRepository()
    store = SnapshotStore(tmp_path / "raw")

    result = await ingest_mlb_window(
        start_date="2026-04-01",
        end_date="2026-04-02",
        season=2026,
        repository=repository,
        client=FakeStatsClient(),
        snapshot_store=store,
    )

    assert result.stats_snapshot_id is None
    assert result.player_stats_upserted == 0
    assert repository.player_stats == []
