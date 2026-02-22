# AGENTS.md

## Purpose
This document defines how humans and coding agents collaborate in this repository.
It is the operating contract for building a deterministic, sabermetrics-driven baseball platform.

## Product Goal
Build a scalable baseball game simulator and analytics platform that can:
- Ingest MLB player, team, and game data from APIs.
- Compare players and teams with modern sabermetrics.
- Predict outcomes with reproducible models.
- Run deterministic simulations for game and season what-if analysis.

## Non-Negotiable Principles
1. Deterministic by default.
2. Sabermetrics over narrative.
3. Reproducibility and auditability are required.
4. Keep architecture simple first, then scale.
5. Every decision must have explicit assumptions and measurable tradeoffs.

## Deterministic System Rules
- All simulation and prediction endpoints must accept `seed`, `model_version`, and `data_snapshot_id`.
- Same input payload + same seed + same model version + same data snapshot must produce identical output.
- No hidden randomness in business logic.
- Randomness is only allowed through an injected, local seeded RNG.
- Core calculations cannot depend on wall-clock time.
- Store and process timestamps in UTC.
- Pin dependency versions; do not use unpinned libraries in production.
- Define and enforce rounding policy at API boundaries to avoid floating drift in responses.
- Every simulated match must have a stable `match_id` derived from deterministic context and teams.
- Play logs must include enough context (`seed`, `model_version`, `data_snapshot_id`, teams, lineup source) to replay.
- Simulator behavior changes should be expressed through versioned ruleset configs before logic rewrites.

## Sabermetrics Standards
- Use rate and context-adjusted metrics as defaults (for example: wOBA, xwOBA, wRC+, FIP, xFIP, SIERA where applicable).
- Separate descriptive metrics from predictive features.
- Prefer explainable baseline models before complex models.
- Track calibration and reliability, not only accuracy.
- Include park factors, era effects, handedness splits, and sample-size stability checks.

## Data Strategy
Primary external sources:
- MLB Stats API for players, teams, schedules, game state, and boxscore-level entities.
- Baseball Savant / Statcast exports for batted-ball and pitch-level expected metrics.

Data handling rules:
- Keep raw ingested payloads immutable.
- Normalize into canonical tables with schema versioning.
- Build feature tables from versioned snapshots.
- Add contract tests for schema drift on external providers.
- Respect provider terms and licensing before commercial usage.

## Architecture Baseline
- Language: Python.
- API: FastAPI.
- OLTP store: PostgreSQL.
- Cache: Redis.
- Batch analytics and feature generation: DuckDB/Parquet and Polars.
- Orchestration: Airflow.
- Model tracking and registry: MLflow.

This can evolve, but changes require an entry in `decisions.md`.

## Recommended Repository Layout
```
src/
  api/
  ingest/
  domain/
  sim/
  cli/
  seeders/
  features/
  models/
  infra/
tests/
  unit/
  integration/
  contract/
docs/
```

## API and Modeling Contracts
- Every response must include metadata:
  - `model_version`
  - `data_snapshot_id`
  - `seed` (if simulation or stochastic process involved)
  - `generated_at_utc`
- Prediction endpoints must expose confidence and calibration metadata.
- Simulation endpoints must expose assumptions used for the run.
- CLI simulation commands must persist machine-readable logs for deterministic replay.

## CLI Simulator Requirements
- Terminal watch mode must show:
  - Scoreboard and inning progression.
  - Lineups and currently active batter/pitcher.
  - Field/turf panel with defensive positions and base occupancy.
  - Chronological play-by-play stream.
- Watch mode must support:
  - Configurable delay between plays.
  - Pause/resume and step control.
- Logging and replay:
  - Write full play logs to `game_logs/` as append-only files.
  - Provide a replay command that reconstructs the same game from stored context.
- Data sourcing policy:
  - Preferred: API/DB roster and player entities.
  - Fallback: synthetic seeded player generator when required data is missing.

## Testing Requirements
- Unit tests for metric calculations and deterministic behavior.
- Golden tests: fixed inputs must always return fixed outputs.
- Contract tests against external API response schemas.
- Integration tests for ingestion to normalized schema pipeline.
- Performance smoke tests for simulation throughput.

## Documentation Workflow
- `plan.MD` is the live project plan and execution status.
- `decisions.md` stores ADR-style architecture and product decisions.
- Any non-trivial change to architecture, modeling, data contracts, or determinism policy must be recorded in `decisions.md`.
- If scope or priority changes, update `plan.MD` in the same change.

## Execution Checklist for Agents
Before coding:
- Read `plan.MD` for current priorities.
- Read latest entries in `decisions.md`.

While coding:
- Keep changes minimal and testable.
- Add or update tests with code changes.
- Preserve deterministic behavior.

Before finishing:
- Run relevant tests.
- Update `plan.MD` progress markers.
- Add decision notes if architecture or strategy changed.
