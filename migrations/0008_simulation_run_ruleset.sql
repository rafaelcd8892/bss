BEGIN;

-- A run is only reproducible if the rules it was played under are known. The engine's
-- tuning constants now live in the ruleset (ADR-028), so retuning the model would
-- otherwise make an old replay quietly produce a different game. Storing the ruleset
-- with the run means a replay is played under the rules it was recorded under.
ALTER TABLE simulation_runs
    ADD COLUMN IF NOT EXISTS ruleset JSONB,
    ADD COLUMN IF NOT EXISTS ruleset_checksum TEXT;

COMMIT;
