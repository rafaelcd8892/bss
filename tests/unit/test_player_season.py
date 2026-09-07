from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from baseball_sim.api.routes import get_catalog_repository
from baseball_sim.domain.contracts import PlayerSeasonLine, PlayerSummary
from baseball_sim.main import app

SOTO = PlayerSummary(
    player_id=665742, full_name="Juan Soto", primary_position="LF", bats="L", throws="L"
)


class FakePlayerCatalog:
    def __init__(self, *, player: PlayerSummary | None, lines: list[PlayerSeasonLine]) -> None:
        self.player = player
        self.lines = lines
        self.requested: list[tuple[int, int]] = []
        self.seasons: list[int] = [2026]

    def get_player_seasons(self, *, player_id: int) -> list[int]:
        del player_id
        return self.seasons

    def list_teams(self) -> list:
        return []

    def get_player(self, *, player_id: int) -> PlayerSummary | None:
        return self.player if self.player and self.player.player_id == player_id else None

    def get_team_roster(self, *, team_id: int) -> list[PlayerSummary]:
        del team_id
        return []

    def get_batting_woba(self, *, player_ids: list[int], season: int) -> dict[int, float]:
        del player_ids, season
        return {}

    def get_player_season_lines(self, *, player_id: int, season: int) -> list[PlayerSeasonLine]:
        self.requested.append((player_id, season))
        return self.lines


def _client(catalog: FakePlayerCatalog) -> TestClient:
    app.dependency_overrides[get_catalog_repository] = lambda: catalog
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.pop(get_catalog_repository, None)


def test_returns_identity_and_season_lines() -> None:
    catalog = FakePlayerCatalog(
        player=SOTO,
        lines=[
            PlayerSeasonLine(
                stat_group="hitting",
                team_id=121,
                plate_appearances=386,
                at_bats=310,
                hits=90,
                home_runs=21,
                walks=70,
                woba=0.3879,
                wrc_plus=149.5,
            )
        ],
    )

    response = _client(catalog).get("/api/v1/players/665742/season")

    assert response.status_code == 200
    payload = response.json()
    assert payload["player"]["full_name"] == "Juan Soto"
    assert payload["season"] == 2026
    assert len(payload["lines"]) == 1
    line = payload["lines"][0]
    assert line["stat_group"] == "hitting"
    assert line["woba"] == 0.3879
    # Pitching fields stay absent rather than being reported as zero.
    assert line["fip"] is None
    assert line["innings_pitched"] is None


def test_unknown_player_is_404() -> None:
    catalog = FakePlayerCatalog(player=None, lines=[])
    response = _client(catalog).get("/api/v1/players/665742/season")
    assert response.status_code == 404
    # A missing player must not trigger a stats lookup.
    assert catalog.requested == []


def test_player_without_ingested_stats_returns_no_lines() -> None:
    catalog = FakePlayerCatalog(player=SOTO, lines=[])
    payload = _client(catalog).get("/api/v1/players/665742/season").json()
    assert payload["lines"] == []


def test_season_can_be_overridden() -> None:
    catalog = FakePlayerCatalog(player=SOTO, lines=[])
    _client(catalog).get("/api/v1/players/665742/season?season=2025")
    assert catalog.requested == [(665742, 2025)]


def test_the_seasons_a_player_actually_has_are_offered() -> None:
    """A career backfill is only useful if a client can find out which years exist."""

    catalog = FakePlayerCatalog(player=SOTO, lines=[])
    catalog.seasons = [2026, 2025, 2019]
    payload = _client(catalog).get("/api/v1/players/665742/season").json()
    assert payload["available_seasons"] == [2026, 2025, 2019]


def test_a_player_whose_career_ended_lands_on_his_last_season() -> None:
    """Defaulting to the configured season would show a retired player as empty."""

    catalog = FakePlayerCatalog(player=SOTO, lines=[])
    catalog.seasons = [2018, 2017]
    payload = _client(catalog).get("/api/v1/players/665742/season").json()
    assert payload["season"] == 2018


def test_an_explicit_season_is_never_second_guessed() -> None:
    catalog = FakePlayerCatalog(player=SOTO, lines=[])
    catalog.seasons = [2026]
    payload = _client(catalog).get("/api/v1/players/665742/season?season=1999").json()
    assert payload["season"] == 1999
