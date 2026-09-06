
from baseball_sim.domain.contracts import (
    ComparePlayersRequest,
    ComparePlayersResult,
    DeterministicContext,
    MetricComparison,
    MetricSource,
    PlayByPlayEvent,
    PredictGameRequest,
    PredictGameResult,
    SimulateGamePlayByPlayResult,
    SimulateGameRequest,
    SimulateGameResult,
)
from baseball_sim.domain.lineup_provider import LineupProvider
from baseball_sim.domain.stats_provider import (
    DEFAULT_STATS_PROVIDER,
    METRIC_SPECS,
    StatsProvider,
)
from baseball_sim.sim.profiles import TeamProfile, synthetic_team_profile
from baseball_sim.sim.rulesets import SimulationRuleset
from baseball_sim.sim.state_machine import (
    GameSimulationTrace,
    PlayTrace,
    simulate_game_state_machine,
    simulate_game_trace,
)
from baseball_sim.sim.winprob import (
    HOME_FIELD_RUNS,
    GameSituation,
    team_run_rates,
    win_probability,
)

HOME_FIELD_RUNS_LABEL = f"{HOME_FIELD_RUNS:g}-run"

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
            left_source=left_rating.sources[name],
            right_source=right_rating.sources[name],
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


def _resolve_profiles(
    request: SimulateGameRequest,
    provider: StatsProvider | None,
) -> tuple[TeamProfile | None, TeamProfile | None, list[str]]:
    if provider is None:
        return None, None, []
    seed = request.context.seed
    home_profile = provider.team_profile(team_id=request.home_team_id, seed=seed)
    away_profile = provider.team_profile(team_id=request.away_team_id, seed=seed)
    note = (
        "Team profiles sourced from stats provider "
        f"({type(provider).__name__}) rather than seed-only synthesis."
    )
    return home_profile, away_profile, [note]


def simulate_game(
    request: SimulateGameRequest,
    *,
    ruleset: SimulationRuleset | None = None,
    ruleset_checksum: str | None = None,
    provider: StatsProvider | None = None,
) -> SimulateGameResult:
    home_profile, away_profile, extra_assumptions = _resolve_profiles(request, provider)
    engine_result = simulate_game_state_machine(
        seed=request.context.seed,
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


def _to_play_by_play_event(play: PlayTrace, home_win_probability: float) -> PlayByPlayEvent:
    return PlayByPlayEvent(
        play_index=play.play_index,
        inning=play.inning,
        half=play.half,
        batting_team_id=play.batting_team_id,
        fielding_team_id=play.fielding_team_id,
        event=play.event,
        outs_before=play.outs_before,
        outs_after=play.outs_after,
        bases_before=play.bases_before,
        bases_after=play.bases_after,
        runs_scored_on_play=play.runs_scored_on_play,
        home_score_after_play=play.home_score_after_play,
        away_score_after_play=play.away_score_after_play,
        description=play.description,
        batter_id=play.batter_id,
        batter_name=play.batter_name,
        home_win_probability=home_win_probability,
    )


def simulate_game_play_by_play(
    request: SimulateGameRequest,
    *,
    ruleset: SimulationRuleset | None = None,
    ruleset_checksum: str | None = None,
    provider: StatsProvider | None = None,
    lineup_provider: LineupProvider | None = None,
) -> SimulateGamePlayByPlayResult:
    home_profile, away_profile, extra_assumptions = _resolve_profiles(request, provider)
    seed = request.context.seed
    home_lineup = None
    away_lineup = None
    if lineup_provider is not None:
        home_lineup = lineup_provider.lineup(team_id=request.home_team_id, seed=seed)
        away_lineup = lineup_provider.lineup(team_id=request.away_team_id, seed=seed)
    trace = simulate_game_trace(
        seed=seed,
        home_team_id=request.home_team_id,
        away_team_id=request.away_team_id,
        scheduled_innings=request.innings,
        ruleset=ruleset,
        ruleset_checksum=ruleset_checksum,
        home_profile=home_profile,
        away_profile=away_profile,
        home_lineup=home_lineup,
        away_lineup=away_lineup,
    )
    engine_result = trace.result
    summary = SimulateGameResult(
        home_team_id=request.home_team_id,
        away_team_id=request.away_team_id,
        innings_played=engine_result.innings_played,
        home_score=engine_result.home_score,
        away_score=engine_result.away_score,
        winner_team_id=engine_result.winner_team_id,
        assumptions=engine_result.assumptions + extra_assumptions,
    )
    return SimulateGamePlayByPlayResult(
        summary=summary,
        line_score_home=trace.line_score_home,
        line_score_away=trace.line_score_away,
        plays=_plays_with_win_probability(
            trace=trace,
            home_profile=home_profile,
            away_profile=away_profile,
            seed=seed,
            home_team_id=request.home_team_id,
            away_team_id=request.away_team_id,
            scheduled_innings=request.innings,
        ),
    )


def _resolved_profiles(
    *,
    provider: StatsProvider | None,
    seed: int,
    home_team_id: int,
    away_team_id: int,
) -> tuple[TeamProfile, TeamProfile, MetricSource]:
    """Profiles for both clubs plus whether they actually came from ingested stats.

    A provider can still fall back per club, so rather than trusting that one was
    supplied, compare against the seeded profile: if it differs, it came from data.
    """

    synthetic_home = synthetic_team_profile(seed=seed, team_id=home_team_id)
    synthetic_away = synthetic_team_profile(seed=seed, team_id=away_team_id)
    if provider is None:
        return synthetic_home, synthetic_away, "synthetic"

    home = provider.team_profile(team_id=home_team_id, seed=seed)
    away = provider.team_profile(team_id=away_team_id, seed=seed)
    both_real = home != synthetic_home and away != synthetic_away
    return home, away, "real" if both_real else "synthetic"


def _plays_with_win_probability(
    *,
    trace: GameSimulationTrace,
    home_profile: TeamProfile | None,
    away_profile: TeamProfile | None,
    seed: int,
    home_team_id: int,
    away_team_id: int,
    scheduled_innings: int,
) -> list[PlayByPlayEvent]:
    home = home_profile or synthetic_team_profile(seed=seed, team_id=home_team_id)
    away = away_profile or synthetic_team_profile(seed=seed, team_id=away_team_id)
    home_rate, away_rate = team_run_rates(home_profile=home, away_profile=away)

    events: list[PlayByPlayEvent] = []
    for play in trace.plays:
        probability = win_probability(
            home_rate=home_rate,
            away_rate=away_rate,
            scheduled_innings=scheduled_innings,
            situation=GameSituation(
                inning=play.inning,
                half=play.half,
                outs=play.outs_after,
                bases=play.bases_after,
                home_score=play.home_score_after_play,
                away_score=play.away_score_after_play,
            ),
        )
        events.append(_to_play_by_play_event(play, probability.home))
    return events


def predict_game(
    request: PredictGameRequest,
    *,
    provider: StatsProvider | None = None,
) -> PredictGameResult:
    seed = request.context.seed
    home_profile, away_profile, source = _resolved_profiles(
        provider=provider,
        seed=seed,
        home_team_id=request.home_team_id,
        away_team_id=request.away_team_id,
    )
    home_rate, away_rate = team_run_rates(home_profile=home_profile, away_profile=away_profile)
    probability = win_probability(home_rate=home_rate, away_rate=away_rate)

    return PredictGameResult(
        home_team_id=request.home_team_id,
        away_team_id=request.away_team_id,
        home_win_probability=probability.home,
        away_win_probability=probability.away,
        confidence=round(abs(probability.home - 0.5) * 2.0, 4),
        source=source,
        home_expected_runs=probability.home_expected_runs,
        away_expected_runs=probability.away_expected_runs,
        explanation=[
            "Pregame baseline: team run rates from the matchup profiles, plus a "
            f"{HOME_FIELD_RUNS_LABEL} home-field allowance.",
            "Probability is a logistic on the projected run differential.",
            f"Team profiles are {source}.",
            "Baseline model, not calibrated — see ADR-004.",
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
