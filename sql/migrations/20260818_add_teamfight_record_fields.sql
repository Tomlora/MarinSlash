BEGIN;

ALTER TABLE IF EXISTS match_teamfight_damage
    ADD COLUMN IF NOT EXISTS physical_damage_window_estimated BIGINT,
    ADD COLUMN IF NOT EXISTS magic_damage_window_estimated BIGINT,
    ADD COLUMN IF NOT EXISTS true_damage_window_estimated BIGINT;

-- Un duel est un vrai 1v1 uniquement pour les deux participants core.
-- duel_wins est ajouté en dernière colonne pour rester compatible avec
-- CREATE OR REPLACE VIEW sur une vue existante PostgreSQL.
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
    COUNT(*) FILTER (
        WHERE fight_category = 'duel'
          AND COALESCE(is_core_participant, TRUE)
    ) AS duels,
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
    ) AS outnumbered_win_rate,
    COUNT(*) FILTER (
        WHERE fight_category = 'duel'
          AND COALESCE(is_core_participant, TRUE)
          AND winner = team
    ) AS duel_wins
FROM match_teamfight_damage
GROUP BY match_id, analyzed_puuid, participant_id, puuid;

COMMIT;
