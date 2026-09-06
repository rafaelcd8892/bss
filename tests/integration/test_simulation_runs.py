"""Recording and recalling runs against a real PostgreSQL.

simulation_runs shipped in migration 0001 but could never accept a row: its
model_version foreign key pointed at a table nothing populates. Migration 0005 removed
both constraints, and these tests are what proves a row now lands.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from baseball_sim.domain.contracts import DeterministicContext, SimulateGameResult
from baseball_sim.domain.simulation_runs import PostgresSimulationRunRepository

CONTEXT = DeterministicContext(
    seed=4242, model_version="baseline-v1", data_snapshot_id="ui"
)
MATCH = "match_00112233aabbccdd"


def summary(home_score: int = 6, away_score: int = 2) -> SimulateGameResult:
    return SimulateGameResult(
        home_team_id=147,
        away_team_id=121,
        innings_played=9,
        home_score=home_score,
        away_score=away_score,
        winner_team_id=147 if home_score > away_score else 121,
        assumptions=["test"],
    )


@pytest.fixture
def runs(postgres_dsn: str, db: Any) -> Iterator[PostgresSimulationRunRepository]:
    del db  # truncates before the test
    repository = PostgresSimulationRunRepository(dsn=postgres_dsn)
    try:
        yield repository
    finally:
        repository.close()


def record(repository: PostgresSimulationRunRepository, **overrides: Any) -> None:
    payload: dict[str, Any] = {
        "match_id": MATCH,
        "context": CONTEXT,
        "home_team_id": 147,
        "away_team_id": 121,
        "innings": 9,
        "stats_source": "postgres",
        "summary": summary(),
    }
    payload.update(overrides)
    repository.record_run(**payload)


class TestRecording:
    def test_a_run_can_be_stored_and_recalled(
        self, runs: PostgresSimulationRunRepository
    ) -> None:
        record(runs)
        stored = runs.get_run(match_id=MATCH)

        assert stored is not None
        assert stored.match_id == MATCH
        assert stored.home_team_id == 147
        assert stored.innings == 9
        assert stored.stats_source == "postgres"
        # The context is the part that actually reproduces the game.
        assert stored.context == CONTEXT
        assert stored.summary.winner_team_id == 147

    def test_a_caller_supplied_snapshot_label_is_accepted(
        self, runs: PostgresSimulationRunRepository
    ) -> None:
        """"ui" is not a catalogued snapshot, and must not need to be.

        The old foreign key would have rejected this row outright.
        """
        record(runs)
        stored = runs.get_run(match_id=MATCH)
        assert stored is not None
        assert stored.context.data_snapshot_id == "ui"

    def test_replaying_the_same_match_updates_rather_than_duplicates(
        self, runs: PostgresSimulationRunRepository
    ) -> None:
        record(runs)
        record(runs, summary=summary(home_score=9, away_score=1))

        with runs._conn.cursor() as cursor:  # noqa: SLF001 - inspecting the test database
            cursor.execute("SELECT count(*) FROM simulation_runs WHERE match_id = %s", (MATCH,))
            assert int(cursor.fetchone()[0]) == 1

        stored = runs.get_run(match_id=MATCH)
        assert stored is not None
        assert stored.summary.home_score == 9

    def test_different_matches_are_separate_rows(
        self, runs: PostgresSimulationRunRepository
    ) -> None:
        record(runs)
        record(runs, match_id="match_ffffffffffffffff")

        with runs._conn.cursor() as cursor:  # noqa: SLF001
            cursor.execute("SELECT count(*) FROM simulation_runs")
            assert int(cursor.fetchone()[0]) == 2

    def test_an_unknown_match_is_absent(
        self, runs: PostgresSimulationRunRepository
    ) -> None:
        assert runs.get_run(match_id="match_0000000000000000") is None
