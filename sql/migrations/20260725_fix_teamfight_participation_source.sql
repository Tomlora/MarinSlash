BEGIN;

-- Hotfix pour les bases où 20260725_expand_match_teamfight_damage.sql
-- a déjà été exécutée avant l'élargissement de participation_source.
-- "event+damage" contient 12 caractères et ne tient pas dans VARCHAR(10).
ALTER TABLE IF EXISTS match_teamfight_damage
    ALTER COLUMN participation_source TYPE TEXT
    USING participation_source::TEXT;

COMMIT;
