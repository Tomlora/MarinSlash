BEGIN;

CREATE SCHEMA IF NOT EXISTS fantasy;

CREATE TABLE IF NOT EXISTS fantasy.competition (
    code TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Europe/Paris',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (code IN ('LEC', 'LCS', 'LFL'))
);

INSERT INTO fantasy.competition (code, display_name)
VALUES
    ('LEC', 'League of Legends EMEA Championship'),
    ('LCS', 'League Championship Series'),
    ('LFL', 'La Ligue Française')
ON CONFLICT (code) DO UPDATE
SET display_name = EXCLUDED.display_name;

CREATE TABLE IF NOT EXISTS fantasy.league (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    owner_discord_id BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'registration',
    scoring_mode TEXT NOT NULL DEFAULT 'classic_sum',
    max_managers SMALLINT NOT NULL DEFAULT 8,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('registration', 'draft', 'active', 'finished', 'cancelled')),
    CHECK (scoring_mode IN ('classic_sum', 'normalized')),
    CHECK (max_managers BETWEEN 2 AND 8),
    UNIQUE (guild_id, name)
);

CREATE TABLE IF NOT EXISTS fantasy.season (
    id BIGSERIAL PRIMARY KEY,
    league_id BIGINT NOT NULL REFERENCES fantasy.league(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    scoring_rule_version TEXT NOT NULL DEFAULT 'riot_classic_v1',
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (league_id, name),
    CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at)
);

CREATE TABLE IF NOT EXISTS fantasy.manager (
    id BIGSERIAL PRIMARY KEY,
    league_id BIGINT NOT NULL REFERENCES fantasy.league(id) ON DELETE CASCADE,
    discord_user_id BIGINT NOT NULL,
    draft_position SMALLINT,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (draft_position IS NULL OR draft_position BETWEEN 1 AND 8),
    UNIQUE (league_id, discord_user_id),
    UNIQUE (league_id, draft_position)
);

CREATE TABLE IF NOT EXISTS fantasy.pro_team (
    id BIGSERIAL PRIMARY KEY,
    competition_code TEXT NOT NULL REFERENCES fantasy.competition(code),
    external_id TEXT NOT NULL,
    name TEXT NOT NULL,
    short_name TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (competition_code, external_id)
);

CREATE TABLE IF NOT EXISTS fantasy.pro_player (
    id BIGSERIAL PRIMARY KEY,
    external_id TEXT NOT NULL UNIQUE,
    handle TEXT NOT NULL,
    role TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (role IN ('TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT'))
);

CREATE TABLE IF NOT EXISTS fantasy.pro_player_team_history (
    id BIGSERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL REFERENCES fantasy.pro_player(id) ON DELETE CASCADE,
    team_id BIGINT NOT NULL REFERENCES fantasy.pro_team(id) ON DELETE CASCADE,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ,
    CHECK (valid_until IS NULL OR valid_until > valid_from)
);

CREATE INDEX IF NOT EXISTS idx_fantasy_player_team_history_lookup
    ON fantasy.pro_player_team_history (player_id, valid_from, valid_until);

CREATE TABLE IF NOT EXISTS fantasy.match_schedule (
    id BIGSERIAL PRIMARY KEY,
    external_id TEXT NOT NULL UNIQUE,
    competition_code TEXT NOT NULL REFERENCES fantasy.competition(code),
    tournament TEXT,
    scheduled_at_utc TIMESTAMPTZ NOT NULL,
    team1_id BIGINT REFERENCES fantasy.pro_team(id),
    team2_id BIGINT REFERENCES fantasy.pro_team(id),
    status TEXT NOT NULL DEFAULT 'scheduled',
    winner_team_id BIGINT REFERENCES fantasy.pro_team(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('scheduled', 'live', 'completed', 'cancelled', 'postponed')),
    CHECK (team1_id IS NULL OR team2_id IS NULL OR team1_id <> team2_id)
);

CREATE INDEX IF NOT EXISTS idx_fantasy_match_schedule_competition_time
    ON fantasy.match_schedule (competition_code, scheduled_at_utc);

CREATE TABLE IF NOT EXISTS fantasy.game (
    id BIGSERIAL PRIMARY KEY,
    external_game_id TEXT NOT NULL UNIQUE,
    schedule_id BIGINT REFERENCES fantasy.match_schedule(id) ON DELETE SET NULL,
    competition_code TEXT NOT NULL REFERENCES fantasy.competition(code),
    game_number SMALLINT,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    winner_team_id BIGINT REFERENCES fantasy.pro_team(id),
    duration_seconds INTEGER,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL,
    CHECK (duration_seconds IS NULL OR duration_seconds >= 0)
);

CREATE TABLE IF NOT EXISTS fantasy.player_game_stats (
    game_id BIGINT NOT NULL REFERENCES fantasy.game(id) ON DELETE CASCADE,
    player_id BIGINT NOT NULL REFERENCES fantasy.pro_player(id) ON DELETE CASCADE,
    team_id BIGINT REFERENCES fantasy.pro_team(id),
    kills INTEGER NOT NULL DEFAULT 0,
    deaths INTEGER NOT NULL DEFAULT 0,
    assists INTEGER NOT NULL DEFAULT 0,
    cs INTEGER NOT NULL DEFAULT 0,
    triple_kills INTEGER NOT NULL DEFAULT 0,
    quadra_kills INTEGER NOT NULL DEFAULT 0,
    penta_kills INTEGER NOT NULL DEFAULT 0,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (game_id, player_id),
    CHECK (kills >= 0 AND deaths >= 0 AND assists >= 0 AND cs >= 0),
    CHECK (triple_kills >= 0 AND quadra_kills >= 0 AND penta_kills >= 0)
);

CREATE TABLE IF NOT EXISTS fantasy.team_game_stats (
    game_id BIGINT NOT NULL REFERENCES fantasy.game(id) ON DELETE CASCADE,
    team_id BIGINT NOT NULL REFERENCES fantasy.pro_team(id) ON DELETE CASCADE,
    won BOOLEAN NOT NULL DEFAULT FALSE,
    barons INTEGER NOT NULL DEFAULT 0,
    dragons INTEGER NOT NULL DEFAULT 0,
    towers INTEGER NOT NULL DEFAULT 0,
    first_blood BOOLEAN NOT NULL DEFAULT FALSE,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (game_id, team_id),
    CHECK (barons >= 0 AND dragons >= 0 AND towers >= 0)
);

CREATE TABLE IF NOT EXISTS fantasy.draft (
    id BIGSERIAL PRIMARY KEY,
    season_id BIGINT NOT NULL UNIQUE REFERENCES fantasy.season(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    rounds SMALLINT NOT NULL DEFAULT 9,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    CHECK (status IN ('pending', 'active', 'completed', 'cancelled')),
    CHECK (rounds = 9)
);

CREATE TABLE IF NOT EXISTS fantasy.draft_pick (
    id BIGSERIAL PRIMARY KEY,
    draft_id BIGINT NOT NULL REFERENCES fantasy.draft(id) ON DELETE CASCADE,
    overall_pick SMALLINT NOT NULL,
    round_number SMALLINT NOT NULL,
    manager_id BIGINT NOT NULL REFERENCES fantasy.manager(id) ON DELETE CASCADE,
    player_id BIGINT REFERENCES fantasy.pro_player(id),
    team_id BIGINT REFERENCES fantasy.pro_team(id),
    picked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((player_id IS NOT NULL)::int + (team_id IS NOT NULL)::int = 1),
    UNIQUE (draft_id, overall_pick),
    UNIQUE (draft_id, player_id),
    UNIQUE (draft_id, team_id)
);

CREATE TABLE IF NOT EXISTS fantasy.roster_asset (
    id BIGSERIAL PRIMARY KEY,
    season_id BIGINT NOT NULL REFERENCES fantasy.season(id) ON DELETE CASCADE,
    manager_id BIGINT NOT NULL REFERENCES fantasy.manager(id) ON DELETE CASCADE,
    player_id BIGINT REFERENCES fantasy.pro_player(id),
    team_id BIGINT REFERENCES fantasy.pro_team(id),
    slot TEXT NOT NULL,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((player_id IS NOT NULL)::int + (team_id IS NOT NULL)::int = 1),
    CHECK (slot IN ('TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT', 'BENCH', 'TEAM')),
    CHECK ((slot = 'TEAM') = (team_id IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_fantasy_roster_player_per_season
    ON fantasy.roster_asset (season_id, player_id)
    WHERE player_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_fantasy_roster_team_per_season
    ON fantasy.roster_asset (season_id, team_id)
    WHERE team_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_fantasy_roster_starter_slot
    ON fantasy.roster_asset (season_id, manager_id, slot)
    WHERE slot IN ('TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT', 'TEAM');

CREATE TABLE IF NOT EXISTS fantasy.roster_history (
    id BIGSERIAL PRIMARY KEY,
    season_id BIGINT NOT NULL REFERENCES fantasy.season(id) ON DELETE CASCADE,
    manager_id BIGINT NOT NULL REFERENCES fantasy.manager(id) ON DELETE CASCADE,
    player_id BIGINT REFERENCES fantasy.pro_player(id),
    team_id BIGINT REFERENCES fantasy.pro_team(id),
    slot TEXT NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ,
    reason TEXT NOT NULL,
    CHECK ((player_id IS NOT NULL)::int + (team_id IS NOT NULL)::int = 1),
    CHECK (slot IN ('TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT', 'BENCH', 'TEAM')),
    CHECK (valid_until IS NULL OR valid_until > valid_from)
);

CREATE INDEX IF NOT EXISTS idx_fantasy_roster_history_at_time
    ON fantasy.roster_history (season_id, manager_id, valid_from, valid_until);

CREATE TABLE IF NOT EXISTS fantasy.trade (
    id BIGSERIAL PRIMARY KEY,
    season_id BIGINT NOT NULL REFERENCES fantasy.season(id) ON DELETE CASCADE,
    proposer_manager_id BIGINT NOT NULL REFERENCES fantasy.manager(id),
    recipient_manager_id BIGINT NOT NULL REFERENCES fantasy.manager(id),
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    CHECK (proposer_manager_id <> recipient_manager_id),
    CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled', 'invalidated'))
);

CREATE TABLE IF NOT EXISTS fantasy.trade_asset (
    id BIGSERIAL PRIMARY KEY,
    trade_id BIGINT NOT NULL REFERENCES fantasy.trade(id) ON DELETE CASCADE,
    from_manager_id BIGINT NOT NULL REFERENCES fantasy.manager(id),
    player_id BIGINT REFERENCES fantasy.pro_player(id),
    team_id BIGINT REFERENCES fantasy.pro_team(id),
    CHECK ((player_id IS NOT NULL)::int + (team_id IS NOT NULL)::int = 1)
);

CREATE TABLE IF NOT EXISTS fantasy.scoring_rule (
    version TEXT PRIMARY KEY,
    rules JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO fantasy.scoring_rule (version, rules)
VALUES (
    'riot_classic_v1',
    '{"player":{"kill":2.0,"death":-0.5,"assist":1.5,"cs":0.01,"triple":2.0,"quadra":5.0,"penta":10.0,"ten_kill_or_assist":2.0},"team":{"win":2.0,"baron":2.0,"dragon":1.0,"first_blood":2.0,"tower":1.0,"win_under_30":2.0}}'::jsonb
)
ON CONFLICT (version) DO NOTHING;

CREATE TABLE IF NOT EXISTS fantasy.player_game_score (
    season_id BIGINT NOT NULL REFERENCES fantasy.season(id) ON DELETE CASCADE,
    game_id BIGINT NOT NULL REFERENCES fantasy.game(id) ON DELETE CASCADE,
    player_id BIGINT NOT NULL REFERENCES fantasy.pro_player(id) ON DELETE CASCADE,
    score NUMERIC(12, 3) NOT NULL,
    rule_version TEXT NOT NULL REFERENCES fantasy.scoring_rule(version),
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (season_id, game_id, player_id, rule_version)
);

CREATE TABLE IF NOT EXISTS fantasy.team_game_score (
    season_id BIGINT NOT NULL REFERENCES fantasy.season(id) ON DELETE CASCADE,
    game_id BIGINT NOT NULL REFERENCES fantasy.game(id) ON DELETE CASCADE,
    team_id BIGINT NOT NULL REFERENCES fantasy.pro_team(id) ON DELETE CASCADE,
    score NUMERIC(12, 3) NOT NULL,
    rule_version TEXT NOT NULL REFERENCES fantasy.scoring_rule(version),
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (season_id, game_id, team_id, rule_version)
);

CREATE TABLE IF NOT EXISTS fantasy.matchup (
    id BIGSERIAL PRIMARY KEY,
    season_id BIGINT NOT NULL REFERENCES fantasy.season(id) ON DELETE CASCADE,
    round_number SMALLINT NOT NULL,
    manager1_id BIGINT REFERENCES fantasy.manager(id),
    manager2_id BIGINT REFERENCES fantasy.manager(id),
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    CHECK (manager1_id IS NOT NULL OR manager2_id IS NOT NULL),
    CHECK (manager1_id IS NULL OR manager2_id IS NULL OR manager1_id <> manager2_id),
    UNIQUE (season_id, round_number, manager1_id, manager2_id)
);

CREATE TABLE IF NOT EXISTS fantasy.manager_period_score (
    matchup_id BIGINT NOT NULL REFERENCES fantasy.matchup(id) ON DELETE CASCADE,
    manager_id BIGINT NOT NULL REFERENCES fantasy.manager(id) ON DELETE CASCADE,
    score NUMERIC(14, 3) NOT NULL DEFAULT 0,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (matchup_id, manager_id)
);

COMMIT;
