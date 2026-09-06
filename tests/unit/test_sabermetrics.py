import pytest

from baseball_sim.sim.sabermetrics import (
    RawBattingLine,
    RawPitchingLine,
    compute_babip,
    compute_batting_average,
    compute_era,
    compute_fip,
    compute_ground_ball_rate,
    compute_iso,
    compute_k_bb_ratio,
    compute_obp,
    compute_ops,
    compute_per_nine,
    compute_slg,
    compute_strikeout_rate,
    compute_walk_rate,
    compute_whip,
    compute_woba,
    compute_wrc_plus,
)

BATTING = RawBattingLine(
    plate_appearances=600,
    at_bats=500,
    singles=100,
    doubles=20,
    triples=2,
    home_runs=30,
    walks=50,
    intentional_walks=5,
    hit_by_pitch=5,
    sacrifice_flies=4,
    strikeouts=120,
    stolen_bases=10,
)

PITCHING = RawPitchingLine(
    innings_pitched=200.0,
    strikeouts=220,
    walks=50,
    hit_by_pitch=6,
    home_runs=18,
)


def test_woba_matches_linear_weights() -> None:
    assert compute_woba(BATTING) == pytest.approx(0.381567, abs=1e-6)


def test_wrc_plus_is_league_relative() -> None:
    assert compute_wrc_plus(compute_woba(BATTING)) == pytest.approx(145.0336, abs=1e-3)


def test_fip_matches_formula() -> None:
    # (13*18 + 3*(50+6) - 2*220) / 200 + 3.10 == 2.91
    assert compute_fip(PITCHING) == pytest.approx(2.91, abs=1e-9)


def test_k_bb_ratio() -> None:
    assert compute_k_bb_ratio(220, 50) == pytest.approx(4.4)


def test_k_bb_ratio_handles_zero_walks() -> None:
    assert compute_k_bb_ratio(7, 0) == pytest.approx(7.0)


def test_empty_lines_are_safe() -> None:
    empty_batting = RawBattingLine(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    empty_pitching = RawPitchingLine(0.0, 0, 0, 0, 0)
    assert compute_woba(empty_batting) == 0.0
    # FIP of a pitcher with no innings collapses to the league constant.
    assert compute_fip(empty_pitching) == pytest.approx(3.10)


class TestWidenedHittingMetrics:
    """The line above: 152 hits, 266 total bases in 500 at-bats."""

    def test_batting_average(self) -> None:
        assert compute_batting_average(BATTING) == pytest.approx(152 / 500)

    def test_on_base_percentage(self) -> None:
        # (H + BB + HBP) / (AB + BB + HBP + SF)
        assert compute_obp(BATTING) == pytest.approx(207 / 559, abs=1e-6)

    def test_slugging_and_ops(self) -> None:
        assert compute_slg(BATTING) == pytest.approx(266 / 500)
        assert compute_ops(BATTING) == pytest.approx(207 / 559 + 266 / 500, abs=1e-6)

    def test_isolated_power_is_slugging_minus_average(self) -> None:
        assert compute_iso(BATTING) == pytest.approx(266 / 500 - 152 / 500)

    def test_babip_excludes_strikeouts_and_home_runs(self) -> None:
        # The defense never touches a strikeout or a home run.
        assert compute_babip(BATTING) == pytest.approx(122 / 354, abs=1e-6)

    def test_rates_are_absent_rather_than_zero_without_at_bats(self) -> None:
        empty = RawBattingLine(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        assert compute_batting_average(empty) is None
        assert compute_slg(empty) is None
        assert compute_iso(empty) is None
        assert compute_babip(empty) is None


WIDE_PITCHING = RawPitchingLine(
    innings_pitched=200.0,
    strikeouts=220,
    walks=50,
    hit_by_pitch=6,
    home_runs=18,
    batters_faced=800,
    earned_runs=60,
    hits_allowed=170,
    ground_outs=200,
    air_outs=150,
)


class TestWidenedPitchingMetrics:
    def test_era(self) -> None:
        assert compute_era(WIDE_PITCHING) == pytest.approx(60 * 9 / 200)

    def test_whip(self) -> None:
        assert compute_whip(WIDE_PITCHING) == pytest.approx((50 + 170) / 200)

    def test_rates_use_batters_faced_not_innings(self) -> None:
        assert compute_strikeout_rate(WIDE_PITCHING) == pytest.approx(220 / 800)
        assert compute_walk_rate(WIDE_PITCHING) == pytest.approx(50 / 800)

    def test_per_nine(self) -> None:
        assert compute_per_nine(220, 200.0) == pytest.approx(220 * 9 / 200)

    def test_ground_ball_share_of_batted_ball_outs(self) -> None:
        assert compute_ground_ball_rate(WIDE_PITCHING) == pytest.approx(200 / 350)

    def test_metrics_needing_unfetched_fields_stay_absent(self) -> None:
        # PITCHING was built before the widening, so it carries no batters faced.
        assert compute_strikeout_rate(PITCHING) is None
        assert compute_era(PITCHING) == pytest.approx(0.0)
        assert compute_ground_ball_rate(PITCHING) is None
