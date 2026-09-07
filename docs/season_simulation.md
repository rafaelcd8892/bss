# Season Simulation

    python -m baseball_sim.eval.run_season --season 2026
    python -m baseball_sim.eval.run_season --season 2026 --seasons 200

Plays the real ingested schedule through the same deterministic engine that serves a
single game, and totals the results into standings. With `--seasons N` it replays the
same schedule under N seeds and reports the distribution instead.

## What varies, and what does not

Team strength is **fixed** across runs: each club's profile, batting order and staff
are resolved once from the ingested season and reused for every game. The only thing
that changes between one simulated season and the next is the seed.

That makes the spread easy to read: it is the model's own noise. If a club's tenth and
ninetieth percentile are fifteen wins apart, then a fifteen-win gap in a single
standings table means nothing at all.

## Determinism

Each game's seed comes from `(season_seed, game_pk)` through the shared 32-bit mix, not
from the game's position in the schedule. Two consequences, both deliberate:

- Filtering or reordering the schedule replays every remaining game identically.
- Separate season seeds do not overlap. A seed that merely added the season to the game
  id would make season 2's game 99 identical to season 1's game 100, so a thousand
  "seasons" would be a few hundred distinct ones wearing different labels — and the
  spread they reported would be too narrow.

A club with no profile is skipped rather than played with a hashed one. A table half
built from data and half from seeds would look like one thing and be another.

## First measurement (2026, 200 seasons, 2,166 ingested games)

*This is what the unfitted model produced, and what the fit below was made against.*

| | simulated | real MLB |
| --- | --- | --- |
| runs per game | 4.14 | ~4.4 |
| win% range, single season | .269 – .667 | ~.380 – .620 |
| systematic spread (best mean wins − worst) | 51 wins | ~40, and that includes luck |
| per-club noise, p10–p90 | 15 wins | ~15 (binomial floor over 144 games) |

Two readings.

**The noise is right.** A p10–p90 of 15 wins over a 144-game schedule is what
independent games with a fixed win probability produce — the binomial standard
deviation at .500 is about 6 wins, and p10–p90 spans 2.56 of them. Nothing to fix.

**The signal is too strong.** The spread between clubs survives averaging over 200
seasons, so it is not luck: the model separates clubs by 51 wins where real baseball
separates them by about 40 *including* luck. The factor-to-outcome mapping is too
aggressive. ADR-020 already recorded those constants as documented starting values
rather than fitted ones; this is the first measurement that says by how much, and in
which direction.

Per ADR-004, the fix is to fit them against this measurement, not to hand-tune until
the table looks plausible. That is what `fit_event_model` does.

## Fitting

    python -m baseball_sim.eval.fit_event_model --season 2026

Two targets, both measured from the ingested games rather than remembered:

- **run environment** — runs per team per game.
- **talent spread** — the standard deviation of team win% with binomial luck removed.
  The observed spread is talent and luck together; the model's spread, averaged over
  many seasons, is talent alone. Comparing them directly would ask the model to
  reproduce noise as if it were skill.

Two knobs, chosen because they are nearly independent. `sensitivity` scales every
outcome's response to the matchup — it moves the spread and barely touches the run
environment. `out_base_shift` moves the league-average out rate — it moves the run
environment and barely touches the spread. The bounds scale with the sensitivity, or a
clamp sized for the old one would bite in the wrong place and quietly undo part of the
fit at the extremes.

The search is a coarse sweep, not an optimizer: with two nearly independent knobs and
targets known to a few percent, anything cleverer would be false precision.

### Result (`rulesets/mlb_2026_fitted.json`, sensitivity 0.7, out base −0.020)

| | unfitted | fitted | real |
| --- | --- | --- | --- |
| runs per game | 4.141 | **4.458** | 4.479 |
| talent spread (SD of win%) | 0.0659 | **0.0481** | 0.0457 |
| single-season win% range | .269 – .667 | **.331 – .618** | .378 – .611 |

The unfitted ruleset is kept rather than edited, so runs recorded under it stay
reproducible — and since every run stores its own ruleset (ADR-028), replaying one
plays it under the rules it was recorded under, not these.

## Cost

A 2,166-game season takes about 0.5 s; 200 seasons take about 100 s. That is the
engine, not the database — roster reads are cached per club (ADR-026).
