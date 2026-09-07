BEGIN;

-- Statcast expected stats. `xwoba` already existed since 0001 but was never
-- populated: it was the one compare metric with no source. The rest come from the
-- same `expectedStatistics` payload and are stored beside it rather than recomputed,
-- because they are measurements, not formulas we can evaluate.
ALTER TABLE player_season_stats
    ADD COLUMN IF NOT EXISTS x_batting_average NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS x_slg NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS x_woba_con NUMERIC(5,4);

COMMIT;
