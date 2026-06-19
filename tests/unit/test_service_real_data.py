"""End-to-end: the compare/simulate services consume real stats via a provider."""

from baseball_sim.domain.contracts import (
    ComparePlayersRequest,
    DeterministicContext,
    SimulateGameRequest,
)
from baseball_sim.domain.service import compare_players, simulate_game
from baseball_sim.domain.stats_provider import StatLineStatsProvider, SyntheticStatsProvider
from baseball_sim.sim.sabermetrics import RawBattingLine, RawPitchingLine

ELITE_BAT = RawBattingLine(
    plate_appearances=700,
    at_bats=560,
    singles=120,
    doubles=40,
    triples=4,
    home_runs=50,
    walks=110,
    intentional_walks=20,
    hit_by_pitch=10,
    sacrifice_flies=6,
    strikeouts=90,
    stolen_bases=25,
)
REPLACEMENT_BAT = RawBattingLine(
    plate_appearances=400,
    at_bats=380,
    singles=70,
    doubles=12,
    triples=1,
    home_runs=4,
    walks=15,
    intentional_walks=0,
    hit_by_pitch=2,
    sacrifice_flies=3,
    strikeouts=110,
    stolen_bases=2,
)
ACE_ARM = RawPitchingLine(
    innings_pitched=200.0, strikeouts=260, walks=35, hit_by_pitch=4, home_runs=14
)
BATTING_PRACTICE_ARM = RawPitchingLine(
    innings_pitched=150.0, strikeouts=95, walks=70, hit_by_pitch=10, home_runs=30
)


def _context() -> DeterministicContext:
    return DeterministicContext(
        seed=1234, model_version="baseline-v1", data_snapshot_id="snapshot-test"
    )


def _provider() -> StatLineStatsProvider:
    return StatLineStatsProvider(
        batting_lines={10: ELITE_BAT, 20: REPLACEMENT_BAT},
        pitching_lines={},
        team_batting={147: [ELITE_BAT] * 9, 121: [REPLACEMENT_BAT] * 9},
        team_pitching={147: [ACE_ARM] * 5, 121: [BATTING_PRACTICE_ARM] * 5},
    )


def test_compare_uses_real_woba_and_picks_elite_hitter() -> None:
    request = ComparePlayersRequest(left_player_id=10, right_player_id=20, context=_context())
    result = compare_players(request, provider=_provider())

    elite_woba = result.metrics["woba"].left_value
    replacement_woba = result.metrics["woba"].right_value
    assert elite_woba > replacement_woba
    assert result.metrics["woba"].better_player_id == 10
    assert "real" in result.summary


def test_compare_with_real_data_is_deterministic() -> None:
    request = ComparePlayersRequest(left_player_id=10, right_player_id=20, context=_context())
    first = compare_players(request, provider=_provider())
    second = compare_players(request, provider=_provider())
    assert first == second


def test_compare_default_provider_matches_synthetic() -> None:
    request = ComparePlayersRequest(
        left_player_id=592450, right_player_id=543037, context=_context()
    )
    default_result = compare_players(request)
    explicit_synthetic = compare_players(request, provider=SyntheticStatsProvider())
    assert default_result == explicit_synthetic


def test_simulate_with_real_profiles_favors_stronger_team() -> None:
    provider = _provider()
    # 147 = elite roster, 121 = weak roster. Run several seeds; the strong team
    # should win the majority.
    strong_wins = 0
    trials = 25
    for seed in range(trials):
        context = DeterministicContext(
            seed=seed, model_version="baseline-v1", data_snapshot_id="snapshot-test"
        )
        request = SimulateGameRequest(
            home_team_id=147, away_team_id=121, innings=9, context=context
        )
        result = simulate_game(request, provider=provider)
        if result.winner_team_id == 147:
            strong_wins += 1
    assert strong_wins >= 17  # comfortably above .500


def test_simulate_real_profile_run_is_deterministic_and_annotated() -> None:
    provider = _provider()
    request = SimulateGameRequest(home_team_id=147, away_team_id=121, innings=9, context=_context())
    first = simulate_game(request, provider=provider)
    second = simulate_game(request, provider=provider)
    assert first == second
    assert any("stats provider" in assumption for assumption in first.assumptions)


def test_simulate_default_provider_matches_legacy() -> None:
    request = SimulateGameRequest(home_team_id=147, away_team_id=121, innings=9, context=_context())
    default_result = simulate_game(request)
    # No provider == seed-only synthesis, with no extra provider assumption.
    assert not any("stats provider" in assumption for assumption in default_result.assumptions)
