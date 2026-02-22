# Data Ingestion

## Objectives
- Keep raw upstream payloads immutable.
- Preserve deterministic snapshot IDs for reproducibility.
- Normalize snapshots into canonical `teams`, `players`, and `games` tables.

## Snapshot Strategy
- Source system: `mlb_stats_api`.
- Categories:
  - `teams`
  - `rosters`
  - `schedule`
- Snapshot ID format:
  - `{source_system}:{category}:{sha256_prefix}`
  - Example: `mlb_stats_api:teams:9f2d4e19c8a31b09`

Raw files are stored at:
- `data/raw/{source_system}/{category}/{sha256_prefix}/{sha256}.json`

Rules:
- Snapshot payload bytes are canonical JSON (`sort_keys=True`, compact separators).
- File writes use exclusive create mode (`xb`) to prevent overwrite.
- Re-ingesting identical payloads resolves to the same snapshot file and ID.

## Pipeline Flow
1. Fetch teams for a season.
2. Fetch team rosters for each team ID.
3. Fetch schedule within date window.
4. Write immutable raw snapshots for each dataset.
5. Record snapshots in `data_snapshots`.
6. Normalize and upsert `teams`, `players`, and `games`.
7. Commit as a single transaction.

## Determinism Notes
- API-serving deterministic behavior uses `seed + model_version + data_snapshot_id`.
- Ingestion determinism is content-based via snapshot hashing.
- To reproduce predictions/simulations exactly, keep model version and referenced snapshot IDs fixed.

