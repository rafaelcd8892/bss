# plan.MD

## Planning Log
- Last updated: 2026-04-10
- Owner: Rafael + coding agents
- Project status: Phase 6 in progress (Textual TUI added; CLI watch MVP complete)

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
8. [ ] Persist roster membership relation (`player_id` to `team_id` by snapshot).
9. [ ] Add simulation run persistence in API endpoints.
10. [ ] Add GitHub Actions matrix for lint/type/tests.

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
