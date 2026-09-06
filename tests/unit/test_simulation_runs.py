"""Recording a simulated game and recalling it by match id."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from baseball_sim.api.routes import (
    get_optional_run_recorder,
    get_simulation_run_repository,
)
from baseball_sim.domain.contracts import (
    DeterministicContext,
    SimulateGameRequest,
    SimulateGameResult,
    SimulationRunResponse,
)
from baseball_sim.domain.service import simulate_game_play_by_play
from baseball_sim.main import app

CONTEXT = DeterministicContext(
    seed=1234, model_version="baseline-v1", data_snapshot_id="test"
)


def request(seed: int = 1234, home: int = 147, away: int = 121) -> SimulateGameRequest:
    return SimulateGameRequest(
        home_team_id=home,
        away_team_id=away,
        innings=9,
        context=DeterministicContext(
            seed=seed, model_version="baseline-v1", data_snapshot_id="test"
        ),
    )


class TestMatchIdentity:
    def test_the_same_context_yields_the_same_match_id(self) -> None:
        first = simulate_game_play_by_play(request())
        second = simulate_game_play_by_play(request())
        assert first.match_id == second.match_id
        # And the same game, which is what makes the id a replay key at all.
        assert first.summary == second.summary

    def test_a_different_seed_yields_a_different_match_id(self) -> None:
        assert (
            simulate_game_play_by_play(request(seed=1)).match_id
            != simulate_game_play_by_play(request(seed=2)).match_id
        )

    def test_swapping_home_and_away_is_a_different_match(self) -> None:
        assert (
            simulate_game_play_by_play(request(home=147, away=121)).match_id
            != simulate_game_play_by_play(request(home=121, away=147)).match_id
        )

    def test_the_id_is_readable_and_stable_in_shape(self) -> None:
        match_id = simulate_game_play_by_play(request()).match_id
        assert match_id.startswith("match_")
        assert len(match_id) == len("match_") + 16


class FakeRunRepository:
    def __init__(self, run: SimulationRunResponse | None = None) -> None:
        self.run = run
        self.recorded: list[str] = []

    def record_run(self, *, match_id: str, **_: object) -> None:
        self.recorded.append(match_id)

    def get_run(self, *, match_id: str) -> SimulationRunResponse | None:
        return self.run if self.run and self.run.match_id == match_id else None


STORED = SimulationRunResponse(
    match_id="match_0123456789abcdef",
    created_at_utc=datetime(2026, 9, 6, 12, 0, tzinfo=UTC),
    home_team_id=147,
    away_team_id=121,
    innings=9,
    context=CONTEXT,
    stats_source="postgres",
    summary=SimulateGameResult(
        home_team_id=147,
        away_team_id=121,
        innings_played=9,
        home_score=5,
        away_score=3,
        winner_team_id=147,
        assumptions=[],
    ),
)


@pytest.fixture
def runs() -> Iterator[FakeRunRepository]:
    repository = FakeRunRepository(run=STORED)
    app.dependency_overrides[get_simulation_run_repository] = lambda: repository
    try:
        yield repository
    finally:
        app.dependency_overrides.pop(get_simulation_run_repository, None)


class TestReplayEndpoint:
    def test_recalls_a_stored_run(self, runs: FakeRunRepository) -> None:
        response = TestClient(app).get(f"/api/v1/games/{STORED.match_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["match_id"] == STORED.match_id
        # The context is what actually reproduces the game.
        assert payload["context"]["seed"] == 1234
        assert payload["stats_source"] == "postgres"
        assert payload["summary"]["winner_team_id"] == 147

    def test_an_unknown_match_is_404(self, runs: FakeRunRepository) -> None:
        response = TestClient(app).get("/api/v1/games/match_deadbeefdeadbeef")
        assert response.status_code == 404
        assert "no recorded run" in response.json()["detail"]


def test_simulation_does_not_persist_by_default() -> None:
    """The viewer must keep working with no database at all."""
    repository = FakeRunRepository()
    app.dependency_overrides[get_optional_run_recorder] = lambda: None
    try:
        response = TestClient(app).post(
            "/api/v1/simulate/game/play-by-play",
            json={
                "home_team_id": 147,
                "away_team_id": 121,
                "innings": 9,
                "context": {
                    "seed": 1234,
                    "model_version": "baseline-v1",
                    "data_snapshot_id": "test",
                },
            },
        )
    finally:
        app.dependency_overrides.pop(get_optional_run_recorder, None)

    assert response.status_code == 200
    assert response.json()["result"]["match_id"].startswith("match_")
    assert repository.recorded == []


def test_recording_stores_the_match_when_switched_on() -> None:
    repository = FakeRunRepository()
    app.dependency_overrides[get_optional_run_recorder] = lambda: repository
    try:
        response = TestClient(app).post(
            "/api/v1/simulate/game/play-by-play",
            json={
                "home_team_id": 147,
                "away_team_id": 121,
                "innings": 9,
                "context": {
                    "seed": 1234,
                    "model_version": "baseline-v1",
                    "data_snapshot_id": "test",
                },
            },
        )
    finally:
        app.dependency_overrides.pop(get_optional_run_recorder, None)

    assert response.status_code == 200
    # The run recorded is the one the caller can now replay by id.
    assert repository.recorded == [response.json()["result"]["match_id"]]
