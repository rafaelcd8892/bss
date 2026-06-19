"""Batting-order identities used to attribute each plate appearance to a batter.

Attribution is pure labeling: it does not touch the RNG or the simulated outcomes,
so seeded games stay byte-for-byte reproducible. A lineup is an ordered list of
:class:`Batter`; the order rotates 1-9 and persists across innings.
"""

from __future__ import annotations

from dataclasses import dataclass

from baseball_sim.seeders.roster import generate_seeded_team_roster


@dataclass(frozen=True)
class Batter:
    player_id: int
    name: str


def synthetic_lineup(*, seed: int, team_id: int) -> list[Batter]:
    roster = generate_seeded_team_roster(team_id=team_id, seed=seed)
    return [Batter(player_id=player.player_id, name=player.full_name) for player in roster.lineup]
