from typing import Any

import pytest

from baseball_sim.domain.postgres_stats import (
    batting_line_from_row,
    build_stat_line_provider_from_rows,
    pitching_line_from_row,
)
from baseball_sim.domain.stats_provider import SyntheticStatsProvider

# Column order mirrors postgres_stats._SELECT_SEASON_STATS:
# player_id, team_id, stat_group, ip, at_bats, singles, doubles, triples,
# home_runs, walks, intentional_walks, hit_by_pitch, sacrifice_flies,
# strikeouts, stolen_bases, pa
# ..., pa, xwoba
HITTING_ROW: tuple[Any, ...] = (
    100, 147, "hitting", None, 540, 112, 30, 3, 35, 50, 5, 6, 4, 120, 10, 600, None
)
PITCHING_ROW: tuple[Any, ...] = (
    200, 147, "pitching", 200.33, None, None, None, None, 17, 45, None, 5, None,
    230, None, None, None,
)


def test_provider_reconstructs_real_lines_from_rows() -> None:
    provider = build_stat_line_provider_from_rows(rows=[HITTING_ROW, PITCHING_ROW])

    hitter = provider.player_rating(player_id=100, seed=1)
    pitcher = provider.player_rating(player_id=200, seed=1)
    assert hitter.source == "real_partial"
    assert hitter.metrics["woba"] > 0.3
    assert pitcher.source == "real_partial"
    assert pitcher.metrics["k_bb_ratio"] > 0.0


def test_provider_aggregates_rows_into_team_profile() -> None:
    provider = build_stat_line_provider_from_rows(rows=[HITTING_ROW, PITCHING_ROW])
    profile = provider.team_profile(team_id=147, seed=1)
    assert 0.0 <= profile.offense <= 1.0
    assert 0.0 <= profile.prevention <= 1.0
    assert profile.range_factor == 0.5


def test_empty_rows_fall_back_to_synthetic() -> None:
    provider = build_stat_line_provider_from_rows(rows=[])
    rating = provider.player_rating(player_id=100, seed=1)
    assert rating == SyntheticStatsProvider().player_rating(player_id=100, seed=1)


# Column order mirrors postgres_stats._SELECT_SEASON_FIELDING:
# player_id, team_id, position, innings, put_outs, assists, errors, chances,
# double_plays, games, games_started
def fielding_row(player_id: int, team_id: int, assists: int) -> tuple[Any, ...]:
    return (player_id, team_id, "SS", 1000.0, 200, assists, 10, 0, 0, 150, 150)


def test_later_snapshots_replace_earlier_ones_instead_of_summing() -> None:
    """A season holds one row per snapshot; summing them would double-count a club.

    ``player_season_stats`` is keyed by snapshot, so a re-ingest leaves April's line
    sitting next to September's. Adding both would blend a stale partial season into
    the club's totals.
    """

    april = (100, 147, "hitting", None, 100, 20, 5, 0, 5, 10, 0, 1, 1, 25, 2, 120, None)
    september = HITTING_ROW
    provider = build_stat_line_provider_from_rows(rows=[april, september])

    from_latest_only = build_stat_line_provider_from_rows(rows=[september])
    assert provider.team_profile(team_id=147, seed=1) == from_latest_only.team_profile(
        team_id=147, seed=1
    )
    assert provider.player_rating(player_id=100, seed=1) == from_latest_only.player_rating(
        player_id=100, seed=1
    )


def test_fielding_rows_drive_range_against_the_league_baseline() -> None:
    rows = [HITTING_ROW, PITCHING_ROW]
    fielding = [fielding_row(100, 147, assists=300), fielding_row(300, 121, assists=239)]

    provider = build_stat_line_provider_from_rows(rows=rows, fielding_rows=fielding)
    assert provider.team_profile(team_id=147, seed=1).range_factor > 0.5


def test_range_stays_neutral_without_fielding_rows() -> None:
    provider = build_stat_line_provider_from_rows(rows=[HITTING_ROW], fielding_rows=[])
    assert provider.team_profile(team_id=147, seed=1).range_factor == 0.5


def hitting_row_with_xwoba(player_id: int, xwoba: float | None) -> tuple[Any, ...]:
    return (player_id,) + HITTING_ROW[1:16] + (xwoba,)


def pitching_row_with_xwoba(player_id: int, xwoba: float | None) -> tuple[Any, ...]:
    return (player_id,) + PITCHING_ROW[1:16] + (xwoba,)


def test_ingested_xwoba_is_reported_as_measured() -> None:
    provider = build_stat_line_provider_from_rows(rows=[hitting_row_with_xwoba(100, 0.412)])
    rating = provider.player_rating(player_id=100, seed=1)
    assert rating.metrics["xwoba"] == 0.412
    assert rating.sources["xwoba"] == "real"


def test_a_pitchers_expected_woba_against_is_not_his_batting_xwoba() -> None:
    """A low xwOBA against is elite pitching; the compare metric ranks high as good.

    Reading the pitching row into `xwoba` would rank an ace below a replacement bat
    on a metric that is supposed to describe hitting.
    """

    provider = build_stat_line_provider_from_rows(rows=[pitching_row_with_xwoba(200, 0.268)])
    rating = provider.player_rating(player_id=200, seed=1)
    assert rating.sources["xwoba"] == "synthetic"
    assert rating.metrics["xwoba"] != 0.268


def test_xwoba_stays_seeded_when_statcast_was_not_ingested() -> None:
    provider = build_stat_line_provider_from_rows(rows=[hitting_row_with_xwoba(100, None)])
    assert provider.player_rating(player_id=100, seed=1).sources["xwoba"] == "synthetic"


# The full SEASON_STATS_COLUMNS row, including the widened components.
WIDE_PITCHING_ROW: tuple[Any, ...] = (
    200, 147, "pitching", 220.67, None, None, None, None, 23, 51, None, 4, None,
    300, None, None, None,
    None, None, None, None, None, 200, 150, 33, 850, 63, 150, 33,
)
WIDE_HITTING_ROW: tuple[Any, ...] = (
    100, 147, "hitting", None, 540, 112, 30, 3, 35, 50, 5, 6, 4, 120, 10, 600, 0.41,
    90, 100, 4, 1, 12, 180, 160, 150, None, None, None, None,
)


class TestWidenedComponentsSurviveTheRoundTrip:
    """Regression guard for a bug the unit tests could not see.

    The career total is built by summing reconstructed lines. The column list left out
    earned runs, hits allowed and batters faced, so every reconstructed pitching line
    carried zeros there — and a nineteen-year career reported an ERA of 0.00 and a WHIP
    of 0.27. The tests all passed, because they built the lines directly instead of
    reading them back through a row.
    """

    def test_a_pitching_row_reconstructs_the_run_prevention_inputs(self) -> None:
        line = pitching_line_from_row(WIDE_PITCHING_ROW)
        assert (line.earned_runs, line.hits_allowed, line.batters_faced) == (63, 150, 850)

    def test_a_batting_row_reconstructs_its_widened_counts(self) -> None:
        line = batting_line_from_row(WIDE_HITTING_ROW)
        assert (line.runs, line.runs_batted_in, line.ground_outs) == (90, 100, 180)

    def test_a_narrow_row_still_parses(self) -> None:
        """A caller selecting the older column set must not start raising."""

        narrow = WIDE_PITCHING_ROW[:17]
        line = pitching_line_from_row(narrow)
        assert line.innings_pitched == pytest.approx(220.67)
        assert line.earned_runs == 0

    def test_the_reconstructed_line_supports_the_metrics_a_total_needs(self) -> None:
        from baseball_sim.domain.career import pitching_total

        total = pitching_total([pitching_line_from_row(WIDE_PITCHING_ROW)])
        assert total is not None
        assert total.era is not None and total.era > 0
        assert total.whip is not None and total.whip > 0.5
        assert total.strikeout_rate is not None
