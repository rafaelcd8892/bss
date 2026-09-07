"""Career totals: many seasons summed into one line.

A rate over several seasons has to be recomputed from the summed counting stats, never
averaged across them. Averaging would weigh a 100-plate-appearance season the same as a
700-plate-appearance one, which is how a cup of coffee ends up moving a career average.

Two things a total deliberately does not carry:

- **xwOBA**, because it is a measurement per season with no stored denominator to
  re-weight it by. Averaging it would be exactly the error above.
- **wRC+**, because it is league-relative and the league moves. A single set of weights
  applied across twenty years answers a question nobody asked.
"""

from __future__ import annotations

from collections.abc import Sequence

from baseball_sim.domain.contracts import PlayerSeasonLine
from baseball_sim.sim.profiles import aggregate_batting, aggregate_pitching
from baseball_sim.sim.sabermetrics import (
    RawBattingLine,
    RawPitchingLine,
    compute_babip,
    compute_batting_average,
    compute_era,
    compute_fip,
    compute_ground_ball_rate,
    compute_iso,
    compute_k_bb_ratio,
    compute_obp,
    compute_ops,
    compute_slg,
    compute_strikeout_rate,
    compute_walk_rate,
    compute_whip,
    compute_woba,
)


def _round(value: float | None, digits: int) -> float | None:
    return round(value, digits) if value is not None else None


def batting_total(lines: Sequence[RawBattingLine]) -> PlayerSeasonLine | None:
    """Sum batting seasons and recompute every rate from the total."""

    if not lines:
        return None
    line = aggregate_batting(lines)
    return PlayerSeasonLine(
        stat_group="hitting",
        plate_appearances=line.plate_appearances,
        at_bats=line.at_bats,
        hits=line.hits,
        doubles=line.doubles,
        triples=line.triples,
        home_runs=line.home_runs,
        walks=line.walks,
        strikeouts=line.strikeouts,
        stolen_bases=line.stolen_bases,
        woba=_round(compute_woba(line), 4) if line.woba_denominator > 0 else None,
        batting_average=_round(compute_batting_average(line), 4),
        obp=_round(compute_obp(line), 4),
        slg=_round(compute_slg(line), 4),
        ops=_round(compute_ops(line), 4),
        iso=_round(compute_iso(line), 4),
        babip=_round(compute_babip(line), 4),
    )


def pitching_total(lines: Sequence[RawPitchingLine]) -> PlayerSeasonLine | None:
    """Sum pitching seasons and recompute every rate from the total."""

    if not lines:
        return None
    line = aggregate_pitching(lines)
    return PlayerSeasonLine(
        stat_group="pitching",
        innings_pitched=line.innings_pitched,
        strikeouts=line.strikeouts,
        walks=line.walks,
        home_runs=line.home_runs,
        fip=_round(compute_fip(line), 3) if line.innings_pitched > 0 else None,
        k_bb_ratio=_round(compute_k_bb_ratio(line.strikeouts, line.walks), 3),
        era=_round(compute_era(line), 3),
        whip=_round(compute_whip(line), 3),
        strikeout_rate=_round(compute_strikeout_rate(line), 4),
        walk_rate=_round(compute_walk_rate(line), 4),
        ground_ball_rate=_round(compute_ground_ball_rate(line), 4),
    )
