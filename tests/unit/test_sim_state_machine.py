from baseball_sim.sim.rulesets import SimulationRuleset
from baseball_sim.sim.state_machine import (
    DeterministicRng,
    simulate_game_state_machine,
    simulate_game_trace,
)


def test_rng_is_deterministic_for_same_seed() -> None:
    first = DeterministicRng(seed=44, home_team_id=147, away_team_id=121)
    second = DeterministicRng(seed=44, home_team_id=147, away_team_id=121)

    first_values = [first.next_unit() for _ in range(5)]
    second_values = [second.next_unit() for _ in range(5)]

    assert first_values == second_values


def test_rng_changes_when_seed_changes() -> None:
    first = DeterministicRng(seed=44, home_team_id=147, away_team_id=121)
    second = DeterministicRng(seed=45, home_team_id=147, away_team_id=121)

    first_values = [first.next_unit() for _ in range(5)]
    second_values = [second.next_unit() for _ in range(5)]

    assert first_values != second_values


def test_game_state_machine_produces_winner_and_reasonable_bounds() -> None:
    result = simulate_game_state_machine(
        seed=1234,
        home_team_id=147,
        away_team_id=121,
        scheduled_innings=9,
    )

    assert result.home_score >= 0
    assert result.away_score >= 0
    assert result.home_score != result.away_score
    assert 9 <= result.innings_played <= 21
    assert result.winner_team_id in {147, 121}
    assert len(result.assumptions) >= 4


def test_game_state_machine_includes_ruleset_metadata() -> None:
    ruleset = SimulationRuleset(
        ruleset_id="test_rules_v2",
        scheduled_innings=9,
        max_innings=12,
        max_plate_appearances_per_half=60,
        skip_home_bottom_if_leading_after_top_final=True,
        enable_walkoff=True,
        enable_runner_on_second_in_extras=True,
        runner_on_second_start_inning=10,
        home_field_event_boost=0.01,
    )
    result = simulate_game_state_machine(
        seed=1234,
        home_team_id=147,
        away_team_id=121,
        scheduled_innings=9,
        ruleset=ruleset,
        ruleset_checksum="abc123",
    )

    assert any("ruleset_id=test_rules_v2" in assumption for assumption in result.assumptions)
    assert any("ruleset_checksum=abc123" in assumption for assumption in result.assumptions)


def test_simulation_trace_is_deterministic() -> None:
    first = simulate_game_trace(
        seed=2222,
        home_team_id=147,
        away_team_id=121,
        scheduled_innings=9,
    )
    second = simulate_game_trace(
        seed=2222,
        home_team_id=147,
        away_team_id=121,
        scheduled_innings=9,
    )

    assert first == second
    assert len(first.plays) > 0
