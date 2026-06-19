"""Normalize MLB Stats API season stat payloads into canonical records.

Turns the ``/people/{id}/stats?stats=season&group=hitting|pitching`` response shape
into :class:`PlayerSeasonStatRecord` rows that carry both the raw counting line and
the computed sabermetrics, ready to upsert into ``player_season_stats``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from baseball_sim.sim.sabermetrics import (
    RawBattingLine,
    RawPitchingLine,
    compute_fip,
    compute_k_bb_ratio,
    compute_woba,
    compute_wrc_plus,
)

StatGroup = Literal["hitting", "pitching"]


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
    )


def parse_pitching_line(stat: dict[str, Any]) -> RawPitchingLine:
    return RawPitchingLine(
        innings_pitched=innings_to_float(stat.get("inningsPitched")),
        strikeouts=_as_int(stat.get("strikeOuts")),
        walks=_as_int(stat.get("baseOnBalls")),
        hit_by_pitch=_as_int(stat.get("hitByPitch")),
        home_runs=_as_int(stat.get("homeRuns")),
    )


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
        woba=round(woba, 4) if woba is not None else None,
        xwoba=None,  # Statcast expected stats are not ingested yet.
        wrc_plus=round(wrc_plus, 1) if wrc_plus is not None else None,
        fip=None,
        k_bb_ratio=None,
    )


def _pitching_record(
    *, player_id: int, season: int, team_id: int | None, line: RawPitchingLine
) -> PlayerSeasonStatRecord:
    fip = compute_fip(line) if line.innings_pitched > 0 else None
    k_bb = compute_k_bb_ratio(line.strikeouts, line.walks) if line.innings_pitched > 0 else None
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
        fip=round(fip, 3) if fip is not None else None,
        k_bb_ratio=round(k_bb, 3) if k_bb is not None else None,
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
