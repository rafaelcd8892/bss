"""Season simulation: standings, determinism, and the spread behind them."""

import pytest

from baseball_sim.sim.profiles import TeamProfile
from baseball_sim.sim.season import (
    ScheduledGame,
    game_seed,
    project_seasons,
    simulate_season,
)

STRONG = TeamProfile(
    offense=0.9, discipline=0.8, power=0.9, speed=0.6,
    prevention=0.9, command=0.8, range_factor=0.7,
)
WEAK = TeamProfile(
    offense=0.1, discipline=0.2, power=0.1, speed=0.4,
    prevention=0.1, command=0.2, range_factor=0.3,
)
EVEN = TeamProfile(
    offense=0.5, discipline=0.5, power=0.5, speed=0.5,
    prevention=0.5, command=0.5, range_factor=0.5,
)


def schedule(games: int, *, home: int = 147, away: int = 121) -> list[ScheduledGame]:
    """Alternating home and away, so home-field advantage does not skew the total."""

    return [
        ScheduledGame(
            game_pk=900_000 + index,
            home_team_id=home if index % 2 == 0 else away,
            away_team_id=away if index % 2 == 0 else home,
        )
        for index in range(games)
    ]


PROFILES = {147: EVEN, 121: EVEN}


class TestDeterminism:
    def test_the_same_seed_replays_the_same_season(self) -> None:
        first = simulate_season(seed=7, schedule=schedule(40), profiles=PROFILES)
        second = simulate_season(seed=7, schedule=schedule(40), profiles=PROFILES)
        assert first == second

    def test_a_different_seed_gives_a_different_season(self) -> None:
        first = simulate_season(seed=7, schedule=schedule(40), profiles=PROFILES)
        second = simulate_season(seed=8, schedule=schedule(40), profiles=PROFILES)
        assert first.standings != second.standings

    def test_a_game_plays_the_same_wherever_it_sits_in_the_schedule(self) -> None:
        """The seed comes from the game id, not its index.

        Otherwise re-running a season with a game filtered out would silently change
        every game after it, and a single game could not be reproduced on its own.
        """

        full = schedule(30)
        reordered = list(reversed(full))
        assert (
            simulate_season(seed=3, schedule=full, profiles=PROFILES).by_team
            == simulate_season(seed=3, schedule=reordered, profiles=PROFILES).by_team
        )

    def test_the_game_seed_separates_neighbouring_games(self) -> None:
        seeds = {game_seed(season_seed=1, game_pk=pk) for pk in range(1000)}
        assert len(seeds) == 1000

    def test_separate_seasons_do_not_replay_each_other_s_games(self) -> None:
        """The projection treats each season as an independent sample.

        A seed that merely added the season to the game id would make season 2 game
        99 identical to season 1 game 100 — so a thousand "seasons" would be a few
        hundred distinct ones wearing different labels, and the spread they report
        would be too narrow.
        """

        schedule_ids = range(900_000, 900_200)
        draws = [
            game_seed(season_seed=season, game_pk=pk)
            for season in range(40)
            for pk in schedule_ids
        ]
        # A good mix collides only by birthday chance over a 32-bit space; an additive
        # one overlaps on almost every neighbouring pair.
        assert len(set(draws)) == len(draws)


class TestStandings:
    def test_every_game_produces_exactly_one_win_and_one_loss(self) -> None:
        result = simulate_season(seed=5, schedule=schedule(50), profiles=PROFILES)
        assert result.games_played == 50
        assert sum(s.wins for s in result.standings) == 50
        assert sum(s.losses for s in result.standings) == 50
        for standing in result.standings:
            assert standing.games == 50

    def test_runs_scored_by_one_club_are_runs_allowed_by_the_other(self) -> None:
        result = simulate_season(seed=5, schedule=schedule(20), profiles=PROFILES)
        home, away = result.standings
        assert home.runs_scored == away.runs_allowed
        assert away.runs_scored == home.runs_allowed

    def test_the_better_club_wins_more_over_a_long_schedule(self) -> None:
        result = simulate_season(
            seed=5, schedule=schedule(200), profiles={147: STRONG, 121: WEAK}
        )
        assert result.standings[0].team_id == 147
        assert result.standings[0].win_percentage > 0.6

    def test_best_record_sorts_first_with_run_differential_breaking_ties(self) -> None:
        result = simulate_season(
            seed=5, schedule=schedule(100), profiles={147: STRONG, 121: WEAK}
        )
        wins = [s.wins for s in result.standings]
        assert wins == sorted(wins, reverse=True)


class TestMissingData:
    def test_a_club_without_a_profile_is_skipped_not_hashed(self) -> None:
        """A table half built from data and half from seeds would look like one thing
        and be another, so an unknown club drops out of the schedule entirely."""

        mixed = [
            ScheduledGame(game_pk=1, home_team_id=147, away_team_id=121),
            ScheduledGame(game_pk=2, home_team_id=147, away_team_id=999),
        ]
        result = simulate_season(seed=1, schedule=mixed, profiles=PROFILES)
        assert result.games_played == 1
        assert set(result.by_team) == {147, 121}

    def test_an_empty_schedule_is_an_empty_table_rather_than_an_error(self) -> None:
        result = simulate_season(seed=1, schedule=[], profiles=PROFILES)
        assert result.games_played == 0
        assert result.standings == ()


class TestProjection:
    def test_it_reports_one_row_per_club_over_the_requested_seasons(self) -> None:
        projections = project_seasons(
            seeds=[1, 2, 3, 4], schedule=schedule(20), profiles=PROFILES
        )
        assert {p.team_id for p in projections} == {147, 121}
        assert all(p.seasons == 4 for p in projections)

    def test_every_season_has_exactly_one_leader(self) -> None:
        seasons = 10
        projections = project_seasons(
            seeds=list(range(seasons)), schedule=schedule(20), profiles=PROFILES
        )
        assert sum(p.best_record_seasons for p in projections) == seasons

    def test_the_percentiles_bracket_the_mean(self) -> None:
        [projection, _] = project_seasons(
            seeds=list(range(12)), schedule=schedule(30), profiles=PROFILES
        )
        assert projection.wins_p10 <= projection.wins_p50 <= projection.wins_p90
        assert projection.wins_p10 <= projection.mean_wins <= projection.wins_p90

    def test_the_spread_is_luck_because_strength_is_fixed(self) -> None:
        """Nothing varies between runs but the seed, so a club's win total still
        moves. That spread is the floor under any claim about a single season."""

        projections = project_seasons(
            seeds=list(range(20)), schedule=schedule(60), profiles=PROFILES
        )
        assert any(p.wins_p90 > p.wins_p10 for p in projections)

    def test_no_seasons_is_no_projection_rather_than_a_divide_by_zero(self) -> None:
        assert project_seasons(seeds=[], schedule=schedule(4), profiles=PROFILES) == ()


def test_win_percentage_of_a_club_that_never_played_is_zero_not_undefined() -> None:
    result = simulate_season(seed=1, schedule=[], profiles=PROFILES)
    assert result.standings == ()
    # And the property itself is safe on a fresh standing.
    from baseball_sim.sim.season import TeamStanding

    empty = TeamStanding(team_id=1, wins=0, losses=0, runs_scored=0, runs_allowed=0)
    assert empty.win_percentage == pytest.approx(0.0)
