BEGIN;

CREATE TABLE IF NOT EXISTS data_snapshots (
    data_snapshot_id TEXT PRIMARY KEY,
    source_system TEXT NOT NULL,
    captured_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload_sha256 TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS model_versions (
    model_version TEXT PRIMARY KEY,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_kind TEXT NOT NULL,
    training_snapshot_id TEXT NOT NULL REFERENCES data_snapshots(data_snapshot_id),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    abbreviation TEXT,
    league_name TEXT,
    division_name TEXT,
    first_seen_snapshot_id TEXT NOT NULL REFERENCES data_snapshots(data_snapshot_id),
    last_updated_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    primary_position TEXT,
    bats CHAR(1),
    throws CHAR(1),
    birth_date DATE,
    mlb_debut_date DATE,
    first_seen_snapshot_id TEXT NOT NULL REFERENCES data_snapshots(data_snapshot_id),
    last_updated_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS games (
    game_pk BIGINT PRIMARY KEY,
    game_date DATE NOT NULL,
    season INTEGER NOT NULL,
    game_type TEXT,
    status_text TEXT,
    home_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    home_score INTEGER,
    away_score INTEGER,
    snapshot_id TEXT NOT NULL REFERENCES data_snapshots(data_snapshot_id),
    loaded_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS player_season_stats (
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    season INTEGER NOT NULL,
    team_id INTEGER REFERENCES teams(team_id),
    pa INTEGER,
    ip NUMERIC(6,2),
    woba NUMERIC(5,4),
    xwoba NUMERIC(5,4),
    wrc_plus NUMERIC(6,2),
    fip NUMERIC(6,3),
    source_snapshot_id TEXT NOT NULL REFERENCES data_snapshots(data_snapshot_id),
    loaded_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (player_id, season, source_snapshot_id)
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    simulation_run_id BIGSERIAL PRIMARY KEY,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    seed BIGINT NOT NULL,
    model_version TEXT NOT NULL REFERENCES model_versions(model_version),
    data_snapshot_id TEXT NOT NULL REFERENCES data_snapshots(data_snapshot_id),
    request_payload JSONB NOT NULL,
    response_payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_games_game_date ON games (game_date);
CREATE INDEX IF NOT EXISTS idx_games_teams ON games (home_team_id, away_team_id);
CREATE INDEX IF NOT EXISTS idx_player_season_stats_season ON player_season_stats (season);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_context
    ON simulation_runs (seed, model_version, data_snapshot_id);

COMMIT;

