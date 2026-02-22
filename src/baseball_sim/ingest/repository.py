from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from baseball_sim.ingest.normalize import GameRecord, PlayerRecord, TeamRecord
from baseball_sim.ingest.snapshot_store import StoredSnapshot


class IngestRepository(Protocol):
    def upsert_data_snapshot(
        self, *, snapshot: StoredSnapshot, notes: str | None = None
    ) -> None: ...

    def upsert_teams(self, *, snapshot_id: str, teams: Sequence[TeamRecord]) -> int: ...

    def upsert_players(self, *, snapshot_id: str, players: Sequence[PlayerRecord]) -> int: ...

    def upsert_games(self, *, snapshot_id: str, games: Sequence[GameRecord]) -> int: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class PostgresIngestRepository:
    def __init__(self, *, dsn: str) -> None:
        import psycopg

        self._conn = psycopg.connect(dsn)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> PostgresIngestRepository:
        return self

    def __exit__(self, exc_type: object, _exc: object, _tb: object) -> None:
        if exc_type is not None:
            self.rollback()
        self.close()

    def upsert_data_snapshot(self, *, snapshot: StoredSnapshot, notes: str | None = None) -> None:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO data_snapshots (
                    data_snapshot_id,
                    source_system,
                    payload_sha256,
                    notes
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (data_snapshot_id) DO NOTHING
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.source_system,
                    snapshot.payload_sha256,
                    notes,
                ),
            )

    def upsert_teams(self, *, snapshot_id: str, teams: Sequence[TeamRecord]) -> int:
        with self._conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO teams (
                    team_id,
                    name,
                    abbreviation,
                    league_name,
                    division_name,
                    first_seen_snapshot_id
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (team_id) DO UPDATE
                SET name = EXCLUDED.name,
                    abbreviation = EXCLUDED.abbreviation,
                    league_name = EXCLUDED.league_name,
                    division_name = EXCLUDED.division_name,
                    last_updated_utc = NOW()
                """,
                [
                    (
                        team.team_id,
                        team.name,
                        team.abbreviation,
                        team.league_name,
                        team.division_name,
                        snapshot_id,
                    )
                    for team in teams
                ],
            )
        return len(teams)

    def upsert_players(self, *, snapshot_id: str, players: Sequence[PlayerRecord]) -> int:
        with self._conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO players (
                    player_id,
                    full_name,
                    primary_position,
                    bats,
                    throws,
                    birth_date,
                    mlb_debut_date,
                    first_seen_snapshot_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id) DO UPDATE
                SET full_name = EXCLUDED.full_name,
                    primary_position = EXCLUDED.primary_position,
                    bats = EXCLUDED.bats,
                    throws = EXCLUDED.throws,
                    birth_date = COALESCE(players.birth_date, EXCLUDED.birth_date),
                    mlb_debut_date = COALESCE(players.mlb_debut_date, EXCLUDED.mlb_debut_date),
                    last_updated_utc = NOW()
                """,
                [
                    (
                        player.player_id,
                        player.full_name,
                        player.primary_position,
                        player.bats,
                        player.throws,
                        player.birth_date,
                        player.mlb_debut_date,
                        snapshot_id,
                    )
                    for player in players
                ],
            )
        return len(players)

    def upsert_games(self, *, snapshot_id: str, games: Sequence[GameRecord]) -> int:
        with self._conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO games (
                    game_pk,
                    game_date,
                    season,
                    game_type,
                    status_text,
                    home_team_id,
                    away_team_id,
                    home_score,
                    away_score,
                    snapshot_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_pk) DO UPDATE
                SET game_date = EXCLUDED.game_date,
                    season = EXCLUDED.season,
                    game_type = EXCLUDED.game_type,
                    status_text = EXCLUDED.status_text,
                    home_team_id = EXCLUDED.home_team_id,
                    away_team_id = EXCLUDED.away_team_id,
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    snapshot_id = EXCLUDED.snapshot_id,
                    loaded_at_utc = NOW()
                """,
                [
                    (
                        game.game_pk,
                        game.game_date,
                        game.season,
                        game.game_type,
                        game.status_text,
                        game.home_team_id,
                        game.away_team_id,
                        game.home_score,
                        game.away_score,
                        snapshot_id,
                    )
                    for game in games
                ],
            )
        return len(games)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()
