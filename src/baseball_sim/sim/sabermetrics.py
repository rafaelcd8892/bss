"""Deterministic sabermetric computation from raw counting stats.

These are pure functions: given raw counting lines and a fixed set of league
weights/constants, they return identical metric values every time. No randomness,
no I/O. This module is the analytical core that turns real ingested MLB stats into
the rate metrics consumed by the compare endpoint and the simulator team profiles.

Formulas follow the standard public sabermetric definitions (FanGraphs):
- wOBA   = (wBB*BB + wHBP*HBP + w1B*1B + w2B*2B + w3B*3B + wHR*HR) / (AB + BB - IBB + SF + HBP)
- wRC+   = ((wOBA - lgwOBA) / wOBAScale + lgR/PA) / (lgR/PA) * 100   (park-neutral baseline)
- FIP    = ((13*HR + 3*(BB + HBP) - 2*K) / IP) + FIP_constant
- K/BB   = strikeouts / walks
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WobaWeights:
    """Linear weights and league context for wOBA / wRC+ (FanGraphs 2023 baseline)."""

    w_bb: float = 0.696
    w_hbp: float = 0.726
    w_1b: float = 0.883
    w_2b: float = 1.244
    w_3b: float = 1.569
    w_hr: float = 2.004
    woba_scale: float = 1.157
    league_woba: float = 0.318
    league_runs_per_pa: float = 0.122


@dataclass(frozen=True)
class FipConstants:
    """Coefficients for the FIP family (constant is the league-normalizing term)."""

    hr_weight: float = 13.0
    bb_hbp_weight: float = 3.0
    k_weight: float = 2.0
    fip_constant: float = 3.10


DEFAULT_WOBA_WEIGHTS = WobaWeights()
DEFAULT_FIP_CONSTANTS = FipConstants()


@dataclass(frozen=True)
class RawBattingLine:
    """Season batting counting stats for a single player."""

    plate_appearances: int
    at_bats: int
    singles: int
    doubles: int
    triples: int
    home_runs: int
    walks: int
    intentional_walks: int
    hit_by_pitch: int
    sacrifice_flies: int
    strikeouts: int
    stolen_bases: int
    # Added once the ingest widened. Defaults keep older construction working, and a
    # zero here means "not ingested" for every metric that needs the field.
    runs: int = 0
    runs_batted_in: int = 0
    caught_stealing: int = 0
    sacrifice_bunts: int = 0
    ground_into_double_play: int = 0
    ground_outs: int = 0
    air_outs: int = 0
    games_played: int = 0

    @property
    def hits(self) -> int:
        return self.singles + self.doubles + self.triples + self.home_runs

    @property
    def total_bases(self) -> int:
        return self.singles + 2 * self.doubles + 3 * self.triples + 4 * self.home_runs

    @property
    def on_base_denominator(self) -> int:
        return self.at_bats + self.walks + self.hit_by_pitch + self.sacrifice_flies

    @property
    def woba_denominator(self) -> int:
        return (
            self.at_bats
            + self.walks
            - self.intentional_walks
            + self.sacrifice_flies
            + self.hit_by_pitch
        )


@dataclass(frozen=True)
class RawPitchingLine:
    """Season pitching counting stats for a single player."""

    innings_pitched: float
    strikeouts: int
    walks: int
    hit_by_pitch: int
    home_runs: int
    # Added once the ingest widened; see RawBattingLine for the defaulting rationale.
    batters_faced: int = 0
    earned_runs: int = 0
    hits_allowed: int = 0
    ground_outs: int = 0
    air_outs: int = 0
    games_played: int = 0
    games_started: int = 0


def compute_woba(line: RawBattingLine, weights: WobaWeights = DEFAULT_WOBA_WEIGHTS) -> float:
    denominator = line.woba_denominator
    if denominator <= 0:
        return 0.0
    numerator = (
        weights.w_bb * (line.walks - line.intentional_walks)
        + weights.w_hbp * line.hit_by_pitch
        + weights.w_1b * line.singles
        + weights.w_2b * line.doubles
        + weights.w_3b * line.triples
        + weights.w_hr * line.home_runs
    )
    return numerator / denominator


def compute_wrc_plus(
    woba: float,
    weights: WobaWeights = DEFAULT_WOBA_WEIGHTS,
) -> float:
    """League- and scale-relative wRC+ (park-neutral; 100 == league average)."""

    runs_above = (woba - weights.league_woba) / weights.woba_scale
    wraa_per_pa = runs_above + weights.league_runs_per_pa
    if weights.league_runs_per_pa <= 0:
        return 100.0
    return (wraa_per_pa / weights.league_runs_per_pa) * 100.0


def compute_fip(
    line: RawPitchingLine,
    constants: FipConstants = DEFAULT_FIP_CONSTANTS,
) -> float:
    if line.innings_pitched <= 0:
        return constants.fip_constant
    raw = (
        constants.hr_weight * line.home_runs
        + constants.bb_hbp_weight * (line.walks + line.hit_by_pitch)
        - constants.k_weight * line.strikeouts
    ) / line.innings_pitched
    return raw + constants.fip_constant


def compute_k_bb_ratio(strikeouts: int, walks: int) -> float:
    """Strikeout-to-walk ratio. Walks of 0 are treated as 1 to avoid divide-by-zero."""

    return strikeouts / max(walks, 1)


def _rate(numerator: float, denominator: float) -> float | None:
    """A rate, or None when the denominator gives it no meaning."""

    return numerator / denominator if denominator > 0 else None


def compute_batting_average(line: RawBattingLine) -> float | None:
    return _rate(line.hits, line.at_bats)


def compute_obp(line: RawBattingLine) -> float | None:
    """On-base percentage: (H + BB + HBP) / (AB + BB + HBP + SF)."""

    reached = line.hits + line.walks + line.hit_by_pitch
    return _rate(reached, line.on_base_denominator)


def compute_slg(line: RawBattingLine) -> float | None:
    """Slugging: total bases per at-bat."""

    return _rate(line.total_bases, line.at_bats)


def compute_ops(line: RawBattingLine) -> float | None:
    obp = compute_obp(line)
    slg = compute_slg(line)
    return None if obp is None or slg is None else obp + slg


def compute_iso(line: RawBattingLine) -> float | None:
    """Isolated power: extra bases per at-bat, i.e. slugging minus average."""

    slg = compute_slg(line)
    average = compute_batting_average(line)
    return None if slg is None or average is None else slg - average


def compute_babip(line: RawBattingLine) -> float | None:
    """Batting average on balls in play.

    Removes the outcomes the defense never touches — strikeouts and home runs — so
    the denominator is only balls that were actually fielded.
    """

    balls_in_play = (
        line.at_bats - line.strikeouts - line.home_runs + line.sacrifice_flies
    )
    return _rate(line.hits - line.home_runs, balls_in_play)


def compute_era(line: RawPitchingLine) -> float | None:
    return _rate(line.earned_runs * 9.0, line.innings_pitched)


def compute_whip(line: RawPitchingLine) -> float | None:
    """Walks and hits per inning pitched."""

    return _rate(line.walks + line.hits_allowed, line.innings_pitched)


def compute_per_nine(count: int, innings_pitched: float) -> float | None:
    return _rate(count * 9.0, innings_pitched)


def compute_strikeout_rate(line: RawPitchingLine) -> float | None:
    """Strikeouts per batter faced — a better rate stat than K/BB or K/9."""

    return _rate(line.strikeouts, line.batters_faced)


def compute_walk_rate(line: RawPitchingLine) -> float | None:
    return _rate(line.walks, line.batters_faced)


def compute_ground_ball_rate(line: RawPitchingLine) -> float | None:
    """Share of batted-ball outs that stayed on the ground.

    An approximation: the API exposes ground and air *outs*, not every batted ball,
    so this is not the true GB% a batted-ball feed would give.
    """

    return _rate(line.ground_outs, line.ground_outs + line.air_outs)


@dataclass(frozen=True)
class RawFieldingLine:
    """Season fielding stats for one player at one position.

    The API reports a split per position played, so a utility player has several of
    these. Positions with no innings (a designated hitter's entry) are not fielding.
    """

    position: str
    innings: float
    put_outs: int
    assists: int
    errors: int
    chances: int = 0
    double_plays: int = 0
    games: int = 0
    games_started: int = 0

    @property
    def plays_made(self) -> int:
        return self.put_outs + self.assists


def compute_range_factor_per_nine(line: RawFieldingLine) -> float | None:
    """Plays made per nine innings at a position.

    Only comparable *within* a position: a first baseman clears 7 and a left fielder
    barely 2, because the position dictates how many balls arrive. Comparing teams on
    a raw average of this would measure their positional mix, not their defense.
    """

    return _rate(line.plays_made * 9.0, line.innings)


def compute_fielding_percentage(line: RawFieldingLine) -> float | None:
    """Share of chances handled cleanly."""

    return _rate(line.plays_made, line.plays_made + line.errors)
