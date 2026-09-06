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

**Sample size dominates.** The first window held 59 finished games, putting a 6.5 point
standard error on the observed rate — wide enough to contain almost any hypothesis. The
current window holds 857, which brings that down to about 1.7 points. See "Why the
first run was left alone" below for what that difference actually changed.

## Results

### Run 2 — season 2026, 857 games (2026-09-06)

After widening the ingestion window from five days to about ten weeks.

| | |
| --- | --- |
| sample | 857 finished, decided games |
| Brier score | 0.2468 |
| skill vs uniform | **+0.0129** |
| mean predicted home win | 0.5203 |
| observed home win rate | 0.5239 (95% interval 0.490 – 0.557) |
| calibration error | **−0.0037** |
| conclusive | no |

The model is now essentially calibrated in the large: it forecasts home teams to win
52.03% of the time and they won 52.39%, a gap of four tenths of a point. Skill is
mildly positive, which is where an MLB pregame model belongs — the sport's variance
caps the achievable range at a few points.

`conclusive` is still false, and correctly so. Even 857 games cannot *prove* the model
right; they only fail to contradict it.

### Run 1 — season 2026, 59 games (2026-09-06)

The first window held only five days of games.

| | |
| --- | --- |
| sample | 59 finished, decided games |
| Brier score | 0.2520 |
| skill vs uniform | −0.0079 |
| mean predicted home win | 0.5197 |
| observed home win rate | 0.4576 (95% interval 0.330 – 0.585) |
| calibration error | +0.0621 |
| conclusive | no |

### Why the first run was left alone

Run 1 showed the model over-predicting home wins by 6.2 points and scoring slightly
*worse* than a coin flip. The obvious response was to lower the home-field constant
until the gap closed.

Run 2 shows that would have been a mistake. The true home-win rate over the wider
window is 52.4%, and the model already said 52.0%. The entire 6.2-point "error" was
sampling noise in 59 games, exactly as the reported standard error of 6.5 points
warned. Tuning the constant to fit it would have pushed a well-calibrated model away
from reality and replaced a documented assumption with a fitted number justified by
nothing but noise.

This is the concrete case for reporting sampling error alongside a score, and for
treating `conclusive: false` as a reason not to act.

## What a real evaluation needs

1. **Game-level history**, so profiles can be rebuilt from stats as they stood *before*
   each game rather than from end-of-season aggregates.
2. **A larger sample still** — a full season is roughly 2,430 games, which would bring
   the standard error down to about 1 point from the current 1.7.
3. **Games spread across the season**, since even ten weeks is not a full year of
   conditions.

Until those exist, this report is a sanity check on the model's shape, not a measure of
forecasting skill.
