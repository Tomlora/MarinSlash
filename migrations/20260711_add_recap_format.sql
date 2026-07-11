BEGIN;

ALTER TABLE tracker
    ADD COLUMN IF NOT EXISTS recap_format VARCHAR(16) NOT NULL DEFAULT 'legacy';

UPDATE tracker
SET recap_format = 'legacy'
WHERE recap_format IS NULL
   OR recap_format NOT IN ('legacy', 'modern');

ALTER TABLE tracker
    DROP CONSTRAINT IF EXISTS tracker_recap_format_check;

ALTER TABLE tracker
    ADD CONSTRAINT tracker_recap_format_check
    CHECK (recap_format IN ('legacy', 'modern'));

COMMENT ON COLUMN tracker.recap_format IS
    'Format du recap LoL : legacy (historique) ou modern (dashboard sombre).';

COMMIT;
