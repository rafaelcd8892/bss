BEGIN;

-- Fielding needs its own table rather than another stat_group in player_season_stats:
-- the API reports one split per position played, so a utility player has several rows
-- and position has to be part of the key.
CREATE TABLE IF NOT EXISTS player_season_fielding (
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    season INTEGER NOT NULL,
    team_id INTEGER,
    position TEXT NOT NULL,
    games INTEGER,
    games_started INTEGER,
    innings NUMERIC(7,2),
    put_outs INTEGER,
    assists INTEGER,
    errors INTEGER,
    chances INTEGER,
    double_plays INTEGER,
    fielding_percentage NUMERIC(5,4),
    range_factor_per_nine NUMERIC(6,3),
    source_snapshot_id TEXT NOT NULL REFERENCES data_snapshots(data_snapshot_id),
    loaded_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (player_id, season, position, source_snapshot_id)
);

CREATE INDEX IF NOT EXISTS idx_player_season_fielding_team
    ON player_season_fielding (season, team_id);

COMMIT;
