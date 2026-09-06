BEGIN;

-- simulation_runs has existed since 0001 but could never accept a row. Its
-- model_version foreign key points at model_versions, which nothing populates, and its
-- data_snapshot_id foreign key requires a catalogued snapshot while the deterministic
-- context is caller-supplied metadata: the web client legitimately sends "ui".
--
-- The run record is an audit log of what was asked for, not a curated catalog entry,
-- so both constraints are dropped. Lineage is kept instead by recording which stats
-- source actually served the run.
ALTER TABLE simulation_runs
    DROP CONSTRAINT IF EXISTS simulation_runs_model_version_fkey,
    DROP CONSTRAINT IF EXISTS simulation_runs_data_snapshot_id_fkey;

ALTER TABLE simulation_runs
    -- The deterministic identity of the matchup: same inputs, same id, same game.
    ADD COLUMN IF NOT EXISTS match_id TEXT,
    -- Denormalized from the request so a run can be found without parsing JSONB.
    ADD COLUMN IF NOT EXISTS home_team_id INTEGER,
    ADD COLUMN IF NOT EXISTS away_team_id INTEGER,
    ADD COLUMN IF NOT EXISTS scheduled_innings INTEGER,
    -- Whether the run was backed by ingested stats or the seeded fallback.
    ADD COLUMN IF NOT EXISTS stats_source TEXT;

-- A match id is the natural key for replay: re-running the same context must land on
-- the same row rather than appending a duplicate.
CREATE UNIQUE INDEX IF NOT EXISTS idx_simulation_runs_match_id
    ON simulation_runs (match_id);

CREATE INDEX IF NOT EXISTS idx_simulation_runs_created
    ON simulation_runs (created_at_utc DESC);

COMMIT;
