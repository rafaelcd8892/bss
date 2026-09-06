"""Read-side catalog repository for browsing canonical teams and players.

The ingestion path writes the ``teams`` / ``players`` tables; this is the read seam
that lets the API (and a future UI) list and look them up. Kept framework-agnostic:
the FastAPI dependency wiring lives in the routes module.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from baseball_sim.domain.contracts import (
    LeaderMetric,
    PlayerSeasonLine,
    PlayerSummary,
    StatLeader,
    TeamSummary,
)
from baseball_sim.domain.postgres_stats import (
    SEASON_FIELDING_COLUMNS,
    SEASON_STATS_COLUMNS,
    batting_line_from_row,
    fielding_line_from_row,
    pitching_line_from_row,
)
from baseball_sim.sim.sabermetrics import (
    RawBattingLine,
    RawFieldingLine,
    RawPitchingLine,
)

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

# Season wOBA for a set of players, newest snapshot per player. Used to order a
# batting lineup by hitting quality instead of alphabetically.
_GET_BATTING_WOBA = """
    SELECT DISTINCT ON (player_id) player_id, woba
    FROM player_season_stats
    WHERE season = %s
      AND stat_group = 'hitting'
      AND woba IS NOT NULL
      AND player_id = ANY(%s)
    ORDER BY player_id, loaded_at_utc DESC
"""


@dataclass(frozen=True)
class CompletedGame:
    """A finished game with a decision, usable as a forecast outcome."""

    game_pk: int
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int

    @property
    def home_won(self) -> bool:
        return self.home_score > self.away_score


@dataclass(frozen=True)
class LeaderMetricMeta:
    """How one leaderboard metric is queried and described.

    ``column`` and ``qualifier_column`` are SQL identifiers chosen from this fixed
    table — never from request input — so the metric name can be interpolated into
    the query safely while the values stay parameterized.
    """

    column: str
    stat_group: str
    qualifier_column: str
    qualifier_unit: str
    descending: bool
    default_minimum: float


LEADER_METRICS: dict[LeaderMetric, LeaderMetricMeta] = {
    "woba": LeaderMetricMeta("woba", "hitting", "pa", "PA", True, 200),
    "wrc_plus": LeaderMetricMeta("wrc_plus", "hitting", "pa", "PA", True, 200),
    # FIP is an ERA-scale metric: lower is better.
    "fip": LeaderMetricMeta("fip", "pitching", "ip", "IP", False, 50),
    "k_bb_ratio": LeaderMetricMeta("k_bb_ratio", "pitching", "ip", "IP", True, 50),
}


def leader_qualifier_label(metric: LeaderMetric, minimum: float) -> str:
    meta = LEADER_METRICS[metric]
    rendered = f"{minimum:g}"
    return f"min {rendered} {meta.qualifier_unit}"


class CatalogRepository(Protocol):
    def list_teams(self) -> list[TeamSummary]: ...

    def get_player(self, *, player_id: int) -> PlayerSummary | None: ...

    def get_team_roster(self, *, team_id: int) -> list[PlayerSummary]: ...

    def get_batting_woba(
        self, *, player_ids: Sequence[int], season: int
    ) -> dict[int, float]: ...

    def get_stat_leaders(
        self, *, metric: LeaderMetric, season: int, minimum: float, limit: int
    ) -> list[StatLeader]: ...

    def get_team_stat_lines(
        self, *, team_id: int, season: int
    ) -> tuple[list[RawBattingLine], list[RawPitchingLine]]: ...

    def get_all_team_stat_lines(
        self, *, season: int
    ) -> dict[int, tuple[list[RawBattingLine], list[RawPitchingLine]]]: ...

    def get_league_fielding_lines(
        self, *, season: int
    ) -> dict[int, list[RawFieldingLine]]: ...

    def get_player_season_lines(
        self, *, player_id: int, season: int
    ) -> list[PlayerSeasonLine]: ...

    def get_completed_games(self, *, season: int) -> list[CompletedGame]: ...


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

    def get_batting_woba(self, *, player_ids: Sequence[int], season: int) -> dict[int, float]:
        if not player_ids:
            return {}
        with self._conn.cursor() as cursor:
            cursor.execute(_GET_BATTING_WOBA, (season, list(player_ids)))
            rows = cursor.fetchall()
        return {int(row[0]): float(row[1]) for row in rows}

    def get_stat_leaders(
        self, *, metric: LeaderMetric, season: int, minimum: float, limit: int
    ) -> list[StatLeader]:
        meta = LEADER_METRICS[metric]
        # Take the newest snapshot row per player, then rank across players.
        query = f"""
            SELECT player_id, full_name, team_id, value, pa, ip
            FROM (
                SELECT DISTINCT ON (s.player_id)
                       s.player_id,
                       p.full_name,
                       s.team_id,
                       s.{meta.column} AS value,
                       s.pa,
                       s.ip
                FROM player_season_stats s
                JOIN players p ON p.player_id = s.player_id
                WHERE s.season = %s
                  AND s.stat_group = %s
                  AND s.{meta.column} IS NOT NULL
                  AND s.{meta.qualifier_column} >= %s
                ORDER BY s.player_id, s.loaded_at_utc DESC
            ) latest
            ORDER BY value {"DESC" if meta.descending else "ASC"}, full_name
            LIMIT %s
        """
        with self._conn.cursor() as cursor:
            cursor.execute(query, (season, meta.stat_group, minimum, limit))
            rows = cursor.fetchall()

        return [
            StatLeader(
                rank=index,
                player_id=int(row[0]),
                full_name=str(row[1]),
                team_id=int(row[2]) if row[2] is not None else None,
                value=float(row[3]),
                plate_appearances=int(row[4]) if row[4] is not None else None,
                innings_pitched=float(row[5]) if row[5] is not None else None,
            )
            for index, row in enumerate(rows, start=1)
        ]

    def get_team_stat_lines(
        self, *, team_id: int, season: int
    ) -> tuple[list[RawBattingLine], list[RawPitchingLine]]:
        """Newest hitting and pitching line per player for one team's season."""

        query = f"""
            SELECT DISTINCT ON (player_id, stat_group) {SEASON_STATS_COLUMNS}
            FROM player_season_stats
            WHERE season = %s AND team_id = %s
            ORDER BY player_id, stat_group, loaded_at_utc DESC
        """
        with self._conn.cursor() as cursor:
            cursor.execute(query, (season, team_id))
            rows = cursor.fetchall()

        batting = [batting_line_from_row(row) for row in rows if str(row[2]) == "hitting"]
        pitching = [pitching_line_from_row(row) for row in rows if str(row[2]) == "pitching"]
        return batting, pitching

    def get_all_team_stat_lines(
        self, *, season: int
    ) -> dict[int, tuple[list[RawBattingLine], list[RawPitchingLine]]]:
        """Every club's lines for a season in one round trip.

        The league table needs all thirty profiles at once; fetching them per team
        would open thirty connections to render one screen.
        """

        query = f"""
            SELECT DISTINCT ON (player_id, stat_group) {SEASON_STATS_COLUMNS}
            FROM player_season_stats
            WHERE season = %s AND team_id IS NOT NULL
            ORDER BY player_id, stat_group, loaded_at_utc DESC
        """
        with self._conn.cursor() as cursor:
            cursor.execute(query, (season,))
            rows = cursor.fetchall()

        by_team: dict[int, tuple[list[RawBattingLine], list[RawPitchingLine]]] = {}
        for row in rows:
            team_id = int(row[1])
            batting, pitching = by_team.setdefault(team_id, ([], []))
            group = str(row[2])
            if group == "hitting":
                batting.append(batting_line_from_row(row))
            elif group == "pitching":
                pitching.append(pitching_line_from_row(row))
        return by_team

    def get_league_fielding_lines(
        self, *, season: int
    ) -> dict[int, list[RawFieldingLine]]:
        """Every club's fielding splits for a season, keyed by team.

        Always league-wide, even when only one club is being rendered: a range factor
        means nothing without the league baseline at the same positions to divide by.
        """

        query = f"""
            SELECT DISTINCT ON (player_id, position) {SEASON_FIELDING_COLUMNS}
            FROM player_season_fielding
            WHERE season = %s AND team_id IS NOT NULL
            ORDER BY player_id, position, loaded_at_utc DESC
        """
        with self._conn.cursor() as cursor:
            cursor.execute(query, (season,))
            rows = cursor.fetchall()

        by_team: dict[int, list[RawFieldingLine]] = {}
        for row in rows:
            by_team.setdefault(int(row[1]), []).append(fielding_line_from_row(row))
        return by_team

    def get_player_season_lines(
        self, *, player_id: int, season: int
    ) -> list[PlayerSeasonLine]:
        """A player's stored season lines, newest snapshot per stat group."""

        query = """
            SELECT DISTINCT ON (stat_group)
                   stat_group, team_id, pa, at_bats, singles, doubles, triples,
                   home_runs, walks, strikeouts, stolen_bases, ip,
                   woba, wrc_plus, fip, k_bb_ratio
            FROM player_season_stats
            WHERE player_id = %s AND season = %s
            ORDER BY stat_group, loaded_at_utc DESC
        """
        with self._conn.cursor() as cursor:
            cursor.execute(query, (player_id, season))
            rows = cursor.fetchall()

        lines: list[PlayerSeasonLine] = []
        for row in rows:
            group = str(row[0])
            if group not in ("hitting", "pitching"):
                continue
            singles, doubles, triples, home_runs = row[4], row[5], row[6], row[7]
            hits = (
                sum(int(part) for part in (singles, doubles, triples, home_runs))
                if group == "hitting" and singles is not None
                else None
            )
            lines.append(
                PlayerSeasonLine(
                    stat_group="hitting" if group == "hitting" else "pitching",
                    team_id=_optional_int(row[1]),
                    plate_appearances=_optional_int(row[2]),
                    at_bats=_optional_int(row[3]),
                    hits=hits,
                    doubles=_optional_int(doubles),
                    triples=_optional_int(triples),
                    home_runs=_optional_int(home_runs),
                    walks=_optional_int(row[8]),
                    strikeouts=_optional_int(row[9]),
                    stolen_bases=_optional_int(row[10]),
                    innings_pitched=_optional_float(row[11]),
                    woba=_optional_float(row[12]),
                    wrc_plus=_optional_float(row[13]),
                    fip=_optional_float(row[14]),
                    k_bb_ratio=_optional_float(row[15]),
                )
            )
        return lines


    def get_completed_games(self, *, season: int) -> list[CompletedGame]:
        """Finished, decided games — the only ones a forecast can be scored against.

        Filtering on "has a score" is not enough: a game in progress already carries a
        partial score, and counting those would silently contaminate the sample.
        """

        query = """
            SELECT game_pk, home_team_id, away_team_id, home_score, away_score
            FROM games
            WHERE season = %s
              AND status_text = 'Final'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
              AND home_score <> away_score
            ORDER BY game_date, game_pk
        """
        with self._conn.cursor() as cursor:
            cursor.execute(query, (season,))
            rows = cursor.fetchall()
        return [
            CompletedGame(
                game_pk=int(row[0]),
                home_team_id=int(row[1]),
                away_team_id=int(row[2]),
                home_score=int(row[3]),
                away_score=int(row[4]),
            )
            for row in rows
        ]


def _optional_int(value: object) -> int | None:
    return int(value) if value is not None else None  # type: ignore[call-overload]


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None  # type: ignore[arg-type]
