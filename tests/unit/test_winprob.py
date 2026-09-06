import pytest

from baseball_sim.sim.profiles import TeamProfile
from baseball_sim.sim.winprob import (
    LEAGUE_RUNS_PER_GAME,
    GameSituation,
    expected_runs,
    team_run_rates,
    win_probability,
)


def profile(offense: float = 0.5, prevention: float = 0.5) -> TeamProfile:
    return TeamProfile(
        offense=offense,
        discipline=0.5,
        power=0.5,
        speed=0.5,
        prevention=prevention,
        command=0.5,
        range_factor=0.5,
    )


AVERAGE = profile()
ELITE = profile(offense=0.9, prevention=0.9)
POOR = profile(offense=0.1, prevention=0.1)


class TestExpectedRuns:
    def test_average_matchup_scores_the_league_average(self) -> None:
        assert expected_runs(offense=0.5, opposing_prevention=0.5) == pytest.approx(
            LEAGUE_RUNS_PER_GAME
        )

    def test_a_better_offense_scores_more(self) -> None:
        assert expected_runs(offense=0.9, opposing_prevention=0.5) > LEAGUE_RUNS_PER_GAME

    def test_a_better_opposing_defense_suppresses_scoring(self) -> None:
        assert expected_runs(offense=0.5, opposing_prevention=0.9) < LEAGUE_RUNS_PER_GAME

    def test_factors_outside_the_unit_range_are_clamped(self) -> None:
        assert expected_runs(offense=5.0, opposing_prevention=0.5) == expected_runs(
            offense=1.0, opposing_prevention=0.5
        )


class TestRunRates:
    def test_each_side_is_scored_against_the_other_defense(self) -> None:
        home_rate, away_rate = team_run_rates(home_profile=ELITE, away_profile=POOR)
        assert home_rate > away_rate

    def test_mirroring_the_matchup_mirrors_the_rates(self) -> None:
        forward = team_run_rates(home_profile=ELITE, away_profile=POOR)
        reversed_ = team_run_rates(home_profile=POOR, away_profile=ELITE)
        assert forward == tuple(reversed(reversed_))


class TestPregame:
    def test_equal_teams_favour_the_home_side_slightly(self) -> None:
        home_rate, away_rate = team_run_rates(home_profile=AVERAGE, away_profile=AVERAGE)
        result = win_probability(home_rate=home_rate, away_rate=away_rate)
        assert 0.5 < result.home < 0.6
        assert result.home + result.away == pytest.approx(1.0)

    def test_the_stronger_club_is_favoured(self) -> None:
        strong_home = win_probability(**_rates(ELITE, POOR))
        strong_away = win_probability(**_rates(POOR, ELITE))
        assert strong_home.home > 0.6
        assert strong_away.home < 0.4

    def test_reports_the_run_rates_behind_the_number(self) -> None:
        result = win_probability(**_rates(ELITE, POOR))
        assert result.home_expected_runs > result.away_expected_runs
        assert result.final is False


def _rates(home: TeamProfile, away: TeamProfile) -> dict[str, float]:
    home_rate, away_rate = team_run_rates(home_profile=home, away_profile=away)
    return {"home_rate": home_rate, "away_rate": away_rate}


def situation(**overrides: object) -> GameSituation:
    base = {
        "inning": 5,
        "half": "bottom",
        "outs": 1,
        "bases": "000",
        "home_score": 0,
        "away_score": 0,
    }
    base.update(overrides)
    return GameSituation(**base)  # type: ignore[arg-type]


class TestInGame:
    def test_settles_once_no_outs_remain(self) -> None:
        result = win_probability(
            **_rates(AVERAGE, AVERAGE),
            situation=situation(inning=9, half="bottom", outs=3, home_score=5, away_score=3),
        )
        assert result.home == 1.0
        assert result.final is True

    def test_does_not_settle_after_the_top_of_the_ninth(self) -> None:
        # The home team still bats, so the game is not over.
        result = win_probability(
            **_rates(AVERAGE, AVERAGE),
            situation=situation(inning=9, half="top", outs=3),
        )
        assert result.final is False

    def test_moves_toward_whoever_leads(self) -> None:
        ahead = win_probability(
            **_rates(AVERAGE, AVERAGE),
            situation=situation(inning=7, home_score=6, away_score=1),
        )
        behind = win_probability(
            **_rates(AVERAGE, AVERAGE),
            situation=situation(inning=7, home_score=1, away_score=6),
        )
        assert ahead.home > 0.8
        assert behind.home < 0.2

    def test_the_same_lead_is_safer_later(self) -> None:
        early = win_probability(
            **_rates(AVERAGE, AVERAGE), situation=situation(inning=2, home_score=2)
        )
        late = win_probability(
            **_rates(AVERAGE, AVERAGE), situation=situation(inning=8, home_score=2)
        )
        assert late.home > early.home

    def test_runners_on_base_help_the_batting_team(self) -> None:
        empty = win_probability(**_rates(AVERAGE, AVERAGE), situation=situation(bases="000"))
        loaded = win_probability(**_rates(AVERAGE, AVERAGE), situation=situation(bases="111"))
        assert loaded.home > empty.home

    def test_never_absolute_while_the_game_is_live(self) -> None:
        blowout = win_probability(
            **_rates(AVERAGE, AVERAGE),
            situation=situation(inning=3, half="top", home_score=20, away_score=0),
        )
        assert blowout.home <= 0.99
        assert blowout.final is False

    def test_team_quality_shifts_a_tied_game(self) -> None:
        # The old frontend model ignored team quality entirely: a tied game read 0.50
        # no matter who was playing.
        strong = win_probability(**_rates(ELITE, POOR), situation=situation())
        weak = win_probability(**_rates(POOR, ELITE), situation=situation())
        assert strong.home > weak.home

    def test_is_a_pure_function(self) -> None:
        args = {**_rates(ELITE, POOR), "situation": situation(inning=6, home_score=3)}
        assert win_probability(**args) == win_probability(**args)
