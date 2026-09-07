from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from baseball_sim.sim.hashing import unit_interval
from baseball_sim.sim.lineups import Batter, synthetic_lineup
from baseball_sim.sim.pitching import MoundAssignment, PitchingStaff, synthetic_staff
from baseball_sim.sim.profiles import TeamProfile, synthetic_team_profile
from baseball_sim.sim.rulesets import (
    DEFAULT_EVENT_MODEL,
    DEFAULT_RULESET,
    EventModel,
    EventRates,
    SimulationRuleset,
)

HalfInningLabel = Literal["top", "bottom"]
PlateAppearanceEvent = Literal[
    "out",
    "walk",
    "single",
    "double",
    "triple",
    "home_run",
    "tiebreaker",
]


def _clamp(value: float, low: float, high: float) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


@dataclass
class DeterministicRng:
    seed: int
    home_team_id: int
    away_team_id: int
    cursor: int = 0

    def next_unit(self) -> float:
        game_hash = (
            (self.home_team_id * 97_531) ^ (self.away_team_id * 193_939) ^ (self.cursor * 834_927)
        ) & 0xFFFFFFFF
        value = unit_interval(seed=self.seed, entity_id=self.cursor, salt=game_hash)
        self.cursor += 1
        return value


@dataclass(frozen=True)
class PlayTrace:
    play_index: int
    inning: int
    half: HalfInningLabel
    batting_team_id: int
    fielding_team_id: int
    event: PlateAppearanceEvent
    outs_before: int
    outs_after: int
    bases_before: str
    bases_after: str
    runs_scored_on_play: int
    home_score_after_play: int
    away_score_after_play: int
    description: str
    batter_id: int | None = None
    batter_name: str | None = None
    pitcher_id: int | None = None
    pitcher_name: str | None = None


@dataclass(frozen=True)
class HalfInningResult:
    runs: int
    plate_appearances: int
    hits: int
    walks: int
    home_runs: int
    walkoff: bool
    home_score_end: int
    away_score_end: int
    plays: list[PlayTrace]
    ending_order_index: int = 0


@dataclass(frozen=True)
class GameEngineResult:
    home_score: int
    away_score: int
    innings_played: int
    winner_team_id: int
    assumptions: list[str]


@dataclass(frozen=True)
class GameSimulationTrace:
    result: GameEngineResult
    plays: list[PlayTrace]
    line_score_home: list[int]
    line_score_away: list[int]


@dataclass
class _HalfInningState:
    outs: int = 0
    runs: int = 0
    plate_appearances: int = 0
    hits: int = 0
    walks: int = 0
    home_runs: int = 0
    on_first: bool = False
    on_second: bool = False
    on_third: bool = False


def simulate_game_state_machine(
    *,
    seed: int,
    home_team_id: int,
    away_team_id: int,
    scheduled_innings: int,
    ruleset: SimulationRuleset | None = None,
    ruleset_checksum: str | None = None,
    home_profile: TeamProfile | None = None,
    away_profile: TeamProfile | None = None,
) -> GameEngineResult:
    trace = simulate_game_trace(
        seed=seed,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        scheduled_innings=scheduled_innings,
        ruleset=ruleset,
        ruleset_checksum=ruleset_checksum,
        home_profile=home_profile,
        away_profile=away_profile,
    )
    return trace.result


def simulate_game_trace(
    *,
    seed: int,
    home_team_id: int,
    away_team_id: int,
    scheduled_innings: int,
    ruleset: SimulationRuleset | None = None,
    ruleset_checksum: str | None = None,
    home_profile: TeamProfile | None = None,
    away_profile: TeamProfile | None = None,
    home_lineup: list[Batter] | None = None,
    away_lineup: list[Batter] | None = None,
    home_staff: PitchingStaff | None = None,
    away_staff: PitchingStaff | None = None,
    rotation_slot: int = 0,
) -> GameSimulationTrace:
    active_ruleset = ruleset if ruleset is not None else DEFAULT_RULESET
    effective_scheduled_innings = max(1, min(scheduled_innings, active_ruleset.max_innings))

    rng = DeterministicRng(seed=seed, home_team_id=home_team_id, away_team_id=away_team_id)
    home_profile = (
        home_profile
        if home_profile is not None
        else synthetic_team_profile(seed=seed, team_id=home_team_id)
    )
    away_profile = (
        away_profile
        if away_profile is not None
        else synthetic_team_profile(seed=seed, team_id=away_team_id)
    )
    home_lineup = (
        home_lineup if home_lineup else synthetic_lineup(seed=seed, team_id=home_team_id)
    )
    away_lineup = (
        away_lineup if away_lineup else synthetic_lineup(seed=seed, team_id=away_team_id)
    )
    # One assignment per club, carried across half-innings: a starter's outing spans
    # innings, so the mound cannot be resolved from within a single half.
    home_mound = MoundAssignment(
        home_staff if home_staff else synthetic_staff(seed=seed, team_id=home_team_id),
        rotation_slot=rotation_slot,
    )
    away_mound = MoundAssignment(
        away_staff if away_staff else synthetic_staff(seed=seed, team_id=away_team_id),
        rotation_slot=rotation_slot,
    )

    home_score = 0
    away_score = 0
    inning = 1
    play_index = 1
    away_order_index = 0
    home_order_index = 0
    reached_plate_appearance_cap = False

    plays: list[PlayTrace] = []
    line_score_home: list[int] = []
    line_score_away: list[int] = []

    while inning <= active_ruleset.max_innings:
        top = _simulate_half_inning(
            rng=rng,
            offense_profile=away_profile,
            defense_profile=home_profile,
            is_home_batting=False,
            inning_number=inning,
            half="top",
            home_score=home_score,
            away_score=away_score,
            scheduled_innings=effective_scheduled_innings,
            ruleset=active_ruleset,
            play_index_start=play_index,
            batting_team_id=away_team_id,
            fielding_team_id=home_team_id,
            offense_lineup=away_lineup,
            order_index_start=away_order_index,
            mound=home_mound,
        )
        play_index += len(top.plays)
        away_order_index = top.ending_order_index
        plays.extend(top.plays)
        home_score = top.home_score_end
        away_score = top.away_score_end
        line_score_away.append(top.runs)
        reached_plate_appearance_cap = reached_plate_appearance_cap or (
            top.plate_appearances >= active_ruleset.max_plate_appearances_per_half
        )

        if (
            inning >= effective_scheduled_innings
            and active_ruleset.skip_home_bottom_if_leading_after_top_final
            and home_score > away_score
        ):
            line_score_home.append(0)
            break

        bottom = _simulate_half_inning(
            rng=rng,
            offense_profile=home_profile,
            defense_profile=away_profile,
            is_home_batting=True,
            inning_number=inning,
            half="bottom",
            home_score=home_score,
            away_score=away_score,
            scheduled_innings=effective_scheduled_innings,
            ruleset=active_ruleset,
            play_index_start=play_index,
            batting_team_id=home_team_id,
            fielding_team_id=away_team_id,
            offense_lineup=home_lineup,
            order_index_start=home_order_index,
            mound=away_mound,
        )
        play_index += len(bottom.plays)
        home_order_index = bottom.ending_order_index
        plays.extend(bottom.plays)
        home_score = bottom.home_score_end
        away_score = bottom.away_score_end
        line_score_home.append(bottom.runs)
        reached_plate_appearance_cap = reached_plate_appearance_cap or (
            bottom.plate_appearances >= active_ruleset.max_plate_appearances_per_half
        )

        if bottom.walkoff:
            break

        if inning >= effective_scheduled_innings and home_score != away_score:
            break

        inning += 1

    innings_played = min(inning, active_ruleset.max_innings)
    if home_score == away_score:
        tiebreak_roll = rng.next_unit()
        home_wins = tiebreak_roll >= 0.5
        if home_wins:
            home_score += 1
            home_score_after = home_score
            away_score_after = away_score
            winner = home_team_id
        else:
            away_score += 1
            home_score_after = home_score
            away_score_after = away_score
            winner = away_team_id

        plays.append(
            PlayTrace(
                play_index=play_index,
                inning=innings_played,
                half="bottom",
                batting_team_id=home_team_id if home_wins else away_team_id,
                fielding_team_id=away_team_id if home_wins else home_team_id,
                event="tiebreaker",
                outs_before=3,
                outs_after=3,
                bases_before="000",
                bases_after="000",
                runs_scored_on_play=1,
                home_score_after_play=home_score_after,
                away_score_after_play=away_score_after,
                description=(
                    "Deterministic tiebreak awarded final run to "
                    f"team {home_team_id if home_wins else away_team_id}."
                ),
            )
        )
    else:
        winner = home_team_id if home_score > away_score else away_team_id

    assumptions = [
        "Plate-appearance-level deterministic state machine with explicit base/outs transitions.",
        "Event probabilities are team-profile matchup based "
        "(offense, discipline, power, prevention).",
        "Home lead after top of final inning can end game without bottom-half simulation.",
        "Extra innings use configurable cap with deterministic tiebreak resolution if still tied.",
        f"ruleset_id={active_ruleset.ruleset_id}",
    ]
    if ruleset_checksum is not None:
        assumptions.append(f"ruleset_checksum={ruleset_checksum}")
    if reached_plate_appearance_cap:
        assumptions.append(
            "At least one half-inning hit safety plate-appearance cap before three outs."
        )

    result = GameEngineResult(
        home_score=home_score,
        away_score=away_score,
        innings_played=innings_played,
        winner_team_id=winner,
        assumptions=assumptions,
    )

    _normalize_line_score_lengths(line_score_home=line_score_home, line_score_away=line_score_away)
    return GameSimulationTrace(
        result=result,
        plays=plays,
        line_score_home=line_score_home,
        line_score_away=line_score_away,
    )


def _simulate_half_inning(
    *,
    rng: DeterministicRng,
    offense_profile: TeamProfile,
    defense_profile: TeamProfile,
    is_home_batting: bool,
    inning_number: int,
    half: HalfInningLabel,
    home_score: int,
    away_score: int,
    scheduled_innings: int,
    ruleset: SimulationRuleset,
    play_index_start: int,
    batting_team_id: int,
    fielding_team_id: int,
    offense_lineup: list[Batter],
    order_index_start: int,
    mound: MoundAssignment,
) -> HalfInningResult:
    probabilities = _event_probabilities(
        offense_profile=offense_profile,
        defense_profile=defense_profile,
        is_home_batting=is_home_batting,
        home_field_event_boost=ruleset.home_field_event_boost,
        event_model=ruleset.event_model,
    )

    state = _HalfInningState()
    if (
        ruleset.enable_runner_on_second_in_extras
        and inning_number >= ruleset.runner_on_second_start_inning
    ):
        state.on_second = True

    play_index = play_index_start
    order_index = order_index_start
    walkoff = False
    plays: list[PlayTrace] = []

    while state.outs < 3 and state.plate_appearances < ruleset.max_plate_appearances_per_half:
        outs_before = state.outs
        runs_before = state.runs
        bases_before = _bases_key(state)
        batter = _batter_at(offense_lineup, order_index)
        order_index += 1
        # Read the mound before the play: the pitcher of record is the one who threw
        # it, not whoever relieves him on the out it produced.
        pitcher = mound.current

        event = _sample_event(roll=rng.next_unit(), probabilities=probabilities)
        _apply_event(event=event, state=state)
        state.plate_appearances += 1

        runs_scored = state.runs - runs_before
        if is_home_batting:
            home_score += runs_scored
        else:
            away_score += runs_scored

        outs_after = state.outs
        bases_after = _bases_key(state)
        mound.record_outs(outs_after - outs_before)

        plays.append(
            PlayTrace(
                play_index=play_index,
                inning=inning_number,
                half=half,
                batting_team_id=batting_team_id,
                fielding_team_id=fielding_team_id,
                event=event,
                outs_before=outs_before,
                outs_after=outs_after,
                bases_before=bases_before,
                bases_after=bases_after,
                runs_scored_on_play=runs_scored,
                home_score_after_play=home_score,
                away_score_after_play=away_score,
                description=_describe_play(
                    event=event, runs_scored=runs_scored, outs_after=outs_after
                ),
                batter_id=batter.player_id if batter is not None else None,
                batter_name=batter.name if batter is not None else None,
                pitcher_id=pitcher.player_id if pitcher is not None else None,
                pitcher_name=pitcher.name if pitcher is not None else None,
            )
        )
        play_index += 1

        if (
            ruleset.enable_walkoff
            and is_home_batting
            and inning_number >= scheduled_innings
            and home_score > away_score
        ):
            walkoff = True
            break

    return HalfInningResult(
        runs=state.runs,
        plate_appearances=state.plate_appearances,
        hits=state.hits,
        walks=state.walks,
        home_runs=state.home_runs,
        walkoff=walkoff,
        home_score_end=home_score,
        away_score_end=away_score,
        plays=plays,
        ending_order_index=order_index,
    )


def _batter_at(lineup: list[Batter], order_index: int) -> Batter | None:
    if not lineup:
        return None
    return lineup[order_index % len(lineup)]


def _rate(rates: EventRates, *, drive: float, home_boost: float) -> float:
    """One outcome's probability: its league base, moved by the matchup and bounded."""

    return _clamp(
        rates.base + rates.sensitivity * drive + rates.home_boost * home_boost,
        rates.minimum,
        rates.maximum,
    )


def _event_probabilities(
    *,
    offense_profile: TeamProfile,
    defense_profile: TeamProfile,
    is_home_batting: bool,
    home_field_event_boost: float,
    event_model: EventModel = DEFAULT_EVENT_MODEL,
) -> dict[PlateAppearanceEvent, float]:
    model = event_model
    attack = (
        offense_profile.offense * model.attack_offense
        + offense_profile.discipline * model.attack_discipline
        + offense_profile.power * model.attack_power
        + offense_profile.speed * model.attack_speed
    )
    prevention = (
        defense_profile.prevention * model.prevention_prevention
        + defense_profile.command * model.prevention_command
        + defense_profile.range_factor * model.prevention_range
    )
    delta = attack - prevention
    home_batting_boost = home_field_event_boost if is_home_batting else 0.0

    # Each outcome responds to the part of the matchup that actually drives it: overall
    # strength for outs and singles, plate discipline against command for walks, power
    # against the glove for doubles, against the arm for home runs.
    out_prob = _rate(model.out, drive=delta, home_boost=home_batting_boost)
    walk_prob = _rate(
        model.walk,
        drive=offense_profile.discipline - defense_profile.command,
        home_boost=home_batting_boost,
    )
    single_prob = _rate(model.single, drive=delta, home_boost=home_batting_boost)
    double_prob = _rate(
        model.double,
        drive=offense_profile.power - defense_profile.range_factor,
        home_boost=home_batting_boost,
    )
    triple_prob = _rate(
        model.triple,
        drive=offense_profile.speed - defense_profile.range_factor,
        home_boost=home_batting_boost,
    )
    home_run_prob = _rate(
        model.home_run,
        drive=offense_profile.power - defense_profile.prevention,
        home_boost=home_batting_boost,
    )

    raw = {
        "out": out_prob,
        "walk": walk_prob,
        "single": single_prob,
        "double": double_prob,
        "triple": triple_prob,
        "home_run": home_run_prob,
        "tiebreaker": 0.0,
    }
    total = sum(raw[event] for event in ("out", "walk", "single", "double", "triple", "home_run"))
    return cast(
        dict[PlateAppearanceEvent, float],
        {event: probability / total for event, probability in raw.items()},
    )


def _sample_event(
    *,
    roll: float,
    probabilities: dict[PlateAppearanceEvent, float],
) -> PlateAppearanceEvent:
    threshold = 0.0
    for event in ("out", "walk", "single", "double", "triple", "home_run"):
        threshold += probabilities[event]
        if roll <= threshold:
            return event
    return "home_run"


def _apply_event(*, event: PlateAppearanceEvent, state: _HalfInningState) -> None:
    if event == "out":
        state.outs += 1
        return

    if event == "walk":
        state.walks += 1
        _advance_walk(state)
        return

    state.hits += 1
    if event == "single":
        _advance_single(state)
        return
    if event == "double":
        _advance_double(state)
        return
    if event == "triple":
        _advance_triple(state)
        return
    if event == "home_run":
        state.home_runs += 1
        _advance_home_run(state)
        return


def _advance_walk(state: _HalfInningState) -> None:
    if state.on_first and state.on_second and state.on_third:
        state.runs += 1
    if state.on_first and state.on_second:
        state.on_third = True
    if state.on_first:
        state.on_second = True
    state.on_first = True


def _advance_single(state: _HalfInningState) -> None:
    if state.on_third:
        state.runs += 1
    if state.on_second:
        state.runs += 1

    runner_from_first = state.on_first
    state.on_third = False
    state.on_second = runner_from_first
    state.on_first = True


def _advance_double(state: _HalfInningState) -> None:
    if state.on_third:
        state.runs += 1
    if state.on_second:
        state.runs += 1

    runner_from_first = state.on_first
    state.on_third = runner_from_first
    state.on_second = True
    state.on_first = False


def _advance_triple(state: _HalfInningState) -> None:
    state.runs += int(state.on_first) + int(state.on_second) + int(state.on_third)
    state.on_first = False
    state.on_second = False
    state.on_third = True


def _advance_home_run(state: _HalfInningState) -> None:
    state.runs += 1 + int(state.on_first) + int(state.on_second) + int(state.on_third)
    state.on_first = False
    state.on_second = False
    state.on_third = False


def _bases_key(state: _HalfInningState) -> str:
    return f"{int(state.on_first)}{int(state.on_second)}{int(state.on_third)}"


def _describe_play(*, event: PlateAppearanceEvent, runs_scored: int, outs_after: int) -> str:
    if event == "out":
        return f"Batter out. Outs: {outs_after}."
    if event == "walk":
        return "Walk issued."
    if event == "single":
        return "Single to the outfield." + _runs_suffix(runs_scored)
    if event == "double":
        return "Double into scoring position." + _runs_suffix(runs_scored)
    if event == "triple":
        return "Triple clears the bases lane." + _runs_suffix(runs_scored)
    if event == "home_run":
        return "Home run over the fence." + _runs_suffix(runs_scored)
    return "Deterministic tiebreak resolved."


def _runs_suffix(runs_scored: int) -> str:
    if runs_scored == 0:
        return ""
    if runs_scored == 1:
        return " 1 run scores."
    return f" {runs_scored} runs score."


def _normalize_line_score_lengths(
    *, line_score_home: list[int], line_score_away: list[int]
) -> None:
    max_length = max(len(line_score_home), len(line_score_away))
    while len(line_score_home) < max_length:
        line_score_home.append(0)
    while len(line_score_away) < max_length:
        line_score_away.append(0)
