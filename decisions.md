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

---

## Change Log
- 2026-02-22: Initialized ADR records for project kickoff.
- 2026-02-22: Added ADR-006 and scaffolded initial deterministic API and database baseline.
- 2026-02-22: Added ADR-007 for content-addressed immutable snapshot storage.
- 2026-02-22: Added ADR-008 for migration runner and bounded ingestion retries.
- 2026-02-22: Added ADR-009 for the deterministic plate-appearance state-machine simulator.
- 2026-02-22: Added ADR-010 for CLI watch mode, deterministic match IDs, and roster seeder fallback.
- 2026-02-22: Added ADR-011 for ruleset-driven simulator configuration.
- 2026-02-22: Added ADR-012 for play-trace output and CLI watch logging format.
- 2026-02-22: Added ADR-013 for API-first CLI roster loading with deterministic seeded fallback.
