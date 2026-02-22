# CLI Watch Simulator

## Command
```bash
python -m baseball_sim.cli.watch --home-team-id 147 --away-team-id 121 --seed 1234
```

## Behavior
- Streams play-by-play events with configurable delay.
- Renders:
  - Scoreboard and line score.
  - Current inning/half/outs.
  - Base occupancy.
  - Defensive field panel.
  - Home/away lineups.
- Supports pause/resume controls.

## Controls
- Live mode:
  - `p` + Enter to pause.
  - `q` + Enter to quit.
- Paused mode:
  - `Enter` to step one play.
  - `r` to resume.
  - `q` to quit.

## Logging
Each run writes to `game_logs/`:
- `<match_id>.jsonl`: meta + play entries + summary marker.
- `<match_id>_summary.json`: final game summary and context.
- `match_registry.jsonl`: append-only mapping for `match_id` to deterministic context.

## Data sources
Current watch mode loads rosters in this order:
- MLB Stats API roster (preferred source).
- Deterministic seeded roster fill for missing slots.
- Full deterministic seeded roster fallback if API lookup fails.

Use `--seeded-rosters-only` to skip API loading and force deterministic seeded rosters for both teams.

Planned extension:
- DB roster source between API and seeded fallback.
