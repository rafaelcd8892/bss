# CLI Watch Simulator

Two modes are available: a classic terminal printer and a full Textual TUI.

---

## Textual TUI (recommended)

```bash
python -m baseball_sim.cli.tui --home-team-id 147 --away-team-id 121 --seed 1234
```

### Layout
- **Left panel** — live score, inning/half, outs pips, bases diamond.
- **Center panel** — line score (updates each inning), defensive field panel.
- **Right panel** — away and home lineups with active-batter indicator (▶).
- **Play log** — scrollable play-by-play with color-coded events (red=HR, yellow=2B, green=1B, …).
- **Footer** — always-visible keybinding hints.

### Controls
| Key | Action |
|-----|--------|
| `p` | Pause auto-play |
| `r` | Resume auto-play |
| `Space` | Step one play (while paused) |
| `q` | Quit |

---

## Classic terminal printer

```bash
python -m baseball_sim.cli.watch --home-team-id 147 --away-team-id 121 --seed 1234
```

Clears the screen each play and prints a text frame. Useful in non-TTY or minimal environments.

### Controls
- Live mode: `p` + Enter to pause, `q` + Enter to quit.
- Paused mode: Enter to step, `r` to resume, `q` to quit.

---

## Shared flags

| Flag | Default | Description |
|------|---------|-------------|
| `--home-team-id` | required | MLB team ID for the home team |
| `--away-team-id` | required | MLB team ID for the away team |
| `--seed` | settings default | Deterministic RNG seed |
| `--innings` | ruleset default | Scheduled innings to play |
| `--delay-seconds` | 0.8 (TUI) / 1.1 (watch) | Seconds between plays in auto mode |
| `--manual` | false | Start paused; step manually |
| `--seeded-rosters-only` | false | Skip MLB API; use deterministic seeded rosters |
| `--ruleset-path` | settings default | Path to ruleset JSON |
| `--log-dir` | `game_logs/` | Directory for JSONL and summary output |

**Common team IDs:** 147 Yankees · 121 Mets · 119 Dodgers · 111 Red Sox · 158 Brewers

---

## Logging

Each run writes to `game_logs/`:
- `<match_id>.jsonl` — meta + play entries + summary marker.
- `<match_id>_summary.json` — final game summary and context.
- `match_registry.jsonl` — append-only mapping of `match_id` to deterministic context.

---

## Roster data sources

Rosters are loaded in this order:
1. MLB Stats API roster (preferred).
2. Deterministic seeded roster fill for missing slots.
3. Full deterministic seeded roster fallback if API lookup fails.

Use `--seeded-rosters-only` to force deterministic seeded rosters (offline-safe, fully reproducible).

Planned extension: DB roster source between API and seeded fallback.
