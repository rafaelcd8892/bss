BEGIN;

-- The MLB Stats API returns 34 hitting and 62 pitching fields per player; the first
-- ingest parsed 12 and 5. These columns cost no extra requests — the data was already
-- in responses we were discarding — and they unlock OBP/SLG/OPS, ISO, BABIP, ERA,
-- WHIP, per-nine rates, batter-faced rates and a ground/air approximation for xFIP.
ALTER TABLE player_season_stats
    -- Raw hitting components
    ADD COLUMN IF NOT EXISTS runs INTEGER,
    ADD COLUMN IF NOT EXISTS runs_batted_in INTEGER,
    ADD COLUMN IF NOT EXISTS caught_stealing INTEGER,
    ADD COLUMN IF NOT EXISTS sacrifice_bunts INTEGER,
    ADD COLUMN IF NOT EXISTS ground_into_double_play INTEGER,
    -- Shared by both groups, like home_runs and walks already are
    ADD COLUMN IF NOT EXISTS ground_outs INTEGER,
    ADD COLUMN IF NOT EXISTS air_outs INTEGER,
    ADD COLUMN IF NOT EXISTS games_played INTEGER,
    -- Raw pitching components
    ADD COLUMN IF NOT EXISTS batters_faced INTEGER,
    ADD COLUMN IF NOT EXISTS earned_runs INTEGER,
    ADD COLUMN IF NOT EXISTS hits_allowed INTEGER,
    ADD COLUMN IF NOT EXISTS games_started INTEGER,
    -- Computed rate stats, stored so leaderboards can rank on them
    ADD COLUMN IF NOT EXISTS batting_average NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS obp NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS slg NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS ops NUMERIC(6,4),
    ADD COLUMN IF NOT EXISTS iso NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS babip NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS era NUMERIC(6,3),
    ADD COLUMN IF NOT EXISTS whip NUMERIC(6,3),
    ADD COLUMN IF NOT EXISTS strikeout_rate NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS walk_rate NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS ground_ball_rate NUMERIC(5,4);

COMMIT;
