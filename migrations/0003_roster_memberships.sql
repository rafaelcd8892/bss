BEGIN;

-- Canonical team -> player membership, captured per ingestion snapshot. The roster
-- payload is already fetched during ingestion; this persists the link (previously
-- discarded) so the serving layer can return a team's roster without calling the
-- external API at request time, preserving the snapshot-based determinism contract.
CREATE TABLE IF NOT EXISTS roster_memberships (
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    season INTEGER,
    primary_position TEXT,
    source_snapshot_id TEXT NOT NULL REFERENCES data_snapshots(data_snapshot_id),
    loaded_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (team_id, player_id, source_snapshot_id)
);

CREATE INDEX IF NOT EXISTS idx_roster_memberships_team_latest
    ON roster_memberships (team_id, loaded_at_utc DESC);

COMMIT;
