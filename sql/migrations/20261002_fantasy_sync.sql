BEGIN;
CREATE TABLE IF NOT EXISTS fantasy.sync_job (
    kind TEXT PRIMARY KEY CHECK (kind IN ('pool', 'schedule')),
    last_attempt_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_error TEXT,
    source TEXT
);
CREATE TABLE IF NOT EXISTS fantasy.schedule_coverage (
    competition_code TEXT PRIMARY KEY REFERENCES fantasy.competition(code),
    refreshed_at TIMESTAMPTZ NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    CHECK (window_end > window_start)
);
COMMIT;
