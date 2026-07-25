BEGIN;

-- ---------------------------------------------------------------------------
-- match_gank_events : une ligne représente désormais une tentative observée,
-- pas uniquement un kill de lane impliquant le jungler.
-- ---------------------------------------------------------------------------
ALTER TABLE IF EXISTS match_gank_events
    ADD COLUMN IF NOT EXISTS gank_id INTEGER,
    ADD COLUMN IF NOT EXISTS start_ms BIGINT,
    ADD COLUMN IF NOT EXISTS end_ms BIGINT,
    ADD COLUMN IF NOT EXISTS outcome TEXT,
    ADD COLUMN IF NOT EXISTS detection_source TEXT,
    ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS kills_for INTEGER,
    ADD COLUMN IF NOT EXISTS kills_against INTEGER,
    ADD COLUMN IF NOT EXISTS jungler_kills INTEGER,
    ADD COLUMN IF NOT EXISTS jungler_assists INTEGER,
    ADD COLUMN IF NOT EXISTS jungler_deaths INTEGER,
    ADD COLUMN IF NOT EXISTS participants_allies INTEGER,
    ADD COLUMN IF NOT EXISTS participants_enemies INTEGER,
    ADD COLUMN IF NOT EXISTS is_teamfight BOOLEAN,
    ADD COLUMN IF NOT EXISTS jungler_damage_delta BIGINT,
    ADD COLUMN IF NOT EXISTS lane_activity_delta BIGINT,
    ADD COLUMN IF NOT EXISTS position_evidence TEXT,
    ADD COLUMN IF NOT EXISTS algorithm_version SMALLINT;

-- Les anciennes lignes provenaient toutes de CHAMPION_KILL. On peut donc
-- backfiller les métadonnées sûres sans prétendre reconstruire les participants,
-- le K/D/A du jungler ou la nature teamfight des anciens événements.
WITH ranked AS (
    SELECT
        ctid,
        ROW_NUMBER() OVER (
            PARTITION BY match_id, team_id
            ORDER BY timestamp_ms, ctid
        ) AS rn
    FROM match_gank_events
)
UPDATE match_gank_events AS event
SET gank_id = COALESCE(event.gank_id, ranked.rn)
FROM ranked
WHERE event.ctid = ranked.ctid
  AND event.gank_id IS NULL;

UPDATE match_gank_events
SET
    start_ms = COALESCE(start_ms, timestamp_ms),
    end_ms = COALESCE(end_ms, timestamp_ms),
    outcome = COALESCE(outcome, CASE WHEN successful THEN 'success' ELSE 'failed' END),
    detection_source = COALESCE(detection_source, 'exact_event'),
    confidence = COALESCE(confidence, 1.0),
    kills_for = COALESCE(kills_for, CASE WHEN successful THEN 1 ELSE 0 END),
    kills_against = COALESCE(kills_against, CASE WHEN successful THEN 0 ELSE 1 END),
    jungler_damage_delta = COALESCE(jungler_damage_delta, 0),
    lane_activity_delta = COALESCE(lane_activity_delta, 0),
    position_evidence = COALESCE(position_evidence, 'exact_event'),
    algorithm_version = COALESCE(algorithm_version, 1)
WHERE
    start_ms IS NULL
    OR end_ms IS NULL
    OR outcome IS NULL
    OR detection_source IS NULL
    OR confidence IS NULL
    OR gank_id IS NULL
    OR algorithm_version IS NULL;

ALTER TABLE IF EXISTS match_gank_events
    DROP CONSTRAINT IF EXISTS match_gank_events_outcome_check;
ALTER TABLE IF EXISTS match_gank_events
    ADD CONSTRAINT match_gank_events_outcome_check
    CHECK (outcome IS NULL OR outcome IN ('success', 'trade', 'failed', 'jungler_death'));

ALTER TABLE IF EXISTS match_gank_events
    DROP CONSTRAINT IF EXISTS match_gank_events_detection_source_check;
ALTER TABLE IF EXISTS match_gank_events
    ADD CONSTRAINT match_gank_events_detection_source_check
    CHECK (
        detection_source IS NULL
        OR detection_source IN ('exact_event', 'sampled_combat', 'inferred_combat')
    );

ALTER TABLE IF EXISTS match_gank_events
    DROP CONSTRAINT IF EXISTS match_gank_events_confidence_check;
ALTER TABLE IF EXISTS match_gank_events
    ADD CONSTRAINT match_gank_events_confidence_check
    CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0));

CREATE INDEX IF NOT EXISTS idx_match_gank_events_match_team_gank
    ON match_gank_events (match_id, team_id, gank_id);
CREATE INDEX IF NOT EXISTS idx_match_gank_events_source_confidence
    ON match_gank_events (detection_source, confidence);
CREATE INDEX IF NOT EXISTS idx_match_gank_events_lane_time
    ON match_gank_events (lane, timestamp_ms);

-- ---------------------------------------------------------------------------
-- match_gank_summary : exposition de la qualité de détection et du taux de
-- succès observé. Les anciens noms restent présents pour compatibilité.
-- ---------------------------------------------------------------------------
ALTER TABLE IF EXISTS match_gank_summary
    ADD COLUMN IF NOT EXISTS failed_made INTEGER,
    ADD COLUMN IF NOT EXISTS failed_received INTEGER,
    ADD COLUMN IF NOT EXISTS exact_attempts_made INTEGER,
    ADD COLUMN IF NOT EXISTS exact_attempts_received INTEGER,
    ADD COLUMN IF NOT EXISTS inferred_attempts_made INTEGER,
    ADD COLUMN IF NOT EXISTS inferred_attempts_received INTEGER,
    ADD COLUMN IF NOT EXISTS high_confidence_made INTEGER,
    ADD COLUMN IF NOT EXISTS high_confidence_received INTEGER,
    ADD COLUMN IF NOT EXISTS observed_success_rate_made DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS observed_death_rate_received DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS algorithm_version SMALLINT;

UPDATE match_gank_summary
SET
    failed_made = COALESCE(failed_made, GREATEST(0, COALESCE(total_ganks_made, 0) - COALESCE(successful_made, 0))),
    failed_received = COALESCE(failed_received, GREATEST(0, COALESCE(total_ganks_received, 0) - COALESCE(successful_received, 0))),
    exact_attempts_made = COALESCE(exact_attempts_made, total_ganks_made, 0),
    exact_attempts_received = COALESCE(exact_attempts_received, total_ganks_received, 0),
    inferred_attempts_made = COALESCE(inferred_attempts_made, 0),
    inferred_attempts_received = COALESCE(inferred_attempts_received, 0),
    high_confidence_made = COALESCE(high_confidence_made, total_ganks_made, 0),
    high_confidence_received = COALESCE(high_confidence_received, total_ganks_received, 0),
    observed_success_rate_made = COALESCE(observed_success_rate_made, success_rate_made, 0),
    observed_death_rate_received = COALESCE(observed_death_rate_received, death_rate_received, 0),
    algorithm_version = COALESCE(algorithm_version, 1)
WHERE
    failed_made IS NULL
    OR failed_received IS NULL
    OR exact_attempts_made IS NULL
    OR exact_attempts_received IS NULL
    OR inferred_attempts_made IS NULL
    OR inferred_attempts_received IS NULL
    OR high_confidence_made IS NULL
    OR high_confidence_received IS NULL
    OR observed_success_rate_made IS NULL
    OR observed_death_rate_received IS NULL
    OR algorithm_version IS NULL;

COMMIT;
