# Rulesets

The simulator is ruleset-driven. A ruleset file controls key game behavior without code changes.

## Default
- Path: `rulesets/mlb_2026_regular.json`
- Env var: `BASEBALL_SIMULATOR_RULESET_PATH`

## Core fields
- `ruleset_id`
- `scheduled_innings`
- `max_innings`
- `max_plate_appearances_per_half`
- `skip_home_bottom_if_leading_after_top_final`
- `enable_walkoff`
- `enable_runner_on_second_in_extras`
- `runner_on_second_start_inning`
- `home_field_event_boost`

## Determinism
- The loaded ruleset checksum is included in simulation assumptions.
- Use fixed `seed + model_version + data_snapshot_id + ruleset` for exact replayability.

