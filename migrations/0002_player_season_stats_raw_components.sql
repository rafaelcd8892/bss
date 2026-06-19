BEGIN;

-- Persist the raw counting components alongside the computed sabermetrics so the
-- analytical layer can reconstruct exact RawBattingLine/RawPitchingLine inputs from
-- the database and feed them through the same StatLineStatsProvider used elsewhere.
ALTER TABLE player_season_stats
    ADD COLUMN IF NOT EXISTS stat_group TEXT,
    ADD COLUMN IF NOT EXISTS at_bats INTEGER,
    ADD COLUMN IF NOT EXISTS singles INTEGER,
    ADD COLUMN IF NOT EXISTS doubles INTEGER,
    ADD COLUMN IF NOT EXISTS triples INTEGER,
    ADD COLUMN IF NOT EXISTS home_runs INTEGER,
    ADD COLUMN IF NOT EXISTS walks INTEGER,
    ADD COLUMN IF NOT EXISTS intentional_walks INTEGER,
    ADD COLUMN IF NOT EXISTS hit_by_pitch INTEGER,
    ADD COLUMN IF NOT EXISTS sacrifice_flies INTEGER,
    ADD COLUMN IF NOT EXISTS strikeouts INTEGER,
    ADD COLUMN IF NOT EXISTS stolen_bases INTEGER,
    ADD COLUMN IF NOT EXISTS k_bb_ratio NUMERIC(6,3);

-- A single player can have both a hitting and a pitching line in the same
-- season/snapshot (NL pitchers, two-way players), so stat_group joins the key.
UPDATE player_season_stats SET stat_group = 'hitting' WHERE stat_group IS NULL;
ALTER TABLE player_season_stats ALTER COLUMN stat_group SET NOT NULL;
ALTER TABLE player_season_stats DROP CONSTRAINT IF EXISTS player_season_stats_pkey;
ALTER TABLE player_season_stats
    ADD PRIMARY KEY (player_id, season, source_snapshot_id, stat_group);

COMMIT;
