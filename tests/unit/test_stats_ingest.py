import asyncio
from pathlib import Path
from typing import Any

import pytest

from baseball_sim.config import Settings
from baseball_sim.ingest.pipeline import (
    ingest_mlb_window,
    stat_groups_for,
    stat_requests_for,
)
from baseball_sim.ingest.snapshot_store import SnapshotStore
from baseball_sim.ingest.stats import (
    PlayerSeasonStatRecord,
    innings_to_float,
    normalize_player_expected,
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

FIELDING_PAYLOAD = {
    "stats": [
        {
            "group": {"displayName": "fielding"},
            "splits": [
                {
                    "stat": {
                        "position": {"abbreviation": "RF"},
                        "innings": "1200.0",
                        "putOuts": 250,
                        "assists": 8,
                        "errors": 3,
                        "chances": 261,
                        "doublePlays": 2,
                        "games": 140,
                        "gamesStarted": 138,
                    },
                    "team": {"id": 147},
                },
                {
                    # A designated-hitter split: no innings, and the API sends a
                    # literal "-.--" range factor. It must not become a record.
                    "stat": {
                        "position": {"abbreviation": "DH"},
                        "innings": "0.0",
                        "rangeFactorPerGame": "-.--",
                    },
                    "team": {"id": 147},
                },
            ],
        }
    ]
}

EXPECTED_HITTING_PAYLOAD = {
    "stats": [
        {
            "type": {"displayName": "expectedStatistics"},
            "group": {"displayName": "hitting"},
            "splits": [
                {
                    "season": "2026",
                    # The API sends these as bare-decimal strings.
                    "stat": {
                        "avg": ".314",
                        "slg": ".733",
                        "woba": ".475",
                        "wobaCon": ".615",
                    },
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
        self, *, player_id: int, season: int, group: str, stat_type: str = "season"
    ) -> dict[str, Any]:
        del player_id, season
        if stat_type == "expectedStatistics":
            return EXPECTED_HITTING_PAYLOAD if group == "hitting" else {}
        if group == "hitting":
            return HITTING_PAYLOAD
        return FIELDING_PAYLOAD if group == "fielding" else PITCHING_PAYLOAD


class FakeStatsRepository:
    def __init__(self) -> None:
        self.player_stats: list[PlayerSeasonStatRecord] = []
        self.fielding: list = []
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

    def upsert_player_season_fielding(self, *, snapshot_id: str, records) -> int:
        del snapshot_id
        self.fielding = list(records)
        return len(self.fielding)

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
    # The roster player is a right fielder: hitting and fielding, no pitching.
    assert result.player_stats_upserted == 1
    assert result.fielding_upserted == 1
    [record] = repository.player_stats
    assert record.stat_group == "hitting"
    assert record.woba is not None
    # The widened parse fills the new rate stats too.
    assert record.obp is not None
    assert record.slg is not None
    assert record.babip is not None
    # The designated-hitter split carries no innings and is dropped rather than
    # stored as a position with zero range.
    [fielding_record] = repository.fielding
    assert fielding_record.line.position == "RF"
    assert fielding_record.range_factor_per_nine is not None


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


class ConcurrencyProbeClient:
    """Records the peak number of simultaneous season-stats requests."""

    def __init__(self, player_count: int) -> None:
        self.player_count = player_count
        self.in_flight = 0
        self.max_in_flight = 0

    async def get_teams(self, *, sport_id: int = 1, season: int | None = None) -> list[dict]:
        del sport_id, season
        return [{"id": 147, "name": "New York Yankees"}]

    async def get_team_roster(self, *, team_id: int, roster_type: str = "active") -> list[dict]:
        del roster_type
        if team_id != 147:
            return []
        return [
            {
                "person": {"id": 1000 + i, "fullName": f"Player {i}"},
                "position": {"abbreviation": "RF"},
            }
            for i in range(self.player_count)
        ]

    async def get_schedule(
        self, *, start_date: str, end_date: str, sport_id: int = 1
    ) -> list[dict]:
        del start_date, end_date, sport_id
        return []

    async def get_player_season_stats(
        self, *, player_id: int, season: int, group: str, stat_type: str = "season"
    ) -> dict[str, Any]:
        del player_id, season, stat_type
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.01)
            if group == "hitting":
                return HITTING_PAYLOAD
            return FIELDING_PAYLOAD if group == "fielding" else PITCHING_PAYLOAD
        finally:
            self.in_flight -= 1


@pytest.mark.asyncio
async def test_player_stats_ingestion_respects_concurrency_limit(tmp_path: Path) -> None:
    client = ConcurrencyProbeClient(player_count=12)
    repository = FakeStatsRepository()
    store = SnapshotStore(tmp_path / "raw")
    settings = Settings(mlb_stats_max_concurrency=3)

    result = await ingest_mlb_window(
        start_date="2026-04-01",
        end_date="2026-04-02",
        season=2026,
        include_player_stats=True,
        settings=settings,
        repository=repository,
        client=client,
        snapshot_store=store,
    )

    # Twelve outfielders means twelve hitting requests, not twenty-four.
    assert result.player_stats_upserted == 12
    assert client.max_in_flight <= 3
    assert client.max_in_flight > 1, "expected the requests to actually overlap"


class TestStatGroupSelection:
    def test_position_players_only_need_hitting(self) -> None:
        # They field too, so the fielding split comes along.
        assert stat_groups_for("RF", fetch_all=False) == ("hitting", "fielding")
        assert stat_groups_for("2b", fetch_all=False) == ("hitting", "fielding")

    def test_pitchers_only_need_pitching(self) -> None:
        assert stat_groups_for("P", fetch_all=False) == ("pitching",)
        assert stat_groups_for("RHP", fetch_all=False) == ("pitching",)

    def test_declared_two_way_players_need_everything(self) -> None:
        assert stat_groups_for("TWP", fetch_all=False) == (
            "hitting",
            "pitching",
            "fielding",
        )

    def test_an_unknown_position_falls_back_to_both(self) -> None:
        # Missing position data must not silently drop a player's stats.
        assert stat_groups_for(None, fetch_all=False) == (
            "hitting",
            "pitching",
            "fielding",
        )

    def test_the_override_always_requests_both(self) -> None:
        assert stat_groups_for("RF", fetch_all=True) == (
            "hitting",
            "pitching",
            "fielding",
        )


@pytest.mark.asyncio
async def test_two_way_players_still_get_both_groups(tmp_path: Path) -> None:
    class TwoWayClient(FakeStatsClient):
        async def get_team_roster(self, *, team_id: int, roster_type: str = "active") -> list[dict]:
            del roster_type, team_id
            return [
                {
                    "person": {"id": 660271, "fullName": "Shohei Ohtani"},
                    "position": {"abbreviation": "TWP"},
                }
            ]

    repository = FakeStatsRepository()
    result = await ingest_mlb_window(
        start_date="2026-04-01",
        end_date="2026-04-02",
        season=2026,
        include_player_stats=True,
        repository=repository,
        client=TwoWayClient(),
        snapshot_store=SnapshotStore(tmp_path / "raw"),
    )

    assert result.player_stats_upserted == 2
    assert {record.stat_group for record in repository.player_stats} == {"hitting", "pitching"}


@pytest.mark.asyncio
async def test_all_stat_groups_override_doubles_the_requests(tmp_path: Path) -> None:
    client = ConcurrencyProbeClient(player_count=4)
    result = await ingest_mlb_window(
        start_date="2026-04-01",
        end_date="2026-04-02",
        season=2026,
        include_player_stats=True,
        all_stat_groups=True,
        repository=FakeStatsRepository(),
        client=client,
        snapshot_store=SnapshotStore(tmp_path / "raw"),
    )

    # Four players, three groups each — but only the two stat groups become
    # stat rows; fielding lands in its own table.
    assert result.player_stats_upserted == 8


class TestExpectedStatistics:
    """Statcast expected outcomes, from the same API rather than a second source."""

    def test_parses_the_bare_decimal_strings_the_api_sends(self) -> None:
        parsed = normalize_player_expected(payload=EXPECTED_HITTING_PAYLOAD)
        assert set(parsed) == {"hitting"}
        expected = parsed["hitting"]
        assert expected.x_woba == pytest.approx(0.475)
        assert expected.x_batting_average == pytest.approx(0.314)
        assert expected.x_slg == pytest.approx(0.733)
        assert expected.x_woba_con == pytest.approx(0.615)

    def test_a_player_without_statcast_is_absent_not_four_nulls(self) -> None:
        empty = {
            "stats": [
                {
                    "type": {"displayName": "expectedStatistics"},
                    "group": {"displayName": "hitting"},
                    "splits": [{"season": "2026", "stat": {}}],
                }
            ]
        }
        assert normalize_player_expected(payload=empty) == {}

    def test_a_malformed_payload_yields_nothing_rather_than_raising(self) -> None:
        assert normalize_player_expected(payload={}) == {}
        assert normalize_player_expected(payload={"stats": "nope"}) == {}


class TestStatRequests:
    def test_expected_is_a_second_view_of_each_countable_group(self) -> None:
        assert stat_requests_for("RF", fetch_all=False) == (
            ("hitting", "season"),
            ("fielding", "season"),
            ("hitting", "expectedStatistics"),
        )

    def test_fielding_has_no_expected_view(self) -> None:
        requests = stat_requests_for("RF", fetch_all=False)
        assert ("fielding", "expectedStatistics") not in requests

    def test_a_pitcher_gets_expected_stats_against_him(self) -> None:
        assert stat_requests_for("SP", fetch_all=False) == (
            ("pitching", "season"),
            ("pitching", "expectedStatistics"),
        )

    def test_it_can_be_turned_off_for_a_counting_only_run(self) -> None:
        requests = stat_requests_for("RF", fetch_all=False, include_expected=False)
        assert all(stat_type == "season" for _, stat_type in requests)


@pytest.mark.asyncio
async def test_expected_stats_attach_to_the_counting_line(tmp_path: Path) -> None:
    """xwOBA is not derived from the counting line, so it rides in on its own request
    and has to land on the right row."""

    repository = FakeStatsRepository()
    await ingest_mlb_window(
        start_date="2026-04-01",
        end_date="2026-04-02",
        season=2026,
        include_player_stats=True,
        repository=repository,
        client=FakeStatsClient(),
        snapshot_store=SnapshotStore(tmp_path / "raw"),
    )

    [record] = repository.player_stats
    assert record.stat_group == "hitting"
    assert record.xwoba == pytest.approx(0.475)
    assert record.x_slg == pytest.approx(0.733)
    # The computed wOBA is untouched: they are different measurements.
    assert record.woba is not None and record.woba != record.xwoba
