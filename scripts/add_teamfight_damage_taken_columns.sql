BEGIN;

ALTER TABLE match_teamfight_damage
    ADD COLUMN IF NOT EXISTS damage_taken_frame_window BIGINT,
    ADD COLUMN IF NOT EXISTS physical_damage_taken_frame_window BIGINT,
    ADD COLUMN IF NOT EXISTS magic_damage_taken_frame_window BIGINT,
    ADD COLUMN IF NOT EXISTS true_damage_taken_frame_window BIGINT;

COMMENT ON COLUMN match_teamfight_damage.damage_taken_frame_window IS
    'Delta totalDamageTaken entre les deux frames Riot du combat; toutes sources de degats.';
COMMENT ON COLUMN match_teamfight_damage.physical_damage_taken_frame_window IS
    'Delta physicalDamageTaken entre les deux frames Riot du combat; toutes sources de degats.';
COMMENT ON COLUMN match_teamfight_damage.magic_damage_taken_frame_window IS
    'Delta magicDamageTaken entre les deux frames Riot du combat; toutes sources de degats.';
COMMENT ON COLUMN match_teamfight_damage.true_damage_taken_frame_window IS
    'Delta trueDamageTaken entre les deux frames Riot du combat; toutes sources de degats.';

COMMIT;
