# baseball-sim

Deterministic, sabermetrics-driven MLB simulation and analytics service.

## Documentation
- `AGENTS.md`: collaboration and deterministic engineering contract.
- `plan.MD`: project roadmap, phase status, and backlog.
- `decisions.md`: architecture decision records (ADRs).
- `docs/data_ingestion.md`: ingestion model and immutable snapshot strategy.
- `docs/simulator.md`: deterministic state-machine simulation model.
- `docs/rulesets.md`: ruleset-driven simulator configuration.
- `docs/cli_watch.md`: terminal watch mode behavior and controls.
- `docs/session_2026-02-22.md`: implementation log for today’s delivered scope.

## Quick Start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn baseball_sim.main:app --reload
```

## API
- `GET /api/v1/health`
- `POST /api/v1/compare/players`
- `POST /api/v1/simulate/game`
- `POST /api/v1/predict/game`

## Migrations
Apply pending SQL migrations:
```bash
python -m baseball_sim.infra.run_migrations
```

Optional overrides:
```bash
python -m baseball_sim.infra.run_migrations --dsn postgresql://... --migrations-dir migrations
```

## Ingestion
Run an ingestion window sync that stores immutable raw snapshots and upserts canonical tables:
```bash
python -m baseball_sim.ingest.run_sync --start-date 2026-04-01 --end-date 2026-04-07 --season 2026
```

Raw payload snapshots are written under `BASEBALL_RAW_DATA_DIR` (default: `data/raw`).

## Simulator Ruleset
Simulation behavior is config-driven via `BASEBALL_SIMULATOR_RULESET_PATH` (default: `rulesets/mlb_2026_regular.json`).

## CLI Watch Simulator
Watch a full deterministic game in terminal with scoreboard, lineups, field panel, and play-by-play pacing:

```bash
python -m baseball_sim.cli.watch --home-team-id 147 --away-team-id 121 --seed 1234 --delay-seconds 0.8
```

By default, CLI rosters use MLB Stats API first and fall back to deterministic seeded players when API data is unavailable or incomplete.

Manual stepping mode:

```bash
python -m baseball_sim.cli.watch --home-team-id 147 --away-team-id 121 --seed 1234 --manual
```

Force seeded-only rosters (skip API calls):

```bash
python -m baseball_sim.cli.watch --home-team-id 147 --away-team-id 121 --seed 1234 --seeded-rosters-only
```

Logs are saved under `game_logs/`:
- `{match_id}.jsonl` (play-by-play)
- `{match_id}_summary.json` (final summary)
- `match_registry.jsonl` (match-to-seed registry)
