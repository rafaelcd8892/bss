"""Career totals: rates recomputed from the sum, never averaged across seasons."""

import pytest

from baseball_sim.domain.career import batting_total, pitching_total
from baseball_sim.sim.sabermetrics import RawBattingLine, RawPitchingLine


def batting(*, pa: int, ab: int, singles: int, home_runs: int = 0) -> RawBattingLine:
    return RawBattingLine(
        plate_appearances=pa,
        at_bats=ab,
        singles=singles,
        doubles=0,
        triples=0,
        home_runs=home_runs,
        walks=pa - ab,
        intentional_walks=0,
        hit_by_pitch=0,
        sacrifice_flies=0,
        strikeouts=0,
        stolen_bases=0,
    )


class TestBattingTotals:
    def test_counting_stats_are_summed(self) -> None:
        total = batting_total([batting(pa=600, ab=540, singles=120, home_runs=30),
                               batting(pa=100, ab=90, singles=20, home_runs=5)])
        assert total is not None
        assert total.plate_appearances == 700
        assert total.home_runs == 35

    def test_a_rate_is_recomputed_from_the_sum_not_averaged(self) -> None:
        """The whole reason this lives on the server.

        A .500 season over 10 at-bats and a .200 season over 500 average to .350, which
        is not a number that describes anybody. The real career average is .206.
        """

        big = batting(pa=500, ab=500, singles=100)
        cameo = batting(pa=10, ab=10, singles=5)
        total = batting_total([big, cameo])
        assert total is not None
        assert total.batting_average == pytest.approx(105 / 510, abs=1e-4)
        averaged = (100 / 500 + 5 / 10) / 2
        assert total.batting_average != pytest.approx(averaged, abs=1e-3)

    def test_ops_is_the_recomputed_obp_plus_slg(self) -> None:
        total = batting_total([batting(pa=600, ab=540, singles=120, home_runs=30)])
        assert total is not None
        assert total.ops == pytest.approx((total.obp or 0) + (total.slg or 0), abs=1e-3)

    def test_league_relative_and_measured_metrics_are_left_out(self) -> None:
        """wRC+ moves with the league and xwOBA has no denominator to re-weight by;
        carrying either across twenty years would answer a question nobody asked."""

        total = batting_total([batting(pa=600, ab=540, singles=120, home_runs=30)])
        assert total is not None
        assert total.wrc_plus is None
        assert total.xwoba is None

    def test_no_seasons_is_no_total(self) -> None:
        assert batting_total([]) is None


def pitching(*, ip: float, k: int, bb: int, er: int, hits: int, bf: int) -> RawPitchingLine:
    return RawPitchingLine(
        innings_pitched=ip,
        strikeouts=k,
        walks=bb,
        hit_by_pitch=0,
        home_runs=10,
        batters_faced=bf,
        earned_runs=er,
        hits_allowed=hits,
    )


class TestPitchingTotals:
    def test_era_comes_from_the_summed_runs_and_innings(self) -> None:
        total = pitching_total([
            pitching(ip=200.0, k=250, bb=50, er=60, hits=150, bf=800),
            pitching(ip=100.0, k=100, bb=30, er=50, hits=100, bf=420),
        ])
        assert total is not None
        assert total.innings_pitched == pytest.approx(300.0)
        assert total.era == pytest.approx(110 * 9 / 300, abs=1e-3)

    def test_whip_uses_the_summed_walks_and_hits(self) -> None:
        total = pitching_total([pitching(ip=200.0, k=250, bb=50, er=60, hits=150, bf=800)])
        assert total is not None
        assert total.whip == pytest.approx(200 / 200, abs=1e-3)

    def test_rates_use_batters_faced_across_the_career(self) -> None:
        total = pitching_total([
            pitching(ip=200.0, k=250, bb=50, er=60, hits=150, bf=800),
            pitching(ip=100.0, k=100, bb=30, er=50, hits=100, bf=420),
        ])
        assert total is not None
        assert total.strikeout_rate == pytest.approx(350 / 1220, abs=1e-4)

    def test_a_career_with_no_innings_reports_no_rate(self) -> None:
        total = pitching_total([pitching(ip=0.0, k=0, bb=0, er=0, hits=0, bf=0)])
        assert total is not None
        assert total.fip is None
        assert total.whip is None

    def test_no_seasons_is_no_total(self) -> None:
        assert pitching_total([]) is None
