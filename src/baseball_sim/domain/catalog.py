"""Read-side catalog repository for browsing canonical teams and players.

The ingestion path writes the ``teams`` / ``players`` tables; this is the read seam
that lets the API (and a future UI) list and look them up. Kept framework-agnostic:
the FastAPI dependency wiring lives in the routes module.
"""

from __future__ import annotations

from typing import Protocol

from baseball_sim.domain.contracts import PlayerSummary, TeamSummary

_LIST_TEAMS = """
    SELECT team_id, name, abbreviation, league_name, division_name
    FROM teams
    ORDER BY name
"""

_GET_PLAYER = """
    SELECT player_id, full_name, primary_position, bats, throws
    FROM players
    WHERE player_id = %s
"""

# Resolve a team's roster from its most recently ingested snapshot, preferring the
# membership's captured position over the player's generic primary position.
_GET_TEAM_ROSTER = """
    SELECT p.player_id,
           p.full_name,
           COALESCE(rm.primary_position, p.primary_position),
           p.bats,
           p.throws
    FROM roster_memberships rm
    JOIN players p ON p.player_id = rm.player_id
    WHERE rm.team_id = %s
      AND rm.source_snapshot_id = (
          SELECT source_snapshot_id
          FROM roster_memberships
          WHERE team_id = %s
          ORDER BY loaded_at_utc DESC
          LIMIT 1
      )
    ORDER BY p.full_name
"""


class CatalogRepository(Protocol):
    def list_teams(self) -> list[TeamSummary]: ...

    def get_player(self, *, player_id: int) -> PlayerSummary | None: ...

    def get_team_roster(self, *, team_id: int) -> list[PlayerSummary]: ...


class PostgresCatalogRepository:
    def __init__(self, *, dsn: str) -> None:
        import psycopg

        self._conn = psycopg.connect(dsn)

    def close(self) -> None:
        self._conn.close()

    def list_teams(self) -> list[TeamSummary]:
        with self._conn.cursor() as cursor:
            cursor.execute(_LIST_TEAMS)
            rows = cursor.fetchall()
        return [
            TeamSummary(
                team_id=row[0],
                name=row[1],
                abbreviation=row[2],
                league_name=row[3],
                division_name=row[4],
            )
            for row in rows
        ]

    def get_player(self, *, player_id: int) -> PlayerSummary | None:
        with self._conn.cursor() as cursor:
            cursor.execute(_GET_PLAYER, (player_id,))
            row = cursor.fetchone()
        if row is None:
            return None
        return PlayerSummary(
            player_id=row[0],
            full_name=row[1],
            primary_position=row[2],
            bats=row[3],
            throws=row[4],
        )

    def get_team_roster(self, *, team_id: int) -> list[PlayerSummary]:
        with self._conn.cursor() as cursor:
            cursor.execute(_GET_TEAM_ROSTER, (team_id, team_id))
            rows = cursor.fetchall()
        return [
            PlayerSummary(
                player_id=row[0],
                full_name=row[1],
                primary_position=row[2],
                bats=row[3],
                throws=row[4],
            )
            for row in rows
        ]
