"""Build a real-data stats provider from the ingested season tables.

Reads the raw counting components persisted by ingestion, reconstructs the exact
``RawBattingLine`` / ``RawPitchingLine`` / ``RawFieldingLine`` inputs, and wraps them
in a :class:`StatLineStatsProvider` so the serving path reuses the same analytical
code as everything else. Falls back to the synthetic provider for any player/team
without ingested data.
"""

from __future__ import annotations

from typing import Any

from baseball_sim.domain.stats_provider import (
    StatLineStatsProvider,
    StatsProvider,
    SyntheticStatsProvider,
)
from baseball_sim.sim.profiles import league_range_factors
from baseball_sim.sim.sabermetrics import (
    RawBattingLine,
    RawFieldingLine,
    RawPitchingLine,
)

#: Column order every season-stats row parser below expects.
SEASON_STATS_COLUMNS = """player_id, team_id, stat_group,
           ip, at_bats, singles, doubles, triples, home_runs,
           walks, intentional_walks, hit_by_pitch, sacrifice_flies,
           strikeouts, stolen_bases, pa"""

_SELECT_SEASON_STATS = """
    SELECT player_id, team_id, stat_group,
           ip, at_bats, singles, doubles, triples, home_runs,
           walks, intentional_walks, hit_by_pitch, sacrifice_flies,
           strikeouts, stolen_bases, pa
    FROM player_season_stats
    WHERE season = %s
    ORDER BY loaded_at_utc
"""

#: Column order :func:`fielding_line_from_row` expects.
SEASON_FIELDING_COLUMNS = """player_id, team_id, position,
           innings, put_outs, assists, errors, chances, double_plays,
           games, games_started"""

_SELECT_SEASON_FIELDING = """
    SELECT player_id, team_id, position,
           innings, put_outs, assists, errors, chances, double_plays,
           games, games_started
    FROM player_season_fielding
    WHERE season = %s
    ORDER BY loaded_at_utc
"""


def build_stat_line_provider(
    *,
    dsn: str,
    season: int,
    fallback: StatsProvider | None = None,
) -> StatLineStatsProvider:
    import psycopg

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(_SELECT_SEASON_STATS, (season,))
            rows = cursor.fetchall()
            cursor.execute(_SELECT_SEASON_FIELDING, (season,))
            fielding_rows = cursor.fetchall()

    return build_stat_line_provider_from_rows(
        rows=rows, fielding_rows=fielding_rows, fallback=fallback
    )


def build_stat_line_provider_from_rows(
    *,
    rows: list[tuple[Any, ...]],
    fielding_rows: list[tuple[Any, ...]] | None = None,
    fallback: StatsProvider | None = None,
) -> StatLineStatsProvider:
    batting_lines: dict[int, RawBattingLine] = {}
    pitching_lines: dict[int, RawPitchingLine] = {}
    team_batting: dict[int, list[RawBattingLine]] = {}
    team_pitching: dict[int, list[RawPitchingLine]] = {}

    # A season accumulates one row per player per snapshot, so the same player is read
    # back several times with progressively fuller lines. Summing them all would blend
    # a stale April line into September's totals, so the latest row wins outright.
    for player_id, team_id, line in _latest_stat_lines(rows):
        if isinstance(line, RawBattingLine):
            batting_lines[player_id] = line
            if team_id is not None:
                team_batting.setdefault(team_id, []).append(line)
        else:
            pitching_lines[player_id] = line
            if team_id is not None:
                team_pitching.setdefault(team_id, []).append(line)

    team_fielding, league_baselines = _fielding_from_rows(fielding_rows or [])

    return StatLineStatsProvider(
        batting_lines=batting_lines,
        pitching_lines=pitching_lines,
        team_batting=team_batting,
        team_pitching=team_pitching,
        team_fielding=team_fielding,
        league_range_baselines=league_baselines,
        fallback=fallback if fallback is not None else SyntheticStatsProvider(),
    )


def _latest_stat_lines(
    rows: list[tuple[Any, ...]],
) -> list[tuple[int, int | None, RawBattingLine | RawPitchingLine]]:
    """Keep the last row per ``(player, stat_group)``, in load order."""

    latest: dict[tuple[int, str], tuple[int, int | None, Any]] = {}
    for row in rows:
        stat_group = str(row[2])
        if stat_group not in ("hitting", "pitching"):
            continue
        player_id = int(row[0])
        team_id = int(row[1]) if row[1] is not None else None
        line = (
            batting_line_from_row(row)
            if stat_group == "hitting"
            else pitching_line_from_row(row)
        )
        latest[(player_id, stat_group)] = (player_id, team_id, line)
    return list(latest.values())


def _fielding_from_rows(
    rows: list[tuple[Any, ...]],
) -> tuple[dict[int, list[RawFieldingLine]], dict[str, float] | None]:
    """Group fielding splits by club and derive the league's per-position baseline."""

    latest: dict[tuple[int, str], tuple[int | None, RawFieldingLine]] = {}
    for row in rows:
        player_id = int(row[0])
        team_id = int(row[1]) if row[1] is not None else None
        line = fielding_line_from_row(row)
        latest[(player_id, line.position)] = (team_id, line)

    team_fielding: dict[int, list[RawFieldingLine]] = {}
    for team_id, line in latest.values():
        if team_id is not None:
            team_fielding.setdefault(team_id, []).append(line)

    if not latest:
        return {}, None
    baselines = league_range_factors(line for _, line in latest.values())
    return team_fielding, baselines or None


def _int(value: Any) -> int:
    return int(value) if value is not None else 0


def _float(value: Any) -> float:
    return float(value) if value is not None else 0.0


def batting_line_from_row(row: tuple[Any, ...]) -> RawBattingLine:
    """Parse a SEASON_STATS_COLUMNS row into a batting line."""

    return RawBattingLine(
        plate_appearances=_int(row[15]),
        at_bats=_int(row[4]),
        singles=_int(row[5]),
        doubles=_int(row[6]),
        triples=_int(row[7]),
        home_runs=_int(row[8]),
        walks=_int(row[9]),
        intentional_walks=_int(row[10]),
        hit_by_pitch=_int(row[11]),
        sacrifice_flies=_int(row[12]),
        strikeouts=_int(row[13]),
        stolen_bases=_int(row[14]),
    )


def pitching_line_from_row(row: tuple[Any, ...]) -> RawPitchingLine:
    """Parse a SEASON_STATS_COLUMNS row into a pitching line."""

    return RawPitchingLine(
        innings_pitched=_float(row[3]),
        strikeouts=_int(row[13]),
        walks=_int(row[9]),
        hit_by_pitch=_int(row[11]),
        home_runs=_int(row[8]),
    )


def fielding_line_from_row(row: tuple[Any, ...]) -> RawFieldingLine:
    """Parse a SEASON_FIELDING_COLUMNS row into a fielding line."""

    return RawFieldingLine(
        position=str(row[2]),
        innings=_float(row[3]),
        put_outs=_int(row[4]),
        assists=_int(row[5]),
        errors=_int(row[6]),
        chances=_int(row[7]),
        double_plays=_int(row[8]),
        games=_int(row[9]),
        games_started=_int(row[10]),
    )
