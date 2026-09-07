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
#:
#: The widened components trail the original set so existing positional reads keep
#: working. They are not optional decoration: without them a reconstructed line reports
#: no earned runs and no hits allowed, so ERA, WHIP and the per-batter rates silently
#: collapse to zero or vanish.
SEASON_STATS_COLUMNS = """player_id, team_id, stat_group,
           ip, at_bats, singles, doubles, triples, home_runs,
           walks, intentional_walks, hit_by_pitch, sacrifice_flies,
           strikeouts, stolen_bases, pa, xwoba,
           runs, runs_batted_in, caught_stealing, sacrifice_bunts,
           ground_into_double_play, ground_outs, air_outs, games_played,
           batters_faced, earned_runs, hits_allowed, games_started"""

_SELECT_SEASON_STATS = """
    SELECT player_id, team_id, stat_group,
           ip, at_bats, singles, doubles, triples, home_runs,
           walks, intentional_walks, hit_by_pitch, sacrifice_flies,
           strikeouts, stolen_bases, pa, xwoba,
           runs, runs_batted_in, caught_stealing, sacrifice_bunts,
           ground_into_double_play, ground_outs, air_outs, games_played,
           batters_faced, earned_runs, hits_allowed, games_started
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
    expected_woba: dict[int, float] = {}

    # Two different questions read the same rows. A club's profile wants each player's
    # line *with that club*, so it takes the rows that carry a team. A player's rating
    # wants his year, so it takes the season total — the row whose team is null — and
    # falls back to his only club line when he was never traded (migration 0009).
    for player_id, team_id, xwoba, line in _latest_stat_lines(rows):
        is_total = team_id is None
        if isinstance(line, RawBattingLine):
            if is_total or player_id not in batting_lines:
                batting_lines[player_id] = line
                # The pitching row carries xwOBA *against*, where a low number is
                # elite — feeding it into a metric the compare table ranks
                # higher-is-better would say an ace hits worse than a replacement bat.
                if xwoba is not None:
                    expected_woba[player_id] = xwoba
            if team_id is not None:
                team_batting.setdefault(team_id, []).append(line)
        else:
            if is_total or player_id not in pitching_lines:
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
        expected_woba=expected_woba,
        fallback=fallback if fallback is not None else SyntheticStatsProvider(),
    )


def _latest_stat_lines(
    rows: list[tuple[Any, ...]],
) -> list[tuple[int, int | None, float | None, RawBattingLine | RawPitchingLine]]:
    """Keep the last row per ``(player, stat_group, team)``, in load order.

    The team is part of the key because a traded player has a line with each club and
    a season total; collapsing them would silently discard all but one.
    """

    latest: dict[tuple[int, str, int | None], tuple[int, int | None, float | None, Any]] = {}
    for row in rows:
        stat_group = str(row[2])
        if stat_group not in ("hitting", "pitching"):
            continue
        player_id = int(row[0])
        team_id = int(row[1]) if row[1] is not None else None
        xwoba = float(row[16]) if len(row) > 16 and row[16] is not None else None
        line = (
            batting_line_from_row(row)
            if stat_group == "hitting"
            else pitching_line_from_row(row)
        )
        latest[(player_id, stat_group, team_id)] = (player_id, team_id, xwoba, line)
    return list(latest.values())


def _fielding_from_rows(
    rows: list[tuple[Any, ...]],
) -> tuple[dict[int, list[RawFieldingLine]], dict[str, float] | None]:
    """Group fielding splits by club and derive the league's per-position baseline."""

    latest: dict[tuple[int, str, int | None], tuple[int | None, RawFieldingLine]] = {}
    for row in rows:
        player_id = int(row[0])
        team_id = int(row[1]) if row[1] is not None else None
        line = fielding_line_from_row(row)
        latest[(player_id, line.position, team_id)] = (team_id, line)

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


def _wide(row: tuple[Any, ...], index: int) -> int:
    """A widened column, tolerant of a row selected before they were added."""

    return _int(row[index]) if len(row) > index else 0


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
        runs=_wide(row, 17),
        runs_batted_in=_wide(row, 18),
        caught_stealing=_wide(row, 19),
        sacrifice_bunts=_wide(row, 20),
        ground_into_double_play=_wide(row, 21),
        ground_outs=_wide(row, 22),
        air_outs=_wide(row, 23),
        games_played=_wide(row, 24),
    )


def pitching_line_from_row(row: tuple[Any, ...]) -> RawPitchingLine:
    """Parse a SEASON_STATS_COLUMNS row into a pitching line."""

    return RawPitchingLine(
        innings_pitched=_float(row[3]),
        strikeouts=_int(row[13]),
        walks=_int(row[9]),
        hit_by_pitch=_int(row[11]),
        home_runs=_int(row[8]),
        batters_faced=_wide(row, 25),
        earned_runs=_wide(row, 26),
        hits_allowed=_wide(row, 27),
        ground_outs=_wide(row, 22),
        air_outs=_wide(row, 23),
        games_played=_wide(row, 24),
        games_started=_wide(row, 28),
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
