"""The catalog SQL, exercised against a real PostgreSQL."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from baseball_sim.domain.catalog import PostgresCatalogRepository

from .conftest import ACE, EMPTY, HAWKS, OTTERS, SCRUB, SEASON, SLUGGER, TWO_WAY


@pytest.fixture
def catalog(postgres_dsn: str, seeded: Any) -> Iterator[PostgresCatalogRepository]:
    del seeded
    repository = PostgresCatalogRepository(dsn=postgres_dsn)
    try:
        yield repository
    finally:
        repository.close()


class TestBrowse:
    def test_lists_teams_alphabetically(self, catalog: PostgresCatalogRepository) -> None:
        teams = catalog.list_teams()
        assert [team.abbreviation for team in teams] == ["EMP", "HWK", "OTT"]
        assert teams[1].league_name == "Test League"

    def test_gets_a_player(self, catalog: PostgresCatalogRepository) -> None:
        player = catalog.get_player(player_id=SLUGGER)
        assert player is not None
        assert player.full_name == "Sam Slugger"
        assert player.bats == "L"

    def test_missing_player_is_none(self, catalog: PostgresCatalogRepository) -> None:
        assert catalog.get_player(player_id=999999) is None

    def test_roster_uses_the_membership_position(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        roster = catalog.get_team_roster(team_id=HAWKS)
        assert [player.full_name for player in roster] == [
            "Sam Slugger",
            "Sid Scrub",
            "Toni Twoway",
        ]
        by_id = {player.player_id: player for player in roster}
        assert by_id[TWO_WAY].primary_position == "TWP"

    def test_roster_of_an_unstocked_club_is_empty(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        assert catalog.get_team_roster(team_id=EMPTY) == []


class TestBattingWoba:
    def test_returns_only_requested_players_with_a_hitting_line(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        woba = catalog.get_batting_woba(
            player_ids=[SLUGGER, ACE, TWO_WAY, 999999], season=SEASON
        )
        # The ace has no hitting line and the unknown id has nothing at all.
        assert set(woba) == {SLUGGER, TWO_WAY}
        assert woba[SLUGGER] == pytest.approx(0.42)

    def test_other_seasons_are_excluded(self, catalog: PostgresCatalogRepository) -> None:
        assert catalog.get_batting_woba(player_ids=[SLUGGER], season=2020) == {}

    def test_empty_request_skips_the_query(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        assert catalog.get_batting_woba(player_ids=[], season=SEASON) == {}


class TestLeaders:
    def test_woba_ranks_high_to_low_and_applies_the_qualifier(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        leaders = catalog.get_stat_leaders(
            metric="woba", season=SEASON, minimum=200, limit=10
        )
        # Scrub has the highest wOBA but only 50 PA, so the qualifier excludes him.
        assert [leader.player_id for leader in leaders] == [SLUGGER, TWO_WAY]
        assert [leader.rank for leader in leaders] == [1, 2]
        assert leaders[0].plate_appearances == 600

    def test_lowering_the_qualifier_lets_the_small_sample_in(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        leaders = catalog.get_stat_leaders(metric="woba", season=SEASON, minimum=0, limit=10)
        assert leaders[0].player_id == SCRUB

    def test_fip_ranks_low_to_high(self, catalog: PostgresCatalogRepository) -> None:
        leaders = catalog.get_stat_leaders(metric="fip", season=SEASON, minimum=50, limit=10)
        # Lower FIP is better, so the ace leads on 2.50 ahead of the two-way 3.10.
        assert [leader.player_id for leader in leaders] == [ACE, TWO_WAY]
        assert leaders[0].innings_pitched == pytest.approx(180.0)

    def test_limit_is_honoured(self, catalog: PostgresCatalogRepository) -> None:
        assert len(catalog.get_stat_leaders(
            metric="woba", season=SEASON, minimum=0, limit=1
        )) == 1

    def test_a_metric_nobody_qualifies_for_returns_nothing(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        assert catalog.get_stat_leaders(
            metric="fip", season=SEASON, minimum=500, limit=10
        ) == []


class TestTeamStatLines:
    def test_returns_both_groups_for_one_club(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        batting, pitching = catalog.get_team_stat_lines(team_id=HAWKS, season=SEASON)
        # Slugger, two-way and scrub bat; only the two-way player pitches here.
        assert len(batting) == 3
        assert len(pitching) == 1
        assert pitching[0].innings_pitched == pytest.approx(90.0)

    def test_a_club_with_no_stats_returns_empty_lines(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        assert catalog.get_team_stat_lines(team_id=EMPTY, season=SEASON) == ([], [])

    def test_league_wide_grouping_matches_per_team(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        by_team = catalog.get_all_team_stat_lines(season=SEASON)
        # The club with nothing ingested simply does not appear.
        assert set(by_team) == {HAWKS, OTTERS}
        assert len(by_team[HAWKS][0]) == 3
        assert len(by_team[OTTERS][1]) == 1
        assert by_team[HAWKS] == catalog.get_team_stat_lines(team_id=HAWKS, season=SEASON)


class TestPlayerSeasonLines:
    def test_two_way_player_gets_both_lines(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        lines = catalog.get_player_season_lines(player_id=TWO_WAY, season=SEASON)
        groups = {line.stat_group for line in lines}
        assert groups == {"hitting", "pitching"}

    def test_hits_are_derived_from_the_stored_components(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        [line] = catalog.get_player_season_lines(player_id=SLUGGER, season=SEASON)
        assert line.hits == 100 + 35 + 3 + 40
        assert line.plate_appearances == 600
        assert line.woba == pytest.approx(0.42)
        # A hitter has no pitching figures rather than zeroes.
        assert line.innings_pitched is None
        assert line.fip is None

    def test_a_pitcher_reports_no_hitting_counts(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        [line] = catalog.get_player_season_lines(player_id=ACE, season=SEASON)
        assert line.stat_group == "pitching"
        assert line.hits is None
        assert line.fip == pytest.approx(2.5)

    def test_other_seasons_are_excluded(self, catalog: PostgresCatalogRepository) -> None:
        assert catalog.get_player_season_lines(player_id=SLUGGER, season=2020) == []
