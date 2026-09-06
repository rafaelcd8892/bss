"""Normalize MLB Stats API season stat payloads into canonical records.

Turns the ``/people/{id}/stats?stats=season&group=hitting|pitching`` response shape
into :class:`PlayerSeasonStatRecord` rows that carry both the raw counting line and
the computed sabermetrics, ready to upsert into ``player_season_stats``.

The parser reads every field the payload already contains that any supported metric
needs. Nothing here costs an extra request: the API returns 34 hitting and 62 pitching
fields per player whether or not we read them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from baseball_sim.sim.sabermetrics import (
    RawBattingLine,
    RawFieldingLine,
    RawPitchingLine,
    compute_babip,
    compute_batting_average,
    compute_era,
    compute_fielding_percentage,
    compute_fip,
    compute_ground_ball_rate,
    compute_iso,
    compute_k_bb_ratio,
    compute_obp,
    compute_ops,
    compute_range_factor_per_nine,
    compute_slg,
    compute_strikeout_rate,
    compute_walk_rate,
    compute_whip,
    compute_woba,
    compute_wrc_plus,
)

StatGroup = Literal["hitting", "pitching"]


@dataclass(frozen=True)
class PlayerSeasonFieldingRecord:
    player_id: int
    season: int
    team_id: int | None
    line: RawFieldingLine
    fielding_percentage: float | None = None
    range_factor_per_nine: float | None = None


@dataclass(frozen=True)
class PlayerSeasonStatRecord:
    player_id: int
    season: int
    team_id: int | None
    stat_group: StatGroup
    batting: RawBattingLine | None
    pitching: RawPitchingLine | None
    pa: int | None
    ip: float | None
    woba: float | None
    xwoba: float | None
    wrc_plus: float | None
    fip: float | None
    k_bb_ratio: float | None
    # Widened metrics. All optional: a metric whose inputs were not ingested stays
    # absent rather than being reported as zero.
    batting_average: float | None = None
    obp: float | None = None
    slg: float | None = None
    ops: float | None = None
    iso: float | None = None
    babip: float | None = None
    era: float | None = None
    whip: float | None = None
    strikeout_rate: float | None = None
    walk_rate: float | None = None
    ground_ball_rate: float | None = None


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0


def innings_to_float(value: Any) -> float:
    """Convert MLB innings-pitched notation (``"123.1"`` == 123 + 1/3) to a float."""

    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or value == "":
        return 0.0
    if "." not in value:
        try:
            return float(value)
        except ValueError:
            return 0.0
    whole_str, _, frac_str = value.partition(".")
    try:
        whole = int(whole_str)
    except ValueError:
        return 0.0
    thirds = {"0": 0.0, "1": 1.0 / 3.0, "2": 2.0 / 3.0}.get(frac_str[:1], 0.0)
    return whole + thirds


def _round(value: float | None, places: int) -> float | None:
    return None if value is None else round(value, places)


def parse_batting_line(stat: dict[str, Any]) -> RawBattingLine:
    hits = _as_int(stat.get("hits"))
    doubles = _as_int(stat.get("doubles"))
    triples = _as_int(stat.get("triples"))
    home_runs = _as_int(stat.get("homeRuns"))
    singles = max(hits - doubles - triples - home_runs, 0)
    return RawBattingLine(
        plate_appearances=_as_int(stat.get("plateAppearances")),
        at_bats=_as_int(stat.get("atBats")),
        singles=singles,
        doubles=doubles,
        triples=triples,
        home_runs=home_runs,
        walks=_as_int(stat.get("baseOnBalls")),
        intentional_walks=_as_int(stat.get("intentionalWalks")),
        hit_by_pitch=_as_int(stat.get("hitByPitch")),
        sacrifice_flies=_as_int(stat.get("sacFlies")),
        strikeouts=_as_int(stat.get("strikeOuts")),
        stolen_bases=_as_int(stat.get("stolenBases")),
        runs=_as_int(stat.get("runs")),
        runs_batted_in=_as_int(stat.get("rbi")),
        caught_stealing=_as_int(stat.get("caughtStealing")),
        sacrifice_bunts=_as_int(stat.get("sacBunts")),
        ground_into_double_play=_as_int(stat.get("groundIntoDoublePlay")),
        ground_outs=_as_int(stat.get("groundOuts")),
        air_outs=_as_int(stat.get("airOuts")),
        games_played=_as_int(stat.get("gamesPlayed")),
    )


def parse_pitching_line(stat: dict[str, Any]) -> RawPitchingLine:
    return RawPitchingLine(
        innings_pitched=innings_to_float(stat.get("inningsPitched")),
        strikeouts=_as_int(stat.get("strikeOuts")),
        walks=_as_int(stat.get("baseOnBalls")),
        hit_by_pitch=_as_int(stat.get("hitBatsmen") or stat.get("hitByPitch")),
        home_runs=_as_int(stat.get("homeRuns")),
        batters_faced=_as_int(stat.get("battersFaced")),
        earned_runs=_as_int(stat.get("earnedRuns")),
        hits_allowed=_as_int(stat.get("hits")),
        ground_outs=_as_int(stat.get("groundOuts")),
        air_outs=_as_int(stat.get("airOuts")),
        games_played=_as_int(stat.get("gamesPlayed")),
        games_started=_as_int(stat.get("gamesStarted")),
    )


def parse_fielding_line(stat: dict[str, Any]) -> RawFieldingLine | None:
    """One position's fielding split, or None when it is not a fielding entry.

    A designated hitter appears here with zero innings and a literal "-.--" range
    factor, which is why the rates are recomputed from the counts rather than parsed
    out of the payload.
    """

    position = stat.get("position")
    abbreviation = position.get("abbreviation") if isinstance(position, dict) else None
    innings = innings_to_float(stat.get("innings"))
    if not isinstance(abbreviation, str) or not abbreviation or innings <= 0:
        return None
    return RawFieldingLine(
        position=abbreviation,
        innings=innings,
        put_outs=_as_int(stat.get("putOuts")),
        assists=_as_int(stat.get("assists")),
        errors=_as_int(stat.get("errors")),
        chances=_as_int(stat.get("chances")),
        double_plays=_as_int(stat.get("doublePlays")),
        games=_as_int(stat.get("games")),
        games_started=_as_int(stat.get("gamesStarted")),
    )


def normalize_player_fielding(
    *, player_id: int, season: int, payload: dict[str, Any]
) -> list[PlayerSeasonFieldingRecord]:
    """Every position a player actually fielded, one record each."""

    stats = payload.get("stats")
    if not isinstance(stats, list):
        return []

    records: list[PlayerSeasonFieldingRecord] = []
    for group_block in stats:
        if not isinstance(group_block, dict):
            continue
        group = group_block.get("group")
        if not isinstance(group, dict) or group.get("displayName") != "fielding":
            continue
        splits = group_block.get("splits")
        if not isinstance(splits, list):
            continue
        for split in splits:
            if not isinstance(split, dict):
                continue
            stat = split.get("stat")
            if not isinstance(stat, dict):
                continue
            line = parse_fielding_line(stat)
            if line is None:
                continue
            records.append(
                PlayerSeasonFieldingRecord(
                    player_id=player_id,
                    season=season,
                    team_id=_split_team_id(split),
                    line=line,
                    fielding_percentage=_round(compute_fielding_percentage(line), 4),
                    range_factor_per_nine=_round(compute_range_factor_per_nine(line), 3),
                )
            )
    return records


def _batting_record(
    *, player_id: int, season: int, team_id: int | None, line: RawBattingLine
) -> PlayerSeasonStatRecord:
    woba = compute_woba(line) if line.woba_denominator > 0 else None
    wrc_plus = compute_wrc_plus(woba) if woba is not None else None
    return PlayerSeasonStatRecord(
        player_id=player_id,
        season=season,
        team_id=team_id,
        stat_group="hitting",
        batting=line,
        pitching=None,
        pa=line.plate_appearances,
        ip=None,
        woba=_round(woba, 4),
        xwoba=None,  # Statcast expected stats are not ingested yet.
        wrc_plus=_round(wrc_plus, 1),
        fip=None,
        k_bb_ratio=None,
        batting_average=_round(compute_batting_average(line), 4),
        obp=_round(compute_obp(line), 4),
        slg=_round(compute_slg(line), 4),
        ops=_round(compute_ops(line), 4),
        iso=_round(compute_iso(line), 4),
        babip=_round(compute_babip(line), 4),
    )


def _pitching_record(
    *, player_id: int, season: int, team_id: int | None, line: RawPitchingLine
) -> PlayerSeasonStatRecord:
    pitched = line.innings_pitched > 0
    fip = compute_fip(line) if pitched else None
    k_bb = compute_k_bb_ratio(line.strikeouts, line.walks) if pitched else None
    return PlayerSeasonStatRecord(
        player_id=player_id,
        season=season,
        team_id=team_id,
        stat_group="pitching",
        batting=None,
        pitching=line,
        pa=None,
        ip=round(line.innings_pitched, 2),
        woba=None,
        xwoba=None,
        wrc_plus=None,
        fip=_round(fip, 3),
        k_bb_ratio=_round(k_bb, 3),
        era=_round(compute_era(line), 3),
        whip=_round(compute_whip(line), 3),
        strikeout_rate=_round(compute_strikeout_rate(line), 4),
        walk_rate=_round(compute_walk_rate(line), 4),
        ground_ball_rate=_round(compute_ground_ball_rate(line), 4),
    )


def normalize_player_stats(
    *,
    player_id: int,
    season: int,
    payload: dict[str, Any],
) -> list[PlayerSeasonStatRecord]:
    """Parse a player's season-stats payload into hitting/pitching records.

    Accepts the MLB ``{"stats": [{"group": ..., "splits": [...]}]}`` envelope and
    returns one record per stat group that has a usable season split.
    """

    stats = payload.get("stats")
    if not isinstance(stats, list):
        return []

    records: list[PlayerSeasonStatRecord] = []
    for group_block in stats:
        if not isinstance(group_block, dict):
            continue
        group = group_block.get("group")
        group_name = group.get("displayName") if isinstance(group, dict) else None
        split = _first_split(group_block.get("splits"))
        if split is None:
            continue
        stat = split.get("stat")
        if not isinstance(stat, dict):
            continue
        team_id = _split_team_id(split)

        if group_name == "hitting":
            records.append(
                _batting_record(
                    player_id=player_id,
                    season=season,
                    team_id=team_id,
                    line=parse_batting_line(stat),
                )
            )
        elif group_name == "pitching":
            records.append(
                _pitching_record(
                    player_id=player_id,
                    season=season,
                    team_id=team_id,
                    line=parse_pitching_line(stat),
                )
            )
    return records


def _first_split(splits: Any) -> dict[str, Any] | None:
    if not isinstance(splits, list):
        return None
    for split in splits:
        if isinstance(split, dict):
            return split
    return None


def _split_team_id(split: dict[str, Any]) -> int | None:
    team = split.get("team")
    if not isinstance(team, dict):
        return None
    team_id = team.get("id")
    return team_id if isinstance(team_id, int) else None
