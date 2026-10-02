BEGIN;
ALTER TABLE fantasy.sync_job DROP CONSTRAINT IF EXISTS sync_job_kind_check;
ALTER TABLE fantasy.sync_job ADD CONSTRAINT sync_job_kind_check CHECK (kind IN ('pool', 'schedule', 'results'));

-- Only complete, validated games enter the scoring pipeline. Reimports must
-- match this snapshot; corrections require a separate, explicit workflow.
CREATE TABLE IF NOT EXISTS fantasy.result_snapshot (
    game_id BIGINT PRIMARY KEY REFERENCES fantasy.game(id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS fantasy.season_scoring_snapshot (
    season_id BIGINT PRIMARY KEY REFERENCES fantasy.season(id) ON DELETE CASCADE,
    rule_version TEXT NOT NULL REFERENCES fantasy.scoring_rule(version),
    rules JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS fantasy.season_game_scored (
    season_id BIGINT NOT NULL REFERENCES fantasy.season(id) ON DELETE CASCADE,
    game_id BIGINT NOT NULL REFERENCES fantasy.result_snapshot(game_id) ON DELETE CASCADE,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (season_id, game_id)
);
CREATE TABLE IF NOT EXISTS fantasy.manager_game_score (
    season_id BIGINT NOT NULL,
    game_id BIGINT NOT NULL,
    manager_id BIGINT NOT NULL REFERENCES fantasy.manager(id),
    roster_history_id BIGINT NOT NULL REFERENCES fantasy.roster_history(id),
    slot TEXT NOT NULL CHECK (slot IN ('TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT', 'TEAM')),
    player_id BIGINT REFERENCES fantasy.pro_player(id),
    team_id BIGINT REFERENCES fantasy.pro_team(id),
    asset_name TEXT NOT NULL,
    score NUMERIC(12, 3) NOT NULL,
    rule_version TEXT NOT NULL REFERENCES fantasy.scoring_rule(version),
    PRIMARY KEY (season_id, game_id, roster_history_id),
    FOREIGN KEY (season_id, game_id) REFERENCES fantasy.season_game_scored(season_id, game_id) ON DELETE CASCADE,
    CHECK ((player_id IS NOT NULL)::int + (team_id IS NOT NULL)::int = 1),
    CHECK ((slot = 'TEAM') = (team_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_fantasy_manager_game_score ON fantasy.manager_game_score(season_id, manager_id);
COMMIT;
