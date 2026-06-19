from baseball_sim.domain.stats_provider import (
    METRIC_SPECS,
    LayeredStatsProvider,
    StatLineStatsProvider,
    SyntheticStatsProvider,
)
from baseball_sim.sim.profiles import synthetic_team_profile
from baseball_sim.sim.sabermetrics import (
    RawBattingLine,
    RawPitchingLine,
    compute_fip,
    compute_k_bb_ratio,
    compute_woba,
    compute_wrc_plus,
)

ELITE_BAT = RawBattingLine(
    plate_appearances=600,
    at_bats=500,
    singles=100,
    doubles=30,
    triples=3,
    home_runs=40,
    walks=80,
    intentional_walks=10,
    hit_by_pitch=8,
    sacrifice_flies=5,
    strikeouts=110,
    stolen_bases=20,
)

ACE_ARM = RawPitchingLine(
    innings_pitched=200.0,
    strikeouts=250,
    walks=40,
    hit_by_pitch=5,
    home_runs=15,
)


def test_synthetic_provider_reproduces_legacy_values() -> None:
    rating = SyntheticStatsProvider().player_rating(player_id=592450, seed=1234)
    # Locked from the original hash-based compare implementation.
    assert rating.metrics == {
        "woba": 0.3498,
        "xwoba": 0.2542,
        "wrc_plus": 115.7,
        "fip": 4.92,
        "k_bb_ratio": 5.42,
    }
    assert rating.source == "synthetic"


def test_synthetic_team_profile_is_stable() -> None:
    profile = SyntheticStatsProvider().team_profile(team_id=147, seed=1234)
    assert profile == synthetic_team_profile(seed=1234, team_id=147)


def test_stat_line_provider_uses_real_batting_metrics() -> None:
    provider = StatLineStatsProvider(
        batting_lines={100: ELITE_BAT},
        pitching_lines={},
        team_batting={},
        team_pitching={},
    )
    rating = provider.player_rating(player_id=100, seed=1234)

    assert rating.source == "real_partial"
    assert rating.metrics["woba"] == round(compute_woba(ELITE_BAT), METRIC_SPECS["woba"].decimals)
    assert rating.metrics["wrc_plus"] == round(
        compute_wrc_plus(compute_woba(ELITE_BAT)), METRIC_SPECS["wrc_plus"].decimals
    )
    # Metrics without batting coverage stay on the synthetic fallback.
    synthetic = SyntheticStatsProvider().player_rating(player_id=100, seed=1234)
    assert rating.metrics["fip"] == synthetic.metrics["fip"]


def test_stat_line_provider_uses_real_pitching_metrics() -> None:
    provider = StatLineStatsProvider(
        batting_lines={},
        pitching_lines={200: ACE_ARM},
        team_batting={},
        team_pitching={},
    )
    rating = provider.player_rating(player_id=200, seed=7)

    assert rating.source == "real_partial"
    assert rating.metrics["fip"] == round(compute_fip(ACE_ARM), METRIC_SPECS["fip"].decimals)
    assert rating.metrics["k_bb_ratio"] == round(
        compute_k_bb_ratio(ACE_ARM.strikeouts, ACE_ARM.walks),
        METRIC_SPECS["k_bb_ratio"].decimals,
    )


def test_two_way_player_is_fully_real() -> None:
    provider = StatLineStatsProvider(
        batting_lines={660: ELITE_BAT},
        pitching_lines={660: ACE_ARM},
        team_batting={},
        team_pitching={},
    )
    rating = provider.player_rating(player_id=660, seed=1)
    assert rating.source == "real"


def test_unknown_player_falls_back_to_synthetic() -> None:
    provider = StatLineStatsProvider(
        batting_lines={100: ELITE_BAT},
        pitching_lines={},
        team_batting={},
        team_pitching={},
    )
    rating = provider.player_rating(player_id=999, seed=1234)
    assert rating == SyntheticStatsProvider().player_rating(player_id=999, seed=1234)


def test_team_profile_from_stats_is_bounded_and_responsive() -> None:
    provider = StatLineStatsProvider(
        batting_lines={},
        pitching_lines={},
        team_batting={147: [ELITE_BAT]},
        team_pitching={147: [ACE_ARM]},
    )
    profile = provider.team_profile(team_id=147, seed=1234)

    for factor in (
        profile.offense,
        profile.discipline,
        profile.power,
        profile.speed,
        profile.prevention,
        profile.command,
    ):
        assert 0.0 <= factor <= 1.0
    # Elite hitting and pitching push offense and prevention toward the top.
    assert profile.offense > 0.6
    assert profile.prevention > 0.6
    # Fielding range is not ingested yet, so it stays neutral.
    assert profile.range_factor == 0.5


def test_team_profile_without_data_falls_back() -> None:
    provider = StatLineStatsProvider(
        batting_lines={},
        pitching_lines={},
        team_batting={},
        team_pitching={},
    )
    profile = provider.team_profile(team_id=147, seed=1234)
    assert profile == synthetic_team_profile(seed=1234, team_id=147)


def test_layered_provider_prefers_real_then_synthetic() -> None:
    real = StatLineStatsProvider(
        batting_lines={100: ELITE_BAT},
        pitching_lines={},
        team_batting={},
        team_pitching={},
    )
    layered = LayeredStatsProvider([real, SyntheticStatsProvider()])

    covered = layered.player_rating(player_id=100, seed=1234)
    uncovered = layered.player_rating(player_id=999, seed=1234)
    assert covered.source == "real_partial"
    assert uncovered.source == "synthetic"
