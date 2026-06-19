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

    @property
    def hits(self) -> int:
        return self.singles + self.doubles + self.triples + self.home_runs

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
