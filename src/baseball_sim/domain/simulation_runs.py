"""Persisting simulated games so they can be recalled by match id.

A deterministic simulator does not need the stored output to replay a game — the
context reproduces it exactly. The record exists for two other reasons: to let a game
be found again from a link, and to keep the original result so a later run can be
checked against it if the engine changes.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from baseball_sim.domain.contracts import (
    DeterministicContext,
    SimulateGameResult,
    SimulationRunResponse,
)

_INSERT_RUN = """
    INSERT INTO simulation_runs (
        match_id, seed, model_version, data_snapshot_id,
        home_team_id, away_team_id, scheduled_innings, stats_source,
        request_payload, response_payload
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (match_id) DO UPDATE
    SET response_payload = EXCLUDED.response_payload,
        stats_source = EXCLUDED.stats_source
"""

_SELECT_RUN = """
    SELECT match_id, created_at_utc, home_team_id, away_team_id, scheduled_innings,
           seed, model_version, data_snapshot_id, stats_source, response_payload
    FROM simulation_runs
    WHERE match_id = %s
"""


class SimulationRunRepository(Protocol):
    def record_run(
        self,
        *,
        match_id: str,
        context: DeterministicContext,
        home_team_id: int,
        away_team_id: int,
        innings: int,
        stats_source: str,
        summary: SimulateGameResult,
    ) -> None: ...

    def get_run(self, *, match_id: str) -> SimulationRunResponse | None: ...


class PostgresSimulationRunRepository:
    def __init__(self, *, dsn: str) -> None:
        import psycopg

        self._conn = psycopg.connect(dsn)

    def close(self) -> None:
        self._conn.close()

    def record_run(
        self,
        *,
        match_id: str,
        context: DeterministicContext,
        home_team_id: int,
        away_team_id: int,
        innings: int,
        stats_source: str,
        summary: SimulateGameResult,
    ) -> None:
        request = {
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "innings": innings,
            "context": context.model_dump(),
        }
        with self._conn.cursor() as cursor:
            cursor.execute(
                _INSERT_RUN,
                (
                    match_id,
                    context.seed,
                    context.model_version,
                    context.data_snapshot_id,
                    home_team_id,
                    away_team_id,
                    innings,
                    stats_source,
                    json.dumps(request, sort_keys=True),
                    json.dumps(summary.model_dump(), sort_keys=True),
                ),
            )
        self._conn.commit()

    def get_run(self, *, match_id: str) -> SimulationRunResponse | None:
        with self._conn.cursor() as cursor:
            cursor.execute(_SELECT_RUN, (match_id,))
            row = cursor.fetchone()
        if row is None:
            return None
        return _run_from_row(row)


def _run_from_row(row: tuple[Any, ...]) -> SimulationRunResponse:
    payload = row[9]
    summary = payload if isinstance(payload, dict) else json.loads(payload)
    return SimulationRunResponse(
        match_id=str(row[0]),
        created_at_utc=row[1],
        home_team_id=int(row[2]),
        away_team_id=int(row[3]),
        innings=int(row[4]),
        context=DeterministicContext(
            seed=int(row[5]),
            model_version=str(row[6]),
            data_snapshot_id=str(row[7]),
        ),
        stats_source=str(row[8]) if row[8] is not None else "unknown",
        summary=SimulateGameResult.model_validate(summary),
    )
