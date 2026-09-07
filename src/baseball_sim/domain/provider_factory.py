"""Select the stats and lineup providers for serving, based on configuration.

Returns ``None`` for the default synthetic path so callers keep their seed-only
behavior byte-for-byte; returns real Postgres-backed providers when configured.

Both are cached per ``(dsn, season)``. They read a season that only changes when
ingestion runs, and rebuilding them per request dominated everything else: a
simulated game spent far longer opening connections than simulating. The cost is
staleness — a process holding these across a re-ingest serves the previous data
until :func:`reset_provider_caches` is called or the process restarts.
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


@lru_cache(maxsize=4)
def _catalog_lineup_provider(dsn: str, season: int) -> LineupProvider:
    return CatalogLineupProvider(dsn=dsn, season=season)


def get_lineup_provider(settings: Settings | None = None) -> LineupProvider | None:
    app_settings = settings if settings is not None else get_settings()
    if app_settings.stats_source == "postgres":
        return _catalog_lineup_provider(app_settings.db_dsn, app_settings.stats_season)
    return None


def reset_provider_caches() -> None:
    """Drop the cached providers so the next call re-reads the database.

    Needed after an ingestion run inside a live process, and by tests that point the
    same dsn at different data.
    """

    _postgres_provider.cache_clear()
    _catalog_lineup_provider.cache_clear()
