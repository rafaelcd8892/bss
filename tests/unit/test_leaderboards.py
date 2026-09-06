from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from baseball_sim.api.routes import get_catalog_repository
from baseball_sim.domain.catalog import LEADER_METRICS, leader_qualifier_label
from baseball_sim.domain.contracts import LeaderMetric, PlayerSummary, StatLeader, TeamSummary
from baseball_sim.main import app


class FakeLeaderCatalog:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def list_teams(self) -> list[TeamSummary]:
        return []

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
        self, *, metric: LeaderMetric, season: int, minimum: float, limit: int
    ) -> list[StatLeader]:
        self.calls.append(
            {"metric": metric, "season": season, "minimum": minimum, "limit": limit}
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
    # FIP is the only ERA-scale metric where lower wins.
    assert [m for m, meta in LEADER_METRICS.items() if not meta.descending] == ["fip"]
