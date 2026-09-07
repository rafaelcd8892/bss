BEGIN;

-- A season is not one row per player. A traded player has a line with each club plus
-- a season total, and until now only the first split survived: the parser kept the
-- total, whose team is NULL, so a traded player counted toward no club's profile at
-- all. Keeping every split means the key has to include the team.
--
-- The team stays nullable because NULL is meaningful here — it is the season total
-- across clubs, which is what a leaderboard and a player rating want. A primary key
-- cannot hold NULL, so the key becomes a unique index over COALESCE(team_id, 0);
-- team id 0 does not exist in the MLB Stats API, so it cannot collide with a club.
ALTER TABLE player_season_stats DROP CONSTRAINT IF EXISTS player_season_stats_pkey;

CREATE UNIQUE INDEX IF NOT EXISTS player_season_stats_key
    ON player_season_stats (
        player_id, season, stat_group, COALESCE(team_id, 0), source_snapshot_id
    );

-- Fielding splits are already one row per position; a traded player fields at the same
-- position for two clubs, so the team belongs in this key for the same reason.
ALTER TABLE player_season_fielding DROP CONSTRAINT IF EXISTS player_season_fielding_pkey;

CREATE UNIQUE INDEX IF NOT EXISTS player_season_fielding_key
    ON player_season_fielding (
        player_id, season, position, COALESCE(team_id, 0), source_snapshot_id
    );

-- History multiplies the rows: a full career is a dozen seasons per player rather than
-- one, so the lookups the serving path makes every request need their own indexes.
CREATE INDEX IF NOT EXISTS idx_player_season_stats_player_season
    ON player_season_stats (player_id, season);

CREATE INDEX IF NOT EXISTS idx_player_season_fielding_season
    ON player_season_fielding (season);

COMMIT;
