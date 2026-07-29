BEGIN;

-- Repair installations where tables named fantasy.league / pro_player /
-- draft_pick already existed before 20260725_fantasy_initial.sql was run.
-- CREATE TABLE IF NOT EXISTS does not reconcile an existing table definition,
-- so the missing columns must be added explicitly.

-- ---------------------------------------------------------------------------
-- fantasy.league
-- ---------------------------------------------------------------------------
ALTER TABLE fantasy.league
    ADD COLUMN IF NOT EXISTS guild_id BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS owner_discord_id BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'cancelled',
    ADD COLUMN IF NOT EXISTS scoring_mode TEXT NOT NULL DEFAULT 'classic_sum',
    ADD COLUMN IF NOT EXISTS max_managers SMALLINT NOT NULL DEFAULT 8;

-- Legacy rows are deliberately kept detached from real Discord guilds.
-- New rows created by the bot always provide guild_id/owner_discord_id.
ALTER TABLE fantasy.league
    ALTER COLUMN guild_id DROP DEFAULT,
    ALTER COLUMN owner_discord_id DROP DEFAULT,
    ALTER COLUMN status SET DEFAULT 'registration',
    ALTER COLUMN scoring_mode SET DEFAULT 'classic_sum',
    ALTER COLUMN max_managers SET DEFAULT 8;

CREATE UNIQUE INDEX IF NOT EXISTS uq_fantasy_league_guild_name
    ON fantasy.league (guild_id, name)
    WHERE guild_id <> 0;

-- ---------------------------------------------------------------------------
-- fantasy.pro_player
-- ---------------------------------------------------------------------------
ALTER TABLE fantasy.pro_player
    ADD COLUMN IF NOT EXISTS external_id TEXT,
    ADD COLUMN IF NOT EXISTS handle TEXT;

-- Preserve legacy rows without pretending they came from the live provider.
UPDATE fantasy.pro_player
SET external_id = 'legacy:' || id::text
WHERE external_id IS NULL;

UPDATE fantasy.pro_player
SET handle = 'legacy-' || id::text
WHERE handle IS NULL OR BTRIM(handle) = '';

ALTER TABLE fantasy.pro_player
    ALTER COLUMN external_id SET NOT NULL,
    ALTER COLUMN handle SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_fantasy_pro_player_external_id
    ON fantasy.pro_player (external_id);

-- Old unidentified rows must not enter a new draft pool. They can remain for
-- history and will naturally be superseded by the next live synchronization.
UPDATE fantasy.pro_player
SET active = FALSE
WHERE external_id LIKE 'legacy:%';

-- ---------------------------------------------------------------------------
-- fantasy.draft_pick
-- ---------------------------------------------------------------------------
ALTER TABLE fantasy.draft_pick
    ADD COLUMN IF NOT EXISTS draft_id BIGINT REFERENCES fantasy.draft(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS overall_pick SMALLINT,
    ADD COLUMN IF NOT EXISTS round_number SMALLINT,
    ADD COLUMN IF NOT EXISTS team_id BIGINT REFERENCES fantasy.pro_team(id);

-- Existing legacy picks cannot be safely attached to a new draft without
-- knowing their original draft/round. Keep them nullable; every new pick made
-- by the Fantasy service explicitly supplies these values.
CREATE UNIQUE INDEX IF NOT EXISTS uq_fantasy_draft_pick_overall
    ON fantasy.draft_pick (draft_id, overall_pick)
    WHERE draft_id IS NOT NULL AND overall_pick IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_fantasy_draft_pick_player
    ON fantasy.draft_pick (draft_id, player_id)
    WHERE draft_id IS NOT NULL AND player_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_fantasy_draft_pick_team
    ON fantasy.draft_pick (draft_id, team_id)
    WHERE draft_id IS NOT NULL AND team_id IS NOT NULL;

COMMIT;
