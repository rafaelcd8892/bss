import math

from baseball_sim.domain.contracts import (
    ComparePlayersRequest,
    ComparePlayersResult,
    DeterministicContext,
    MetricComparison,
    PredictGameRequest,
    PredictGameResult,
    SimulateGameRequest,
    SimulateGameResult,
)
from baseball_sim.domain.stats_provider import (
    DEFAULT_STATS_PROVIDER,
    METRIC_SPECS,
    StatsProvider,
)
from baseball_sim.sim.hashing import scale
from baseball_sim.sim.rulesets import SimulationRuleset
from baseball_sim.sim.state_machine import simulate_game_state_machine


def _team_strength(seed: int, team_id: int, salt: int) -> float:
    offense = scale(
        seed=seed,
        entity_id=team_id,
        salt=salt,
        minimum=0.25,
        maximum=0.42,
        decimals=4,
    )
    pitching = scale(
        seed=seed,
        entity_id=team_id,
        salt=salt + 11,
        minimum=3.2,
        maximum=4.8,
        decimals=4,
    )
    offense_runs = 2.8 + ((offense - 0.25) / 0.17) * 2.0
    pitching_adjustment = ((pitching - 3.2) / 1.6) * 1.2
    return offense_runs + (1.2 - pitching_adjustment)


def compare_players(
    request: ComparePlayersRequest,
    *,
    provider: StatsProvider | None = None,
) -> ComparePlayersResult:
    active_provider = provider if provider is not None else DEFAULT_STATS_PROVIDER
    left = request.left_player_id
    right = request.right_player_id
    seed = request.context.seed

    left_rating = active_provider.player_rating(player_id=left, seed=seed)
    right_rating = active_provider.player_rating(player_id=right, seed=seed)

    comparisons: dict[str, MetricComparison] = {}
    left_wins = 0
    right_wins = 0

    for name, spec in METRIC_SPECS.items():
        left_value = left_rating.metrics[name]
        right_value = right_rating.metrics[name]
        delta = round(left_value - right_value, spec.decimals)
        if spec.direction == "higher_is_better":
            better_player_id = left if left_value >= right_value else right
        else:
            better_player_id = left if left_value <= right_value else right

        if better_player_id == left:
            left_wins += 1
        else:
            right_wins += 1

        comparisons[name] = MetricComparison(
            left_value=left_value,
            right_value=right_value,
            delta_left_minus_right=delta,
            better_player_id=better_player_id,
            direction=spec.direction,
        )

    summary = (
        f"Player {left} leads {left_wins} metrics; player {right} leads {right_wins} metrics. "
        f"Sources: left={left_rating.source}, right={right_rating.source}."
    )
    return ComparePlayersResult(
        left_player_id=left,
        right_player_id=right,
        metrics=comparisons,
        summary=summary,
    )


def simulate_game(
    request: SimulateGameRequest,
    *,
    ruleset: SimulationRuleset | None = None,
    ruleset_checksum: str | None = None,
    provider: StatsProvider | None = None,
) -> SimulateGameResult:
    seed = request.context.seed
    home_profile = None
    away_profile = None
    extra_assumptions: list[str] = []
    if provider is not None:
        home_profile = provider.team_profile(team_id=request.home_team_id, seed=seed)
        away_profile = provider.team_profile(team_id=request.away_team_id, seed=seed)
        extra_assumptions.append(
            "Team profiles sourced from stats provider "
            f"({type(provider).__name__}) rather than seed-only synthesis."
        )

    engine_result = simulate_game_state_machine(
        seed=seed,
        home_team_id=request.home_team_id,
        away_team_id=request.away_team_id,
        scheduled_innings=request.innings,
        ruleset=ruleset,
        ruleset_checksum=ruleset_checksum,
        home_profile=home_profile,
        away_profile=away_profile,
    )
    return SimulateGameResult(
        home_team_id=request.home_team_id,
        away_team_id=request.away_team_id,
        innings_played=engine_result.innings_played,
        home_score=engine_result.home_score,
        away_score=engine_result.away_score,
        winner_team_id=engine_result.winner_team_id,
        assumptions=engine_result.assumptions + extra_assumptions,
    )


def predict_game(request: PredictGameRequest) -> PredictGameResult:
    seed = request.context.seed
    home = request.home_team_id
    away = request.away_team_id

    home_strength = _team_strength(seed=seed, team_id=home, salt=401)
    away_strength = _team_strength(seed=seed, team_id=away, salt=409)
    strength_delta = (home_strength - away_strength) + 0.18

    home_prob = 1.0 / (1.0 + math.exp(-strength_delta))
    away_prob = 1.0 - home_prob
    confidence = abs(home_prob - 0.5) * 2.0

    return PredictGameResult(
        home_team_id=home,
        away_team_id=away,
        home_win_probability=round(home_prob, 4),
        away_win_probability=round(away_prob, 4),
        confidence=round(confidence, 4),
        explanation=[
            "Probability derived from deterministic seeded team-strength function.",
            "Home-field prior encoded as +0.18 log-odds shift.",
            "Confidence is distance from 50/50 baseline.",
        ],
    )


def default_context(
    *,
    seed: int,
    model_version: str,
    data_snapshot_id: str,
) -> DeterministicContext:
    return DeterministicContext(
        seed=seed,
        model_version=model_version,
        data_snapshot_id=data_snapshot_id,
    )
