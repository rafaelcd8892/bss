from __future__ import annotations

from typing import Any

import pytest

from baseball_sim.cli.roster_loader import load_watch_rosters_with_client


class FakeRosterClient:
    def __init__(
        self,
        *,
        teams: list[dict[str, Any]],
        rosters_by_team_id: dict[int, list[dict[str, Any]]],
        roster_errors_by_team_id: dict[int, Exception] | None = None,
    ) -> None:
        self._teams = teams
        self._rosters_by_team_id = rosters_by_team_id
        self._roster_errors_by_team_id = roster_errors_by_team_id or {}

    async def get_teams(
        self,
        *,
        sport_id: int = 1,
        season: int | None = None,
    ) -> list[dict[str, Any]]:
        _ = sport_id, season
        return self._teams

    async def get_team_roster(
        self,
        *,
        team_id: int,
        roster_type: str = "active",
    ) -> list[dict[str, Any]]:
        _ = roster_type
        if team_id in self._roster_errors_by_team_id:
            raise self._roster_errors_by_team_id[team_id]
        return self._rosters_by_team_id.get(team_id, [])


def _entry(*, player_id: int, full_name: str, position: str) -> dict[str, Any]:
    return {
        "person": {"id": player_id, "fullName": full_name},
        "position": {"abbreviation": position},
    }


@pytest.mark.asyncio
async def test_load_watch_rosters_uses_api_data_when_available() -> None:
    client = FakeRosterClient(
        teams=[
            {"id": 147, "name": "Yankees"},
            {"id": 121, "name": "Mets"},
        ],
        rosters_by_team_id={
            147: [
                _entry(player_id=1, full_name="Pitcher One", position="P"),
                _entry(player_id=2, full_name="Catcher One", position="C"),
                _entry(player_id=3, full_name="First Base", position="1B"),
                _entry(player_id=4, full_name="Second Base", position="2B"),
                _entry(player_id=5, full_name="Third Base", position="3B"),
                _entry(player_id=6, full_name="Shortstop", position="SS"),
                _entry(player_id=7, full_name="Left Field", position="LF"),
                _entry(player_id=8, full_name="Center Field", position="CF"),
                _entry(player_id=9, full_name="Right Field", position="RF"),
                _entry(player_id=10, full_name="Designated Hitter", position="DH"),
            ],
            121: [
                _entry(player_id=101, full_name="Pitcher Two", position="P"),
                _entry(player_id=102, full_name="Catcher Two", position="C"),
                _entry(player_id=103, full_name="First Base Two", position="1B"),
                _entry(player_id=104, full_name="Second Base Two", position="2B"),
                _entry(player_id=105, full_name="Third Base Two", position="3B"),
                _entry(player_id=106, full_name="Shortstop Two", position="SS"),
                _entry(player_id=107, full_name="Left Field Two", position="LF"),
                _entry(player_id=108, full_name="Center Field Two", position="CF"),
                _entry(player_id=109, full_name="Right Field Two", position="RF"),
                _entry(player_id=110, full_name="Designated Hitter Two", position="DH"),
            ],
        },
    )

    rosters = await load_watch_rosters_with_client(
        client=client,
        home_team_id=147,
        away_team_id=121,
        seed=42,
        home_team_name_override=None,
        away_team_name_override=None,
    )

    assert rosters.home.source == "api"
    assert rosters.away.source == "api"
    assert rosters.home.roster.team_name == "Yankees"
    assert rosters.away.roster.team_name == "Mets"
    assert rosters.home.roster.fielders["P"].full_name == "Pitcher One"
    assert rosters.away.roster.fielders["CF"].full_name == "Center Field Two"
    assert len(rosters.home.roster.lineup) == 9
    assert len(rosters.away.roster.lineup) == 9


@pytest.mark.asyncio
async def test_load_watch_rosters_uses_hybrid_fallback_when_api_roster_is_partial() -> None:
    client = FakeRosterClient(
        teams=[{"id": 147, "name": "Yankees"}, {"id": 121, "name": "Mets"}],
        rosters_by_team_id={
            147: [
                _entry(player_id=1, full_name="Pitcher One", position="P"),
                _entry(player_id=2, full_name="Catcher One", position="C"),
            ],
            121: [
                _entry(player_id=101, full_name="Pitcher Two", position="P"),
                _entry(player_id=102, full_name="Catcher Two", position="C"),
            ],
        },
    )

    rosters = await load_watch_rosters_with_client(
        client=client,
        home_team_id=147,
        away_team_id=121,
        seed=123,
        home_team_name_override=None,
        away_team_name_override=None,
    )

    assert rosters.home.source == "api_with_seeded_fallback"
    assert rosters.away.source == "api_with_seeded_fallback"
    assert rosters.home.note is not None
    assert rosters.away.note is not None
    assert rosters.home.roster.fielders["P"].full_name == "Pitcher One"
    assert rosters.away.roster.fielders["C"].full_name == "Catcher Two"
    assert len(rosters.home.roster.lineup) == 9
    assert len(rosters.away.roster.lineup) == 9


@pytest.mark.asyncio
async def test_load_watch_rosters_falls_back_to_seeded_when_api_errors() -> None:
    client = FakeRosterClient(
        teams=[{"id": 147, "name": "Yankees"}, {"id": 121, "name": "Mets"}],
        rosters_by_team_id={
            121: [_entry(player_id=201, full_name="Away Pitcher", position="P")],
        },
        roster_errors_by_team_id={
            147: RuntimeError("boom"),
        },
    )

    rosters = await load_watch_rosters_with_client(
        client=client,
        home_team_id=147,
        away_team_id=121,
        seed=7,
        home_team_name_override="Custom Home",
        away_team_name_override=None,
    )

    assert rosters.home.source == "seeded_fallback_api_error"
    assert rosters.home.note is not None
    assert rosters.home.roster.team_name == "Custom Home"
    assert rosters.away.source == "api_with_seeded_fallback"
    assert len(rosters.home.roster.lineup) == 9
