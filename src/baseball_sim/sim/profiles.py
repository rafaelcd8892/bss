"""Team matchup profiles consumed by the simulation state machine.

A :class:`TeamProfile` is seven factors in ``[0, 1]`` describing how a team hits and
prevents runs. Two builders produce it:

- :func:`synthetic_team_profile` — deterministic hash of ``(seed, team_id)``. Used as
  the fallback when no real stats are available (preserves prior behavior exactly).
- :func:`team_profile_from_stats` — aggregates real ingested batting/pitching/fielding
  lines into the same factor space via documented league reference ranges.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from baseball_sim.sim.hashing import unit_interval
from baseball_sim.sim.sabermetrics import (
    DEFAULT_FIP_CONSTANTS,
    DEFAULT_WOBA_WEIGHTS,
    FipConstants,
    RawBattingLine,
    RawFieldingLine,
    RawPitchingLine,
    WobaWeights,
    compute_fip,
    compute_k_bb_ratio,
    compute_range_factor_per_nine,
    compute_woba,
)

# Synthetic-profile salts (kept identical to the original state-machine hashing
# so seeded simulations are byte-for-byte reproducible).
_OFFENSE_SALT = 701
_DISCIPLINE_SALT = 709
_POWER_SALT = 719
_SPEED_SALT = 727
_PREVENTION_SALT = 733
_COMMAND_SALT = 739
_RANGE_SALT = 743

# League reference ranges used to map real aggregate metrics into [0, 1] factors.
_WOBA_RANGE = (0.290, 0.360)
_BB_RATE_RANGE = (0.060, 0.120)
_ISO_RANGE = (0.120, 0.220)
_SB_RATE_RANGE = (0.000, 0.100)
_FIP_RANGE = (3.000, 5.000)
_K_BB_RANGE = (1.500, 4.000)
_NEUTRAL_RANGE_FACTOR = 0.5

# Floors applied when aggregating a club. A pitcher's handful of plate appearances
# would otherwise be summed into the team's wOBA, and a position player's mop-up
# inning into its FIP. Filtering the ingest by position helps, but `primary_position`
# can be stale; a floor here does not depend on that being right.
MIN_TEAM_BATTING_PA = 25
MIN_TEAM_PITCHING_IP = 5.0
#: A fielding split below this is a cameo at a position, not evidence of range.
MIN_TEAM_FIELDING_INNINGS = 20.0

#: Band for a club's range relative to the league at the same positions. A club making
#: 12% fewer plays than average at its positions maps to 0, and 12% more to 1.
_RELATIVE_RANGE_BAND = (0.88, 1.12)


@dataclass(frozen=True)
class TeamProfile:
    offense: float
    discipline: float
    power: float
    speed: float
    prevention: float
    command: float
    range_factor: float


def synthetic_team_profile(*, seed: int, team_id: int) -> TeamProfile:
    return TeamProfile(
        offense=unit_interval(seed=seed, entity_id=team_id, salt=_OFFENSE_SALT),
        discipline=unit_interval(seed=seed, entity_id=team_id, salt=_DISCIPLINE_SALT),
        power=unit_interval(seed=seed, entity_id=team_id, salt=_POWER_SALT),
        speed=unit_interval(seed=seed, entity_id=team_id, salt=_SPEED_SALT),
        prevention=unit_interval(seed=seed, entity_id=team_id, salt=_PREVENTION_SALT),
        command=unit_interval(seed=seed, entity_id=team_id, salt=_COMMAND_SALT),
        range_factor=unit_interval(seed=seed, entity_id=team_id, salt=_RANGE_SALT),
    )


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return _NEUTRAL_RANGE_FACTOR
    fraction = (value - low) / (high - low)
    return min(1.0, max(0.0, fraction))


def _normalize_inverted(value: float, low: float, high: float) -> float:
    return 1.0 - _normalize(value, low, high)


def league_range_factors(
    lines: Iterable[RawFieldingLine],
) -> dict[str, float]:
    """Innings-weighted league range factor for each position.

    Computed from the ingested league rather than hardcoded, so the baseline moves
    with the data instead of drifting away from it.
    """

    totals: dict[str, list[float]] = {}
    for line in lines:
        if line.innings <= 0:
            continue
        plays, innings = totals.setdefault(line.position, [0.0, 0.0])
        totals[line.position] = [plays + line.plays_made, innings + line.innings]
    return {
        position: (plays * 9.0) / innings
        for position, (plays, innings) in totals.items()
        if innings > 0
    }


def relative_range(
    lines: Sequence[RawFieldingLine], baselines: Mapping[str, float]
) -> float | None:
    """A club's plays made against what the league makes at the same positions.

    Weighted by innings, so a regular shortstop counts for more than a September
    call-up, and normalized per position so the number reflects defense rather than
    which positions the club happened to field.
    """

    weighted = 0.0
    innings_total = 0.0
    for line in lines:
        if line.innings < MIN_TEAM_FIELDING_INNINGS:
            continue
        baseline = baselines.get(line.position)
        player_rate = compute_range_factor_per_nine(line)
        if not baseline or player_rate is None:
            continue
        weighted += (player_rate / baseline) * line.innings
        innings_total += line.innings
    return weighted / innings_total if innings_total > 0 else None


def team_profile_from_stats(
    *,
    batting_lines: Sequence[RawBattingLine],
    pitching_lines: Sequence[RawPitchingLine],
    fielding_lines: Sequence[RawFieldingLine] = (),
    league_range_baselines: Mapping[str, float] | None = None,
    weights: WobaWeights = DEFAULT_WOBA_WEIGHTS,
    fip_constants: FipConstants = DEFAULT_FIP_CONSTANTS,
) -> TeamProfile | None:
    """Build a profile from aggregated team stats, or ``None`` if there is no data."""

    if not batting_lines and not pitching_lines:
        return None

    counted_batting = [
        line for line in batting_lines if line.plate_appearances >= MIN_TEAM_BATTING_PA
    ]
    counted_pitching = [
        line for line in pitching_lines if line.innings_pitched >= MIN_TEAM_PITCHING_IP
    ]

    offense, discipline, power, speed = _offense_factors(counted_batting, weights)
    prevention, command = _pitching_factors(counted_pitching, fip_constants)

    # Without fielding data, or without a league to compare against, range stays
    # neutral rather than being guessed.
    relative = (
        relative_range(fielding_lines, league_range_baselines)
        if fielding_lines and league_range_baselines
        else None
    )
    range_factor = (
        _normalize(relative, *_RELATIVE_RANGE_BAND)
        if relative is not None
        else _NEUTRAL_RANGE_FACTOR
    )

    return TeamProfile(
        offense=offense,
        discipline=discipline,
        power=power,
        speed=speed,
        prevention=prevention,
        command=command,
        range_factor=range_factor,
    )


def _offense_factors(
    batting_lines: Sequence[RawBattingLine],
    weights: WobaWeights,
) -> tuple[float, float, float, float]:
    if not batting_lines:
        return (
            _NEUTRAL_RANGE_FACTOR,
            _NEUTRAL_RANGE_FACTOR,
            _NEUTRAL_RANGE_FACTOR,
            _NEUTRAL_RANGE_FACTOR,
        )

    team_line = aggregate_batting(batting_lines)
    team_woba = compute_woba(team_line, weights)

    plate_appearances = max(team_line.plate_appearances, 1)
    at_bats = max(team_line.at_bats, 1)
    bb_rate = team_line.walks / plate_appearances
    iso = (team_line.doubles + 2 * team_line.triples + 3 * team_line.home_runs) / at_bats
    sb_rate = team_line.stolen_bases / plate_appearances

    return (
        _normalize(team_woba, *_WOBA_RANGE),
        _normalize(bb_rate, *_BB_RATE_RANGE),
        _normalize(iso, *_ISO_RANGE),
        _normalize(sb_rate, *_SB_RATE_RANGE),
    )


def _pitching_factors(
    pitching_lines: Sequence[RawPitchingLine],
    fip_constants: FipConstants,
) -> tuple[float, float]:
    if not pitching_lines:
        return (_NEUTRAL_RANGE_FACTOR, _NEUTRAL_RANGE_FACTOR)

    team_line = aggregate_pitching(pitching_lines)
    team_fip = compute_fip(team_line, fip_constants)
    k_bb = compute_k_bb_ratio(team_line.strikeouts, team_line.walks)

    return (
        _normalize_inverted(team_fip, *_FIP_RANGE),
        _normalize(k_bb, *_K_BB_RANGE),
    )


def aggregate_batting(lines: Sequence[RawBattingLine]) -> RawBattingLine:
    """Sum batting lines into a single team line."""

    return RawBattingLine(
        plate_appearances=sum(line.plate_appearances for line in lines),
        at_bats=sum(line.at_bats for line in lines),
        singles=sum(line.singles for line in lines),
        doubles=sum(line.doubles for line in lines),
        triples=sum(line.triples for line in lines),
        home_runs=sum(line.home_runs for line in lines),
        walks=sum(line.walks for line in lines),
        intentional_walks=sum(line.intentional_walks for line in lines),
        hit_by_pitch=sum(line.hit_by_pitch for line in lines),
        sacrifice_flies=sum(line.sacrifice_flies for line in lines),
        strikeouts=sum(line.strikeouts for line in lines),
        stolen_bases=sum(line.stolen_bases for line in lines),
    )


def aggregate_pitching(lines: Sequence[RawPitchingLine]) -> RawPitchingLine:
    """Sum pitching lines into a single team line."""

    return RawPitchingLine(
        innings_pitched=round(sum(line.innings_pitched for line in lines), 2),
        strikeouts=sum(line.strikeouts for line in lines),
        walks=sum(line.walks for line in lines),
        hit_by_pitch=sum(line.hit_by_pitch for line in lines),
        home_runs=sum(line.home_runs for line in lines),
    )
