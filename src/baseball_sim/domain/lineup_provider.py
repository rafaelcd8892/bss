"""Lineup providers: resolve a team's batting order and staff for play attribution.

Mirrors the stats-provider seam. The catalog-backed provider builds both from the
persisted roster (real player names), falling back per team to the deterministic
synthetic ones when there is not enough data — so attribution always works.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from baseball_sim.sim.lineups import Batter, synthetic_lineup
from baseball_sim.sim.pitching import (
    ROTATION_SIZE,
    Pitcher,
    PitchingStaff,
    appearance_outs,
    synthetic_staff,
)

if TYPE_CHECKING:
    from baseball_sim.domain.contracts import PitcherWorkload, PlayerSummary

_LINEUP_SIZE = 9
#: A club needs at least this many arms before its real staff is used at all.
_MIN_STAFF_SIZE = 6


class LineupProvider(Protocol):
    def lineup(self, *, team_id: int, seed: int) -> list[Batter]: ...

    def staff(self, *, team_id: int, seed: int) -> PitchingStaff: ...


class SyntheticLineupProvider:
    def lineup(self, *, team_id: int, seed: int) -> list[Batter]:
        return synthetic_lineup(seed=seed, team_id=team_id)

    def staff(self, *, team_id: int, seed: int) -> PitchingStaff:
        return synthetic_staff(seed=seed, team_id=team_id)


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


def staff_from_roster(
    roster: Sequence[PlayerSummary],
    *,
    team_id: int,
    seed: int,
    fallback: LineupProvider,
    workloads: Mapping[int, PitcherWorkload] | None = None,
) -> PitchingStaff:
    """Split a club's pitchers into a rotation and a bullpen.

    The rotation is the five arms with the most starts; everyone else relieves. The
    pen is ordered worst FIP first, which is roughly how a bullpen is spent: middle
    relief early, the best arm saved for the end.

    Each pitcher's outing length comes from his own season — innings over starts for a
    rotation arm, innings over appearances for a reliever — so a horse and a
    five-and-dive starter are not simulated as the same pitcher.
    """

    arms = [player for player in roster if player.primary_position == "P"]
    if len(arms) < _MIN_STAFF_SIZE:
        return fallback.staff(team_id=team_id, seed=seed)

    loads = workloads or {}

    def starts(player: PlayerSummary) -> int:
        load = loads.get(player.player_id)
        return load.games_started or 0 if load else 0

    # Most starts first, name for a stable tie-break so the staff is reproducible.
    ordered = sorted(arms, key=lambda player: (-starts(player), player.full_name))
    rotation_arms, bullpen_arms = ordered[:ROTATION_SIZE], ordered[ROTATION_SIZE:]

    def worst_fip_first(player: PlayerSummary) -> tuple[float, str]:
        load = loads.get(player.player_id)
        # No FIP sorts as league-average rather than as the best or worst arm.
        return (-(load.fip if load and load.fip is not None else 4.0), player.full_name)

    bullpen_arms.sort(key=worst_fip_first)

    return PitchingStaff(
        rotation=tuple(_pitcher(player, loads, starter=True) for player in rotation_arms),
        bullpen=tuple(_pitcher(player, loads, starter=False) for player in bullpen_arms),
    )


def _pitcher(
    player: PlayerSummary, loads: Mapping[int, PitcherWorkload], *, starter: bool
) -> Pitcher:
    load = loads.get(player.player_id)
    role = (load.games_started if starter else load.appearances) if load else None
    return Pitcher(
        player_id=player.player_id,
        name=player.full_name,
        expected_outs=appearance_outs(
            innings=load.innings if load else None,
            role_appearances=role,
            total_appearances=load.appearances if load else None,
            starter=starter,
        ),
    )


@dataclass(frozen=True)
class TeamRosterData:
    """Everything one club's attribution needs, read in a single trip."""

    roster: Sequence[PlayerSummary]
    woba: Mapping[int, float]
    workloads: Mapping[int, PitcherWorkload]


class CatalogLineupProvider:
    """Real batting order and staff from the persisted roster.

    Reads are cached per club for the life of the provider. Simulating a season is
    2,430 games against thirty clubs: fetching the roster on every call meant two
    connections per game, which cost more than a hundred times the simulation itself.
    The read does not depend on the seed — only the synthetic fallback does — so a
    club's data is fetched once and the orders derived from it.

    The cache is therefore as old as the provider. Callers that hold one across a
    re-ingest will serve the previous roster until they build a new one.
    """

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
        self._teams: dict[int, TeamRosterData] = {}

    def team_data(self, *, team_id: int) -> TeamRosterData:
        cached = self._teams.get(team_id)
        if cached is not None:
            return cached

        from baseball_sim.domain.catalog import PostgresCatalogRepository

        repository = PostgresCatalogRepository(dsn=self._dsn)
        try:
            roster = repository.get_team_roster(team_id=team_id)
            player_ids = [player.player_id for player in roster]
            data = TeamRosterData(
                roster=roster,
                woba=repository.get_batting_woba(
                    player_ids=player_ids, season=self._season
                ),
                workloads=repository.get_pitching_workload(
                    player_ids=player_ids, season=self._season
                ),
            )
        finally:
            repository.close()

        # A concurrent caller may have filled this in the meantime. Both results are
        # equal, so the last write wins harmlessly and no lock is needed.
        self._teams[team_id] = data
        return data

    def lineup(self, *, team_id: int, seed: int) -> list[Batter]:
        data = self.team_data(team_id=team_id)
        return lineup_from_roster(
            data.roster,
            team_id=team_id,
            seed=seed,
            fallback=self._fallback,
            woba=data.woba,
            size=self._size,
        )

    def staff(self, *, team_id: int, seed: int) -> PitchingStaff:
        data = self.team_data(team_id=team_id)
        return staff_from_roster(
            data.roster,
            team_id=team_id,
            seed=seed,
            fallback=self._fallback,
            workloads=data.workloads,
        )
