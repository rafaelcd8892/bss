from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeededPlayer:
    player_id: int
    full_name: str
    position: str
    bats: str
    throws: str


@dataclass(frozen=True)
class SeededTeamRoster:
    team_id: int
    team_name: str
    lineup: list[SeededPlayer]
    fielders: dict[str, SeededPlayer]


_FIRST_NAMES = [
    "Alex",
    "Jordan",
    "Casey",
    "Riley",
    "Mateo",
    "Diego",
    "Noah",
    "Liam",
    "Ethan",
    "Lucas",
    "Avery",
    "Julian",
]

_LAST_NAMES = [
    "Rivera",
    "Torres",
    "Walker",
    "Santiago",
    "Hernandez",
    "Miller",
    "Kim",
    "Soto",
    "Garcia",
    "Lopez",
    "Foster",
    "Reed",
]

_LINEUP_ORDER = ["CF", "SS", "1B", "RF", "DH", "3B", "LF", "2B", "C"]
_FIELD_ORDER = ["P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]


def generate_seeded_team_roster(
    *,
    team_id: int,
    seed: int,
    team_name: str | None = None,
) -> SeededTeamRoster:
    players: list[SeededPlayer] = []
    for index in range(1, 13):
        position = _position_for_index(index)
        players.append(
            SeededPlayer(
                player_id=(team_id * 10_000) + index,
                full_name=_seeded_name(seed=seed, team_id=team_id, index=index),
                position=position,
                bats=_seeded_hand(seed=seed, team_id=team_id, index=index, salt=13),
                throws=_seeded_hand(seed=seed, team_id=team_id, index=index, salt=31),
            )
        )

    lineup = [_pick_for_position(players=players, position=pos) for pos in _LINEUP_ORDER]
    fielders = {pos: _pick_for_position(players=players, position=pos) for pos in _FIELD_ORDER}

    return SeededTeamRoster(
        team_id=team_id,
        team_name=team_name or f"Team {team_id}",
        lineup=lineup,
        fielders=fielders,
    )


def _seeded_name(*, seed: int, team_id: int, index: int) -> str:
    first = _FIRST_NAMES[
        _mix(seed=seed, team_id=team_id, index=index, salt=101) % len(_FIRST_NAMES)
    ]
    last = _LAST_NAMES[_mix(seed=seed, team_id=team_id, index=index, salt=211) % len(_LAST_NAMES)]
    return f"{first} {last}"


def _seeded_hand(*, seed: int, team_id: int, index: int, salt: int) -> str:
    roll = _mix(seed=seed, team_id=team_id, index=index, salt=salt) % 100
    return "L" if roll < 28 else "R"


def _position_for_index(index: int) -> str:
    if index <= len(_FIELD_ORDER):
        return _FIELD_ORDER[index - 1]
    return "BENCH"


def _pick_for_position(*, players: list[SeededPlayer], position: str) -> SeededPlayer:
    for player in players:
        if player.position == position:
            return player
    return players[0]


def _mix(*, seed: int, team_id: int, index: int, salt: int) -> int:
    mixed = (seed ^ (team_id * 2654435761) ^ (index * 2246822519) ^ salt) & 0xFFFFFFFF
    return (mixed * 1664525 + 1013904223) & 0xFFFFFFFF
