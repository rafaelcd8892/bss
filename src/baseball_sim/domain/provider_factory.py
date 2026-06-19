"""Select the stats provider for serving based on configuration.

Returns ``None`` for the default synthetic path so callers keep their seed-only
behavior byte-for-byte; returns a real Postgres-backed provider when configured.
"""

from __future__ import annotations

from functools import lru_cache

from baseball_sim.config import Settings, get_settings
from baseball_sim.domain.lineup_provider import CatalogLineupProvider, LineupProvider
from baseball_sim.domain.stats_provider import StatsProvider


@lru_cache(maxsize=4)
def _postgres_provider(dsn: str, season: int) -> StatsProvider:
    from baseball_sim.domain.postgres_stats import build_stat_line_provider

    return build_stat_line_provider(dsn=dsn, season=season)


def get_stats_provider(settings: Settings | None = None) -> StatsProvider | None:
    app_settings = settings if settings is not None else get_settings()
    if app_settings.stats_source == "postgres":
        return _postgres_provider(app_settings.db_dsn, app_settings.stats_season)
    return None


def get_lineup_provider(settings: Settings | None = None) -> LineupProvider | None:
    app_settings = settings if settings is not None else get_settings()
    if app_settings.stats_source == "postgres":
        return CatalogLineupProvider(dsn=app_settings.db_dsn)
    return None
