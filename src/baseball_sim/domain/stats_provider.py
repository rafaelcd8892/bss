"""Stats providers: the seam between raw data and the analytical layer.

Both the compare endpoint and the simulator consume team/player ratings through a
:class:`StatsProvider`. This lets the same code path serve either real ingested MLB
stats or a deterministic synthetic fallback, chosen at the edge:

- :class:`SyntheticStatsProvider` reproduces the original hash-based values exactly,
  so seeded runs stay byte-for-byte reproducible when no data is available.
- :class:`StatLineStatsProvider` computes real sabermetrics from supplied stat lines
  and delegates any metric/team it cannot cover to a fallback provider.
- :class:`LayeredStatsProvider` chains providers (real first, synthetic last),
  mirroring the API-first-with-seeded-fallback philosophy of roster loading.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from baseball_sim.sim.hashing import scale
from baseball_sim.sim.profiles import (
    TeamProfile,
    synthetic_team_profile,
    team_profile_from_stats,
)
from baseball_sim.sim.sabermetrics import (
    DEFAULT_FIP_CONSTANTS,
    DEFAULT_WOBA_WEIGHTS,
    FipConstants,
    RawBattingLine,
    RawPitchingLine,
    WobaWeights,
    compute_fip,
    compute_k_bb_ratio,
    compute_woba,
    compute_wrc_plus,
)

MetricDirection = Literal["higher_is_better", "lower_is_better"]
RatingSource = Literal["synthetic", "real", "real_partial"]


@dataclass(frozen=True)
class MetricSpec:
    direction: MetricDirection
    minimum: float
    maximum: float
    decimals: int
    salt: int


# Canonical metric set and order. ``salt`` values match the original compare
# implementation so the synthetic provider is a drop-in for prior behavior.
METRIC_SPECS: dict[str, MetricSpec] = {
    "woba": MetricSpec("higher_is_better", 0.255, 0.415, 4, salt=1),
    "xwoba": MetricSpec("higher_is_better", 0.250, 0.430, 4, salt=2),
    "wrc_plus": MetricSpec("higher_is_better", 70.0, 175.0, 1, salt=3),
    "fip": MetricSpec("lower_is_better", 2.6, 5.2, 2, salt=4),
    "k_bb_ratio": MetricSpec("higher_is_better", 1.2, 6.0, 2, salt=5),
}


@dataclass(frozen=True)
class PlayerRating:
    player_id: int
    metrics: dict[str, float]
    source: RatingSource


class StatsProvider(Protocol):
    def player_rating(self, *, player_id: int, seed: int) -> PlayerRating: ...

    def team_profile(self, *, team_id: int, seed: int) -> TeamProfile: ...


class SyntheticStatsProvider:
    """Deterministic hash-based ratings — the always-available fallback."""

    def player_rating(self, *, player_id: int, seed: int) -> PlayerRating:
        metrics = {
            name: scale(
                seed=seed,
                entity_id=player_id,
                salt=spec.salt,
                minimum=spec.minimum,
                maximum=spec.maximum,
                decimals=spec.decimals,
            )
            for name, spec in METRIC_SPECS.items()
        }
        return PlayerRating(player_id=player_id, metrics=metrics, source="synthetic")

    def team_profile(self, *, team_id: int, seed: int) -> TeamProfile:
        return synthetic_team_profile(seed=seed, team_id=team_id)


class StatLineStatsProvider:
    """Real sabermetrics from ingested stat lines, with per-metric fallback.

    A position player contributes real hitting metrics (``woba``, ``wrc_plus``); a
    pitcher contributes real ``fip`` and ``k_bb_ratio``. Metrics not derivable from a
    player's data (e.g. a hitter's FIP, or ``xwoba`` which needs Statcast) are filled
    from ``fallback`` and the rating is marked ``real_partial``.
    """

    def __init__(
        self,
        *,
        batting_lines: Mapping[int, RawBattingLine],
        pitching_lines: Mapping[int, RawPitchingLine],
        team_batting: Mapping[int, Sequence[RawBattingLine]],
        team_pitching: Mapping[int, Sequence[RawPitchingLine]],
        fallback: StatsProvider | None = None,
        weights: WobaWeights = DEFAULT_WOBA_WEIGHTS,
        fip_constants: FipConstants = DEFAULT_FIP_CONSTANTS,
    ) -> None:
        self._batting = dict(batting_lines)
        self._pitching = dict(pitching_lines)
        self._team_batting = dict(team_batting)
        self._team_pitching = dict(team_pitching)
        self._fallback: StatsProvider = (
            fallback if fallback is not None else SyntheticStatsProvider()
        )
        self._weights = weights
        self._fip_constants = fip_constants

    def player_rating(self, *, player_id: int, seed: int) -> PlayerRating:
        batting = self._batting.get(player_id)
        pitching = self._pitching.get(player_id)
        if batting is None and pitching is None:
            return self._fallback.player_rating(player_id=player_id, seed=seed)

        baseline = self._fallback.player_rating(player_id=player_id, seed=seed)
        metrics = dict(baseline.metrics)

        if batting is not None and batting.woba_denominator > 0:
            woba = compute_woba(batting, self._weights)
            metrics["woba"] = round(woba, METRIC_SPECS["woba"].decimals)
            metrics["wrc_plus"] = round(
                compute_wrc_plus(woba, self._weights), METRIC_SPECS["wrc_plus"].decimals
            )

        if pitching is not None and pitching.innings_pitched > 0:
            metrics["fip"] = round(
                compute_fip(pitching, self._fip_constants), METRIC_SPECS["fip"].decimals
            )
            metrics["k_bb_ratio"] = round(
                compute_k_bb_ratio(pitching.strikeouts, pitching.walks),
                METRIC_SPECS["k_bb_ratio"].decimals,
            )

        has_both = batting is not None and pitching is not None
        source: RatingSource = "real" if has_both else "real_partial"
        return PlayerRating(player_id=player_id, metrics=metrics, source=source)

    def team_profile(self, *, team_id: int, seed: int) -> TeamProfile:
        profile = team_profile_from_stats(
            batting_lines=self._team_batting.get(team_id, ()),
            pitching_lines=self._team_pitching.get(team_id, ()),
            weights=self._weights,
            fip_constants=self._fip_constants,
        )
        if profile is None:
            return self._fallback.team_profile(team_id=team_id, seed=seed)
        return profile


class LayeredStatsProvider:
    """Try each provider in order; first non-synthetic answer wins, else last."""

    def __init__(self, providers: Sequence[StatsProvider]) -> None:
        if not providers:
            raise ValueError("LayeredStatsProvider requires at least one provider")
        self._providers = list(providers)

    def player_rating(self, *, player_id: int, seed: int) -> PlayerRating:
        last: PlayerRating | None = None
        for provider in self._providers:
            rating = provider.player_rating(player_id=player_id, seed=seed)
            if rating.source != "synthetic":
                return rating
            last = rating
        assert last is not None
        return last

    def team_profile(self, *, team_id: int, seed: int) -> TeamProfile:
        return self._providers[0].team_profile(team_id=team_id, seed=seed)


DEFAULT_STATS_PROVIDER: StatsProvider = SyntheticStatsProvider()
