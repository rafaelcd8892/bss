from fastapi.testclient import TestClient

from baseball_sim.domain.contracts import DeterministicContext, SimulateGameRequest
from baseball_sim.domain.service import simulate_game, simulate_game_play_by_play
from baseball_sim.main import app

_EVENT_TYPES = {"out", "walk", "single", "double", "triple", "home_run", "tiebreaker"}


def _request() -> SimulateGameRequest:
    return SimulateGameRequest(
        home_team_id=147,
        away_team_id=121,
        innings=9,
        context=DeterministicContext(
            seed=1234, model_version="baseline-v1", data_snapshot_id="snapshot-test"
        ),
    )


def test_play_by_play_summary_matches_plain_simulation() -> None:
    request = _request()
    pbp = simulate_game_play_by_play(request)
    summary_only = simulate_game(request)
    assert pbp.summary == summary_only


def test_play_by_play_is_deterministic() -> None:
    request = _request()
    assert simulate_game_play_by_play(request) == simulate_game_play_by_play(request)


def test_play_by_play_trace_is_coherent() -> None:
    result = simulate_game_play_by_play(_request())

    assert result.plays, "expected at least one play"
    assert [play.play_index for play in result.plays] == list(
        range(1, len(result.plays) + 1)
    )
    assert len(result.line_score_home) == len(result.line_score_away)

    for play in result.plays:
        assert play.event in _EVENT_TYPES
        assert set(play.bases_before) <= {"0", "1"}
        assert len(play.bases_after) == 3

    # The final play's running score equals the (pre-tiebreak) summary score, and
    # the line score totals reconcile with the final score.
    last = result.plays[-1]
    assert last.home_score_after_play == result.summary.home_score
    assert last.away_score_after_play == result.summary.away_score
    assert sum(result.line_score_home) <= result.summary.home_score
    assert sum(result.line_score_away) <= result.summary.away_score


def test_play_by_play_endpoint_returns_trace() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/simulate/game/play-by-play",
        json={
            "home_team_id": 147,
            "away_team_id": 121,
            "innings": 9,
            "context": {
                "seed": 1234,
                "model_version": "baseline-v1",
                "data_snapshot_id": "snapshot-test",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["context"]["seed"] == 1234
    result = payload["result"]
    assert result["summary"]["winner_team_id"] in {147, 121}
    assert len(result["plays"]) > 0
    first_play = result["plays"][0]
    assert first_play["play_index"] == 1
    assert "description" in first_play
