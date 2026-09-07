"""League-wide season stats, for backfilling players no longer on a roster.

The career backfill follows the players a club currently rosters, so a past season is
only as complete as today's rosters — a 2019 leaderboard built from it is the best 2019
among players still active, not the best of 2019. Anyone since retired is missing.

The fix is a different endpoint. `/stats?stats=season&playerPool=all` returns every
player who appeared in a season, with the same stat objects the per-player endpoint
serves: one request covers 1,287 hitters rather than 1,287 requests covering one each.
That matters beyond speed — ADR-025 permits non-bulk use, and two calls a season is
categorically not the thing that phrase is about.

One caveat this shape carries: a player who changed clubs appears **once**, with his
season total tagged to his last club. Storing that team would credit a club with a
season the player only half played there, so a multi-club row is stored with no team —
which is exactly what a null team already means (ADR-030): the season total.
"""

from __future__ import annotations

from typing import Any

from baseball_sim.ingest.normalize import PlayerRecord
from baseball_sim.ingest.stats import (
    PlayerSeasonStatRecord,
    _batting_record,
    _pitching_record,
    parse_batting_line,
    parse_pitching_line,
)


def _split_player(split: dict[str, Any]) -> tuple[int, str] | None:
    player = split.get("player")
    if not isinstance(player, dict):
        return None
    player_id = player.get("id")
    full_name = player.get("fullName")
    if not isinstance(player_id, int) or not isinstance(full_name, str):
        return None
    return player_id, full_name


def _split_position(split: dict[str, Any]) -> str | None:
    position = split.get("position")
    if not isinstance(position, dict):
        return None
    abbreviation = position.get("abbreviation")
    return abbreviation if isinstance(abbreviation, str) else None


def _split_team_id(split: dict[str, Any]) -> int | None:
    """The club, unless the player had more than one.

    A multi-club row is the season total: the payload tags it with whichever club he
    finished at, and storing that would credit them with a season he only partly spent
    there. Null says "across clubs", which is what the rest of the system reads it as.
    """

    if (split.get("numTeams") or 1) > 1:
        return None
    team = split.get("team")
    if not isinstance(team, dict):
        return None
    team_id = team.get("id")
    return team_id if isinstance(team_id, int) else None


def normalize_league_stats(
    *, season: int, payload: dict[str, Any]
) -> tuple[list[PlayerRecord], list[PlayerSeasonStatRecord]]:
    """Parse a league-wide stats payload into players and their season lines.

    Players come back too because a retired player has no row anywhere else, and the
    stat row's foreign key needs one.
    """

    stats = payload.get("stats")
    if not isinstance(stats, list):
        return [], []

    players: dict[int, PlayerRecord] = {}
    records: list[PlayerSeasonStatRecord] = []

    for group_block in stats:
        if not isinstance(group_block, dict):
            continue
        group = group_block.get("group")
        group_name = group.get("displayName") if isinstance(group, dict) else None
        if group_name not in ("hitting", "pitching"):
            continue
        splits = group_block.get("splits")
        if not isinstance(splits, list):
            continue

        for split in splits:
            if not isinstance(split, dict):
                continue
            identity = _split_player(split)
            stat = split.get("stat")
            if identity is None or not isinstance(stat, dict):
                continue
            player_id, full_name = identity

            players.setdefault(
                player_id,
                PlayerRecord(
                    player_id=player_id,
                    full_name=full_name,
                    primary_position=_split_position(split),
                    # The bulk payload carries no handedness or biography; leaving these
                    # null is honest, and a later roster ingest fills them in.
                    bats=None,
                    throws=None,
                    birth_date=None,
                    mlb_debut_date=None,
                ),
            )

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
            else:
                records.append(
                    _pitching_record(
                        player_id=player_id,
                        season=season,
                        team_id=team_id,
                        line=parse_pitching_line(stat),
                    )
                )

    return list(players.values()), records
