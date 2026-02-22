from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from baseball_sim.config import Settings, get_settings
from baseball_sim.ingest.mlb_stats_client import create_default_mlb_stats_client
from baseball_sim.seeders.roster import SeededPlayer, SeededTeamRoster, generate_seeded_team_roster

LINEUP_ORDER = ["CF", "SS", "1B", "RF", "DH", "3B", "LF", "2B", "C"]
FIELD_ORDER = ["P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]
OUTFIELD_POSITIONS = {"LF", "CF", "RF"}


@dataclass(frozen=True)
class LoadedTeamRoster:
    roster: SeededTeamRoster
    source: str
    note: str | None = None


@dataclass(frozen=True)
class LoadedWatchRosters:
    home: LoadedTeamRoster
    away: LoadedTeamRoster


class RosterClientProtocol(Protocol):
    async def get_teams(
        self,
        *,
        sport_id: int = 1,
        season: int | None = None,
    ) -> list[dict[str, Any]]: ...

    async def get_team_roster(
        self,
        *,
        team_id: int,
        roster_type: str = "active",
    ) -> list[dict[str, Any]]: ...


async def load_watch_rosters(
    *,
    home_team_id: int,
    away_team_id: int,
    seed: int,
    home_team_name_override: str | None,
    away_team_name_override: str | None,
    use_api_rosters: bool = True,
    settings: Settings | None = None,
) -> LoadedWatchRosters:
    app_settings = settings if settings is not None else get_settings()
    if not use_api_rosters:
        return _seeded_only_watch_rosters(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            seed=seed,
            home_team_name_override=home_team_name_override,
            away_team_name_override=away_team_name_override,
        )

    async with create_default_mlb_stats_client(app_settings) as client:
        return await load_watch_rosters_with_client(
            client=client,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            seed=seed,
            home_team_name_override=home_team_name_override,
            away_team_name_override=away_team_name_override,
            sport_id=app_settings.mlb_stats_sport_id,
            use_api_rosters=True,
        )


async def load_watch_rosters_with_client(
    *,
    client: RosterClientProtocol,
    home_team_id: int,
    away_team_id: int,
    seed: int,
    home_team_name_override: str | None,
    away_team_name_override: str | None,
    sport_id: int = 1,
    use_api_rosters: bool = True,
) -> LoadedWatchRosters:
    if not use_api_rosters:
        return _seeded_only_watch_rosters(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            seed=seed,
            home_team_name_override=home_team_name_override,
            away_team_name_override=away_team_name_override,
        )

    team_name_map = await _safe_team_name_lookup(client=client, sport_id=sport_id)
    home_result, away_result = await asyncio.gather(
        _load_team_roster_with_fallback(
            client=client,
            team_id=home_team_id,
            team_name_override=home_team_name_override,
            team_name_map=team_name_map,
            seed=seed,
        ),
        _load_team_roster_with_fallback(
            client=client,
            team_id=away_team_id,
            team_name_override=away_team_name_override,
            team_name_map=team_name_map,
            seed=seed,
        ),
    )
    return LoadedWatchRosters(home=home_result, away=away_result)


def _seeded_only_watch_rosters(
    *,
    home_team_id: int,
    away_team_id: int,
    seed: int,
    home_team_name_override: str | None,
    away_team_name_override: str | None,
) -> LoadedWatchRosters:
    home_roster = generate_seeded_team_roster(
        team_id=home_team_id,
        seed=seed,
        team_name=home_team_name_override,
    )
    away_roster = generate_seeded_team_roster(
        team_id=away_team_id,
        seed=seed,
        team_name=away_team_name_override,
    )
    return LoadedWatchRosters(
        home=LoadedTeamRoster(roster=home_roster, source="seeded_forced"),
        away=LoadedTeamRoster(roster=away_roster, source="seeded_forced"),
    )


async def _safe_team_name_lookup(
    *,
    client: RosterClientProtocol,
    sport_id: int,
) -> dict[int, str]:
    try:
        teams = await client.get_teams(sport_id=sport_id)
    except Exception:
        return {}

    team_name_map: dict[int, str] = {}
    for team in teams:
        team_id = team.get("id")
        team_name = team.get("name")
        if not isinstance(team_name, str):
            team_name = team.get("teamName")
        if isinstance(team_id, int) and isinstance(team_name, str) and team_name:
            team_name_map[team_id] = team_name
    return team_name_map


async def _load_team_roster_with_fallback(
    *,
    client: RosterClientProtocol,
    team_id: int,
    team_name_override: str | None,
    team_name_map: dict[int, str],
    seed: int,
) -> LoadedTeamRoster:
    team_name = team_name_override or team_name_map.get(team_id)
    seeded_roster = generate_seeded_team_roster(
        team_id=team_id,
        seed=seed,
        team_name=team_name,
    )

    try:
        api_roster_payload = await client.get_team_roster(team_id=team_id)
    except Exception as exc:
        return LoadedTeamRoster(
            roster=seeded_roster,
            source="seeded_fallback_api_error",
            note=f"MLB API roster lookup failed ({type(exc).__name__}).",
        )

    api_players = _extract_api_players(payload=api_roster_payload)
    if not api_players:
        return LoadedTeamRoster(
            roster=seeded_roster,
            source="seeded_fallback_empty_api",
            note="MLB API roster returned no usable players.",
        )

    hybrid_roster, seeded_slots = _build_hybrid_roster(
        team_id=team_id,
        team_name=seeded_roster.team_name,
        api_players=api_players,
        seeded_fallback=seeded_roster,
    )
    if seeded_slots == 0:
        return LoadedTeamRoster(roster=hybrid_roster, source="api")
    return LoadedTeamRoster(
        roster=hybrid_roster,
        source="api_with_seeded_fallback",
        note=f"Used seeded fallback for {seeded_slots} roster slots.",
    )


def _extract_api_players(*, payload: list[dict[str, Any]]) -> list[SeededPlayer]:
    players: list[SeededPlayer] = []
    seen_ids: set[int] = set()

    for entry in payload:
        person = entry.get("person")
        if not isinstance(person, dict):
            continue
        player_id = person.get("id")
        full_name = person.get("fullName")
        if not isinstance(player_id, int) or not isinstance(full_name, str) or full_name == "":
            continue
        if player_id in seen_ids:
            continue
        position = _normalize_position(entry=entry)
        players.append(
            SeededPlayer(
                player_id=player_id,
                full_name=full_name,
                position=position,
                bats="?",
                throws="?",
            )
        )
        seen_ids.add(player_id)

    return sorted(players, key=lambda player: player.player_id)


def _normalize_position(*, entry: dict[str, Any]) -> str:
    position_payload = entry.get("position")
    if not isinstance(position_payload, dict):
        return "BENCH"
    abbreviation = position_payload.get("abbreviation")
    if not isinstance(abbreviation, str) or abbreviation == "":
        return "BENCH"

    value = abbreviation.strip().upper()
    if value in {"P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"}:
        return value

    mapped_positions = {
        "SP": "P",
        "RP": "P",
        "CP": "P",
        "RHP": "P",
        "LHP": "P",
        "TWP": "P",
        "OF": "CF",
        "IF": "2B",
        "UT": "DH",
        "UTIL": "DH",
        "PH": "DH",
        "PR": "DH",
    }
    return mapped_positions.get(value, "BENCH")


def _build_hybrid_roster(
    *,
    team_id: int,
    team_name: str,
    api_players: list[SeededPlayer],
    seeded_fallback: SeededTeamRoster,
) -> tuple[SeededTeamRoster, int]:
    seeded_slots = 0
    fielders: dict[str, SeededPlayer] = {}
    lineup: list[SeededPlayer] = []

    used_fielders: set[int] = set()
    for field_position in FIELD_ORDER:
        candidate = _pick_api_player(
            players=api_players,
            desired_slot=field_position,
            used_player_ids=used_fielders,
        )
        if candidate is None:
            seeded_slots += 1
            candidate = seeded_fallback.fielders[field_position]
        fielders[field_position] = candidate
        used_fielders.add(candidate.player_id)

    used_lineup: set[int] = set()
    for lineup_slot in LINEUP_ORDER:
        candidate = _pick_api_player(
            players=api_players,
            desired_slot=lineup_slot,
            used_player_ids=used_lineup,
        )
        if candidate is None:
            seeded_slots += 1
            candidate = _pick_seeded_lineup_fallback(
                seeded_fallback=seeded_fallback,
                desired_slot=lineup_slot,
                used_player_ids=used_lineup,
            )
        lineup.append(candidate)
        used_lineup.add(candidate.player_id)

    return (
        SeededTeamRoster(
            team_id=team_id,
            team_name=team_name,
            lineup=lineup,
            fielders=fielders,
        ),
        seeded_slots,
    )


def _pick_api_player(
    *,
    players: list[SeededPlayer],
    desired_slot: str,
    used_player_ids: set[int],
) -> SeededPlayer | None:
    if desired_slot == "DH":
        exact_dh = _pick_api_player_by_predicate(
            players=players,
            used_player_ids=used_player_ids,
            predicate=lambda player: player.position == "DH",
        )
        if exact_dh is not None:
            return exact_dh
        return _pick_api_player_by_predicate(
            players=players,
            used_player_ids=used_player_ids,
            predicate=lambda player: player.position != "P",
        )

    return _pick_api_player_by_predicate(
        players=players,
        used_player_ids=used_player_ids,
        predicate=lambda player: _position_matches(
            player_position=player.position,
            desired_slot=desired_slot,
        ),
    )


def _pick_api_player_by_predicate(
    *,
    players: list[SeededPlayer],
    used_player_ids: set[int],
    predicate: Callable[[SeededPlayer], bool],
) -> SeededPlayer | None:
    for player in players:
        if player.player_id in used_player_ids:
            continue
        if predicate(player):
            return player
    return None


def _pick_seeded_lineup_fallback(
    *,
    seeded_fallback: SeededTeamRoster,
    desired_slot: str,
    used_player_ids: set[int],
) -> SeededPlayer:
    candidates = [
        player
        for player in seeded_fallback.lineup
        if _position_matches(player_position=player.position, desired_slot=desired_slot)
    ]
    candidates.extend(seeded_fallback.lineup)
    for candidate in candidates:
        if candidate.player_id not in used_player_ids:
            return candidate
    return seeded_fallback.lineup[0]


def _position_matches(*, player_position: str, desired_slot: str) -> bool:
    if desired_slot == "DH":
        return player_position != "P"
    if desired_slot in OUTFIELD_POSITIONS:
        return player_position in OUTFIELD_POSITIONS
    return player_position == desired_slot
