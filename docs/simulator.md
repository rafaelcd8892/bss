# Simulator

## Engine
The simulator uses a deterministic plate-appearance state machine.

### Plate-appearance events
- `out`
- `walk`
- `single`
- `double`
- `triple`
- `home_run`

### State tracked
- Outs (`0..3`) per half inning
- Base occupancy (`1B`, `2B`, `3B`)
- Runs scored

### Inning and game rules
- Simulate top then bottom each inning.
- If home team leads after top of the final scheduled inning, bottom-half is skipped.
- If tied at the end of scheduled innings, continue extras up to inning 21.
- If still tied at inning cap, resolve winner with deterministic tiebreak.

### Determinism contract
Same `seed + model_version + data_snapshot_id + request payload` yields identical output.

