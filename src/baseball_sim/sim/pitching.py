"""Pitching staffs and who is on the mound, for play attribution.

Like the batting order in :mod:`baseball_sim.sim.lineups`, this is pure labeling: it
never touches the RNG, so a seeded game stays byte-for-byte reproducible whether or
not a staff was supplied.

A staff is a rotation plus a bullpen. The starter is picked by rotation slot, so the
same club opens a given game with the same arm and a series turns over like a real
rotation. Each pitcher carries the number of outs he is expected to record, derived
from his own season (innings per start, or per appearance for a reliever) rather than
from one league-wide constant: a horse and a five-and-dive starter are not the same
pitcher, and the ingested data already says which is which.
"""

from __future__ import annotations

from dataclasses import dataclass

from baseball_sim.seeders.roster import generate_seeded_staff

#: A five-man rotation. The slot is chosen by the caller from the match id.
ROTATION_SIZE = 5

#: Fallbacks for a pitcher with no ingested workload. 16 outs is a shade over five
#: innings, which is roughly what a modern start lasts; a reliever gets one inning.
DEFAULT_STARTER_OUTS = 16
DEFAULT_RELIEVER_OUTS = 3

#: Bounds on a derived appearance length. Season rates can be extreme in small
#: samples — an opener with one start of two innings, or a long man who threw once.
MIN_STARTER_OUTS = 9
MAX_STARTER_OUTS = 27
MIN_RELIEVER_OUTS = 1
MAX_RELIEVER_OUTS = 9

#: A season's innings are reported as one total, not split by role. The ratio is only
#: trustworthy when the pitcher worked in one role: a swingman with 128 innings over 15
#: starts and 14 relief outings reads as an eight-and-a-half-inning starter. Below this
#: share of appearances in the role, the league shape is used instead of a number the
#: data cannot support.
MIN_ROLE_SHARE = 0.7


@dataclass(frozen=True)
class Pitcher:
    player_id: int
    name: str
    #: Outs this pitcher is expected to record in one appearance.
    expected_outs: int


@dataclass(frozen=True)
class PitchingStaff:
    rotation: tuple[Pitcher, ...]
    bullpen: tuple[Pitcher, ...]

    def starter_for(self, *, rotation_slot: int) -> Pitcher | None:
        if not self.rotation:
            return None
        return self.rotation[rotation_slot % len(self.rotation)]


def appearance_outs(
    *,
    innings: float | None,
    role_appearances: int | None,
    total_appearances: int | None = None,
    starter: bool,
) -> int:
    """How long one appearance lasts, from a season's innings over appearances.

    ``role_appearances`` is starts for a rotation arm and total appearances for a
    reliever; ``total_appearances`` is the whole season either way. When the two
    disagree the innings are shared with another role and the ratio cannot be read —
    see :data:`MIN_ROLE_SHARE`.
    """

    default = DEFAULT_STARTER_OUTS if starter else DEFAULT_RELIEVER_OUTS
    if not innings or not role_appearances or innings <= 0 or role_appearances <= 0:
        return default
    if total_appearances and role_appearances / total_appearances < MIN_ROLE_SHARE:
        return default
    outs = round((innings / role_appearances) * 3)
    low, high = (
        (MIN_STARTER_OUTS, MAX_STARTER_OUTS)
        if starter
        else (MIN_RELIEVER_OUTS, MAX_RELIEVER_OUTS)
    )
    return max(low, min(high, outs))


class MoundAssignment:
    """Walks one club's staff through a game.

    The starter works until he has recorded his expected outs, then the bullpen takes
    over in order. When the pen is spent the last arm finishes the game: a real manager
    would be out of options too, and a game must not fail to be attributed.
    """

    def __init__(self, staff: PitchingStaff | None, *, rotation_slot: int = 0) -> None:
        self._staff = staff
        starter = staff.starter_for(rotation_slot=rotation_slot) if staff else None
        self._queue = list(staff.bullpen) if staff else []
        self._current = starter if starter is not None else self._next_arm()
        self._outs_recorded = 0

    @property
    def current(self) -> Pitcher | None:
        return self._current

    def record_outs(self, outs: int) -> None:
        if self._current is None or outs <= 0:
            return
        self._outs_recorded += outs
        if self._outs_recorded < self._current.expected_outs:
            return
        replacement = self._next_arm()
        if replacement is None:
            return
        self._current = replacement
        self._outs_recorded = 0

    def _next_arm(self) -> Pitcher | None:
        return self._queue.pop(0) if self._queue else None


def synthetic_staff(*, seed: int, team_id: int) -> PitchingStaff:
    """A deterministic staff for the seed-only path, with league-average workloads."""

    arms = generate_seeded_staff(team_id=team_id, seed=seed)
    rotation = tuple(
        Pitcher(player_id=arm.player_id, name=arm.full_name, expected_outs=DEFAULT_STARTER_OUTS)
        for arm in arms[:ROTATION_SIZE]
    )
    bullpen = tuple(
        Pitcher(player_id=arm.player_id, name=arm.full_name, expected_outs=DEFAULT_RELIEVER_OUTS)
        for arm in arms[ROTATION_SIZE:]
    )
    return PitchingStaff(rotation=rotation, bullpen=bullpen)
