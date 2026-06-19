from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from baseball_sim.api.routes import get_catalog_repository
from baseball_sim.domain.contracts import PlayerSummary, TeamSummary
from baseball_sim.main import app


class FakeCatalog:
    def list_teams(self) -> list[TeamSummary]:
        return [
            TeamSummary(
                team_id=147,
                name="New York Yankees",
                abbreviation="NYY",
                league_name="American League",
                division_name="AL East",
            ),
            TeamSummary(team_id=121, name="New York Mets"),
        ]

    def get_player(self, *, player_id: int) -> PlayerSummary | None:
        if player_id == 592450:
            return PlayerSummary(
                player_id=592450,
                full_name="Aaron Judge",
                primary_position="RF",
                bats="R",
                throws="R",
            )
        return None

    def get_team_roster(self, *, team_id: int) -> list[PlayerSummary]:
        if team_id == 147:
            return [
                PlayerSummary(player_id=592450, full_name="Aaron Judge", primary_position="RF"),
                PlayerSummary(player_id=543037, full_name="Gerrit Cole", primary_position="P"),
            ]
        return []


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_catalog_repository] = lambda: FakeCatalog()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_catalog_repository, None)


def test_list_teams(client: TestClient) -> None:
    response = client.get("/api/v1/teams")
    assert response.status_code == 200
    teams = response.json()["teams"]
    assert len(teams) == 2
    assert teams[0]["abbreviation"] == "NYY"
    assert teams[1]["league_name"] is None


def test_get_player_found(client: TestClient) -> None:
    response = client.get("/api/v1/players/592450")
    assert response.status_code == 200
    assert response.json()["full_name"] == "Aaron Judge"


def test_get_player_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/players/1")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_team_roster(client: TestClient) -> None:
    response = client.get("/api/v1/teams/147/roster")
    assert response.status_code == 200
    payload = response.json()
    assert payload["team_id"] == 147
    assert [p["full_name"] for p in payload["players"]] == ["Aaron Judge", "Gerrit Cole"]


def test_get_team_roster_empty_for_unknown_team(client: TestClient) -> None:
    response = client.get("/api/v1/teams/999/roster")
    assert response.status_code == 200
    assert response.json()["players"] == []
