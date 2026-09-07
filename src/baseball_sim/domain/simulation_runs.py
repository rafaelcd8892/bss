"""Persisting simulated games so they can be recalled by match id.

A deterministic simulator reproduces a game from its context — but only under the same
rules. The engine's tuning constants live in the ruleset, so the ruleset is stored with
the run and a replay is played under the rules it was recorded under. Retuning the
model therefore cannot change what an old replay produces (ADR-028).

The stored result is kept as well, so a replay can be checked against what was
originally recorded rather than trusted.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from baseball_sim.domain.contracts import (
    DeterministicContext,
    SimulateGameResult,
    SimulationRunResponse,
)
from baseball_sim.sim.rulesets import (
    SimulationRuleset,
    ruleset_from_payload,
    ruleset_to_payload,
)

_INSERT_RUN = """
    INSERT INTO simulation_runs (
        match_id, seed, model_version, data_snapshot_id,
        home_team_id, away_team_id, scheduled_innings, stats_source,
        request_payload, response_payload, ruleset, ruleset_checksum
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (match_id) DO UPDATE
    SET response_payload = EXCLUDED.response_payload,
        stats_source = EXCLUDED.stats_source
"""

_SELECT_RUN = """
    SELECT match_id, created_at_utc, home_team_id, away_team_id, scheduled_innings,
           seed, model_version, data_snapshot_id, stats_source, response_payload,
           ruleset, ruleset_checksum
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
        ruleset: SimulationRuleset,
        ruleset_checksum: str,
    ) -> None: ...

    def get_run(self, *, match_id: str) -> SimulationRunResponse | None: ...

    def get_run_ruleset(self, *, match_id: str) -> SimulationRuleset | None: ...


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
        ruleset: SimulationRuleset,
        ruleset_checksum: str,
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
                    json.dumps(ruleset_to_payload(ruleset), sort_keys=True),
                    ruleset_checksum,
                ),
            )
        self._conn.commit()

    def get_run(self, *, match_id: str) -> SimulationRunResponse | None:
        row = self._row(match_id)
        return _run_from_row(row) if row is not None else None

    def get_run_ruleset(self, *, match_id: str) -> SimulationRuleset | None:
        """The rules this run was played under, or ``None`` if it was not recorded.

        A run stored before the ruleset was persisted has no payload. Returning
        ``None`` lets the caller say so rather than replay it under today's rules and
        present the result as the original.
        """

        row = self._row(match_id)
        if row is None or row[10] is None:
            return None
        payload = row[10] if isinstance(row[10], dict) else json.loads(row[10])
        return ruleset_from_payload(payload)

    def _row(self, match_id: str) -> tuple[Any, ...] | None:
        with self._conn.cursor() as cursor:
            cursor.execute(_SELECT_RUN, (match_id,))
            return cursor.fetchone()


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
        ruleset_id=_stored_ruleset_id(row[10]),
        ruleset_checksum=str(row[11]) if row[11] is not None else None,
    )


def _stored_ruleset_id(payload: Any) -> str | None:
    if payload is None:
        return None
    parsed = payload if isinstance(payload, dict) else json.loads(payload)
    value = parsed.get("ruleset_id")
    return str(value) if value is not None else None
