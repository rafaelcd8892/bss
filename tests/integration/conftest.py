"""Integration tests against a real PostgreSQL.

These exercise the hand-written SQL that the fake-repository unit tests cannot reach:
the DISTINCT ON queries, the joins, the latest-snapshot subqueries and the upserts.

They skip cleanly when no test database is reachable, so `pytest` still works on a
machine without PostgreSQL. CI provides one as a service container.

The test database comes from BASEBALL_TEST_DB_DSN, or is derived from BASEBALL_DB_DSN
by appending `_test` to the database name. As a hard safety rail this module refuses
to touch any database whose name does not end in `_test`, because the fixtures
truncate tables.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse, urlunparse

import pytest

from baseball_sim.config import Settings
from baseball_sim.infra.migrations import apply_migrations

TEST_DB_SUFFIX = "_test"

# Everything the fixtures reset. schema_migrations is deliberately excluded: the
# schema is applied once per session and must survive between tests.
_RESET_TABLES = (
    "roster_memberships",
    "player_season_stats",
    "simulation_runs",
    "games",
    "players",
    "teams",
    "model_versions",
    "data_snapshots",
)


def resolve_test_dsn() -> str | None:
    """The test database URL, or None when one is not configured."""

    explicit = os.environ.get("BASEBALL_TEST_DB_DSN")
    if explicit:
        return explicit

    base = os.environ.get("BASEBALL_DB_DSN") or Settings().db_dsn
    parsed = urlparse(base)
    database = parsed.path.lstrip("/")
    if not database:
        return None
    return urlunparse(parsed._replace(path=f"/{database}{TEST_DB_SUFFIX}"))


def _database_name(dsn: str) -> str:
    return urlparse(dsn).path.lstrip("/")


def _guard_is_test_database(dsn: str) -> None:
    name = _database_name(dsn)
    if not name.endswith(TEST_DB_SUFFIX):
        raise RuntimeError(
            f"Refusing to run integration tests against database {name!r}: "
            f"the fixtures truncate tables and the name must end in {TEST_DB_SUFFIX!r}."
        )


def _ensure_database(dsn: str) -> None:
    """Create the test database if it is missing."""

    import psycopg

    target = _database_name(dsn)
    admin = urlunparse(urlparse(dsn)._replace(path="/postgres"))
    with psycopg.connect(admin, autocommit=True, connect_timeout=5) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target,))
            if cursor.fetchone() is None:
                cursor.execute(f'CREATE DATABASE "{target}"')


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    dsn = resolve_test_dsn()
    if dsn is None:
        pytest.skip("no test database configured")

    _guard_is_test_database(dsn)

    try:
        _ensure_database(dsn)
        apply_migrations(dsn=dsn, migrations_dir="migrations")
    except Exception as exc:  # pragma: no cover - depends on the local machine
        pytest.skip(f"test database unavailable: {type(exc).__name__}: {exc}")

    return dsn


@pytest.fixture
def db(postgres_dsn: str) -> Iterator[Any]:
    """A clean connection: every reset table is emptied before the test runs."""

    import psycopg

    with psycopg.connect(postgres_dsn, autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"TRUNCATE TABLE {', '.join(_RESET_TABLES)} RESTART IDENTITY CASCADE"
            )
        yield conn


SNAPSHOT_ID = "test:snapshot:0001"
SEASON = 2026

HAWKS = 100  # a club with hitters, a two-way player and pitching
OTTERS = 200  # a club with only pitching ingested
EMPTY = 300  # a club with no stats at all

SLUGGER = 1  # elite hitter, comfortably over the qualifier
ACE = 2  # elite pitcher
TWO_WAY = 3  # both a hitting and a pitching line
SCRUB = 4  # a hitter below the default qualifier


@pytest.fixture
def seeded(db: Any) -> Any:
    """A small, deterministic league covering the cases the queries must handle."""

    with db.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO data_snapshots (data_snapshot_id, source_system, payload_sha256)
            VALUES (%s, 'test', 'deadbeef')
            """,
            (SNAPSHOT_ID,),
        )
        cursor.executemany(
            """
            INSERT INTO teams (team_id, name, abbreviation, league_name, division_name,
                               first_seen_snapshot_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            [
                (HAWKS, "Test Hawks", "HWK", "Test League", "Test East", SNAPSHOT_ID),
                (OTTERS, "Test Otters", "OTT", "Test League", "Test West", SNAPSHOT_ID),
                (EMPTY, "Test Empties", "EMP", "Test League", "Test West", SNAPSHOT_ID),
            ],
        )
        cursor.executemany(
            """
            INSERT INTO players (player_id, full_name, primary_position, bats, throws,
                                 first_seen_snapshot_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            [
                (SLUGGER, "Sam Slugger", "RF", "L", "R", SNAPSHOT_ID),
                (ACE, "Ada Ace", "P", "R", "R", SNAPSHOT_ID),
                (TWO_WAY, "Toni Twoway", "TWP", "L", "L", SNAPSHOT_ID),
                (SCRUB, "Sid Scrub", "2B", "R", "R", SNAPSHOT_ID),
            ],
        )
        cursor.executemany(
            """
            INSERT INTO roster_memberships (team_id, player_id, season, primary_position,
                                            source_snapshot_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [
                (HAWKS, SLUGGER, SEASON, "RF", SNAPSHOT_ID),
                (HAWKS, TWO_WAY, SEASON, "TWP", SNAPSHOT_ID),
                (HAWKS, SCRUB, SEASON, "2B", SNAPSHOT_ID),
                (OTTERS, ACE, SEASON, "P", SNAPSHOT_ID),
            ],
        )
        cursor.executemany(
            """
            INSERT INTO player_season_stats (
                player_id, season, team_id, stat_group, pa, ip,
                woba, wrc_plus, fip, k_bb_ratio,
                at_bats, singles, doubles, triples, home_runs,
                walks, intentional_walks, hit_by_pitch, sacrifice_flies,
                strikeouts, stolen_bases, source_snapshot_id
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s
            )
            """,
            [
                # Slugger: elite bat, 600 PA — clears the default 200 PA qualifier.
                (SLUGGER, SEASON, HAWKS, "hitting", 600, None,
                 0.4200, 175.0, None, None,
                 520, 100, 35, 3, 40, 70, 8, 6, 4, 110, 12, SNAPSHOT_ID),
                # Ace: elite arm, 180 IP — clears the default 50 IP qualifier.
                (ACE, SEASON, OTTERS, "pitching", None, 180.00,
                 None, None, 2.500, 6.000, None, None, None, None, 18,
                 30, None, 4, None, 220, None, SNAPSHOT_ID),
                # Two-way: both lines, same player, same season and snapshot.
                (TWO_WAY, SEASON, HAWKS, "hitting", 400, None,
                 0.3600, 130.0, None, None,
                 350, 70, 20, 2, 18, 45, 3, 5, 3, 90, 6, SNAPSHOT_ID),
                (TWO_WAY, SEASON, HAWKS, "pitching", None, 90.00,
                 None, None, 3.100, 4.000, None, None, None, None, 9,
                 25, None, 3, None, 100, None, SNAPSHOT_ID),
                # Scrub: only 50 PA, below the default qualifier.
                (SCRUB, SEASON, HAWKS, "hitting", 50, None,
                 0.4900, 200.0, None, None,
                 45, 12, 3, 0, 4, 4, 0, 1, 0, 10, 1, SNAPSHOT_ID),
            ],
        )
    return db
