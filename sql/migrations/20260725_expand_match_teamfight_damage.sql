BEGIN;

ALTER TABLE IF EXISTS match_teamfight_damage
    ADD COLUMN IF NOT EXISTS first_kill_ms BIGINT,
    ADD COLUMN IF NOT EXISTS last_kill_ms BIGINT,
    ADD COLUMN IF NOT EXISTS kill_span_ms BIGINT,
    ADD COLUMN IF NOT EXISTS allied_kills INTEGER,
    ADD COLUMN IF NOT EXISTS enemy_kills INTEGER,
    ADD COLUMN IF NOT EXISTS winner TEXT,
    ADD COLUMN IF NOT EXISTS core_allies INTEGER,
    ADD COLUMN IF NOT EXISTS core_enemies INTEGER,
    ADD COLUMN IF NOT EXISTS participants_allies INTEGER,
    ADD COLUMN IF NOT EXISTS participants_enemies INTEGER,
    ADD COLUMN IF NOT EXISTS proximity_allies INTEGER,
    ADD COLUMN IF NOT EXISTS proximity_enemies INTEGER,
    ADD COLUMN IF NOT EXISTS fight_type TEXT,
    ADD COLUMN IF NOT EXISTS fight_type_with_proximity TEXT,
    ADD COLUMN IF NOT EXISTS fight_category TEXT,
    ADD COLUMN IF NOT EXISTS is_teamfight BOOLEAN,
    ADD COLUMN IF NOT EXISTS is_outnumbered BOOLEAN,
    ADD COLUMN IF NOT EXISTS outnumbered_team TEXT,
    ADD COLUMN IF NOT EXISTS won_while_outnumbered BOOLEAN,
    ADD COLUMN IF NOT EXISTS shared_damage_window BOOLEAN,
    ADD COLUMN IF NOT EXISTS shared_window_fight_count INTEGER,
    ADD COLUMN IF NOT EXISTS is_core_participant BOOLEAN,
    ADD COLUMN IF NOT EXISTS is_proximity_participant BOOLEAN,
    ADD COLUMN IF NOT EXISTS was_killer BOOLEAN,
    ADD COLUMN IF NOT EXISTS was_victim BOOLEAN,
    ADD COLUMN IF NOT EXISTS was_assistant BOOLEAN,
    ADD COLUMN IF NOT EXISTS was_damage_source BOOLEAN,
    ADD COLUMN IF NOT EXISTS fight_kills INTEGER,
    ADD COLUMN IF NOT EXISTS fight_deaths INTEGER,
    ADD COLUMN IF NOT EXISTS fight_assists INTEGER,
    ADD COLUMN IF NOT EXISTS survived BOOLEAN,
    ADD COLUMN IF NOT EXISTS enemies_damaged_count INTEGER,
    ADD COLUMN IF NOT EXISTS damage_share_on_dead_targets DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS damage_frame_window BIGINT;

-- La nouvelle valeur "event+damage" fait 12 caractères. L'ancien schéma
-- utilisait VARCHAR(10), ce qui provoquait StringDataRightTruncation.
ALTER TABLE IF EXISTS match_teamfight_damage
    ALTER COLUMN participation_source TYPE TEXT
    USING participation_source::TEXT;

-- L'ancien CHECK n'autorisait que les valeurs historiques. Les nouvelles
-- sources "damage" et "event+damage" sont produites par le calcul enrichi.
ALTER TABLE IF EXISTS match_teamfight_damage
    DROP CONSTRAINT IF EXISTS match_teamfight_damage_participation_source_check;

ALTER TABLE IF EXISTS match_teamfight_damage
    ADD CONSTRAINT match_teamfight_damage_participation_source_check
    CHECK (participation_source IN ('event', 'damage', 'event+damage', 'proximity'));

-- Backfill des champs qui peuvent être reconstruits sans ambiguïté sur l'historique.
UPDATE match_teamfight_damage
SET
    first_kill_ms = COALESCE(first_kill_ms, start_ms),
    last_kill_ms = COALESCE(last_kill_ms, end_ms),
    kill_span_ms = COALESCE(kill_span_ms, GREATEST(0, end_ms - start_ms)),
    allied_kills = COALESCE(allied_kills, kills_allies),
    enemy_kills = COALESCE(enemy_kills, kills_enemies),
    shared_damage_window = COALESCE(shared_damage_window, FALSE),
    shared_window_fight_count = COALESCE(shared_window_fight_count, 1),
    damage_frame_window = COALESCE(damage_frame_window, damage_window_estimated)
WHERE
    first_kill_ms IS NULL
    OR last_kill_ms IS NULL
    OR kill_span_ms IS NULL
    OR allied_kills IS NULL
    OR enemy_kills IS NULL
    OR shared_damage_window IS NULL
    OR shared_window_fight_count IS NULL
    OR damage_frame_window IS NULL;

-- start_minute/end_minute sont des valeurs MM.SS, pas des minutes décimales.
-- Exemple : 658000 ms = 10 min 58 s => 10.58, et non 10.97.
UPDATE match_teamfight_damage
SET
    start_minute = (
        FLOOR(start_ms::numeric / 60000)
        + FLOOR(MOD(start_ms, 60000)::numeric / 1000) / 100
    ),
    end_minute = (
        FLOOR(end_ms::numeric / 60000)
        + FLOOR(MOD(end_ms, 60000)::numeric / 1000) / 100
    )
WHERE start_ms IS NOT NULL
  AND end_ms IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_match_teamfight_damage_match_fight
    ON match_teamfight_damage (match_id, analyzed_puuid, fight_id);

CREATE INDEX IF NOT EXISTS idx_match_teamfight_damage_player
    ON match_teamfight_damage (puuid, fight_category);

CREATE INDEX IF NOT EXISTS idx_match_teamfight_damage_type
    ON match_teamfight_damage (fight_type, is_outnumbered, is_teamfight);

-- Vue pratique pour les futurs records/badges : clutch, survie, dégâts et KDA de combat.
CREATE OR REPLACE VIEW match_teamfight_player_summary AS
SELECT
    match_id,
    analyzed_puuid,
    participant_id,
    puuid,
    MAX(player_name) AS player_name,
    MAX(champion) AS champion,
    MAX(team) AS team,
    COUNT(*) AS fights_participated,
    COUNT(*) FILTER (WHERE is_core_participant) AS core_fights,
    COUNT(*) FILTER (WHERE fight_category = 'duel') AS duels,
    COUNT(*) FILTER (WHERE fight_category = 'skirmish') AS skirmishes,
    COUNT(*) FILTER (WHERE is_teamfight) AS teamfights,
    COUNT(*) FILTER (
        WHERE is_outnumbered AND team = outnumbered_team
    ) AS outnumbered_fights,
    COUNT(*) FILTER (
        WHERE won_while_outnumbered AND team = outnumbered_team
    ) AS outnumbered_wins,
    SUM(COALESCE(fight_kills, 0)) AS fight_kills,
    SUM(COALESCE(fight_deaths, 0)) AS fight_deaths,
    SUM(COALESCE(fight_assists, 0)) AS fight_assists,
    SUM(COALESCE(damage_on_dead_targets, 0)) AS damage_on_dead_targets,
    AVG(damage_share_on_dead_targets) FILTER (
        WHERE damage_share_on_dead_targets IS NOT NULL
    ) AS avg_damage_share_on_dead_targets,
    AVG(CASE WHEN survived THEN 1.0 ELSE 0.0 END) FILTER (
        WHERE survived IS NOT NULL
    ) AS survival_rate,
    (
        COUNT(*) FILTER (
            WHERE won_while_outnumbered AND team = outnumbered_team
        )::DOUBLE PRECISION
        / NULLIF(
            COUNT(*) FILTER (
                WHERE is_outnumbered AND team = outnumbered_team
            ),
            0
        )
    ) AS outnumbered_win_rate
FROM match_teamfight_damage
GROUP BY match_id, analyzed_puuid, participant_id, puuid;

COMMIT;
