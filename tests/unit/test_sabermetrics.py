import pytest

from baseball_sim.sim.sabermetrics import (
    RawBattingLine,
    RawPitchingLine,
    compute_fip,
    compute_k_bb_ratio,
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
