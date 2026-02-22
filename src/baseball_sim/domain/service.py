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
from baseball_sim.sim.rulesets import SimulationRuleset
from baseball_sim.sim.state_machine import simulate_game_state_machine


def _u32_mix(seed: int, entity_id: int, salt: int) -> int:
    mixed = (seed ^ (entity_id * 2_654_435_761) ^ (salt * 2_246_822_519)) & 0xFFFFFFFF
    return (mixed * 1_664_525 + 1_013_904_223) & 0xFFFFFFFF


def _unit_interval(seed: int, entity_id: int, salt: int) -> float:
    mixed = _u32_mix(seed=seed, entity_id=entity_id, salt=salt)
    return mixed / 4_294_967_295.0


def _scale(
    *,
    seed: int,
    entity_id: int,
    salt: int,
    minimum: float,
    maximum: float,
    decimals: int,
) -> float:
    raw = _unit_interval(seed=seed, entity_id=entity_id, salt=salt)
    value = minimum + (maximum - minimum) * raw
    return round(value, decimals)


def _team_strength(seed: int, team_id: int, salt: int) -> float:
    offense = _scale(
        seed=seed,
        entity_id=team_id,
        salt=salt,
        minimum=0.25,
        maximum=0.42,
        decimals=4,
    )
    pitching = _scale(
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


def compare_players(request: ComparePlayersRequest) -> ComparePlayersResult:
    left = request.left_player_id
    right = request.right_player_id
    seed = request.context.seed

    metric_values = {
        "woba": ("higher_is_better", (0.255, 0.415, 4)),
        "xwoba": ("higher_is_better", (0.250, 0.430, 4)),
        "wrc_plus": ("higher_is_better", (70.0, 175.0, 1)),
        "fip": ("lower_is_better", (2.6, 5.2, 2)),
        "k_bb_ratio": ("higher_is_better", (1.2, 6.0, 2)),
    }

    comparisons: dict[str, MetricComparison] = {}
    left_wins = 0
    right_wins = 0

    for salt, (name, (direction, (minimum, maximum, decimals))) in enumerate(
        metric_values.items(),
        start=1,
    ):
        left_value = _scale(
            seed=seed,
            entity_id=left,
            salt=salt,
            minimum=minimum,
            maximum=maximum,
            decimals=decimals,
        )
        right_value = _scale(
            seed=seed,
            entity_id=right,
            salt=salt,
            minimum=minimum,
            maximum=maximum,
            decimals=decimals,
        )
        delta = round(left_value - right_value, decimals)
        if direction == "higher_is_better":
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
            direction=direction,
        )

    summary = f"Player {left} leads {left_wins} metrics; player {right} leads {right_wins} metrics."
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
) -> SimulateGameResult:
    engine_result = simulate_game_state_machine(
        seed=request.context.seed,
        home_team_id=request.home_team_id,
        away_team_id=request.away_team_id,
        scheduled_innings=request.innings,
        ruleset=ruleset,
        ruleset_checksum=ruleset_checksum,
    )
    return SimulateGameResult(
        home_team_id=request.home_team_id,
        away_team_id=request.away_team_id,
        innings_played=engine_result.innings_played,
        home_score=engine_result.home_score,
        away_score=engine_result.away_score,
        winner_team_id=engine_result.winner_team_id,
        assumptions=engine_result.assumptions,
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
