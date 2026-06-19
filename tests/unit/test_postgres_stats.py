from typing import Any

from baseball_sim.domain.postgres_stats import build_stat_line_provider_from_rows
from baseball_sim.domain.stats_provider import SyntheticStatsProvider

# Column order mirrors postgres_stats._SELECT_SEASON_STATS:
# player_id, team_id, stat_group, ip, at_bats, singles, doubles, triples,
# home_runs, walks, intentional_walks, hit_by_pitch, sacrifice_flies,
# strikeouts, stolen_bases, pa
HITTING_ROW: tuple[Any, ...] = (
    100, 147, "hitting", None, 540, 112, 30, 3, 35, 50, 5, 6, 4, 120, 10, 600
)
PITCHING_ROW: tuple[Any, ...] = (
    200, 147, "pitching", 200.33, None, None, None, None, 17, 45, None, 5, None, 230, None, None
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
