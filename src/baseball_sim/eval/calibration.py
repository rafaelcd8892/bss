"""Measuring the forecast instead of trusting it (ADR-004).

A probability model is only as good as its calibration: when it says 60%, the event
should happen about 60% of the time. This module turns a set of forecasts and their
outcomes into the numbers that answer that.

Everything here is pure. What it deliberately does not do is decide whether a result
is good — that needs the sample size and the reference scores reported alongside it,
which is why they are part of the report rather than prose around it.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

#: Brier score of a forecaster who always says 50/50. The no-information reference.
UNIFORM_BRIER = 0.25


@dataclass(frozen=True)
class Observation:
    """One forecast and what actually happened."""

    predicted_home_win: float
    home_won: bool


@dataclass(frozen=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_predicted: float
    observed_rate: float

    @property
    def gap(self) -> float:
        """Signed calibration error: positive means the model was over-confident."""

        return round(self.mean_predicted - self.observed_rate, 4)


@dataclass(frozen=True)
class CalibrationReport:
    sample_size: int
    brier_score: float
    #: Always predicting 50/50. Beating this is the minimum bar.
    uniform_brier: float
    #: Always predicting the observed base rate. Computed from the same sample, so it
    #: flatters itself — a forecaster could not have known the rate in advance.
    base_rate_brier: float
    skill_vs_uniform: float
    mean_predicted: float
    observed_rate: float
    #: mean_predicted - observed_rate. The headline miscalibration.
    calibration_error: float
    #: Standard error of the observed rate. With a small sample this dominates, and
    #: reporting it is what stops a Brier score from being read as settled.
    observed_standard_error: float
    bins: list[ReliabilityBin]

    @property
    def observed_interval(self) -> tuple[float, float]:
        """Approximate 95% interval for the observed rate."""

        margin = 1.96 * self.observed_standard_error
        return (
            round(max(0.0, self.observed_rate - margin), 4),
            round(min(1.0, self.observed_rate + margin), 4),
        )

    @property
    def conclusive(self) -> bool:
        """Whether the sample can distinguish the model from its own predictions.

        False when the model's mean forecast sits inside the interval around the
        observed rate: the data is consistent with the model being right, and equally
        consistent with it being wrong.
        """

        low, high = self.observed_interval
        return not (low <= self.mean_predicted <= high)


def brier_score(observations: list[Observation]) -> float:
    """Mean squared error of the probabilities. Lower is better; 0.25 is a coin flip."""

    if not observations:
        return 0.0
    total = sum(
        (item.predicted_home_win - (1.0 if item.home_won else 0.0)) ** 2
        for item in observations
    )
    return total / len(observations)


def reliability_bins(
    observations: list[Observation], *, bin_count: int = 5
) -> list[ReliabilityBin]:
    """Group forecasts by confidence and compare each group to what happened.

    Empty bins are dropped: with a narrow-spread model most of the range is unused,
    and printing zero-count rows implies coverage that is not there.
    """

    if not observations or bin_count < 1:
        return []

    width = 1.0 / bin_count
    bins: list[ReliabilityBin] = []
    for index in range(bin_count):
        lower = index * width
        upper = 1.0 if index == bin_count - 1 else (index + 1) * width
        members = [
            item
            for item in observations
            if lower <= item.predicted_home_win < upper
            or (index == bin_count - 1 and item.predicted_home_win == 1.0)
        ]
        if not members:
            continue
        bins.append(
            ReliabilityBin(
                lower=round(lower, 4),
                upper=round(upper, 4),
                count=len(members),
                mean_predicted=round(
                    sum(item.predicted_home_win for item in members) / len(members), 4
                ),
                observed_rate=round(
                    sum(1 for item in members if item.home_won) / len(members), 4
                ),
            )
        )
    return bins


def calibration_report(
    observations: list[Observation], *, bin_count: int = 5
) -> CalibrationReport:
    size = len(observations)
    if size == 0:
        return CalibrationReport(
            sample_size=0,
            brier_score=0.0,
            uniform_brier=UNIFORM_BRIER,
            base_rate_brier=0.0,
            skill_vs_uniform=0.0,
            mean_predicted=0.0,
            observed_rate=0.0,
            calibration_error=0.0,
            observed_standard_error=0.0,
            bins=[],
        )

    score = brier_score(observations)
    observed = sum(1 for item in observations if item.home_won) / size
    predicted = sum(item.predicted_home_win for item in observations) / size

    return CalibrationReport(
        sample_size=size,
        brier_score=round(score, 4),
        uniform_brier=UNIFORM_BRIER,
        base_rate_brier=round(observed * (1.0 - observed), 4),
        skill_vs_uniform=round(1.0 - score / UNIFORM_BRIER, 4),
        mean_predicted=round(predicted, 4),
        observed_rate=round(observed, 4),
        calibration_error=round(predicted - observed, 4),
        observed_standard_error=round(sqrt(observed * (1.0 - observed) / size), 4),
        bins=reliability_bins(observations, bin_count=bin_count),
    )
