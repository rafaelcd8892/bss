from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from baseball_sim.ingest.normalize import (
    GameRecord,
    PlayerRecord,
    RosterMembershipRecord,
    TeamRecord,
)
from baseball_sim.ingest.snapshot_store import StoredSnapshot
from baseball_sim.ingest.stats import PlayerSeasonStatRecord


class IngestRepository(Protocol):
    def upsert_data_snapshot(
        self, *, snapshot: StoredSnapshot, notes: str | None = None
    ) -> None: ...

    def upsert_teams(self, *, snapshot_id: str, teams: Sequence[TeamRecord]) -> int: ...

    def upsert_players(self, *, snapshot_id: str, players: Sequence[PlayerRecord]) -> int: ...

    def upsert_games(self, *, snapshot_id: str, games: Sequence[GameRecord]) -> int: ...

    def upsert_player_season_stats(
        self, *, snapshot_id: str, records: Sequence[PlayerSeasonStatRecord]
    ) -> int: ...

    def upsert_roster_memberships(
        self,
        *,
        snapshot_id: str,
        season: int,
        memberships: Sequence[RosterMembershipRecord],
    ) -> int: ...

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

    def upsert_player_season_stats(
        self, *, snapshot_id: str, records: Sequence[PlayerSeasonStatRecord]
    ) -> int:
        with self._conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO player_season_stats (
                    player_id, season, team_id, stat_group,
                    pa, ip, woba, xwoba, wrc_plus, fip, k_bb_ratio,
                    at_bats, singles, doubles, triples, home_runs,
                    walks, intentional_walks, hit_by_pitch, sacrifice_flies,
                    strikeouts, stolen_bases, source_snapshot_id
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (player_id, season, source_snapshot_id, stat_group) DO UPDATE
                SET team_id = EXCLUDED.team_id,
                    pa = EXCLUDED.pa,
                    ip = EXCLUDED.ip,
                    woba = EXCLUDED.woba,
                    xwoba = EXCLUDED.xwoba,
                    wrc_plus = EXCLUDED.wrc_plus,
                    fip = EXCLUDED.fip,
                    k_bb_ratio = EXCLUDED.k_bb_ratio,
                    at_bats = EXCLUDED.at_bats,
                    singles = EXCLUDED.singles,
                    doubles = EXCLUDED.doubles,
                    triples = EXCLUDED.triples,
                    home_runs = EXCLUDED.home_runs,
                    walks = EXCLUDED.walks,
                    intentional_walks = EXCLUDED.intentional_walks,
                    hit_by_pitch = EXCLUDED.hit_by_pitch,
                    sacrifice_flies = EXCLUDED.sacrifice_flies,
                    strikeouts = EXCLUDED.strikeouts,
                    stolen_bases = EXCLUDED.stolen_bases,
                    loaded_at_utc = NOW()
                """,
                [_player_season_stats_row(record, snapshot_id) for record in records],
            )
        return len(records)

    def upsert_roster_memberships(
        self,
        *,
        snapshot_id: str,
        season: int,
        memberships: Sequence[RosterMembershipRecord],
    ) -> int:
        with self._conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO roster_memberships (
                    team_id, player_id, season, primary_position, source_snapshot_id
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (team_id, player_id, source_snapshot_id) DO UPDATE
                SET season = EXCLUDED.season,
                    primary_position = EXCLUDED.primary_position,
                    loaded_at_utc = NOW()
                """,
                [
                    (
                        membership.team_id,
                        membership.player_id,
                        season,
                        membership.primary_position,
                        snapshot_id,
                    )
                    for membership in memberships
                ],
            )
        return len(memberships)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()


def _player_season_stats_row(
    record: PlayerSeasonStatRecord, snapshot_id: str
) -> tuple[object, ...]:
    batting = record.batting
    pitching = record.pitching
    # Home runs, walks, HBP and strikeouts are shared columns: a hitting row fills
    # them from the batting line, a pitching row from the pitching line.
    home_runs = batting.home_runs if batting is not None else _p(pitching, "home_runs")
    walks = batting.walks if batting is not None else _p(pitching, "walks")
    hit_by_pitch = batting.hit_by_pitch if batting is not None else _p(pitching, "hit_by_pitch")
    strikeouts = batting.strikeouts if batting is not None else _p(pitching, "strikeouts")
    return (
        record.player_id,
        record.season,
        record.team_id,
        record.stat_group,
        record.pa,
        record.ip,
        record.woba,
        record.xwoba,
        record.wrc_plus,
        record.fip,
        record.k_bb_ratio,
        batting.at_bats if batting is not None else None,
        batting.singles if batting is not None else None,
        batting.doubles if batting is not None else None,
        batting.triples if batting is not None else None,
        home_runs,
        walks,
        batting.intentional_walks if batting is not None else None,
        hit_by_pitch,
        batting.sacrifice_flies if batting is not None else None,
        strikeouts,
        batting.stolen_bases if batting is not None else None,
        snapshot_id,
    )


def _p(pitching: object, attribute: str) -> int | None:
    return getattr(pitching, attribute) if pitching is not None else None
