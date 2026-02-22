from baseball_sim.domain.contracts import (
    ComparePlayersRequest,
    DeterministicContext,
    PredictGameRequest,
    SimulateGameRequest,
)
from baseball_sim.domain.service import compare_players, predict_game, simulate_game


def _context() -> DeterministicContext:
    return DeterministicContext(
        seed=1234,
        model_version="baseline-v1",
        data_snapshot_id="snapshot-2026-02-22",
    )


def test_compare_players_is_deterministic() -> None:
    request = ComparePlayersRequest(
        left_player_id=592450,
        right_player_id=543037,
        context=_context(),
    )

    first = compare_players(request)
    second = compare_players(request)

    assert first == second


def test_simulate_game_is_deterministic() -> None:
    request = SimulateGameRequest(
        home_team_id=147,
        away_team_id=121,
        innings=9,
        context=_context(),
    )

    first = simulate_game(request)
    second = simulate_game(request)

    assert first == second


def test_predict_game_probabilities_sum_to_one() -> None:
    request = PredictGameRequest(
        home_team_id=147,
        away_team_id=121,
        context=_context(),
    )

    result = predict_game(request)

    assert round(result.home_win_probability + result.away_win_probability, 4) == 1.0
