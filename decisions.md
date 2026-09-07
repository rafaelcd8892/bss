# decisions.md

## Purpose
This file stores architecture decision records (ADRs) and major product decisions.
Use it to capture what was decided, why, and consequences.

## ADR Template
When adding a new decision, use this format:

```
## ADR-XXX: Title
- Date: YYYY-MM-DD
- Status: Proposed | Accepted | Superseded
- Context:
- Decision:
- Consequences:
- Alternatives considered:
```

---

## ADR-001: Deterministic-First Platform
- Date: 2026-02-22
- Status: Accepted
- Context:
  - The product must support reproducible simulations and auditable predictions.
  - Analysts need confidence that repeated runs are identical under fixed inputs.
- Decision:
  - Enforce deterministic contracts using `seed`, `model_version`, and `data_snapshot_id`.
  - Require immutable data snapshots and explicit model lineage in outputs.
- Consequences:
  - Increased engineering rigor in data pipelines and model serving.
  - Easier debugging, auditing, and scientific comparison across experiments.
- Alternatives considered:
  - Best-effort reproducibility without strict contract enforcement.

## ADR-002: Python + FastAPI + PostgreSQL as Core Stack
- Date: 2026-02-22
- Status: Accepted
- Context:
  - Need fast iteration for data ingestion, sabermetrics computation, and ML.
  - Need robust transactional storage and predictable operational model.
- Decision:
  - Use Python for domain logic and modeling.
  - Use FastAPI for API services.
  - Use PostgreSQL for canonical and serving data.
- Consequences:
  - Strong ecosystem fit for analytics and ML.
  - Clear migration path to scale with caching and partitioning.
- Alternatives considered:
  - Node.js service layer with separate ML microservice.
  - JVM-first stack for all services.

## ADR-003: Data Source Strategy (MLB Stats API + Baseball Savant)
- Date: 2026-02-22
- Status: Accepted
- Context:
  - Need broad coverage across roster/team/game entities and advanced batted-ball metrics.
- Decision:
  - Use MLB Stats API for core baseball entities and schedules/game feeds.
  - Use Baseball Savant/Statcast exports for expected metrics and pitch/batted-ball depth.
- Consequences:
  - Broad data coverage with practical ingestion paths.
  - Must harden against schema changes and validate usage terms.
- Alternatives considered:
  - Paid third-party consolidated baseball data feeds from day one.

## ADR-004: Explainable Baselines Before Complex Models
- Date: 2026-02-22
- Status: Accepted
- Context:
  - Product trust and analyst adoption require interpretability and calibration.
- Decision:
  - Start with explainable, well-calibrated baseline models.
  - Add model complexity only when baseline limits are clear and measured.
- Consequences:
  - Faster validation and clearer debugging path.
  - May sacrifice early peak accuracy versus complex models.
- Alternatives considered:
  - Start with high-complexity black-box models.

## ADR-005: Layered Data Architecture (Raw, Canonical, Features)
- Date: 2026-02-22
- Status: Accepted
- Context:
  - Need traceability from external payloads to prediction-ready features.
- Decision:
  - Maintain three layers:
    - Raw immutable payloads.
    - Canonical normalized relational tables.
    - Versioned feature datasets for training/inference.
- Consequences:
  - Strong auditability and simpler reprocessing.
  - Higher storage and pipeline orchestration overhead.
- Alternatives considered:
  - Single transformed store without raw retention.

## ADR-006: SQL-First Migrations and Metadata-Rich API Responses
- Date: 2026-02-22
- Status: Accepted
- Context:
  - The first milestone needs a low-friction migration process and strict run traceability.
  - Deterministic behavior must be visible in API responses, not only internal logs.
- Decision:
  - Start with ordered SQL migration files under `migrations/`.
  - Include deterministic context and generation timestamp in simulation/comparison/prediction responses.
- Consequences:
  - Simple onboarding and transparent schema evolution at project start.
  - Future move to tool-managed migrations (for example Alembic) may require backfilling migration metadata.
- Alternatives considered:
  - Start immediately with framework-managed migrations only.
  - Keep deterministic context internal and omit from API payloads.

## ADR-007: Content-Addressed Raw Snapshot Storage
- Date: 2026-02-22
- Status: Accepted
- Context:
  - External MLB payloads can change shape and content over time.
  - We need exact replayability for ingestion outputs and model inputs.
- Decision:
  - Store raw payloads as canonical JSON bytes.
  - Generate snapshot identity from SHA-256 hash and source category.
  - Treat snapshot files as immutable by writing with exclusive create mode.
- Consequences:
  - Identical payloads deduplicate naturally and map to stable snapshot IDs.
  - Storage layout stays simple and supports forensic replay.
  - Payload-level schema drift can be analyzed directly from preserved raw files.
- Alternatives considered:
  - Time-based snapshot IDs without content hashing.
  - Mutable "latest" files only, without raw historical retention.

## ADR-008: Lightweight Migration Runner and Bounded API Retries
- Date: 2026-02-22
- Status: Accepted
- Context:
  - The project needs a repeatable database bootstrap step for local/CI environments.
  - External API availability and transient failures can disrupt ingestion runs.
- Decision:
  - Add an internal migration runner that tracks applied versions in `schema_migrations`.
  - Validate checksum integrity for previously applied migration versions.
  - Apply each migration in a transaction and protect with advisory lock.
  - Add bounded MLB API retries with exponential backoff for transient status codes.
- Consequences:
  - Faster onboarding and more reliable ingestion jobs.
  - Migration execution behavior is explicit and testable in-repo.
  - Retry behavior adds latency during outages but prevents many avoidable failures.
- Alternatives considered:
  - Continue manual migration application only.
  - Rely on single-attempt API calls with no retry/backoff policy.

## ADR-009: Plate-Appearance State Machine for Game Simulation
- Date: 2026-02-22
- Status: Accepted
- Context:
  - Prior simulation logic was aggregate-score based and not built on baseball event transitions.
  - We need deterministic but structurally realistic inning flow for future sabermetric enhancements.
- Decision:
  - Implement deterministic plate-appearance event sampling (`out`, `walk`, `single`, `double`, `triple`, `home_run`).
  - Track explicit base-state and outs transitions per half-inning.
  - Enforce MLB end-of-game conditions (skip home bottom-half when already leading after top of final inning).
  - Bound extra innings and resolve deadlock deterministically if the cap is reached.
- Consequences:
  - Simulator is now structurally aligned with baseball mechanics and easier to extend.
  - Model fidelity still depends on event-probability calibration, which remains an active roadmap item.
- Alternatives considered:
  - Keep aggregate run-estimate simulation without play-state transitions.

## ADR-010: CLI Watch Mode, Deterministic Match IDs, and Synthetic Roster Fallback
- Date: 2026-02-22
- Status: Accepted
- Context:
  - The project needs a human-observable simulator experience for debugging, demos, and analyst trust.
  - API/DB player availability may be incomplete during early ingestion windows.
- Decision:
  - Add a terminal watch-mode simulator interface with scoreboard, field view, lineups, and play-by-play pacing controls.
  - Persist per-play logs and summary artifacts for every simulated game.
  - Assign deterministic `match_id` values tied to seed and simulation context.
  - Use a fallback roster seeder when team/player data is unavailable from API/DB.
- Consequences:
  - Faster validation of simulation behavior and better observability during development.
  - Added CLI/UI complexity and logging storage overhead.
  - Synthetic data paths must be explicitly labeled to avoid confusion with real MLB entities.
- Alternatives considered:
  - API-only simulator responses with no interactive terminal interface.
  - Hard-fail when external player data is missing.

## ADR-011: Ruleset-Driven Simulator Configuration
- Date: 2026-02-22
- Status: Accepted
- Context:
  - MLB rule variants and simulator behavior will evolve over seasons and feature phases.
  - We want faster iteration without rewriting core simulation loop logic.
- Decision:
  - Introduce versioned JSON rulesets loaded from configurable path.
  - Keep core rule toggles and limits in ruleset config (walkoff, innings cap, extras runner, PA cap).
  - Include ruleset checksum in simulation assumptions for replay auditability.
- Consequences:
  - Behavior changes are trackable and deployable as config artifacts.
  - Rule processing remains deterministic and easier to extend.
- Alternatives considered:
  - Hard-code all simulator behavior in Python only.
  - Use ad-hoc environment variables without versioned ruleset files.

## ADR-012: Simulation Trace + CLI Watch Logging Format
- Date: 2026-02-22
- Status: Accepted
- Context:
  - Terminal watch mode requires per-play state visibility, not just final score output.
  - Deterministic replay/debugging needs durable event logs and match registry linkage.
- Decision:
  - Extend simulator with play-level trace output while preserving API summary contract.
  - Introduce `match_id` derived from deterministic context.
  - Persist logs as JSONL play stream plus summary JSON and append-only match registry.
- Consequences:
  - Enables watch/replay workflows and high-fidelity debugging.
  - Adds storage overhead and requires schema stability for log consumers.
- Alternatives considered:
  - Keep summary-only simulation output without per-play trace.
  - Store logs only in stdout with no persisted artifacts.

## ADR-013: CLI Roster Loading Uses API-First with Deterministic Seeded Fallback
- Date: 2026-02-22
- Status: Accepted
- Context:
  - Watch mode should prefer real MLB roster data when available.
  - CLI experience must remain reliable in offline/dev scenarios or when API data is incomplete.
  - Deterministic replay/debugging requires transparent roster-source metadata in logs.
- Decision:
  - Load team names and rosters from MLB Stats API by default in CLI watch mode.
  - Fill missing lineup/field slots using deterministic seeded players derived from `seed` and `team_id`.
  - Fall back to full seeded roster if API lookup fails or returns unusable payloads.
  - Persist roster source and fallback notes in game log metadata and summary.
- Consequences:
  - Better realism for watch mode without sacrificing run reliability.
  - API outages/degraded payloads no longer block simulator usage.
  - Exact roster composition can vary over time unless seeded-only mode is used.
- Alternatives considered:
  - Keep watch mode seeded-only until DB roster store is complete.
  - Hard-fail CLI run when API roster data is unavailable.

## ADR-014: Stats Provider Seam Connecting Real Data to Compare and Simulator
- Date: 2026-06-19
- Status: Accepted
- Context:
  - The compare endpoint and simulator produced metrics/team profiles by hashing
    entity IDs from the seed; ingested MLB data was never consumed by either.
  - The `player_season_stats` table existed in the schema but was never written or read.
  - We need real sabermetrics to drive analysis while preserving determinism and the
    ability to run offline/without a database.
- Decision:
  - Add a pure sabermetrics module (`sim/sabermetrics.py`) computing wOBA, wRC+, FIP,
    and K/BB from raw counting lines with versioned league weights.
  - Introduce a `StatsProvider` seam consumed by `compare_players` and `simulate_game`:
    - `SyntheticStatsProvider` reproduces prior hash-based values exactly (fallback).
    - `StatLineStatsProvider` computes real metrics from stat lines, with per-metric
      fallback (`real` / `real_partial` sourcing) and a real team-profile builder.
    - `LayeredStatsProvider` chains real-first, synthetic-last.
  - Extend ingestion to fetch per-player season splits, compute sabermetrics, and store
    raw components + computed metrics in `player_season_stats` (migration `0002`).
  - Select the provider via `BASEBALL_STATS_SOURCE`; default stays synthetic so the
    legacy path is bit-identical and runs without a database.
- Consequences:
  - Real data now drives compare and simulation when available; behavior is unchanged
    when it is not, and determinism is preserved in both modes.
  - One analytical code path serves both DB-backed and in-memory inputs.
  - Fielding range and Statcast `xwoba` remain synthetic until those feeds are ingested.
- Alternatives considered:
  - Reading precomputed metrics only (cannot rebuild team-profile aggregates).
  - Hard cutover to real data with no synthetic fallback (breaks offline/CI runs).

## ADR-015: Web Interface — Backend Readiness and React Frontend
- Date: 2026-06-19
- Status: Accepted
- Context:
  - The API exposed only summaries; a rich UI needs the per-play trace, browsable
    teams/players/rosters, and cross-origin access. None existed.
  - Rafael is a Python developer; the JS frontend should carry minimal maintenance.
- Decision:
  - Backend readiness (Phase 7.0):
    - `POST /simulate/game/play-by-play` returns the full deterministic trace (events,
      bases, outs, running score, line score) via `simulate_game_trace`.
    - Read-side `domain/catalog.py` (`CatalogRepository` + Postgres impl) behind a
      FastAPI dependency, serving `GET /teams`, `/teams/{id}/roster`, `/players/{id}`.
    - Migration `0003` persists `roster_memberships` (team→player per snapshot); the
      pipeline now keeps the roster link it already fetched, so rosters serve from the
      database without calling the external API at request time.
    - Configurable CORS (`BASEBALL_CORS_ALLOW_ORIGINS`) and an optional static mount
      serving `frontend/dist` so one process can host API + UI in production.
  - Frontend (Phase 7.1): React + Vite + TypeScript + Tailwind in `frontend/`. The
    typed API client is generated from the backend OpenAPI (`openapi-typescript` +
    `openapi-fetch`) so the contract cannot drift. A live game viewer (scoreboard,
    animated diamond, color-coded play-by-play ticker, line score, play-through
    controls) consumes the play-by-play endpoint and needs no database.
- Consequences:
  - The UI builds on a stable, typed contract; the viewer runs offline (synthetic).
  - Roster serving is snapshot-consistent, preserving the determinism contract.
  - A JS toolchain now lives in the repo, but generated types keep hand-maintenance low.
- Alternatives considered:
  - Enhancing the Textual TUI (aesthetic ceiling) or a desktop app (packaging cost).
  - Hand-written API types (drift risk); live MLB roster fetch at serve time (breaks
    the snapshot/determinism contract).

## ADR-016: Batter Attribution via Layered Lineup Providers
- Date: 2026-06-19
- Status: Accepted
- Context:
  - The simulator modeled offense at team level; plays were not attributed to a batter,
    which limits the viewer's realism and future box-score features.
- Decision:
  - Thread an ordered lineup through the simulator. Each plate appearance names the
    current batter; the 1-9 order persists across innings. Attribution is pure
    labeling and never touches the RNG, so seeded games stay byte-for-byte reproducible.
  - Resolve lineups with a layered `LineupProvider`: real names from the persisted
    roster (`CatalogLineupProvider`) with a per-team synthetic fallback; the simulator
    defaults to a deterministic synthetic lineup when none is supplied.
- Consequences:
  - The viewer shows batter names with no behavior change to outcomes.
  - Pitcher attribution remains future work (defense is still team-level).
- Alternatives considered:
  - Synthetic-only attribution (no real names) or real-only (breaks offline runs).

## ADR-017: Viewer Visual System — Theme Tokens, Club Colors, Baseline Win Probability
- Date: 2026-09-05
- Status: Accepted
- Context:
  - The live viewer worked but read as a neutral log beside a scoreboard: no club
    identity, a static wireframe diamond, a play stream dominated by identical OUT rows,
    and linear-only playback even though the whole game is already client-side and
    deterministic.
- Decision:
  - Theme: semantic design tokens (`--color-surface`, `--color-ink`, `--color-line`…)
    defined once and redefined under `[data-theme="dark"]` and `prefers-color-scheme`.
    Components only use token utilities, so no `dark:` variants appear in component code
    and a theme change is a token edit. An inline script applies the stored/system theme
    before first paint.
  - Club colors: official primary/secondary per club, resolved against surface luminance
    at render time, plus matchup disambiguation that falls back to a club's secondary
    (then a neutral) when two clubs are perceptually too close — several clubs share a
    near-identical navy or red, which otherwise made the scoreboard and win-probability
    bar unreadable.
  - Timeline: a draggable scrubber over the in-memory play list, ticks weighted and
    coloured by event. Deterministic replay makes random access free, so the game becomes
    explorable rather than merely watchable.
  - Shareable replay: matchup and seed live in the URL and auto-simulate on load, so a
    replay link needs no server state at all.
  - Win probability: a documented baseline (simplified RE24 plus league scoring rate,
    with sigma shrinking as outs run out), labelled "baseline" in the UI.
- Consequences:
  - Every matchup stays legible regardless of club color collisions.
  - Replay links work with no database, ahead of persisted simulation runs.
  - Win probability is explainable but uncalibrated; it must never be presented as a
    forecast, and stays labelled as a baseline (ADR-004).
- Alternatives considered:
  - `dark:` utility variants throughout (churn in every component, easy to miss cases).
  - Club primary colors unconditionally (navy-on-navy matchups became unreadable).
  - Reusing `/predict/game` for win probability: it is seed-hashed team strength and not
    situational, so it would not move during a game.

## ADR-018: Batting Order Derived from Season wOBA
- Date: 2026-09-05
- Status: Accepted
- Context:
  - With real rosters ingested, `lineup_from_roster` took the first nine non-pitchers
    from a roster query ordered by `full_name`, so the batting order was alphabetical:
    Francisco Lindor batted eighth because of his initial. Harmless with synthetic
    names, clearly wrong once the viewer showed real players.
- Decision:
  - Order the batting lineup by ingested season wOBA, best hitter first.
  - Keep the ordering in Python (`lineup_from_roster`) and have the database only
    supply data (`CatalogRepository.get_batting_woba`), so the rule is unit-testable
    without a database.
  - Players with no ingested wOBA sort last; ties break on name. The order is therefore
    fully determined by the data, preserving the reproducibility contract.
  - Pitchers remain excluded regardless of their hitting line.
- Consequences:
  - Lineups are materially more realistic and the best hitters get the most plate
    appearances, which also makes run production respond to real team quality.
  - This is an explainable heuristic, not a manager's card: it ignores speed,
    handedness splits, defense and platoon usage. It must not be presented as a
    predicted real lineup.
  - Teams without ingested hitting stats fall back to the synthetic lineup unchanged.
- Alternatives considered:
  - Sorting in SQL (moves a modeling rule into the query and out of reach of tests).
  - A fuller lineup-construction model (speed at the top, power in the middle) — worth
    revisiting, but ADR-004 favours the explainable baseline first.

## ADR-019: Analyze Data Foundations Before Dashboard Screens
- Date: 2026-09-05
- Status: Accepted
- Context:
  - The web interface grows into three sections (Game / Analyze / Explore). Before
    drawing dashboard screens, the serving API had gaps that would have forced the UI
    to either invent data or present seeded placeholders as measurements.
- Decision:
  - Report provenance per metric (`MetricSource`), not only in a summary string, so a
    client can visibly separate ingested values from seeded ones.
  - Add `GET /stats/leaders` with an explicit playing-time qualifier and a `direction`
    field, so clients never hardcode which way a metric points (FIP is lower-better).
  - Add `GET /teams/{id}/profile` returning the simulator's seven factors plus the
    aggregate inputs behind them (team wOBA/FIP, players counted) and a `source` label,
    so a team rating can be audited rather than taken on faith.
  - Keep leaderboard metric names mapped through a fixed table to SQL identifiers;
    request input is never interpolated into a query.
  - Do **not** surface `POST /predict/game` in the dashboard yet: it is still a hash of
    the seed and is not situational, so featuring it would present invented numbers as
    analysis. It needs rebuilding on the stats provider first.
- Consequences:
  - The dashboard can be built without a single fabricated number, and every displayed
    value can state where it came from.
  - `xwoba` is reported as synthetic everywhere until Statcast is ingested, which keeps
    that gap visible instead of hidden.
- Alternatives considered:
  - Building screens first and retrofitting provenance (the UI would have shipped with
    seeded values presented as real).
  - Computing leaderboards client-side from a bulk stats dump (heavy, and it moves
    qualification rules out of one auditable place).

## ADR-020: One Win-Probability Model, Server-Side
- Date: 2026-09-06
- Status: Accepted
- Context:
  - The product shipped two unrelated win-probability implementations. The viewer
    computed its own baseline in the browser from score, inning, outs and base state,
    while `/predict/game` derived team strength by hashing the seed. They disagreed on
    the same matchup, and neither was complete: the viewer's model ignored team quality
    entirely, so a tied first inning read 0.50 whether it was the best club against the
    worst or the reverse; predict ignored game state and was not grounded in any data.
- Decision:
  - Build a single model in `sim/winprob.py` that combines both halves: team quality
    becomes an expected runs-per-game rate from the matchup profiles, and game state
    adds the current score, the outs remaining and the base/out run expectancy. A
    pregame forecast is simply the case with no state.
  - Carry the resulting probability on every play in the play-by-play response, so the
    viewer renders a number it does not compute. The browser copy is deleted rather
    than kept in sync.
  - Rebuild `predict_game` on the stats provider and report `source` plus the run rates
    behind the number, so the forecast can be audited.
  - Determine `source` by comparing each club's profile against its seeded one: a
    provider can still fall back per club, so supplying a provider is not proof that the
    answer is grounded. It is reported `real` only when both clubs came from data.
- Consequences:
  - Both surfaces agree, and the seed no longer influences team quality when real stats
    are available — the same matchup forecasts identically at any seed.
  - The constants are documented starting values, not fitted ones. Widening the run-rate
    band to match the observed league spread moved a best-versus-worst matchup from 57%
    to 65%, which is the right order of magnitude; ADR-004 requires that the rest be
    measured rather than hand-tuned, which is the next step.
- Alternatives considered:
  - Keeping the browser model and calling the API per play (85 requests to draw one game).
  - Leaving predict as it was and labelling it (it is a public endpoint shaped like
    analysis; a label does not make an invented number useful).

---

## ADR-021: Range Factor as a League-Relative, Position-Normalized Rate
- Date: 2026-09-06
- Status: Accepted
- Context:
  - `range_factor` was the last of the simulator's seven factors still pinned to a
    neutral 0.5 for every club. Fielding turned out to cost nothing extra to ingest:
    the same `/people/{id}/stats` endpoint serves `group=fielding`, returning one split
    per position played.
  - A raw range factor (plays made per nine innings) is not comparable across
    positions: a first baseman is around 8.1 and a third baseman around 2.4, so a club
    that happens to play its innings at putout-heavy positions would look rangy for
    reasons that have nothing to do with defense.
- Decision:
  - Store fielding in its own table, `player_season_fielding`, keyed by position: the
    API reports one split per position, so a utility player is several rows and
    position has to be part of the key. Reusing `player_season_stats` would have needed
    a wider key and a column set that means nothing for hitters.
  - Compute the league baseline per position from the ingested league itself
    (`league_range_factors`) rather than hardcoding it, so it moves with the data.
  - Express a club as `relative_range`: its plays made against what the league makes at
    the same positions, weighted by innings, then mapped through a documented ±12% band
    into `[0, 1]`. Splits under `MIN_TEAM_FIELDING_INNINGS` (20) are cameos and are
    dropped, the same shape of floor ADR-019 established for batting and pitching.
  - Recompute the rates from the counting stats instead of parsing them: a designated
    hitter appears in this payload with zero innings and a literal `"-.--"` range
    factor. Those entries are dropped rather than stored as a position with no range.
  - Report `fielders_counted` on the team profile, and render a dash rather than 0.50
    where it is zero: the neutral value is a placeholder, not a measurement, and the
    table must not present the two identically.
- Consequences:
  - Range now spreads from 0.31 to 0.77 across the thirty clubs, all thirty distinct,
    on real 2026 data — the factor carries information instead of cancelling out.
  - Pitchers are not asked for fielding: their own defense is a rounding error on team
    range, and skipping them keeps the request count down. A declared two-way player
    still is, and contributed the single `P` split in the league (0.0% of counted
    innings, so it neither distorts nor helps).
  - Determinism goldens needed no refresh after all. The plan assumed activating the
    factor would move seeded output, but the seeded path builds its profile from
    hashes and never touches these lines; only runs served from Postgres change.
- Alternatives considered:
  - A hardcoded league baseline per position (drifts away from the data, and would have
    to be revised every season).
  - Defensive Runs Saved or UZR (better metrics, but neither is in this API; they would
    reopen the licensing question ADR-003 defers to Statcast).

---

## ADR-022: The Newest Snapshot Wins When Reading a Season
- Date: 2026-09-06
- Status: Accepted
- Context:
  - `player_season_stats` is keyed by `(player_id, season, source_snapshot_id,
    stat_group)`, so every ingestion run appends a fresh row per player rather than
    replacing the previous one — by design, since ADR-007 keeps snapshots immutable.
  - The serving provider read the season with no snapshot filter and appended every row
    into the club's aggregate. With two snapshots ingested, thirty clubs were each
    built from roughly twice their real roster. The distortion hid well: every factor
    is a ratio, so duplicating an unchanged line cancels out exactly. It only bites
    when the two snapshots differ — which is precisely what a re-ingest produces, an
    April line summed alongside September's.
  - The catalog repository already did this correctly with `DISTINCT ON`; the provider
    path did not, and nothing tested the disagreement.
- Decision:
  - Deduplicate on read in both paths: the newest row per `(player, stat_group)`, and
    per `(player, position)` for fielding. Aggregates are built from the deduplicated
    lines, never from the raw rows.
- Consequences:
  - Re-ingesting a season is now idempotent from the serving side, which it has to be:
    Step 5 required a re-ingest, and every later step will too.
  - Snapshots stay immutable and fully queryable for lineage; the collapse happens at
    read time, where it belongs.
- Alternatives considered:
  - Upserting over the previous snapshot's row (destroys the audit trail ADR-007 exists
    to protect).
  - Filtering to a single snapshot id per season (a run can legitimately span more than
    one, and a player traded mid-season would vanish).

---

## ADR-023: Pitcher Attribution — Rotation by Match, Outings from Each Pitcher's Season
- Date: 2026-09-06
- Status: Accepted
- Context:
  - ADR-018 gave every plate appearance a batter. The other half of the matchup was
    still anonymous: no play named who threw it, so a box score could not credit a
    pitcher and the play-by-play read as if nobody were on the mound.
  - Like batting-order attribution, this has to be pure labeling. If naming the pitcher
    consumed the RNG or changed an outcome, every seeded game in the repository would
    move and the determinism guarantee would be gone.
- Decision:
  - Model a staff as a five-man rotation plus a bullpen. The starter is chosen by
    rotation slot derived from the match id, so a given matchup always opens with the
    same arm and a series turns over like a real rotation, without the simulator
    needing a schedule it does not have.
  - Give each pitcher his own outing length from his own season — innings over starts
    for a rotation arm, innings over appearances for a reliever — rather than one
    league-wide constant. A horse and a five-and-dive starter are not the same pitcher,
    and the ingested data already says which is which.
  - Guard that ratio. A season reports one innings total, not one per role, so for a
    swingman it is unreadable: Sean Manaea's 128 innings over 15 starts and 14 relief
    outings computes to an eight-and-a-half-inning starter. Below `MIN_ROLE_SHARE`
    (70% of appearances in the role) the league shape is used instead of a number the
    data cannot support — the same choice made everywhere else in this codebase when a
    measurement is not actually there.
  - Order the bullpen worst FIP first, which is roughly how a pen is spent: middle
    relief early, the best arm saved for the end.
  - When the pen is spent, the last arm finishes the game. A real manager would be out
    of options too, and a twentieth inning must still be attributed rather than fail.
  - Read the mound *before* applying the play. The out that ends an outing belongs to
    the pitcher who recorded it, not to the reliever who has not thrown a pitch yet.
- Consequences:
  - Play-by-play names both halves of every matchup, and the viewer shows who the
    batter is facing. Seeded games are unchanged: a test asserts that supplying a staff
    leaves the result and every event identical.
  - The relief model is deliberately naive — a starter leaves on outs recorded, not on
    runs allowed or on the leverage of the moment. It is explainable and it is honest
    about what it is; ADR-004 requires the rest be measured rather than hand-tuned.
  - Attribution is only as good as the roster. A club with fewer than six ingested arms
    falls back to the synthetic staff rather than fielding a two-man pen.
- Alternatives considered:
  - Fixed innings per starter from the ruleset (simpler, but simulates every club's ace
    and its fifth starter as the same pitcher when the data distinguishes them).
  - Pulling the starter on runs allowed (closer to a real manager, but adds constants
    to calibrate that no ingested data supports yet).
  - Always starting the best arm by FIP (inflates every club's pitching across a
    simulated season).

---

## ADR-024: Statcast Expected Stats Come From the Stats API, Not Baseball Savant
- Date: 2026-09-07
- Status: Accepted (revises ADR-003)
- Context:
  - ADR-003 assumed expected metrics would need Baseball Savant exports: a second
    source, a second client, a second schema, and a licensing review before any of it.
    That assumption was never tested; it was made before the Stats API was explored.
  - `xwoba` had a column since migration 0001 and a slot in the compare metric set, but
    no source. It was the last metric the UI had to label "seeded".
  - Checking `/api/v1/statTypes` shows `expectedStatistics` among the 61 available
    types. It returns `woba`, `avg`, `slg` and `wobaCon` for a player-season, and it
    works for both the hitting and the pitching group.
- Decision:
  - Take expected stats from the endpoint already in use. No Savant client, no second
    source, no new schema beyond three columns beside the `xwoba` that already existed.
  - Model the request as a second *stat type* over the same group rather than a new
    group: `stat_requests_for` now returns `(group, stat_type)` pairs. Fielding has no
    expected view, so it gets none. The whole thing can be switched off for a run that
    only wants the counting lines — it is roughly a third more requests.
  - Serve `xwoba` only from the **hitting** row. The pitching row carries xwOBA
    *against*, where a low number is elite, and the compare table ranks this metric
    higher-is-better: feeding a pitcher's value in would rank an ace below a
    replacement bat on a metric meant to describe hitting. The pitching value is still
    stored — it belongs with the prevention metrics, not here.
  - Store the expected values as they arrive rather than deriving them. They are
    measurements of batted-ball quality, not formulas we can evaluate; that is exactly
    why `xwoba` could never be computed like the other four compare metrics.
- Consequences:
  - 100% coverage on the ingested season: 419 of 419 hitting rows and 418 of 418
    pitching rows carry an expected line. Compare now reports three measured metrics
    for a hitter instead of two, and no metric in the product is seeded when the data
    is there.
  - ADR-003's Savant half is not wrong so much as unnecessary for this purpose. It
    would still be the source for pitch-level and batted-ball detail, which the Stats
    API does not expose. Nothing depends on it today.
- Alternatives considered:
  - Baseball Savant CSV exports, per ADR-003 (a whole source to maintain for four
    numbers that arrive from an endpoint we already call).
  - Approximating xwOBA from the counting line (it is not derivable from it; that is
    the entire point of the metric).

---

## ADR-025: MLBAM Terms Constrain Bulk and Commercial Use
- Date: 2026-09-07
- Status: Accepted
- Context:
  - ADR-003 listed "validate usage terms" as a consequence and never closed it. Every
    Stats API response carries a copyright line pointing at MLBAM's terms.
  - Those terms state that only "individual, non-commercial, non-bulk use" is
    permitted, and that anything else requires prior written authorization from MLBAM.
  - This matters now because the next things on the roadmap are precisely bulk: full
    career history for every rostered player, and club logos and player headshots.
- Decision:
  - Record the constraint rather than discover it later. The project stays a personal,
    non-commercial analysis tool; the commercial rollout mentioned in `plan.MD` would
    need authorization, and that is a business decision, not an engineering one.
  - Keep ingestion paced and bounded (the concurrency limiter already does this), and
    prefer requests that return more per call — `yearByYear` returns a full career in
    one request, which is both cheaper for us and lighter on the API.
  - Reference images by URL rather than copying them into our storage. The URLs are
    derivable from ids we already hold, so no column and no copy is needed, and we do
    not redistribute MLBAM's materials.
- Consequences:
  - The historical backfill is feasible technically and is a judgement call
    contractually. It is not blocked, but it is not something to run unattended.
  - Anything commercial requires a conversation with MLBAM first.
- Alternatives considered:
  - Ignoring the terms (not an option).
  - A paid consolidated data feed, as ADR-003 already considered — the answer if the
    project ever needs commercial footing.

---

## ADR-026: Cache Roster Reads Per Club, Not Per Call
- Date: 2026-09-07
- Status: Accepted
- Context:
  - The simulation engine is fast: 0.31 ms a game, a 2,430-game season in 0.7 s. But
    with real data a game cost 36 ms, because `CatalogLineupProvider` opened a
    connection inside `lineup()` and another inside `staff()`, and the API rebuilt the
    provider on every request. A simulated season spent 1.5 minutes on connections and
    one second simulating.
  - That ratio — a hundred times more time fetching than computing — is what stood
    between this engine and mass season simulation, which is the point of a
    deterministic simulator.
  - The reads do not depend on the seed. Only the synthetic fallback does. So the same
    roster was being fetched again for every game a club played.
- Decision:
  - Cache a club's roster, wOBA and pitcher workloads together in one `TeamRosterData`,
    read once per club per provider, and derive both the batting order and the staff
    from it. That also collapses the two round trips into one.
  - Cache the provider instance per `(dsn, season)`, as the stats provider already was.
    Without this the per-club cache would be discarded on every request.
  - Close the connection even though the data is kept. Caching a result must not mean
    holding a connection.
  - No lock. A concurrent miss recomputes equal data and the last write wins; a lock
    would cost more than the duplicated work it prevents.
  - Add `reset_provider_caches()` for the case this creates: a process that ingests and
    then serves within its own lifetime.
- Consequences:
  - 36 ms a game becomes 0.018 ms. A full season against real data — profiles,
    lineups, staffs and all — runs in **1.0 s**, down from about 1.5 minutes.
  - The live API benefits as much: the play-by-play endpoint went from 63 ms to 11 ms.
  - The cost is staleness. A long-running process serves the roster it first read until
    it is reset or restarted. That is already true of the stats provider, and for a
    season that only changes when ingestion runs it is the right trade — but it is a
    real behaviour change, not a free win.
- Alternatives considered:
  - A connection pool (helps the constant, not the fact that the same roster was being
    fetched thousands of times).
  - A TTL cache (adds a tuning knob to a thing that changes only when we run ingestion).
  - Passing rosters in from the caller (pushes the problem to every call site and makes
    the API endpoint assemble what the provider exists to assemble).

---

## ADR-027: Season Simulation Over the Real Schedule, With the Spread Reported
- Date: 2026-09-07
- Status: Accepted
- Context:
  - A deterministic engine that can only play one game at a time cannot answer the
    questions people actually have about a season. ADR-026 removed the data-access
    cost that made this impractical.
  - A single simulated standings table invites over-reading. Baseball over 162 games
    produces large gaps from luck alone, and a table with no spread attached to it
    looks far more conclusive than it is.
- Decision:
  - Play the **real ingested schedule** rather than a generated round robin. It is
    already in the database, it carries the actual matchup structure, and it keeps the
    door open to scoring a simulated season against what really happened.
  - Resolve each club's profile, lineup and staff **once per season**, not per game. A
    club is the same club in April and September.
  - Derive each game's seed from `(season_seed, game_pk)` through the shared mix.
    Position-based seeds would make a filtered schedule replay differently, and an
    additive seed would make separate seasons overlap — a thousand samples that are
    really a few hundred, reporting a spread that is too narrow.
  - Skip a club with no profile rather than falling back to a hashed one. Everywhere
    else in this codebase a missing measurement stays visibly missing; a standings
    table is the worst possible place to break that rule.
  - Ship `--seasons N`, and report percentiles beside the mean. The projection is the
    point, not a nicety.
- Consequences:
  - A 2,166-game season runs in 0.5 s; 200 seasons in about 100 s.
  - The first run produced a finding (`docs/season_simulation.md`): the per-club noise
    matches the binomial floor exactly, so the randomness is right, but the systematic
    spread between clubs is 51 wins where real baseball manages about 40 including
    luck. The factor-to-outcome mapping is too aggressive. That is now a measurement
    rather than a suspicion, which is what ADR-004 asks for before tuning anything.
- Alternatives considered:
  - A generated balanced schedule (loses the real matchup structure and the ability to
    compare against actual results, for no benefit while the real one is ingested).
  - Reporting only a single season (the number people would quote is precisely the one
    the spread shows is unquotable).

---

## ADR-028: The Ruleset Owns the Event Model, and a Run Keeps the Ruleset It Was Played Under
- Date: 2026-09-07
- Status: Accepted
- Context:
  - Season simulation measured the model's spread (ADR-027) and found it 1.43x too
    wide. Fixing that means changing the constants inside `_event_probabilities`.
  - Those constants were compiled into the engine. Changing them would silently change
    every stored run: `/games/{match_id}` hands the saved context back to the
    simulator, which is only a faithful replay while the rules have not moved. A
    retune would have made old replays produce a different game and still present it
    as the original.
  - This will not be the last retune. A fix that only covers this one is not a fix.
- Decision:
  - Lift every constant that turns two profiles into plate-appearance probabilities
    into an `EventModel` on the `SimulationRuleset`: the attack and prevention weights,
    and per outcome its league base, its sensitivity to the matchup, its bounds and its
    home-field share. The engine reads them; it no longer holds them.
  - Store the serialized ruleset with each run, and replay through a new endpoint,
    `GET /games/{match_id}/play-by-play`, that plays it under its own rules.
  - Refuse — 409, not a silent fallback — to replay a run recorded before the ruleset
    was stored. It cannot be honoured, and a replay that quietly uses today's rules
    while claiming to be the original is worse than no replay.
  - Record the current constants as goldens first (`tests/data/event_model_golden.json`,
    100 games across even, lopsided and extreme matchups) and assert the refactor left
    them untouched. Moving where numbers live must not move what they produce, and
    that claim should be checkable rather than asserted.
  - `ruleset_from_payload` tolerates a missing field by falling back to its default. A
    run recorded before a field existed was played under that default, so the default
    is what reproduces it; refusing to parse would lose the replay for no gain.
- Consequences:
  - Retuning the model is now a new ruleset rather than an edit to the engine, and the
    `ruleset_checksum` already folds into `match_id`, so a retuned model produces new
    identities instead of colliding with old ones.
  - The API guarantee is in place before the retune that needs it. The web viewer does
    **not** use it yet — its replay route still re-simulates through the normal
    endpoint under the current ruleset. That is a tracked gap, not a finished feature.
  - The event model is now data, which means an invalid one is possible; `_validate_event_model`
    rejects bounds that are inverted, outside `[0, 1]`, or that exclude their own base.
- Alternatives considered:
  - Editing the constants and clearing `simulation_runs` (works once, then the next
    retune poses the identical problem).
  - Constants in the ruleset without storing it per run (the checksum would mark old
    runs as different, but replaying one would still use today's rules).

---

## ADR-029: The Event Model Is Fitted, Not Chosen
- Date: 2026-09-07
- Status: Accepted
- Context:
  - ADR-020 recorded the engine's constants as documented starting points. ADR-027
    measured what they were worth: per-club noise matched the binomial floor exactly,
    but the systematic spread between clubs was 1.43x too wide, and the league run
    environment was 4.14 runs a game against a real 4.479.
  - ADR-028 made retuning safe by moving the model into the ruleset and storing the
    ruleset with each run.
- Decision:
  - Fit rather than choose. `eval/fit_event_model.py` measures both targets from the
    ingested games and sweeps two knobs against them, and the shipped ruleset is
    generated from its output rather than typed by hand.
  - Take the talent target with binomial luck removed in quadrature. The observed
    spread across real clubs is talent and luck together; the model's spread, averaged
    over many seasons, is talent alone. Fitting one to the other directly would ask the
    model to manufacture noise as if it were skill — the exact error ADR-027 was
    written to prevent.
  - Two knobs, not one, because the two defects are close to independent: sensitivity
    moves the spread, the out base moves the run environment. Fitting sensitivity first
    keeps the two searches from chasing each other.
  - Scale each outcome's bounds along with its sensitivity. A clamp sized for the old
    sensitivity bites at the wrong place under the new one and silently undoes part of
    the fit at the extremes, which is where lopsided matchups live.
  - Ship it as a new ruleset (`mlb_2026_fitted.json`) and leave the unfitted one in
    place. Editing it would have changed what its recorded runs mean.
  - A coarse grid, not an optimizer. With two nearly independent knobs and targets
    known to a few percent, a finer search would be false precision.
- Consequences:
  - Runs per game 4.141 → 4.458 against a target of 4.479; talent spread 0.0659 →
    0.0481 against 0.0457. The single-season win% range narrows from .269–.667 to
    .331–.618, against a real .378–.611.
  - This is fitted **in sample**, on the same season it is measured against, exactly as
    `docs/calibration.md` already warns about the win-probability check. It removes a
    known bias; it does not demonstrate forecasting skill. A second season of ingested
    games would make it testable out of sample.
  - The remaining constants — the attack and prevention weights, and which matchup term
    drives which outcome — are still unfitted. They are shape rather than scale, and
    nothing yet measures them.
- Alternatives considered:
  - Hand-tuning until the standings looked plausible (what ADR-004 exists to prevent).
  - Fitting to the observed spread without removing luck (would have left the model
    about 35% too wide while appearing to match).
  - Narrowing the normalization bands in `profiles.py` instead. Measured and rejected:
    the offense factor spans 0.193–0.689 across real clubs, which maps a real team wOBA
    range of .304–.338 onto half of `[0, 1]`. The bands are reasonable; the
    amplification was downstream.

---

## ADR-030: Keep Every Split, and Ingest Whole Careers
- Date: 2026-09-07
- Status: Accepted
- Context:
  - The parser kept only the first split of each stat group. The MLB Stats API leads
    with the **season total**, whose team is null, so a traded player was stored with
    no team — and the serving layer only aggregates rows that carry one. Every traded
    player therefore counted toward no club's profile at all. It looked like working
    data; it was a silent hole.
  - Separately, `yearByYear` returns a player's whole career in a single request. A
    full backfill costs the same number of requests as one season, which makes the
    history question a schema question rather than a budget one.
- Decision:
  - Keep **every** split. A traded player yields a row per club plus the season total,
    because the two answer different questions: a club's profile wants his line with
    that club, while a leaderboard and a player rating want his year.
  - Put the team in the key. It stays nullable, since NULL is meaningful — it *is* the
    season total — so the key becomes a unique index over `COALESCE(team_id, 0)`
    rather than a primary key. Team id 0 does not exist in the API, so it cannot
    collide with a club.
  - Make every read say which one it wants. Player-level reads order by
    `team_id IS NULL DESC` to prefer the total, falling back to the single club row for
    a player who was never traded. Club-level reads filter to rows that carry a team.
    A club is never credited with the total, which would count a traded player twice.
  - Read the season from each split rather than from the request. A career arrives in
    one payload; stamping it with the requested season would collapse a decade onto one
    year. Expected (Statcast) stats have no year-by-year view, so they stay pinned to
    the requested season and are not attached to older lines.
  - Ship history behind `--history` rather than making it the default. It writes a row
    per season per club, and MLBAM's terms (ADR-025) make a bulk backfill a deliberate
    act rather than a routine one.
- Consequences:
  - The current season went from 837 stat rows to 1,064: 109 season totals for traded
    players and 955 club lines. Verified that a club's rows sum exactly to the total.
  - The backfill produced 9,495 stat rows over 19 seasons (2008-2026) and 8,051
    fielding rows, in under a minute and under 4 MB. Max Scherzer carries 19 seasons.
  - A player's page can now show any season he has, and the API reports
    `available_seasons` so a client does not have to guess. A player whose career ended
    before the configured season lands on his last one instead of looking empty.
  - Mutation testing found a real gap while checking this: the fielding parser's
    multi-split handling had no test with teeth, so a utility player silently losing a
    position would not have been caught. Now covered.
- Alternatives considered:
  - Storing only per-club splits and deriving the total by summing (correct
    arithmetically, but every player-level read would have to aggregate, and a player
    with no club-bearing split would vanish).
  - Storing only the total, as before (the status quo, which is the bug).
  - A sentinel team id in a real primary key (readable in the schema, but it puts a
    fake club in the data itself rather than only in the index expression).

---

## Change Log
- 2026-09-07: Leaders can be narrowed to a club and to a past season, with the
  backfill's coverage limit stated on the board rather than left to be inferred.
- 2026-09-07: Player search reaches Explore, and the viewer's club pickers became
  keyboard-accessible comboboxes that match on abbreviation.
- 2026-09-07: Added a player search endpoint with accent-insensitive matching, and
  replaced Compare's club-then-roster cascade with it.
- 2026-09-07: Compare caught up with the rest — identities from the season endpoint,
  headshots and club marks, a season selector over the ingested history, and the
  descriptive stat line shown apart from the five scored metrics.
- 2026-09-07: Added a season-by-season career table with server-computed totals, and
  collapsed the career chart behind it.
- 2026-09-07: Served the widened metrics and added career trajectory charts — the
  ingested history and the stored-but-unserved metrics both reach the UI.
- 2026-09-07: Added ADR-030; every stat split is kept, so traded players count toward
  their clubs, and `--history` backfills whole careers.
- 2026-09-07: Closed ADR-028's open gap — the web replay route now uses the faithful
  replay endpoint, and club logos and player headshots are referenced per ADR-025.
- 2026-09-07: Added ADR-029; the event model is fitted against the ingested season
  instead of chosen, and ships as its own ruleset.
- 2026-09-07: Added ADR-028; the event model moved into the ruleset and every run now
  stores the ruleset it was played under, so retuning cannot rewrite an old replay.
- 2026-09-07: Added ADR-027; season simulation over the real schedule with a
  projection mode, and the first season-level measurement of the model's spread.
- 2026-09-07: Added ADR-026; roster reads cached per club, making a full simulated
  season with real data run in a second instead of a minute and a half.
- 2026-09-07: Added ADR-024 and ADR-025; Statcast expected stats come from the Stats
  API rather than Baseball Savant, and MLBAM's bulk/commercial terms are recorded.
- 2026-09-06: Added ADR-023; every play now names the pitcher who threw it, with the
  rotation chosen by match id and outing lengths taken from each pitcher's season.
- 2026-09-06: Added ADR-021 and ADR-022; fielding ingested and mapped onto a
  league-relative range factor, and season reads now collapse to the newest snapshot.
- 2026-09-06: Added ADR-020; one win-probability model, server-side, with predict
  rebuilt on real team profiles.
- 2026-09-05: Added ADR-019; Analyze data foundations (per-metric provenance,
  leaderboards, team profile endpoint) landed before dashboard screens.
- 2026-09-05: Added ADR-018; batting order now derives from season wOBA.
- 2026-09-05: Added ADR-017; viewer visual system (theme tokens, club colors, scrubber,
  shareable replay URLs, baseline win probability, box score).
- 2026-06-19: Added ADR-016; batter attribution via layered lineup providers.
- 2026-06-19: Added ADR-015; web-interface backend readiness (play-by-play, catalog
  endpoints, roster-membership persistence, CORS) and the React live game viewer.
- 2026-06-19: Added ADR-014; wired real sabermetrics into compare/simulate via the
  stats provider seam; CI now triggers on `master`.
- 2026-02-22: Initialized ADR records for project kickoff.
- 2026-02-22: Added ADR-006 and scaffolded initial deterministic API and database baseline.
- 2026-02-22: Added ADR-007 for content-addressed immutable snapshot storage.
- 2026-02-22: Added ADR-008 for migration runner and bounded ingestion retries.
- 2026-02-22: Added ADR-009 for the deterministic plate-appearance state-machine simulator.
- 2026-02-22: Added ADR-010 for CLI watch mode, deterministic match IDs, and roster seeder fallback.
- 2026-02-22: Added ADR-011 for ruleset-driven simulator configuration.
- 2026-02-22: Added ADR-012 for play-trace output and CLI watch logging format.
- 2026-02-22: Added ADR-013 for API-first CLI roster loading with deterministic seeded fallback.
