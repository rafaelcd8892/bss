"""Lineup providers: resolve a team's batting order for play attribution.

Mirrors the stats-provider seam. The catalog-backed provider builds a lineup from the
persisted roster (real player names), falling back per team to the deterministic
synthetic lineup when there is not enough data — so attribution always works.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
    woba: Mapping[int, float] | None = None,
    size: int = _LINEUP_SIZE,
) -> list[Batter]:
    """Build a batting order from real roster players, excluding pitchers.

    Batters are ordered best-first by season wOBA. That is a deliberately simple,
    explainable heuristic — not a real manager's card, which also weighs speed,
    handedness splits and defense — but it is far closer to reality than the
    alphabetical order that falls out of the roster query.

    Players with no ingested wOBA sort last, and ties break on name, so the order is
    fully determined by the data and the lineup stays reproducible.

    Falls back to the synthetic lineup when there are not enough position players.
    """

    position_players = [player for player in roster if player.primary_position != "P"]
    if len(position_players) < size:
        return fallback.lineup(team_id=team_id, seed=seed)

    scores = woba or {}

    def rank(player: PlayerSummary) -> tuple[int, float, str]:
        rating = scores.get(player.player_id)
        # (has-stats first, wOBA descending, name for a stable tie-break)
        return (0 if rating is not None else 1, -(rating or 0.0), player.full_name)

    ordered = sorted(position_players, key=rank)
    return [Batter(player_id=player.player_id, name=player.full_name) for player in ordered[:size]]


class CatalogLineupProvider:
    """Real batting order from the persisted roster, ordered by season wOBA."""

    def __init__(
        self,
        *,
        dsn: str,
        season: int,
        fallback: LineupProvider | None = None,
        size: int = _LINEUP_SIZE,
    ) -> None:
        self._dsn = dsn
        self._season = season
        self._fallback: LineupProvider = (
            fallback if fallback is not None else SyntheticLineupProvider()
        )
        self._size = size

    def lineup(self, *, team_id: int, seed: int) -> list[Batter]:
        from baseball_sim.domain.catalog import PostgresCatalogRepository

        repository = PostgresCatalogRepository(dsn=self._dsn)
        try:
            roster = repository.get_team_roster(team_id=team_id)
            woba = repository.get_batting_woba(
                player_ids=[player.player_id for player in roster], season=self._season
            )
        finally:
            repository.close()

        return lineup_from_roster(
            roster,
            team_id=team_id,
            seed=seed,
            fallback=self._fallback,
            woba=woba,
            size=self._size,
        )
