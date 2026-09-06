# Win-probability calibration

ADR-004 says to add model complexity only once the baseline's limits are *measured*.
This is that measurement, and the honest reading of it.

## What is being scored

The pregame forecast from `sim/winprob.py`: team quality becomes an expected
runs-per-game rate from the matchup profiles, and a logistic on the projected run
differential turns that into a probability. Run it with:

```bash
python -m baseball_sim.eval.run_calibration --season 2026
```

## How to read the numbers

| field | meaning |
| --- | --- |
| `brier_score` | Mean squared error of the probabilities. Lower is better. |
| `uniform_brier` | 0.25 — a forecaster who always says 50/50. The minimum bar. |
| `skill_vs_uniform` | `1 - brier / 0.25`. Negative means worse than a coin flip. |
| `calibration_error` | `mean_predicted - observed_rate`. Positive means over-claiming. |
| `observed_standard_error` | Sampling noise in the observed rate. |
| `conclusive` | False when the mean forecast falls inside the interval around the observed rate — the sample cannot separate the model from anything. |

Baseball sets a low ceiling here. Even a strong public MLB model scores around
0.235–0.245 against the 0.25 baseline, so the whole usable range is a few points wide.
A skill score near zero is not the same failure it would be in a lower-variance sport.

## Two caveats that matter more than the score

**This is in-sample.** Team profiles are built from full-season aggregates, and the
games being scored happened inside that same season. The model already "knows" how the
season turned out. This is not a backtest, and the number flatters the model.

**The sample is tiny.** The current window holds 59 finished, decided games. The
standard error on the observed home-win rate is about 6.5 points, so the interval spans
roughly 0.33 to 0.58 — wide enough to contain both the model's forecast and the true
league home-field advantage of about 0.54.

## Result — season 2026, run 2026-09-06

| | |
| --- | --- |
| sample | 59 finished, decided games |
| Brier score | 0.2520 |
| skill vs uniform | **−0.0079** |
| mean predicted home win | 0.5197 |
| observed home win rate | 0.4576 (95% interval 0.330 – 0.585) |
| calibration error | +0.0621 |
| conclusive | **no** |

Every forecast landed in a single reliability bin (0.4–0.6): on real clubs the model's
spread is narrow, so there is no reliability curve to read yet.

### What this does and does not tell us

It says the model shows **no demonstrated skill on this sample** and leans slightly
toward the home side relative to what happened. It does **not** say the model is
mis-tuned: 59 games cannot distinguish a 0.52 forecast from a 0.46 outcome, and the
window happened to be one where home teams lost more often than the league norm.

The right response is therefore *not* to adjust the home-field constant. Tuning a
constant to fit 59 games of noise would make the model worse and less explainable, and
would replace a documented assumption with a fitted one that nobody can justify.

## What a real evaluation needs

1. **Game-level history**, so profiles can be rebuilt from stats as they stood *before*
   each game rather than from end-of-season aggregates.
2. **A much larger sample** — a full season is roughly 2,430 games, which brings the
   standard error on the observed rate down to about 1 point.
3. **A wider ingestion window**, since the current five-day window is not representative
   of a season.

Until those exist, this report is a sanity check on the model's shape, not a measure of
forecasting skill.
