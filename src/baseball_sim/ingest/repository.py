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
from baseball_sim.ingest.stats import PlayerSeasonFieldingRecord, PlayerSeasonStatRecord


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

    def upsert_player_season_fielding(
        self, *, snapshot_id: str, records: Sequence[PlayerSeasonFieldingRecord]
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
                _PLAYER_SEASON_STATS_SQL,
                [_player_season_stats_row(record, snapshot_id) for record in records],
            )
        return len(records)

    def upsert_player_season_fielding(
        self, *, snapshot_id: str, records: Sequence[PlayerSeasonFieldingRecord]
    ) -> int:
        with self._conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO player_season_fielding (
                    player_id, season, team_id, position, games, games_started,
                    innings, put_outs, assists, errors, chances, double_plays,
                    fielding_percentage, range_factor_per_nine, source_snapshot_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id, season, position, source_snapshot_id) DO UPDATE
                SET team_id = EXCLUDED.team_id,
                    games = EXCLUDED.games,
                    games_started = EXCLUDED.games_started,
                    innings = EXCLUDED.innings,
                    put_outs = EXCLUDED.put_outs,
                    assists = EXCLUDED.assists,
                    errors = EXCLUDED.errors,
                    chances = EXCLUDED.chances,
                    double_plays = EXCLUDED.double_plays,
                    fielding_percentage = EXCLUDED.fielding_percentage,
                    range_factor_per_nine = EXCLUDED.range_factor_per_nine,
                    loaded_at_utc = NOW()
                """,
                [
                    (
                        record.player_id, record.season, record.team_id,
                        record.line.position, record.line.games, record.line.games_started,
                        record.line.innings, record.line.put_outs, record.line.assists,
                        record.line.errors, record.line.chances, record.line.double_plays,
                        record.fielding_percentage, record.range_factor_per_nine,
                        snapshot_id,
                    )
                    for record in records
                ],
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


#: Column order for the player_season_stats upsert. Kept as data so the statement and
#: the row tuple can never drift apart — with 40-odd columns, hand-written placeholders
#: are a bug waiting to happen.
_PLAYER_SEASON_STATS_COLUMNS = (
    "player_id", "season", "team_id", "stat_group",
    "pa", "ip", "woba", "xwoba", "wrc_plus", "fip", "k_bb_ratio",
    "at_bats", "singles", "doubles", "triples", "home_runs",
    "walks", "intentional_walks", "hit_by_pitch", "sacrifice_flies",
    "strikeouts", "stolen_bases",
    "runs", "runs_batted_in", "caught_stealing", "sacrifice_bunts",
    "ground_into_double_play", "ground_outs", "air_outs", "games_played",
    "batters_faced", "earned_runs", "hits_allowed", "games_started",
    "batting_average", "obp", "slg", "ops", "iso", "babip",
    "era", "whip", "strikeout_rate", "walk_rate", "ground_ball_rate",
    "x_batting_average", "x_slg", "x_woba_con",
    "source_snapshot_id",
)

#: Everything except the composite key is refreshed on conflict.
_PLAYER_SEASON_STATS_KEY = ("player_id", "season", "source_snapshot_id", "stat_group")

_PLAYER_SEASON_STATS_SQL = """
    INSERT INTO player_season_stats ({columns})
    VALUES ({placeholders})
    ON CONFLICT ({key}) DO UPDATE
    SET {updates},
        loaded_at_utc = NOW()
""".format(
    columns=", ".join(_PLAYER_SEASON_STATS_COLUMNS),
    placeholders=", ".join(["%s"] * len(_PLAYER_SEASON_STATS_COLUMNS)),
    key=", ".join(_PLAYER_SEASON_STATS_KEY),
    updates=",\n        ".join(
        f"{column} = EXCLUDED.{column}"
        for column in _PLAYER_SEASON_STATS_COLUMNS
        if column not in _PLAYER_SEASON_STATS_KEY
    ),
)


def _player_season_stats_row(
    record: PlayerSeasonStatRecord, snapshot_id: str
) -> tuple[object, ...]:
    batting = record.batting
    pitching = record.pitching
    hitting = batting is not None

    def shared(attribute: str) -> int | None:
        """A column both groups populate, taken from whichever line this row is."""

        source = batting if hitting else pitching
        return getattr(source, attribute) if source is not None else None

    def bat(attribute: str) -> int | None:
        return getattr(batting, attribute) if batting is not None else None

    def arm(attribute: str) -> int | None:
        return getattr(pitching, attribute) if pitching is not None else None

    values: tuple[object, ...] = (
        record.player_id, record.season, record.team_id, record.stat_group,
        record.pa, record.ip, record.woba, record.xwoba, record.wrc_plus,
        record.fip, record.k_bb_ratio,
        bat("at_bats"), bat("singles"), bat("doubles"), bat("triples"),
        # Home runs, walks, HBP and strikeouts are shared columns: a hitting row fills
        # them from the batting line, a pitching row from the pitching line.
        shared("home_runs"), shared("walks"), bat("intentional_walks"),
        shared("hit_by_pitch"), bat("sacrifice_flies"), shared("strikeouts"),
        bat("stolen_bases"),
        bat("runs"), bat("runs_batted_in"), bat("caught_stealing"),
        bat("sacrifice_bunts"), bat("ground_into_double_play"),
        shared("ground_outs"), shared("air_outs"), shared("games_played"),
        arm("batters_faced"), arm("earned_runs"), arm("hits_allowed"),
        arm("games_started"),
        record.batting_average, record.obp, record.slg, record.ops, record.iso,
        record.babip, record.era, record.whip, record.strikeout_rate,
        record.walk_rate, record.ground_ball_rate,
        record.x_batting_average, record.x_slg, record.x_woba_con,
        snapshot_id,
    )
    assert len(values) == len(_PLAYER_SEASON_STATS_COLUMNS)
    return values
