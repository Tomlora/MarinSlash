BEGIN;

-- Hotfix pour les bases où 20260725_expand_match_teamfight_damage.sql
-- a déjà été exécutée avant l'élargissement de participation_source.
-- "event+damage" contient 12 caractères et ne tient pas dans VARCHAR(10).
ALTER TABLE IF EXISTS match_teamfight_damage
    ALTER COLUMN participation_source TYPE TEXT
    USING participation_source::TEXT;

-- L'ancien schéma limitait participation_source à "event" / "proximity".
-- Le nouveau calcul distingue aussi les participants confirmés uniquement par
-- victimDamageReceived ("damage") et ceux confirmés par les deux sources
-- ("event+damage"). La contrainte doit donc évoluer en même temps que le type.
ALTER TABLE IF EXISTS match_teamfight_damage
    DROP CONSTRAINT IF EXISTS match_teamfight_damage_participation_source_check;

ALTER TABLE IF EXISTS match_teamfight_damage
    ADD CONSTRAINT match_teamfight_damage_participation_source_check
    CHECK (participation_source IN ('event', 'damage', 'event+damage', 'proximity'));

COMMIT;
