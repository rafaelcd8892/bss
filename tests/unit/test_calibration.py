import pytest

from baseball_sim.eval.calibration import (
    UNIFORM_BRIER,
    Observation,
    brier_score,
    calibration_report,
    reliability_bins,
)


def obs(predicted: float, won: bool) -> Observation:
    return Observation(predicted_home_win=predicted, home_won=won)


class TestBrierScore:
    def test_perfect_forecasts_score_zero(self) -> None:
        assert brier_score([obs(1.0, True), obs(0.0, False)]) == 0.0

    def test_confidently_wrong_forecasts_score_one(self) -> None:
        assert brier_score([obs(0.0, True), obs(1.0, False)]) == 1.0

    def test_a_coin_flip_scores_the_uniform_reference(self) -> None:
        assert brier_score([obs(0.5, True), obs(0.5, False)]) == UNIFORM_BRIER

    def test_no_observations_scores_zero(self) -> None:
        assert brier_score([]) == 0.0


class TestReliabilityBins:
    def test_groups_forecasts_by_confidence(self) -> None:
        bins = reliability_bins(
            [obs(0.1, False), obs(0.15, False), obs(0.9, True)], bin_count=5
        )
        assert [(b.lower, b.count) for b in bins] == [(0.0, 2), (0.8, 1)]

    def test_empty_bins_are_dropped(self) -> None:
        # Three of five bins have nothing in them and must not appear at all.
        bins = reliability_bins([obs(0.5, True)], bin_count=5)
        assert len(bins) == 1
        assert bins[0].count == 1

    def test_a_certain_forecast_lands_in_the_top_bin(self) -> None:
        bins = reliability_bins([obs(1.0, True)], bin_count=5)
        assert bins[0].upper == 1.0

    def test_reports_predicted_against_observed(self) -> None:
        [only] = reliability_bins(
            [obs(0.6, True), obs(0.6, False)], bin_count=5
        )
        assert only.mean_predicted == 0.6
        assert only.observed_rate == 0.5
        # Positive gap means the model claimed more than happened.
        assert only.gap == pytest.approx(0.1)


class TestCalibrationReport:
    def test_summarises_a_sample(self) -> None:
        report = calibration_report([obs(0.6, True), obs(0.6, True), obs(0.6, False)])
        assert report.sample_size == 3
        assert report.mean_predicted == pytest.approx(0.6)
        assert report.observed_rate == pytest.approx(0.6667, abs=1e-4)
        # The model under-claimed here, so the error is negative.
        assert report.calibration_error < 0

    def test_skill_is_negative_when_worse_than_a_coin_flip(self) -> None:
        # Confident and wrong every time.
        report = calibration_report([obs(0.9, False), obs(0.9, False)])
        assert report.brier_score > UNIFORM_BRIER
        assert report.skill_vs_uniform < 0

    def test_skill_is_positive_when_better_than_a_coin_flip(self) -> None:
        report = calibration_report([obs(0.9, True), obs(0.9, True)])
        assert report.skill_vs_uniform > 0

    def test_a_small_sample_is_reported_as_inconclusive(self) -> None:
        # Two games cannot separate a 60% forecast from anything.
        report = calibration_report([obs(0.6, True), obs(0.6, False)])
        low, high = report.observed_interval
        assert low <= report.mean_predicted <= high
        assert report.conclusive is False

    def test_a_clear_miss_is_reported_as_conclusive(self) -> None:
        # A confident forecast that never happens, over enough games to matter.
        report = calibration_report([obs(0.95, False)] * 200)
        assert report.conclusive is True
        assert report.calibration_error > 0

    def test_standard_error_shrinks_with_more_games(self) -> None:
        small = calibration_report([obs(0.5, True), obs(0.5, False)] * 5)
        large = calibration_report([obs(0.5, True), obs(0.5, False)] * 500)
        assert large.observed_standard_error < small.observed_standard_error

    def test_an_empty_sample_is_safe(self) -> None:
        report = calibration_report([])
        assert report.sample_size == 0
        assert report.bins == []
        assert report.conclusive is False
