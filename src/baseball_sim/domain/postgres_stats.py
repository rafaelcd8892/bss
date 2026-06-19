"""Build a real-data stats provider from the ``player_season_stats`` table.

Reads the raw counting components persisted by ingestion, reconstructs the exact
``RawBattingLine`` / ``RawPitchingLine`` inputs, and wraps them in a
:class:`StatLineStatsProvider` so the serving path reuses the same analytical code
as everything else. Falls back to the synthetic provider for any player/team without
ingested data.
"""

from __future__ import annotations

from typing import Any

from baseball_sim.domain.stats_provider import (
    StatLineStatsProvider,
    StatsProvider,
    SyntheticStatsProvider,
)
from baseball_sim.sim.sabermetrics import RawBattingLine, RawPitchingLine

_SELECT_SEASON_STATS = """
    SELECT player_id, team_id, stat_group,
           ip, at_bats, singles, doubles, triples, home_runs,
           walks, intentional_walks, hit_by_pitch, sacrifice_flies,
           strikeouts, stolen_bases, pa
    FROM player_season_stats
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

    return build_stat_line_provider_from_rows(rows=rows, fallback=fallback)


def build_stat_line_provider_from_rows(
    *,
    rows: list[tuple[Any, ...]],
    fallback: StatsProvider | None = None,
) -> StatLineStatsProvider:
    batting_lines: dict[int, RawBattingLine] = {}
    pitching_lines: dict[int, RawPitchingLine] = {}
    team_batting: dict[int, list[RawBattingLine]] = {}
    team_pitching: dict[int, list[RawPitchingLine]] = {}

    for row in rows:
        player_id = int(row[0])
        team_id = int(row[1]) if row[1] is not None else None
        stat_group = str(row[2])

        if stat_group == "hitting":
            line = _batting_line_from_row(row)
            batting_lines[player_id] = line
            if team_id is not None:
                team_batting.setdefault(team_id, []).append(line)
        elif stat_group == "pitching":
            pitching = _pitching_line_from_row(row)
            pitching_lines[player_id] = pitching
            if team_id is not None:
                team_pitching.setdefault(team_id, []).append(pitching)

    return StatLineStatsProvider(
        batting_lines=batting_lines,
        pitching_lines=pitching_lines,
        team_batting=team_batting,
        team_pitching=team_pitching,
        fallback=fallback if fallback is not None else SyntheticStatsProvider(),
    )


def _int(value: Any) -> int:
    return int(value) if value is not None else 0


def _batting_line_from_row(row: tuple[Any, ...]) -> RawBattingLine:
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


def _pitching_line_from_row(row: tuple[Any, ...]) -> RawPitchingLine:
    return RawPitchingLine(
        innings_pitched=float(row[3]) if row[3] is not None else 0.0,
        strikeouts=_int(row[13]),
        walks=_int(row[9]),
        hit_by_pitch=_int(row[11]),
        home_runs=_int(row[8]),
    )
