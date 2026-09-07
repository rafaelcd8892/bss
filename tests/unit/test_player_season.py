from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from baseball_sim.api.routes import get_catalog_repository
from baseball_sim.domain.contracts import (
    PlayerSearchResult,
    PlayerSeasonLine,
    PlayerSummary,
)
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
        self.career: list[tuple[int, PlayerSeasonLine]] = []
        self.raw: tuple[list, list] = ([], [])
        self.search_results: list[PlayerSearchResult] = []

    def get_player_career(
        self, *, player_id: int
    ) -> list[tuple[int, PlayerSeasonLine]]:
        del player_id
        return self.career

    def get_player_career_raw(self, *, player_id: int) -> tuple[list, list]:
        del player_id
        return self.raw

    def search_players(self, *, query: str, limit: int) -> list[PlayerSearchResult]:
        del query, limit
        return self.search_results

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


def test_a_career_is_returned_newest_season_first() -> None:
    catalog = FakePlayerCatalog(player=SOTO, lines=[])
    catalog.career = [
        (2024, PlayerSeasonLine(stat_group="hitting", woba=0.401)),
        (2026, PlayerSeasonLine(stat_group="hitting", woba=0.388)),
        (2025, PlayerSeasonLine(stat_group="hitting", woba=0.372)),
    ]
    payload = _client(catalog).get("/api/v1/players/665742/career").json()
    assert [entry["season"] for entry in payload["seasons"]] == [2026, 2025, 2024]


def test_a_two_way_season_keeps_both_lines_together() -> None:
    catalog = FakePlayerCatalog(player=SOTO, lines=[])
    catalog.career = [
        (2026, PlayerSeasonLine(stat_group="hitting", woba=0.388)),
        (2026, PlayerSeasonLine(stat_group="pitching", fip=3.2)),
    ]
    [season] = _client(catalog).get("/api/v1/players/665742/career").json()["seasons"]
    assert {line["stat_group"] for line in season["lines"]} == {"hitting", "pitching"}


def test_a_single_season_database_returns_one_entry_not_an_error() -> None:
    """Without --history the backfill never ran; that is a shorter answer, not a fault."""

    catalog = FakePlayerCatalog(player=SOTO, lines=[])
    catalog.career = [(2026, PlayerSeasonLine(stat_group="hitting", woba=0.388))]
    payload = _client(catalog).get("/api/v1/players/665742/career").json()
    assert len(payload["seasons"]) == 1


def test_an_unknown_player_has_no_career() -> None:
    catalog = FakePlayerCatalog(player=None, lines=[])
    assert _client(catalog).get("/api/v1/players/665742/career").status_code == 404


def test_the_season_line_carries_the_widened_metrics() -> None:
    """They were ingested and stored long before anything served them."""

    catalog = FakePlayerCatalog(
        player=SOTO,
        lines=[
            PlayerSeasonLine(
                stat_group="hitting", woba=0.388, obp=0.399, slg=0.526,
                ops=0.925, iso=0.249, babip=0.266, xwoba=0.410, x_slg=0.578,
            )
        ],
    )
    [line] = _client(catalog).get("/api/v1/players/665742/season").json()["lines"]
    assert line["ops"] == 0.925
    assert line["xwoba"] == 0.410
    assert line["x_slg"] == 0.578


class TestPlayerSearch:
    """Finding a player by name, rather than knowing his club first."""

    def catalog_with(self, results: list[PlayerSearchResult]) -> FakePlayerCatalog:
        catalog = FakePlayerCatalog(player=SOTO, lines=[])
        catalog.search_results = results
        return catalog

    def test_it_returns_matches_with_enough_context_to_tell_them_apart(self) -> None:
        catalog = self.catalog_with([
            PlayerSearchResult(
                player_id=665742, full_name="Juan Soto",
                primary_position="LF", team_id=121, latest_season=2026,
            )
        ])
        payload = _client(catalog).get("/api/v1/players/search?q=soto").json()
        assert payload["query"] == "soto"
        assert payload["players"][0]["team_id"] == 121
        assert payload["players"][0]["latest_season"] == 2026

    def test_the_route_is_not_swallowed_by_the_player_id_route(self) -> None:
        """`/players/search` and `/players/{id}` collide unless order is deliberate.

        Declared the other way round, "search" is parsed as an id and the endpoint
        returns a validation error instead of results.
        """

        response = _client(self.catalog_with([])).get("/api/v1/players/search?q=x")
        assert response.status_code == 200

    def test_an_empty_query_is_rejected_rather_than_listing_everyone(self) -> None:
        assert _client(self.catalog_with([])).get("/api/v1/players/search?q=").status_code == 422

    def test_the_limit_is_bounded(self) -> None:
        client = _client(self.catalog_with([]))
        assert client.get("/api/v1/players/search?q=a&limit=0").status_code == 422
        assert client.get("/api/v1/players/search?q=a&limit=500").status_code == 422

    def test_no_match_is_an_empty_list_not_an_error(self) -> None:
        payload = _client(self.catalog_with([])).get("/api/v1/players/search?q=zzz").json()
        assert payload["players"] == []
