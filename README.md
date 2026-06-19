# baseball-sim

Deterministic, sabermetrics-driven MLB simulation and analytics service.

## Documentation
- `AGENTS.md`: collaboration and deterministic engineering contract.
- `plan.MD`: project roadmap, phase status, and backlog.
- `decisions.md`: architecture decision records (ADRs).
- `docs/data_ingestion.md`: ingestion model and immutable snapshot strategy.
- `docs/simulator.md`: deterministic state-machine simulation model.
- `docs/rulesets.md`: ruleset-driven simulator configuration.
- `docs/sabermetrics.md`: real sabermetrics computation and the stats-provider seam.
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

## Web Frontend (live game viewer)
A React + Vite + TypeScript app in `frontend/` renders the deterministic game as a live
broadcast: scoreboard, animated diamond, play-by-play ticker, line score, and
play/pause/step controls. The typed API client is generated from the backend's OpenAPI.

```bash
# terminal 1 — API
uvicorn baseball_sim.main:app --port 8000

# terminal 2 — frontend (Vite dev server proxies /api to :8000)
cd frontend
npm install
npm run gen:api   # regenerate the typed client from openapi.json
npm run dev
```

Production: `npm run build` emits `frontend/dist`, which the API serves automatically
when present (single process hosts both API and UI). The game viewer needs no database
(it uses the deterministic synthetic provider unless `BASEBALL_STATS_SOURCE=postgres`).

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

To also ingest per-player season stats and compute sabermetrics (wOBA, wRC+, FIP, K/BB):
```bash
python -m baseball_sim.ingest.run_sync --start-date 2026-04-01 --end-date 2026-04-07 \
  --season 2026 --include-player-stats
```

## Real Sabermetrics vs Synthetic Fallback
Compare and simulation consume player/team ratings through a `StatsProvider`. By
default (`BASEBALL_STATS_SOURCE=synthetic`) ratings are deterministic seed-only values.
Set `BASEBALL_STATS_SOURCE=postgres` (and `BASEBALL_STATS_SEASON`) to drive them from
real ingested stats, falling back to synthetic per-player/team when data is missing.
See `docs/sabermetrics.md`.

## Simulator Ruleset
Simulation behavior is config-driven via `BASEBALL_SIMULATOR_RULESET_PATH` (default: `rulesets/mlb_2026_regular.json`).

## CLI Watch Simulator

### Textual TUI (recommended)
Full interactive TUI with 3-panel layout, color-coded play log, bases diamond, and keyboard controls:

```bash
python -m baseball_sim.cli.tui --home-team-id 147 --away-team-id 121 --seed 1234 --seeded-rosters-only
```

Manual step-through mode:

```bash
python -m baseball_sim.cli.tui --home-team-id 147 --away-team-id 121 --seed 1234 --seeded-rosters-only --manual
```

Controls: `p` pause · `r` resume · `Space` step · `q` quit

### Classic terminal printer
```bash
python -m baseball_sim.cli.watch --home-team-id 147 --away-team-id 121 --seed 1234 --delay-seconds 0.8
```

By default, CLI rosters use MLB Stats API first and fall back to deterministic seeded players when API data is unavailable or incomplete. Use `--seeded-rosters-only` to skip API calls entirely.

Common team IDs: 147 Yankees · 121 Mets · 119 Dodgers · 111 Red Sox · 158 Brewers

Logs are saved under `game_logs/`:
- `{match_id}.jsonl` (play-by-play)
- `{match_id}_summary.json` (final summary)
- `match_registry.jsonl` (match-to-seed registry)

See `docs/cli_watch.md` for full flag reference.
