"""Roster reads are cached per club, because simulating a season is 2,430 games.

Fetching the roster on every call cost 36 ms per game against a real database —
roughly a hundred times the simulation itself, and the one thing standing between
this engine and mass season simulation.
"""

import pytest

from baseball_sim.config import Settings
from baseball_sim.domain.contracts import PitcherWorkload, PlayerSummary
from baseball_sim.domain.lineup_provider import CatalogLineupProvider
from baseball_sim.domain.provider_factory import get_lineup_provider, reset_provider_caches


class CountingRepository:
    """Stands in for the Postgres catalog and counts how often it is opened."""

    opened = 0
    closed = 0

    def __init__(self, *, dsn: str) -> None:
        del dsn
        type(self).opened += 1

    def get_team_roster(self, *, team_id: int) -> list[PlayerSummary]:
        return [
            PlayerSummary(
                player_id=team_id * 100 + i,
                full_name=f"Player {i:02d}",
                primary_position="P" if i < 8 else "RF",
            )
            for i in range(18)
        ]

    def get_batting_woba(self, *, player_ids: list[int], season: int) -> dict[int, float]:
        del season
        return {player_id: 0.330 for player_id in player_ids}

    def get_pitching_workload(
        self, *, player_ids: list[int], season: int
    ) -> dict[int, PitcherWorkload]:
        del season
        return {
            player_id: PitcherWorkload(innings=180.0, appearances=30, games_started=30)
            for player_id in player_ids
        }

    def close(self) -> None:
        type(self).closed += 1


@pytest.fixture
def counting(monkeypatch: pytest.MonkeyPatch) -> type[CountingRepository]:
    CountingRepository.opened = 0
    CountingRepository.closed = 0
    monkeypatch.setattr(
        "baseball_sim.domain.catalog.PostgresCatalogRepository", CountingRepository
    )
    return CountingRepository


def test_a_club_is_read_once_however_many_games_it_plays(
    counting: type[CountingRepository],
) -> None:
    provider = CatalogLineupProvider(dsn="postgresql://test", season=2026)

    for seed in range(50):
        provider.lineup(team_id=147, seed=seed)
        provider.staff(team_id=147, seed=seed)

    assert counting.opened == 1


def test_the_lineup_and_the_staff_share_one_read(
    counting: type[CountingRepository],
) -> None:
    """They need the same roster; fetching it twice doubled the cost for nothing."""

    provider = CatalogLineupProvider(dsn="postgresql://test", season=2026)
    provider.lineup(team_id=147, seed=1)
    provider.staff(team_id=147, seed=1)
    assert counting.opened == 1


def test_each_club_is_read_separately(counting: type[CountingRepository]) -> None:
    provider = CatalogLineupProvider(dsn="postgresql://test", season=2026)
    for team_id in (147, 121, 119):
        provider.lineup(team_id=team_id, seed=1)
        provider.lineup(team_id=team_id, seed=2)
    assert counting.opened == 3


def test_the_connection_is_closed_even_though_the_result_is_kept(
    counting: type[CountingRepository],
) -> None:
    """Caching the data must not mean holding the connection open."""

    provider = CatalogLineupProvider(dsn="postgresql://test", season=2026)
    provider.lineup(team_id=147, seed=1)
    assert (counting.opened, counting.closed) == (1, 1)


def test_caching_does_not_change_what_is_produced(
    counting: type[CountingRepository],
) -> None:
    provider = CatalogLineupProvider(dsn="postgresql://test", season=2026)
    first_lineup = provider.lineup(team_id=147, seed=3)
    first_staff = provider.staff(team_id=147, seed=3)
    assert provider.lineup(team_id=147, seed=3) == first_lineup
    assert provider.staff(team_id=147, seed=3) == first_staff


class TestProviderInstanceCache:
    def settings(self) -> Settings:
        return Settings(
            stats_source="postgres",
            db_dsn="postgresql://test",
            stats_season=2026,
        )

    def test_the_same_configuration_reuses_the_provider(self) -> None:
        """Otherwise the per-club cache would be thrown away on every request."""

        reset_provider_caches()
        settings = self.settings()
        assert get_lineup_provider(settings) is get_lineup_provider(settings)

    def test_resetting_forces_a_rebuild_after_an_ingest(self) -> None:
        reset_provider_caches()
        first = get_lineup_provider(self.settings())
        reset_provider_caches()
        assert get_lineup_provider(self.settings()) is not first

    def test_the_synthetic_default_is_still_no_provider(self) -> None:
        assert get_lineup_provider(Settings(stats_source="synthetic")) is None
