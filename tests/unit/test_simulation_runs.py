"""Recording a simulated game and recalling it by match id."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
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
from baseball_sim.sim.rulesets import (
    DEFAULT_EVENT_MODEL,
    DEFAULT_RULESET,
    SimulationRuleset,
)

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


RETUNED = replace(
    DEFAULT_RULESET,
    ruleset_id="retuned_for_test",
    event_model=replace(
        DEFAULT_EVENT_MODEL,
        # Half the sensitivity: clubs finish closer together, and every game differs
        # from one played under the default.
        out=replace(DEFAULT_EVENT_MODEL.out, sensitivity=-0.06),
        single=replace(DEFAULT_EVENT_MODEL.single, sensitivity=0.025),
    ),
)


class RulesetAwareRepository:
    """Holds one run and the rules it was played under."""

    def __init__(self, *, ruleset: SimulationRuleset | None) -> None:
        self._ruleset = ruleset

    def record_run(self, **_: object) -> None:
        raise AssertionError("this fake only serves reads")

    def get_run(self, *, match_id: str) -> SimulationRunResponse:
        return SimulationRunResponse(
            match_id=match_id,
            created_at_utc=datetime.now(UTC),
            home_team_id=147,
            away_team_id=121,
            innings=9,
            context=CONTEXT,
            stats_source="synthetic",
            ruleset_id=self._ruleset.ruleset_id if self._ruleset else None,
            ruleset_checksum="stored-checksum" if self._ruleset else None,
            summary=SimulateGameResult(
                home_team_id=147,
                away_team_id=121,
                innings_played=9,
                home_score=0,
                away_score=0,
                winner_team_id=147,
                assumptions=[],
            ),
        )

    def get_run_ruleset(self, *, match_id: str) -> SimulationRuleset | None:
        del match_id
        return self._ruleset


@contextmanager
def replay_client(ruleset: SimulationRuleset | None) -> Iterator[TestClient]:
    app.dependency_overrides[get_simulation_run_repository] = (
        lambda: RulesetAwareRepository(ruleset=ruleset)
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_simulation_run_repository, None)


def _score(payload: dict) -> tuple[int, int]:
    summary = payload["result"]["summary"]
    return summary["home_score"], summary["away_score"]


class TestReplayUsesTheStoredRuleset:
    """The reason the ruleset is stored at all.

    Re-simulating a recorded game under today's constants would hand back a different
    game every time the model is retuned, while still presenting it as the original.
    """

    def test_a_run_replays_under_the_rules_it_was_recorded_under(self) -> None:
        with replay_client(RETUNED) as client:
            replayed = client.get("/api/v1/games/match_test/play-by-play").json()

        under_current_rules = simulate_game_play_by_play(request())
        assert _score(replayed) != (
            under_current_rules.summary.home_score,
            under_current_rules.summary.away_score,
        )

    def test_the_replay_is_itself_reproducible(self) -> None:
        with replay_client(RETUNED) as client:
            first = client.get("/api/v1/games/match_test/play-by-play").json()
            second = client.get("/api/v1/games/match_test/play-by-play").json()
        # `meta` carries a generation timestamp; the game itself must not move.
        assert first["result"] == second["result"]

    def test_the_default_ruleset_replays_the_original_game(self) -> None:
        with replay_client(DEFAULT_RULESET) as client:
            replayed = client.get("/api/v1/games/match_test/play-by-play").json()
        expected = simulate_game_play_by_play(request(), ruleset=DEFAULT_RULESET)
        assert _score(replayed) == (
            expected.summary.home_score,
            expected.summary.away_score,
        )
        assert replayed["result"]["plays"][0]["event"] == expected.plays[0].event

    def test_a_run_with_no_stored_ruleset_is_refused_not_guessed(self) -> None:
        """Recorded before the guarantee existed, so it cannot be honoured."""

        with replay_client(None) as client:
            response = client.get("/api/v1/games/match_test/play-by-play")
        assert response.status_code == 409
        assert "cannot be replayed faithfully" in response.json()["detail"]
