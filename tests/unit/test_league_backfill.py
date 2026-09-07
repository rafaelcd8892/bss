"""Backfilling a past season with everyone who played in it."""

from typing import Any

import pytest

from baseball_sim.ingest.backfill import backfill_season
from baseball_sim.ingest.league_stats import normalize_league_stats
from baseball_sim.ingest.snapshot_store import SnapshotStore


def split(
    *,
    player_id: int,
    name: str,
    team_id: int | None = 147,
    num_teams: int = 1,
    position: str = "RF",
    stat: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "player": {"id": player_id, "fullName": name},
        "position": {"abbreviation": position},
        "numTeams": num_teams,
        "stat": stat
        or {
            "plateAppearances": 600,
            "atBats": 540,
            "hits": 160,
            "doubles": 30,
            "triples": 2,
            "homeRuns": 35,
            "baseOnBalls": 55,
            "strikeOuts": 120,
        },
    }
    if team_id is not None:
        payload["team"] = {"id": team_id, "name": "A Club"}
    return payload


def hitting(splits: list[dict[str, Any]]) -> dict[str, Any]:
    return {"stats": [{"group": {"displayName": "hitting"}, "splits": splits}]}


class TestNormalising:
    def test_a_player_and_his_line_both_come_back(self) -> None:
        """A retired player has no row from any roster ingest, so the stat row's
        foreign key would have nothing to point at."""

        players, records = normalize_league_stats(
            season=2019, payload=hitting([split(player_id=1, name="Old Timer")])
        )
        assert [player.full_name for player in players] == ["Old Timer"]
        assert [record.player_id for record in records] == [1]
        assert records[0].season == 2019

    def test_the_position_comes_from_the_split(self) -> None:
        players, _ = normalize_league_stats(
            season=2019,
            payload=hitting([split(player_id=1, name="Arm", position="P")]),
        )
        assert players[0].primary_position == "P"

    def test_handedness_is_left_absent_rather_than_guessed(self) -> None:
        """The bulk payload carries none; a later roster ingest fills it in."""

        players, _ = normalize_league_stats(
            season=2019, payload=hitting([split(player_id=1, name="Old Timer")])
        )
        assert players[0].bats is None and players[0].throws is None

    def test_a_single_club_season_keeps_its_club(self) -> None:
        _, records = normalize_league_stats(
            season=2019, payload=hitting([split(player_id=1, name="Loyal", team_id=121)])
        )
        assert records[0].team_id == 121

    def test_a_multi_club_season_is_stored_with_no_club(self) -> None:
        """The payload tags a traded player's total with whichever club he finished
        at. Storing that would credit them with a season he only half played there —
        and a null team already means "across clubs" everywhere else."""

        _, records = normalize_league_stats(
            season=2019,
            payload=hitting([split(player_id=1, name="Well Travelled", team_id=133, num_teams=3)]),
        )
        assert records[0].team_id is None

    def test_the_metrics_are_computed_the_same_way_as_everywhere_else(self) -> None:
        _, records = normalize_league_stats(
            season=2019, payload=hitting([split(player_id=1, name="Old Timer")])
        )
        assert records[0].woba is not None
        assert records[0].obp is not None

    @pytest.mark.parametrize(
        "payload",
        [{}, {"stats": None}, {"stats": [{"group": {"displayName": "hitting"}, "splits": None}]}],
    )
    def test_a_malformed_payload_yields_nothing_rather_than_raising(
        self, payload: dict[str, Any]
    ) -> None:
        assert normalize_league_stats(season=2019, payload=payload) == ([], [])

    def test_a_split_with_no_player_is_skipped(self) -> None:
        payload = hitting([{"stat": {"atBats": 1}}, split(player_id=2, name="Real")])
        players, records = normalize_league_stats(season=2019, payload=payload)
        assert len(players) == 1 and len(records) == 1


class FakeLeagueClient:
    def __init__(self) -> None:
        self.requests: list[tuple[int, str]] = []

    async def get_league_season_stats(
        self, *, season: int, group: str, limit: int = 2000, offset: int = 0
    ) -> dict[str, Any]:
        del limit, offset
        self.requests.append((season, group))
        if group == "hitting":
            return hitting([split(player_id=1, name="Old Timer")])
        return {
            "stats": [
                {
                    "group": {"displayName": "pitching"},
                    "splits": [
                        {
                            "player": {"id": 2, "fullName": "Retired Arm"},
                            "position": {"abbreviation": "P"},
                            "numTeams": 1,
                            "team": {"id": 147},
                            "stat": {
                                "inningsPitched": "180.0",
                                "strikeOuts": 200,
                                "baseOnBalls": 45,
                                "homeRuns": 20,
                            },
                        }
                    ],
                }
            ]
        }


class FakeRepository:
    def __init__(self) -> None:
        self.players: list = []
        self.records: list = []
        self.snapshots: list = []
        self.order: list[str] = []

    def upsert_data_snapshot(self, *, snapshot, notes=None) -> None:
        del notes
        self.snapshots.append(snapshot)

    def upsert_players(self, *, snapshot_id: str, players) -> int:
        del snapshot_id
        self.order.append("players")
        self.players = list(players)
        return len(self.players)

    def upsert_player_season_stats(self, *, snapshot_id: str, records) -> int:
        del snapshot_id
        self.order.append("stats")
        self.records = list(records)
        return len(self.records)


@pytest.mark.asyncio
async def test_a_season_costs_two_requests_not_one_per_player(tmp_path) -> None:
    """The whole reason this uses the league endpoint. ADR-025 permits non-bulk use,
    and one call per player for 1,287 players is the thing that phrase is about."""

    client = FakeLeagueClient()
    await backfill_season(
        season=2019,
        repository=FakeRepository(),
        client=client,
        snapshot_store=SnapshotStore(tmp_path / "raw"),
    )
    assert client.requests == [(2019, "hitting"), (2019, "pitching")]


@pytest.mark.asyncio
async def test_players_are_written_before_their_stat_rows(tmp_path) -> None:
    """The other way round violates the foreign key for anyone new."""

    repository = FakeRepository()
    await backfill_season(
        season=2019,
        repository=repository,
        client=FakeLeagueClient(),
        snapshot_store=SnapshotStore(tmp_path / "raw"),
    )
    assert repository.order == ["players", "stats"]


@pytest.mark.asyncio
async def test_both_groups_land_and_the_raw_payload_is_snapshotted(tmp_path) -> None:
    repository = FakeRepository()
    result = await backfill_season(
        season=2019,
        repository=repository,
        client=FakeLeagueClient(),
        snapshot_store=SnapshotStore(tmp_path / "raw"),
    )
    assert result.players_upserted == 2
    assert {record.stat_group for record in repository.records} == {"hitting", "pitching"}
    assert len(repository.snapshots) == 1
    assert result.snapshot_id == repository.snapshots[0].snapshot_id
