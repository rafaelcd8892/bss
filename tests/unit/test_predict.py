"""predict_game after it stopped hashing the seed for team quality."""

import pytest

from baseball_sim.domain.contracts import DeterministicContext, PredictGameRequest
from baseball_sim.domain.service import predict_game
from baseball_sim.domain.stats_provider import StatLineStatsProvider
from baseball_sim.sim.sabermetrics import RawBattingLine, RawPitchingLine

STRONG = 147
WEAK = 121
UNKNOWN = 999

ELITE_BAT = RawBattingLine(700, 560, 120, 40, 4, 50, 110, 20, 10, 6, 90, 25)
POOR_BAT = RawBattingLine(400, 380, 70, 12, 1, 4, 15, 0, 2, 3, 110, 2)
ACE_ARM = RawPitchingLine(200.0, 260, 35, 4, 14)
POOR_ARM = RawPitchingLine(150.0, 95, 70, 10, 30)


def context(seed: int = 1234) -> DeterministicContext:
    return DeterministicContext(
        seed=seed, model_version="baseline-v1", data_snapshot_id="test"
    )


def request(home: int = STRONG, away: int = WEAK, seed: int = 1234) -> PredictGameRequest:
    return PredictGameRequest(home_team_id=home, away_team_id=away, context=context(seed))


def provider(*, cover_away: bool = True) -> StatLineStatsProvider:
    team_batting = {STRONG: [ELITE_BAT] * 9}
    team_pitching = {STRONG: [ACE_ARM] * 5}
    if cover_away:
        team_batting[WEAK] = [POOR_BAT] * 9
        team_pitching[WEAK] = [POOR_ARM] * 5
    return StatLineStatsProvider(
        batting_lines={},
        pitching_lines={},
        team_batting=team_batting,
        team_pitching=team_pitching,
    )


class TestProbabilities:
    def test_probabilities_sum_to_one(self) -> None:
        result = predict_game(request(), provider=provider())
        assert result.home_win_probability + result.away_win_probability == pytest.approx(1.0)

    def test_the_better_club_is_favoured(self) -> None:
        favoured = predict_game(request(home=STRONG, away=WEAK), provider=provider())
        against = predict_game(request(home=WEAK, away=STRONG), provider=provider())
        assert favoured.home_win_probability > 0.5
        assert against.home_win_probability < 0.5

    def test_reports_the_run_rates_behind_the_number(self) -> None:
        result = predict_game(request(), provider=provider())
        assert result.home_expected_runs > result.away_expected_runs
        assert result.confidence == pytest.approx(
            abs(result.home_win_probability - 0.5) * 2, abs=1e-4
        )


class TestProvenance:
    def test_without_a_provider_the_forecast_is_seeded(self) -> None:
        result = predict_game(request())
        assert result.source == "synthetic"
        assert any("synthetic" in line for line in result.explanation)

    def test_with_data_for_both_clubs_it_is_real(self) -> None:
        assert predict_game(request(), provider=provider()).source == "real"

    def test_data_for_only_one_club_is_not_reported_as_real(self) -> None:
        # The away club falls back to a seeded profile, so the number is not fully
        # grounded and must not claim to be.
        result = predict_game(request(), provider=provider(cover_away=False))
        assert result.source == "synthetic"

    def test_an_unknown_club_falls_back(self) -> None:
        result = predict_game(request(home=STRONG, away=UNKNOWN), provider=provider())
        assert result.source == "synthetic"


class TestDeterminism:
    def test_repeated_calls_agree(self) -> None:
        assert predict_game(request(), provider=provider()) == predict_game(
            request(), provider=provider()
        )

    def test_real_data_makes_the_seed_irrelevant_to_team_quality(self) -> None:
        """The heart of the rebuild.

        The old implementation derived team strength from the seed, so the same
        matchup returned a different forecast for every seed. With real profiles the
        seed no longer touches team quality at all.
        """
        first = predict_game(request(seed=1), provider=provider())
        second = predict_game(request(seed=999999), provider=provider())
        assert first.home_win_probability == second.home_win_probability
        assert first.home_expected_runs == second.home_expected_runs

    def test_without_data_the_seed_still_drives_the_fallback(self) -> None:
        # The seeded fallback is meant to vary by seed; that is what makes it seeded.
        first = predict_game(request(seed=1))
        second = predict_game(request(seed=999999))
        assert first.home_win_probability != second.home_win_probability
