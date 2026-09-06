# Sabermetrics & Stats Providers

This document describes how real ingested MLB stats flow into the compare endpoint
and the simulator, and how the system degrades gracefully to deterministic synthetic
values when data is missing.

## Layers

```
MLB Stats API  ──ingest──▶  player_season_stats (raw components + computed metrics)
                                     │
                                     ▼
                    PostgresStatsProvider (reconstructs raw lines)
                                     │
        ┌────────────────────────────┴───────────────────────────┐
        ▼                                                          ▼
 StatLineStatsProvider (real sabermetrics)            SyntheticStatsProvider (seeded)
        └────────────────── fallback chain ───────────────────────┘
                                     │
                ┌────────────────────┴────────────────────┐
                ▼                                          ▼
        compare_players                              simulate_game
       (per-player ratings)                        (team-profile matchup)
```

A `StatsProvider` exposes two methods:

- `player_rating(player_id, seed) -> PlayerRating` — the five compare metrics.
- `team_profile(team_id, seed) -> TeamProfile` — seven `[0,1]` matchup factors.

### Providers

- **`SyntheticStatsProvider`** — deterministic hash of `(seed, entity_id, salt)`.
  Always available, reproduces the original seed-only behavior byte-for-byte. It is
  the universal fallback so a run never fails for missing data.
- **`StatLineStatsProvider`** — computes real sabermetrics from supplied
  `RawBattingLine` / `RawPitchingLine` inputs. Metrics it cannot derive for a player
  (e.g. a pure hitter's FIP, or `xwoba` which needs Statcast) fall back per-metric and
  the rating is marked `real_partial`. A player with both hitting and pitching data is
  marked `real`.
- **`LayeredStatsProvider`** — chains providers, preferring the first non-synthetic
  answer. Mirrors the API-first-with-seeded-fallback philosophy of roster loading
  (ADR-013).

Selection is config-driven via `BASEBALL_STATS_SOURCE` (`synthetic` default, or
`postgres`) and `BASEBALL_STATS_SEASON`. The API resolves a provider per request; the
synthetic default passes `None` so the legacy path stays bit-identical.

## Formulas (`sim/sabermetrics.py`)

Pure functions, no I/O, fixed league weights (FanGraphs 2023 baseline):

| Metric | Formula |
| --- | --- |
| wOBA | `(wBB·uBB + wHBP·HBP + w1B·1B + w2B·2B + w3B·3B + wHR·HR) / (AB + BB − IBB + SF + HBP)` |
| wRC+ | `((wOBA − lgwOBA)/wOBAScale + lgR/PA) / (lgR/PA) · 100` (park-neutral) |
| FIP | `(13·HR + 3·(BB + HBP) − 2·K) / IP + FIP_constant` |
| K/BB | `K / max(BB, 1)` |

Weights live in `WobaWeights` / `FipConstants` dataclasses so they can be versioned
per season without touching call sites.

### Widened metrics

The MLB Stats API returns 34 hitting and 62 pitching fields per player. The first
ingest parsed 12 and 5; the rest were arriving in responses we already paid for and
were being discarded. Parsing them added these, at no extra request cost:

| metric | formula |
| --- | --- |
| AVG | `H / AB` |
| OBP | `(H + BB + HBP) / (AB + BB + HBP + SF)` |
| SLG | `TB / AB` |
| OPS | `OBP + SLG` |
| ISO | `SLG - AVG` |
| BABIP | `(H - HR) / (AB - K - HR + SF)` |
| ERA | `ER x 9 / IP` |
| WHIP | `(BB + H) / IP` |
| K% / BB% | `K / BF`, `BB / BF` — rates against batters faced, not innings |
| GB% | `GO / (GO + AO)` — an approximation: the API gives ground and air *outs*, not every batted ball |

Every one returns `None` rather than zero when its inputs were not ingested, so a
missing measurement never masquerades as a real value of nought.

## Ingestion scope and aggregation trust

Two separate concerns that are easy to conflate:

**Scope** — which groups to request. Asking for both hitting and pitching for all ~840
players doubles the request count and stores lines nobody wants. `stat_groups_for`
picks by roster position: hitting for position players, pitching for pitchers, both for
a declared two-way player, and both when the position is unknown. `--all-stat-groups`
overrides it.

**Trust** — which lines to count. This is where the correctness win is. Roster
positions can be stale, so scope filtering alone cannot be relied on: a pitcher's four
plate appearances would still be summed into the club's team wOBA. `team_profile_from_stats`
therefore applies its own floor (`MIN_TEAM_BATTING_PA`, `MIN_TEAM_PITCHING_IP`) before
aggregating, which does not depend on the position data being right.

## Team profile from real stats (`sim/profiles.py`)

Aggregated team batting/pitching lines map into the simulator's seven factors via
documented league reference ranges:

| Factor | Source | Reference range |
| --- | --- | --- |
| offense | team wOBA | 0.290 – 0.360 |
| discipline | BB / PA | 0.060 – 0.120 |
| power | ISO = (2B + 2·3B + 3·HR)/AB | 0.120 – 0.220 |
| speed | SB / PA | 0.000 – 0.100 |
| prevention | team FIP (inverted) | 3.000 – 5.000 |
| command | team K/BB | 1.500 – 4.000 |
| range_factor | *(fielding not yet ingested)* | neutral 0.5 |

`range_factor` is held neutral until fielding data is ingested — a tracked roadmap
item rather than a silent guess.

## Ingestion

`ingest_mlb_window(..., include_player_stats=True)` (or `run_sync --include-player-stats`)
fetches per-player season hitting/pitching splits, computes the sabermetrics, and
upserts both the raw components and the computed metrics into `player_season_stats`.
Raw stat payloads are snapshotted immutably under `data/raw` like all other ingestion
(ADR-007). Storing raw components lets the serving layer reconstruct the exact same
`RawBattingLine`/`RawPitchingLine` and reuse one analytical code path end-to-end.
