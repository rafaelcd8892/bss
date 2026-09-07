"""Season simulation: a schedule of games played through the same engine.

Pure, like the rest of ``sim``. It takes a schedule and each club's already-resolved
profile, batting order and staff, and returns standings. Resolving those is the
caller's job, and it happens once per season rather than once per game — a club is
the same club in April and September, and re-deriving it 162 times was the difference
between a season taking a second and taking a minute (ADR-026).

Every game's seed is derived from the season seed and the game's own id, so a season
reproduces exactly, and so does any single game inside it, independently of the order
the schedule happens to be in.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import mean

from baseball_sim.sim.hashing import U32_MASK, u32_mix
from baseball_sim.sim.lineups import Batter
from baseball_sim.sim.pitching import PitchingStaff
from baseball_sim.sim.profiles import TeamProfile
from baseball_sim.sim.rulesets import SimulationRuleset
from baseball_sim.sim.state_machine import simulate_game_trace

#: Salt keeping per-game seeds clear of every other use of the hash.
_GAME_SEED_SALT = 911


@dataclass(frozen=True)
class ScheduledGame:
    game_pk: int
    home_team_id: int
    away_team_id: int


@dataclass(frozen=True)
class TeamStanding:
    team_id: int
    wins: int
    losses: int
    runs_scored: int
    runs_allowed: int

    @property
    def games(self) -> int:
        return self.wins + self.losses

    @property
    def win_percentage(self) -> float:
        return self.wins / self.games if self.games else 0.0

    @property
    def run_differential(self) -> int:
        return self.runs_scored - self.runs_allowed


@dataclass(frozen=True)
class SeasonResult:
    seed: int
    games_played: int
    #: Best record first; run differential breaks a tie, then team id so the order is
    #: total and reproducible rather than dependent on dictionary insertion.
    standings: tuple[TeamStanding, ...]

    @property
    def by_team(self) -> dict[int, TeamStanding]:
        return {standing.team_id: standing for standing in self.standings}


def game_seed(*, season_seed: int, game_pk: int) -> int:
    """The seed one scheduled game is played with.

    Derived from the game's own id rather than its position in the schedule, so
    re-running a season with games filtered or reordered plays each one identically.
    """

    return u32_mix(seed=season_seed & U32_MASK, entity_id=game_pk, salt=_GAME_SEED_SALT)


@dataclass
class _Tally:
    wins: int = 0
    losses: int = 0
    runs_scored: int = 0
    runs_allowed: int = 0


def simulate_season(
    *,
    seed: int,
    schedule: Sequence[ScheduledGame],
    profiles: Mapping[int, TeamProfile],
    lineups: Mapping[int, list[Batter]] | None = None,
    staffs: Mapping[int, PitchingStaff] | None = None,
    scheduled_innings: int = 9,
    ruleset: SimulationRuleset | None = None,
) -> SeasonResult:
    """Play every scheduled game and total the results.

    A club with no entry in ``profiles`` is skipped rather than silently played with a
    seeded profile: a season table built half from data and half from hashes would
    look like one thing and be another.
    """

    tallies: dict[int, _Tally] = {}
    played = 0

    for game in schedule:
        home = profiles.get(game.home_team_id)
        away = profiles.get(game.away_team_id)
        if home is None or away is None:
            continue

        trace = simulate_game_trace(
            seed=game_seed(season_seed=seed, game_pk=game.game_pk),
            home_team_id=game.home_team_id,
            away_team_id=game.away_team_id,
            scheduled_innings=scheduled_innings,
            ruleset=ruleset,
            home_profile=home,
            away_profile=away,
            home_lineup=lineups.get(game.home_team_id) if lineups else None,
            away_lineup=lineups.get(game.away_team_id) if lineups else None,
            home_staff=staffs.get(game.home_team_id) if staffs else None,
            away_staff=staffs.get(game.away_team_id) if staffs else None,
            rotation_slot=game.game_pk,
        )
        result = trace.result
        played += 1

        home_tally = tallies.setdefault(game.home_team_id, _Tally())
        away_tally = tallies.setdefault(game.away_team_id, _Tally())
        home_tally.runs_scored += result.home_score
        home_tally.runs_allowed += result.away_score
        away_tally.runs_scored += result.away_score
        away_tally.runs_allowed += result.home_score
        if result.winner_team_id == game.home_team_id:
            home_tally.wins += 1
            away_tally.losses += 1
        else:
            away_tally.wins += 1
            home_tally.losses += 1

    standings = tuple(
        sorted(
            (
                TeamStanding(
                    team_id=team_id,
                    wins=tally.wins,
                    losses=tally.losses,
                    runs_scored=tally.runs_scored,
                    runs_allowed=tally.runs_allowed,
                )
                for team_id, tally in tallies.items()
            ),
            key=lambda s: (-s.wins, -s.run_differential, s.team_id),
        )
    )
    return SeasonResult(seed=seed, games_played=played, standings=standings)


@dataclass(frozen=True)
class TeamProjection:
    """One club's distribution of season outcomes across repeated simulations."""

    team_id: int
    seasons: int
    mean_wins: float
    wins_p10: int
    wins_p50: int
    wins_p90: int
    best_record_seasons: int

    @property
    def best_record_share(self) -> float:
        return self.best_record_seasons / self.seasons if self.seasons else 0.0


def _percentile(sorted_values: Sequence[int], fraction: float) -> int:
    """Nearest-rank percentile. Win totals are counts, so the answer stays a count."""

    if not sorted_values:
        return 0
    index = max(0, min(len(sorted_values) - 1, round(fraction * (len(sorted_values) - 1))))
    return sorted_values[index]


def project_seasons(
    *,
    seeds: Sequence[int],
    schedule: Sequence[ScheduledGame],
    profiles: Mapping[int, TeamProfile],
    lineups: Mapping[int, list[Batter]] | None = None,
    staffs: Mapping[int, PitchingStaff] | None = None,
    scheduled_innings: int = 9,
    ruleset: SimulationRuleset | None = None,
) -> tuple[TeamProjection, ...]:
    """Replay the same schedule under many seeds and summarize the spread.

    Team strength is fixed, so the only thing varying is how the games fall. The
    spread is therefore the model's own noise — how much of a standings gap a season
    of luck can manufacture between clubs that are not actually different.
    """

    win_totals: dict[int, list[int]] = {}
    best_record: dict[int, int] = {}

    for seed in seeds:
        result = simulate_season(
            seed=seed,
            schedule=schedule,
            profiles=profiles,
            lineups=lineups,
            staffs=staffs,
            scheduled_innings=scheduled_innings,
            ruleset=ruleset,
        )
        for standing in result.standings:
            win_totals.setdefault(standing.team_id, []).append(standing.wins)
        if result.standings:
            leader = result.standings[0].team_id
            best_record[leader] = best_record.get(leader, 0) + 1

    projections = []
    for team_id, wins in win_totals.items():
        ordered = sorted(wins)
        projections.append(
            TeamProjection(
                team_id=team_id,
                seasons=len(ordered),
                mean_wins=round(mean(ordered), 1),
                wins_p10=_percentile(ordered, 0.10),
                wins_p50=_percentile(ordered, 0.50),
                wins_p90=_percentile(ordered, 0.90),
                best_record_seasons=best_record.get(team_id, 0),
            )
        )
    return tuple(sorted(projections, key=lambda p: (-p.mean_wins, p.team_id)))
