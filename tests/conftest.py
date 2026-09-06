"""Test-suite wide isolation from ambient developer configuration.

`Settings` reads a local `.env`, so a developer pointing their machine at a real
Postgres (BASEBALL_STATS_SOURCE=postgres) would otherwise make the API tests try to
open a database connection. Environment variables outrank `.env` in pydantic-settings,
so pinning them here keeps every test hermetic and reproducible on any machine.
"""

from collections.abc import Iterator

import pytest

from baseball_sim.config import get_settings

PINNED_ENV = {
    "BASEBALL_APP_ENV": "dev",
    "BASEBALL_APP_NAME": "baseball-sim",
    "BASEBALL_STATS_SOURCE": "synthetic",
    "BASEBALL_STATS_SEASON": "2026",
    "BASEBALL_SIMULATOR_RULESET_PATH": "rulesets/mlb_2026_regular.json",
}


@pytest.fixture(autouse=True)
def hermetic_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key, value in PINNED_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
