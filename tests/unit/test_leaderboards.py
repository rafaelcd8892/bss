from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from baseball_sim.api.routes import get_catalog_repository
from baseball_sim.domain.catalog import LEADER_METRICS, leader_qualifier_label
from baseball_sim.domain.contracts import LeaderMetric, PlayerSummary, StatLeader, TeamSummary
from baseball_sim.main import app
from baseball_sim.sim.sabermetrics import (
    RawBattingLine,
    RawFieldingLine,
    RawPitchingLine,
)


class FakeLeaderCatalog:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def list_teams(self) -> list[TeamSummary]:
        return []

    def get_league_fielding_lines(self, *, season: int) -> dict[int, list[RawFieldingLine]]:
        del season
        return {}

    def get_ingested_seasons(self) -> list[int]:
        return [2026, 2025]

    def get_player(self, *, player_id: int) -> PlayerSummary | None:
        del player_id
        return None

    def get_team_roster(self, *, team_id: int) -> list[PlayerSummary]:
        del team_id
        return []

    def get_batting_woba(self, *, player_ids: list[int], season: int) -> dict[int, float]:
        del player_ids, season
        return {}

    def get_stat_leaders(
        self,
        *,
        metric: LeaderMetric,
        season: int,
        minimum: float,
        limit: int,
        team_id: int | None = None,
    ) -> list[StatLeader]:
        self.calls.append(
            {
                "metric": metric,
                "season": season,
                "minimum": minimum,
                "limit": limit,
                "team_id": team_id,
            }
        )
        return [
            StatLeader(
                rank=1,
                player_id=665742,
                full_name="Juan Soto",
                team_id=121,
                value=0.3879,
                plate_appearances=386,
            )
        ]


@pytest.fixture
def catalog() -> Iterator[FakeLeaderCatalog]:
    fake = FakeLeaderCatalog()
    app.dependency_overrides[get_catalog_repository] = lambda: fake
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_catalog_repository, None)


def test_leaders_defaults_to_woba(catalog: FakeLeaderCatalog) -> None:
    response = TestClient(app).get("/api/v1/stats/leaders")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metric"] == "woba"
    assert payload["direction"] == "higher_is_better"
    assert payload["qualifier"] == "min 200 PA"
    assert payload["leaders"][0]["full_name"] == "Juan Soto"
    # The season falls back to the configured one, and the default qualifier applies.
    assert catalog.calls[0]["season"] == 2026
    assert catalog.calls[0]["minimum"] == 200


def test_fip_is_reported_as_lower_is_better(catalog: FakeLeaderCatalog) -> None:
    response = TestClient(app).get("/api/v1/stats/leaders?metric=fip")

    assert response.status_code == 200
    payload = response.json()
    assert payload["direction"] == "lower_is_better"
    assert payload["qualifier"] == "min 50 IP"


def test_explicit_query_parameters_are_passed_through(catalog: FakeLeaderCatalog) -> None:
    response = TestClient(app).get(
        "/api/v1/stats/leaders?metric=k_bb_ratio&season=2025&limit=5&minimum=80"
    )

    assert response.status_code == 200
    assert catalog.calls[0] == {
        "metric": "k_bb_ratio",
        "season": 2025,
        "minimum": 80.0,
        "limit": 5,
        "team_id": None,
    }


def test_unknown_metric_is_rejected(catalog: FakeLeaderCatalog) -> None:
    response = TestClient(app).get("/api/v1/stats/leaders?metric=batting_average")
    assert response.status_code == 422
    assert catalog.calls == []


def test_limit_is_bounded(catalog: FakeLeaderCatalog) -> None:
    assert TestClient(app).get("/api/v1/stats/leaders?limit=0").status_code == 422
    assert TestClient(app).get("/api/v1/stats/leaders?limit=500").status_code == 422


def test_every_metric_has_metadata_and_a_label() -> None:
    for metric, meta in LEADER_METRICS.items():
        label = leader_qualifier_label(metric, meta.default_minimum)
        assert label.startswith("min ")
        assert meta.qualifier_unit in label
    # Direction is per metric and never inferred from the name. The run-prevention
    # metrics rank low-first, and so does a walk rate — a pitching leaderboard for
    # walks is the pitchers who issue fewest, not most.
    lower_is_better = {m for m, meta in LEADER_METRICS.items() if not meta.descending}
    assert lower_is_better == {"fip", "era", "whip", "walk_rate"}
    # A hitter's strikeout rate would rank the other way; this one is the pitcher's.
    assert LEADER_METRICS["strikeout_rate"].stat_group == "pitching"
    assert LEADER_METRICS["strikeout_rate"].descending


ELITE_LINE = RawBattingLine(
    plate_appearances=600,
    at_bats=520,
    singles=100,
    doubles=35,
    triples=3,
    home_runs=38,
    walks=70,
    intentional_walks=8,
    hit_by_pitch=6,
    sacrifice_flies=4,
    strikeouts=110,
    stolen_bases=18,
)
ACE_LINE = RawPitchingLine(
    innings_pitched=180.0, strikeouts=220, walks=40, hit_by_pitch=5, home_runs=16
)
#: A shortstop making 4.5 plays per nine — the league average built below is 4.0.
RANGY_SHORTSTOP = RawFieldingLine(
    position="SS", innings=1000.0, put_outs=200, assists=300, errors=10
)
PLODDING_SHORTSTOP = RawFieldingLine(
    position="SS", innings=1000.0, put_outs=150, assists=239, errors=14
)


class FakeProfileCatalog(FakeLeaderCatalog):
    def __init__(self, *, with_data: bool) -> None:
        super().__init__()
        self.with_data = with_data

    def get_team_stat_lines(
        self, *, team_id: int, season: int
    ) -> tuple[list[RawBattingLine], list[RawPitchingLine]]:
        del team_id, season
        if not self.with_data:
            return [], []
        return [ELITE_LINE] * 9, [ACE_LINE] * 5


def _client_with(catalog: FakeProfileCatalog) -> TestClient:
    app.dependency_overrides[get_catalog_repository] = lambda: catalog
    return TestClient(app)


def test_team_profile_from_real_stats() -> None:
    catalog = FakeProfileCatalog(with_data=True)
    try:
        response = _client_with(catalog).get("/api/v1/teams/147/profile")
    finally:
        app.dependency_overrides.pop(get_catalog_repository, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "real"
    assert payload["team_id"] == 147
    assert payload["batters_counted"] == 9
    assert payload["pitchers_counted"] == 5
    # The aggregate inputs behind the factors are reported so they can be audited.
    assert payload["team_woba"] > 0.3
    assert payload["team_fip"] is not None
    factors = payload["factors"]
    assert all(0.0 <= factors[name] <= 1.0 for name in factors)
    assert factors["offense"] > 0.6
    # No fielding ingested for this club, so range stays neutral and says so.
    assert factors["range_factor"] == 0.5
    assert payload["fielders_counted"] == 0


class FakeFieldingCatalog(FakeProfileCatalog):
    """Two clubs whose shortstops differ; the league baseline is their average."""

    def get_league_fielding_lines(self, *, season: int) -> dict[int, list[RawFieldingLine]]:
        del season
        return {147: [RANGY_SHORTSTOP], 121: [PLODDING_SHORTSTOP]}


def test_range_factor_reflects_fielding_against_the_league() -> None:
    catalog = FakeFieldingCatalog(with_data=True)
    try:
        client = _client_with(catalog)
        rangy = client.get("/api/v1/teams/147/profile").json()
        plodding = client.get("/api/v1/teams/121/profile").json()
    finally:
        app.dependency_overrides.pop(get_catalog_repository, None)

    # Same positions, so the comparison is defense rather than positional mix.
    assert rangy["factors"]["range_factor"] > 0.5 > plodding["factors"]["range_factor"]
    assert rangy["fielders_counted"] == 1


def test_range_factor_is_neutral_when_a_club_matches_the_league() -> None:
    """A club fielding exactly at the baseline must land in the middle of the band."""

    class MatchingCatalog(FakeProfileCatalog):
        def get_league_fielding_lines(
            self, *, season: int
        ) -> dict[int, list[RawFieldingLine]]:
            del season
            return {147: [RANGY_SHORTSTOP], 121: [RANGY_SHORTSTOP]}

    try:
        payload = _client_with(MatchingCatalog(with_data=True)).get(
            "/api/v1/teams/147/profile"
        ).json()
    finally:
        app.dependency_overrides.pop(get_catalog_repository, None)

    assert payload["factors"]["range_factor"] == pytest.approx(0.5)


def test_team_profile_falls_back_to_synthetic_without_data() -> None:
    catalog = FakeProfileCatalog(with_data=False)
    try:
        response = _client_with(catalog).get("/api/v1/teams/147/profile")
    finally:
        app.dependency_overrides.pop(get_catalog_repository, None)

    assert response.status_code == 200
    payload = response.json()
    # Clearly labelled rather than silently presented as measured.
    assert payload["source"] == "synthetic"
    assert payload["batters_counted"] == 0
    assert payload["team_woba"] is None


class FakeLeagueCatalog(FakeLeaderCatalog):
    def get_all_team_stat_lines(
        self, *, season: int
    ) -> dict[int, tuple[list[RawBattingLine], list[RawPitchingLine]]]:
        del season
        return {
            147: ([ELITE_LINE] * 9, [ACE_LINE] * 5),
            # A club with hitting only still gets a profile; pitching stays neutral.
            121: ([ELITE_LINE] * 4, []),
        }


def test_league_team_profiles() -> None:
    catalog = FakeLeagueCatalog()
    app.dependency_overrides[get_catalog_repository] = lambda: catalog
    try:
        response = TestClient(app).get("/api/v1/stats/teams")
    finally:
        app.dependency_overrides.pop(get_catalog_repository, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["season"] == 2026
    teams = {team["team_id"]: team for team in payload["teams"]}
    assert set(teams) == {121, 147}
    assert all(team["source"] == "real" for team in teams.values())

    # Every club reports the aggregate inputs behind its factors.
    assert teams[147]["batters_counted"] == 9
    assert teams[147]["pitchers_counted"] == 5
    assert teams[147]["team_fip"] is not None
    # No pitching ingested for 121, so FIP is absent rather than invented.
    assert teams[121]["pitchers_counted"] == 0
    assert teams[121]["team_fip"] is None
    assert teams[121]["factors"]["prevention"] == 0.5


def test_league_profiles_are_ordered_by_team_id() -> None:
    catalog = FakeLeagueCatalog()
    app.dependency_overrides[get_catalog_repository] = lambda: catalog
    try:
        payload = TestClient(app).get("/api/v1/stats/teams").json()
    finally:
        app.dependency_overrides.pop(get_catalog_repository, None)

    ids = [team["team_id"] for team in payload["teams"]]
    assert ids == sorted(ids)


class TestLeaderFilters:
    """A board can be narrowed to a club and to a season."""

    def test_a_club_narrows_the_ranking_itself(self, catalog: FakeLeaderCatalog) -> None:
        """Not the ranking's result.

        Filtering a finished top ten would leave a club board with however few of its
        players happened to make the league's list — usually none.
        """

        TestClient(app).get("/api/v1/stats/leaders?metric=woba&team_id=147")
        assert catalog.calls[0]["team_id"] == 147

    def test_the_whole_league_is_the_default(self, catalog: FakeLeaderCatalog) -> None:
        TestClient(app).get("/api/v1/stats/leaders?metric=woba")
        assert catalog.calls[0]["team_id"] is None

    def test_the_response_says_which_club_it_was_narrowed_to(
        self, catalog: FakeLeaderCatalog
    ) -> None:
        del catalog
        payload = TestClient(app).get("/api/v1/stats/leaders?team_id=147").json()
        assert payload["team_id"] == 147

    def test_a_nonsense_club_is_rejected_rather_than_queried(
        self, catalog: FakeLeaderCatalog
    ) -> None:
        response = TestClient(app).get("/api/v1/stats/leaders?team_id=0")
        assert response.status_code == 422
        assert catalog.calls == []

    def test_the_seasons_endpoint_offers_what_was_ingested(
        self, catalog: FakeLeaderCatalog
    ) -> None:
        del catalog
        assert TestClient(app).get("/api/v1/stats/seasons").json() == [2026, 2025]
