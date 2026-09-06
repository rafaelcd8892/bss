# plan.MD

## Planning Log
- Last updated: 2026-09-05
- Owner: Rafael + coding agents
- Project status: Real sabermetrics feed compare + the simulator (stats-provider seam);
  Phase 7.1 live game viewer is feature-complete on synthetic data — club identity,
  themes, scrubbable timeline, shareable replays, baseline win probability.

## Resume Here (next session)
Done 2026-06-19: real sabermetrics seam (ADR-014); CI fix (`master`); play-by-play API;
catalog endpoints + roster-membership persistence (migration 0003); CORS + static
serving; React live game viewer (`frontend/`); batter attribution (ADR-015, ADR-016).
Done 2026-09-05: viewer visual system (ADR-017) — light/dark theme tokens with toggle,
official club colors with contrast + matchup disambiguation, ballpark field with animated
bases, out-streak collapsing in the play log, draggable event-coloured scrubber, shareable
replay URLs, baseline win probability, final box score with standouts, team pickers.
Suite: 82 tests, ruff + mypy --strict clean; frontend `npm run build` clean.

Done 2026-09-05 (later): local Postgres 18 + `baseball` DB, migrations 0001-0003, real
ingest (30 teams / 840 players / 934 stat rows / 70 games), `stats_source=postgres`
verified end to end; ingestion concurrency bounded (ADR none, see commit); batting order
now ordered by real season wOBA (ADR-018); tests made hermetic against a local `.env`.

Open items, recommended order:
1. Persist `simulation_runs` + `GET /games/{match_id}`; front `/replay/{match_id}` route.
   (URL-based replay already works without a database; this adds history + snapshot ids.)
3. Dashboard (Phase 7.2): compare + predict views over real sabermetrics, with charts.
4. Pitcher attribution (simulator models defense at team level only today).
5. Data depth: ingest fielding (→ `range_factor`) and Statcast xwOBA; ephemeral-PG
   integration test for the Postgres stats/catalog paths.
6. Viewer polish: runner motion along the basepath, mobile layout (<720px) review.
Run locally: `uvicorn baseball_sim.main:app --port 8000` + `cd frontend && npm run dev`
(or `preview_start` the `app` and `web` configs in `.claude/launch.json`).

## North Star
Create a deterministic, scalable baseball simulator and sabermetrics intelligence platform that supports:
- Player and team comparisons.
- Game and season simulation.
- Outcome prediction with explainable models.

## Product Goals (v1)
1. Reliable MLB data ingestion.
2. Deterministic simulation engine.
3. Player and team comparison API.
4. Baseline predictive models with calibration.
5. Simple UI or API-first workflow for analysts.
6. CLI live-watch simulator with persistent play logs and deterministic match seeds.

## Success Criteria
- Same request + same `seed` + same `model_version` + same `data_snapshot_id` returns identical results.
- Daily ingestion SLA >= 99% successful runs.
- Feature freshness lag < 24 hours for scheduled updates.
- Prediction calibration error tracked and documented each release.
- P95 API latency under target budget for compare and predict endpoints.

## Phase Plan

### Phase 0: Foundation (Week 1)
- [x] Initialize repo structure and tooling.
- [x] Set up FastAPI service skeleton.
- [x] Set up PostgreSQL schema baseline.
- [x] Set up linting, type checks, and test harness.
- [x] Define deterministic simulation contract (`seed`, versions, snapshots).

Exit criteria:
- Minimal service runs locally.
- CI checks run on every change.

### Phase 1: Data Ingestion and Modeling Surface (Weeks 2-3)
- [x] Implement ingestion clients for MLB Stats API entities.
- [x] Define canonical data model for players, teams, games, events.
- [x] Add raw-to-normalized pipeline with schema versioning.
- [x] Add contract tests for external API response shape.
- [ ] Add scheduled ingestion workflow (Airflow or equivalent).

Exit criteria:
- Historical and daily ingest produce reproducible snapshots.

### Phase 2: Sabermetrics Core (Weeks 3-5)
- [x] Implement metric computation service (wOBA, xwOBA-derived features, wRC+ baseline, FIP family baseline).
- [x] Compute metrics from real ingested stats (`sim/sabermetrics.py`) and wire into compare/simulator via a stats-provider seam with synthetic fallback.
- [ ] Add context adjustments (park, handedness, season context).
- [x] Build compare endpoints for player and team analysis.
- [x] Add explanation payloads for metric differences.

Exit criteria:
- Compare APIs return deterministic, auditable metric breakdowns.

### Phase 3: Deterministic Simulator (Weeks 5-7)
- [x] Design simulator state machine and event transition model.
- [x] Implement seeded RNG strategy and deterministic execution harness.
- [x] Make simulator ruleset config-driven for easier rule evolution.
- [x] Add simulation endpoints for single game and batch scenarios.
- [x] Build golden tests with fixed seeds and snapshots.

Exit criteria:
- Simulator reproduces exact outputs under repeated runs.

### Phase 4: Prediction Layer (Weeks 7-9)
- [x] Build baseline win-probability model and projection model.
- [ ] Add calibration and drift monitoring outputs.
- [ ] Register model versions and inference metadata.
- [x] Add prediction endpoint with confidence payload.

Exit criteria:
- Production-ready prediction API with tracked model lineage.

### Phase 5: Scale and Operations (Weeks 9+)
- [ ] Introduce Redis caching strategy for hot queries.
- [ ] Add queue/backpressure controls for heavy simulation workloads.
- [ ] Add observability (metrics, traces, error budgets).
- [ ] Load-test critical APIs and optimize bottlenecks.

Exit criteria:
- System supports concurrent workloads with stable latency and reliability.

### Phase 6: CLI Broadcast Simulator (Weeks 3-6, parallel track)
- [x] Build terminal scoreboard view (inning, outs, count summary, score by inning).
- [x] Render lineup cards for both teams and active batter/pitcher indicators.
- [x] Render field/turf panel with defensive positions and base occupancy.
- [x] Implement paced play-by-play stream with configurable delay and pause/resume.
- [x] Add deterministic match identifier and seed registry for replayability.
- [x] Persist full play logs to disk (JSONL) and summarized box report (JSON).
- [x] Build Textual TUI (`cli.tui`) with 3-panel layout, color-coded play log, and keyboard controls.
- [ ] Add CLI commands to replay logged games from stored seed and snapshot metadata.
- [x] Add roster seeder to generate synthetic players when API/player data is missing.
- [x] Wire API roster loading with deterministic seeded fallback for missing/inaccessible data.
- [ ] Add DB roster source between API and deterministic seeded fallback.

Exit criteria:
- User can watch full simulated games in terminal with live updates and pauses.
- Every simulated match can be replayed exactly from saved seed + context.
- Logs are queryable and reusable for debugging and analytics.

## Active Backlog (Next 10 Tasks)
1. [x] Create base directory layout (`src`, `tests`, `docs`).
2. [x] Bootstrap FastAPI app with health endpoint.
3. [x] Define initial PostgreSQL schema and migrations setup.
4. [x] Add config management for environment and deterministic runtime flags.
5. [x] Implement first MLB Stats API ingestion client.
6. [x] Create raw payload storage strategy and naming conventions.
7. [x] Add first canonical tables (`players`, `teams`, `games`).
8. [x] Implement first compare endpoint scaffold.
9. [x] Add deterministic test utilities (seed fixtures, snapshot IDs).
10. [x] Create CI workflow for tests and linting.

## Upcoming Backlog (Next 10 Tasks)
1. [ ] Add scheduled ingestion workflow (Airflow DAG + daily trigger).
2. [ ] Add migration integration test against ephemeral PostgreSQL.
3. [x] Add CLI broadcast command (`simulate watch`) with pause/resume controls.
4. [x] Implement persistent play log writer (`game_logs/*.jsonl`).
5. [x] Define and store deterministic match IDs mapped to seeds.
6. [x] Add roster seeder and synthetic player profile generator.
7. [x] Wire roster loading fallback chain (API -> synthetic seeded).
8. [x] Persist roster membership relation (`player_id` to `team_id` by snapshot) — migration `0003`.
9. [ ] Add simulation run persistence in API endpoints.
10. [x] Fix CI trigger (now runs on `master`) — matrix expansion still open.

## Real-Data Integration (delivered 2026-06-19)
- [x] Pure sabermetrics computation module (`sim/sabermetrics.py`): wOBA, wRC+, FIP, K/BB.
- [x] `StatsProvider` seam: synthetic (legacy-exact), stat-line (real), layered fallback.
- [x] Wire compare + simulator to consume providers; default synthetic = no regression.
- [x] Ingest per-player season stats and compute sabermetrics (`--include-player-stats`).
- [x] Migration `0002`: raw stat components + computed metrics in `player_season_stats`.
- [x] Postgres read provider behind `BASEBALL_STATS_SOURCE=postgres`.
- [ ] Ingest fielding data to replace neutral `range_factor`.
- [ ] Ingest Statcast expected stats to replace synthetic `xwoba`.
- [ ] Integration test of the Postgres stats path against ephemeral PostgreSQL.

## Phase 7: Web Interface (started 2026-06-19)
Goal: an attractive web app — a live game viewer first, then an analytics dashboard.
Deterministic replay (share a URL, reproduce the exact game) is the headline feature.

Stack decision:
- Frontend: React + Vite + TypeScript, lives in `frontend/` (monorepo). Tailwind for
  styling, TanStack Query for data, `openapi-typescript` to generate the API client
  from FastAPI's OpenAPI so the contract never drifts.
- Dev: Vite proxies `/api` to uvicorn. Prod: FastAPI can serve the static build.

### Phase 7.0 — Backend readiness (Python; the real blocker)
- [x] Expose the play-by-play trace via API (reuse `simulate_game_trace`).
- [x] Add read-side repository + browse endpoints: `GET /teams`, `/teams/{id}/roster`,
      `/players/{id}` (`domain/catalog.py`; roster from persisted memberships).
- [x] Include team/player names (not just IDs) in catalog responses.
- [x] Add CORS middleware (configurable via `BASEBALL_CORS_ALLOW_ORIGINS`) and an
      optional static mount that serves `frontend/dist` when present.
- [ ] Persist `simulation_runs` and expose `GET` by `match_id` for shareable replay.

### Phase 7.1 — Live game viewer
- [x] Scaffold React + Vite + TS + Tailwind in `frontend/`; typed API client generated
      from OpenAPI (`npm run gen:api`).
- [x] Scoreboard, animated diamond, play-by-play ticker, line score, play-through
      controls (play/pause/step/reset/speed) consuming `/simulate/game/play-by-play`.
- [x] Batter attribution: thread lineups through the simulator so each play names the
      batter (rotating 1-9, persisted across innings). Layered lineup provider — real
      from the persisted roster, synthetic fallback. Pure labeling; determinism intact.
- [ ] Replay-by-match_id route (depends on `simulation_runs` persistence).
- [ ] Team/player pickers backed by the catalog endpoints (replace hardcoded labels).
- [ ] Pitcher attribution (simulator models defense at team level only today).

### Phase 7.2 — Analytics dashboard
All three Analyze views and the Explore screens are built and covered by tests.
Remaining: a player search endpoint to replace the club -> roster cascade in Compare.
Navigation skeleton decided: three sections (Game / Analyze / Explore) with react-router,
every view deep-linkable. Analyze holds player/team analysis; game-scoped analysis
(box score, win probability) stays inside the viewer.
- [x] Per-metric provenance in `/compare/players` (ADR-019).
- [x] `GET /stats/leaders` with qualifier + direction metadata.
- [x] `GET /teams/{id}/profile` with the factors and their aggregate inputs.
- [x] Introduce react-router and the Game / Analyze / Explore shell (deep-linkable,
      old `/?home&away&seed` replay links redirect to `/game` keeping the query).
- [x] SPA fallback in the FastAPI static mount, excluding the API prefix so a missing
      endpoint still answers a JSON 404 instead of the HTML shell.
- [x] Analyze screen: Leaders (metric, qualifier and limit all live in the URL).
- [x] Analyze screen: Compare (per-metric provenance visible; seeded metrics excluded
      from the verdict). Player picking cascades team -> roster.
- [x] Analyze screen: Teams — sortable league table over `GET /stats/teams`, with the
      aggregate wOBA/FIP inputs alongside the factors.
- [ ] A player search endpoint would beat the team -> roster cascade for picking.
- [x] Frontend test suite: Vitest + Testing Library (40 tests), wired into CI as a
      second job alongside the Python one.
- [x] Explore screens: clubs index, team page (profile + roster), player page with
      season lines. Leaders and Compare link into player pages.
- [ ] Ingestion drops `bats` / `throws`: `normalize_players` reads them off the roster
      entry, but the MLB API returns them on `person` and only when hydrated. The
      columns exist and are always NULL, so the UI omits them.
- [ ] Rebuild `/predict/game` on the stats provider before featuring it (today it is
      seed-hashed and not situational, so it must stay out of the dashboard).

## Execution Plan (agreed 2026-09-06)

Ordered by dependency and risk. Each step lists what it delivers and how we know it
is done. Steps are sequential unless marked parallel.

### Step 1 — Integration tests against a real PostgreSQL (DONE 2026-09-06)
Why first: roughly seven hand-written queries (DISTINCT ON, joins, ANY(%s), the
latest-snapshot subquery) now serve four endpoints and three screens, and no test
executes any of them — every test uses a fake repository. The cost of adding this
grows with each DB feature that follows.

- [x] Test database fixture: create/reset `baseball_test`, apply migrations 0001-000N.
      No Docker needed — the local PostgreSQL 18 install is enough; CI uses a service
      container. Tests skip cleanly when no test database is reachable.
- [x] Deterministic seed fixture: 3 clubs, ~6 players covering a hitter, a pitcher and
      a two-way player, plus one club with no stats.
- [x] Cover the read side: `list_teams`, `get_player`, `get_team_roster`,
      `get_batting_woba`, `get_stat_leaders` (both directions + qualifier),
      `get_team_stat_lines`, `get_all_team_stat_lines`, `get_player_season_lines`.
- [x] Cover the write side: ingestion upserts, and idempotency when the same snapshot
      is ingested twice.
- [x] Verify the tests have teeth by breaking one query on purpose (three mutations,
      each failing only the tests that cover it).

Done when: the suite runs green locally and in CI, and a deliberately broken query
fails a test rather than passing silently.

### Step 2 — Rebuild `/predict/game` on real data (DONE 2026-09-06)
Why: it is the only endpoint that publishes invented numbers unlabelled, and the
product currently ships two disagreeing win-probability implementations — the viewer
computes its own baseline in the frontend while `/predict/game` hashes the seed.

- [x] Move the win-probability baseline server-side (`sim/winprob.py`), pure and tested,
      as the single model.
- [x] Rebuild `predict_game` on team profiles from the stats provider (pregame: no
      base/out state, so the projection reduces to team strength plus home advantage).
- [x] Report `source` and the inputs behind the number, as the team-profile endpoint does.
- [x] Point the viewer at the shared model so both surfaces agree on a matchup.

Done when: a strong-versus-weak matchup moves the probability, the viewer and predict
agree pregame, and nothing in the response is seed-derived without saying so.

### Step 2b — Calibration
Why: ADR-004 says add complexity once the baseline's limits are *measured*. Two
baselines currently ship unmeasured.

- [ ] Backfill pregame probabilities for completed ingested games and compare to results.
- [ ] Brier score plus reliability bins, written down per release.

Done when: there is a number, and it is in the docs.

### Step 3 — Richer, cleaner ingestion
The API already returns far more than we parse: 34 hitting fields (we read 12) and 62
pitching fields (we read 5), for requests we already pay for. wOBA and FIP are already
correctly specified and will not change — this only adds metrics.

- [ ] 3a. `bats` / `throws`: add `hydrate=person` to the roster fetch and read
      `person.batSide.code` / `person.pitchHand.code`. 30 requests, not 840.
- [ ] 3b. Widen `player_season_stats` (migration) and the parser for fields already in
      the payload: runs, RBI, total bases, GIDP, sac bunts, caught stealing, ground/air
      outs; battersFaced, outs, earned runs, hits, games started, strikes/balls.
      Newly computable: BABIP, ISO, OBP/SLG/OPS, K%, BB%, WHIP, ERA, K/9, BB/9, HR/9,
      and a GB/FB approximation that enables xFIP.
- [ ] 3c. Ingest by position — hitting for non-pitchers, pitching for pitchers, both for
      TWP — with a flag to fetch every group. Halves the request count and drops most
      junk lines.
- [ ] 3d. Separately, apply a playing-time floor when aggregating team profiles. This is
      where the actual correctness win is: today a pitcher's handful of plate
      appearances is summed into the club's team wOBA. Filtering at ingestion helps but
      is brittle, because `primary_position` can be stale; a floor at aggregation is not.

Done when: a re-ingest populates the new columns, wOBA/FIP are unchanged, and team
profiles no longer count sub-threshold lines.

### Step 4 — Persisted simulation runs and replay
URL-based replay already covers the main use case, so this is about history and real
snapshot lineage rather than the headline feature.

- [ ] Persist `simulation_runs` on the serving path.
- [ ] `GET /games/{match_id}`; front route `/replay/:matchId`.
- [ ] Carry a real `data_snapshot_id` in the deterministic context instead of a literal.

Done when: a simulated game can be recalled by `match_id` and replays identically.

### Step 5 — Fielding, and pitcher attribution
Cheaper than first assumed: fielding comes from the same `/people/{id}/stats` endpoint
with `group=fielding`, returning one split per position played, including
`rangeFactorPer9Inn`, assists, putouts, errors, chances, fielding pct and innings.

- [ ] Ingest the fielding group; migration for the fielding columns.
- [ ] Map it onto `range_factor` with a documented league range, replacing the neutral
      0.5 every club carries today.
- [ ] Pitcher attribution in the simulator, alongside the same defensive model.
- [ ] Surface the column in the Teams table, which currently omits it as a constant.

Done when: `range_factor` varies by club, determinism goldens are refreshed
deliberately, and the Teams table shows it.

### Step 6 — Statcast expected stats
- [ ] Baseball Savant ingestion (a genuinely separate source per ADR-003), including a
      terms-of-use review.
- [ ] Populate `xwoba` so Compare stops labelling it seeded.

Done when: `xwoba` reports `real` and the last synthetic metric in the compare table
disappears.

## Risks and Mitigations
- External API schema changes:
  - Mitigation: contract tests and versioned parsers.
- Data licensing/commercial constraints:
  - Mitigation: legal review before commercial rollout.
- Non-deterministic numerical behavior:
  - Mitigation: pinned deps, strict rounding, deterministic test suite.
- Scope creep in first release:
  - Mitigation: preserve API-first MVP boundaries.

## Working Rules
- Keep `plan.MD` current when priorities or status change.
- Record architecture/modeling changes in `decisions.md`.
- Do not merge major changes without tests for deterministic behavior.
