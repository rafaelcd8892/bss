"""Lineup providers: resolve a team's batting order for play attribution.

Mirrors the stats-provider seam. The catalog-backed provider builds a lineup from the
persisted roster (real player names), falling back per team to the deterministic
synthetic lineup when there is not enough data — so attribution always works.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

from baseball_sim.sim.lineups import Batter, synthetic_lineup

if TYPE_CHECKING:
    from baseball_sim.domain.contracts import PlayerSummary

_LINEUP_SIZE = 9


class LineupProvider(Protocol):
    def lineup(self, *, team_id: int, seed: int) -> list[Batter]: ...


class SyntheticLineupProvider:
    def lineup(self, *, team_id: int, seed: int) -> list[Batter]:
        return synthetic_lineup(seed=seed, team_id=team_id)


def lineup_from_roster(
    roster: Sequence[PlayerSummary],
    *,
    team_id: int,
    seed: int,
    fallback: LineupProvider,
    size: int = _LINEUP_SIZE,
) -> list[Batter]:
    """Build a batting order from real roster players, excluding pitchers.

    Falls back to the synthetic lineup when there are not enough position players.
    """

    batters = [
        Batter(player_id=player.player_id, name=player.full_name)
        for player in roster
        if player.primary_position != "P"
    ]
    if len(batters) < size:
        return fallback.lineup(team_id=team_id, seed=seed)
    return batters[:size]


class CatalogLineupProvider:
    """Real batting order from the persisted roster, synthetic fallback per team."""

    def __init__(
        self,
        *,
        dsn: str,
        fallback: LineupProvider | None = None,
        size: int = _LINEUP_SIZE,
    ) -> None:
        self._dsn = dsn
        self._fallback: LineupProvider = (
            fallback if fallback is not None else SyntheticLineupProvider()
        )
        self._size = size

    def lineup(self, *, team_id: int, seed: int) -> list[Batter]:
        from baseball_sim.domain.catalog import PostgresCatalogRepository

        repository = PostgresCatalogRepository(dsn=self._dsn)
        try:
            roster = repository.get_team_roster(team_id=team_id)
        finally:
            repository.close()

        return lineup_from_roster(
            roster,
            team_id=team_id,
            seed=seed,
            fallback=self._fallback,
            size=self._size,
        )
