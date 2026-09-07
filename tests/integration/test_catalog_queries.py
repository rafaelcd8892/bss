"""The catalog SQL, exercised against a real PostgreSQL."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from baseball_sim.domain.catalog import PostgresCatalogRepository

from .conftest import (
    ACE,
    EMPTY,
    HAWKS,
    OTTERS,
    SCRUB,
    SEASON,
    SLUGGER,
    TWO_WAY,
    UNMEASURED,
)


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

    def test_a_club_filter_narrows_the_board_against_real_sql(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        """A fake catalog cannot catch this one.

        The club clause sits between the qualifier and the limit in the query text, so
        its parameter has to be bound in that position. Passing it first still type
        checks and still satisfies a unit test with a fake — it only fails when real
        SQL runs.
        """

        hawks = catalog.get_stat_leaders(
            metric="woba", season=SEASON, minimum=0, limit=10, team_id=HAWKS
        )
        assert {leader.player_id for leader in hawks} == {SLUGGER, TWO_WAY, SCRUB}
        assert all(leader.team_id == HAWKS for leader in hawks)

    def test_the_qualifier_still_applies_within_a_club(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        hawks = catalog.get_stat_leaders(
            metric="woba", season=SEASON, minimum=200, limit=10, team_id=HAWKS
        )
        # Scrub's 50 PA is below the floor whether the board is a club or the league.
        assert [leader.player_id for leader in hawks] == [SLUGGER, TWO_WAY]

    def test_a_club_with_nobody_qualified_is_an_empty_board(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        assert catalog.get_stat_leaders(
            metric="woba", season=SEASON, minimum=0, limit=10, team_id=OTTERS
        ) == []

    def test_ingested_seasons_are_reported_newest_first(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        assert catalog.get_ingested_seasons() == [SEASON]

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
        # Slugger, the two-way player, Scrub and the unmeasured hitter.
        assert len(batting) == 4
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
        assert len(by_team[HAWKS][0]) == 4
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


class TestCompletedGames:
    def test_only_finished_decided_games_are_returned(
        self, postgres_dsn: str, seeded_games: Any
    ) -> None:
        del seeded_games
        repository = PostgresCatalogRepository(dsn=postgres_dsn)
        try:
            games = repository.get_completed_games(season=SEASON)
        finally:
            repository.close()

        # In progress, scheduled, tied and other-season rows are all excluded.
        assert [game.game_pk for game in games] == [1, 2]

    def test_reports_which_side_won(self, postgres_dsn: str, seeded_games: Any) -> None:
        del seeded_games
        repository = PostgresCatalogRepository(dsn=postgres_dsn)
        try:
            games = {game.game_pk: game for game in repository.get_completed_games(season=SEASON)}
        finally:
            repository.close()

        assert games[1].home_won is True
        assert games[2].home_won is False

    def test_a_season_with_no_games_is_empty(
        self, postgres_dsn: str, seeded_games: Any
    ) -> None:
        del seeded_games
        repository = PostgresCatalogRepository(dsn=postgres_dsn)
        try:
            assert repository.get_completed_games(season=1999) == []
        finally:
            repository.close()


class TestPlayerStatsTable:
    """The universal table: everyone, sorted server-side, paged."""

    def table(self, catalog: PostgresCatalogRepository, **overrides: object):
        params: dict = {
            "season": SEASON,
            "stat_group": "hitting",
            "sort": "pa",
            "descending": True,
            "limit": 50,
            "offset": 0,
        }
        params.update(overrides)
        return catalog.get_player_stats_table(**params)  # type: ignore[arg-type]

    def test_it_returns_everyone_with_no_qualifier_of_its_own(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        """A leaderboard applies a playing-time floor; this table exists to show all."""

        total, rows = self.table(catalog)
        assert total == 4
        assert {row.player_id for row in rows} == {SLUGGER, TWO_WAY, SCRUB, UNMEASURED}

    def test_a_minimum_can_be_asked_for(self, catalog: PostgresCatalogRepository) -> None:
        total, rows = self.table(catalog, minimum=200)
        assert total == 3
        assert SCRUB not in {row.player_id for row in rows}

    def test_the_group_decides_which_players_appear(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        _, hitters = self.table(catalog)
        _, pitchers = self.table(catalog, stat_group="pitching", sort="ip")
        assert ACE not in {row.player_id for row in hitters}
        assert ACE in {row.player_id for row in pitchers}
        # The two-way player is in both, which is the point of splitting by group.
        assert TWO_WAY in {row.player_id for row in hitters}
        assert TWO_WAY in {row.player_id for row in pitchers}

    def test_sorting_runs_over_the_whole_set_not_the_page(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        _, descending = self.table(catalog, sort="woba", descending=True, limit=1)
        _, ascending = self.table(catalog, sort="woba", descending=False, limit=1)
        # A client sorting its own page could never produce these two answers.
        assert descending[0].player_id == SCRUB
        assert ascending[0].player_id == TWO_WAY

    def test_a_missing_metric_sorts_last_in_both_directions(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        """Absent is not best and not worst; either end would read as a result.

        Sorted on a metric some rows have and one does not — Postgres puts NULLs first
        on DESC by default, so without an explicit NULLS LAST the unmeasured player
        would top a wOBA table.
        """

        for descending in (True, False):
            _, rows = self.table(catalog, sort="woba", descending=descending)
            assert rows[-1].player_id == UNMEASURED
            assert rows[-1].line.woba is None

    def test_paging_walks_the_ranking(self, catalog: PostgresCatalogRepository) -> None:
        _, first = self.table(catalog, sort="woba", limit=1, offset=0)
        _, second = self.table(catalog, sort="woba", limit=1, offset=1)
        assert first[0].player_id != second[0].player_id

    def test_the_total_counts_matches_not_the_page(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        total, rows = self.table(catalog, limit=1)
        assert len(rows) == 1
        assert total == 4

    def test_a_name_search_narrows_it(self, catalog: PostgresCatalogRepository) -> None:
        total, rows = self.table(catalog, query="slug")
        assert total == 1 and rows[0].player_id == SLUGGER

    def test_a_club_narrows_it(self, catalog: PostgresCatalogRepository) -> None:
        total, _ = self.table(catalog, team_id=OTTERS, stat_group="pitching", sort="ip")
        assert total == 1

    def test_rows_carry_the_identity_a_table_needs(
        self, catalog: PostgresCatalogRepository
    ) -> None:
        _, rows = self.table(catalog, query="slug")
        assert rows[0].full_name
        assert rows[0].team_id == HAWKS
        assert rows[0].line.stat_group == "hitting"
