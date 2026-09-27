CREATE TABLE IF NOT EXISTS records_preferences (
    discord BIGINT PRIMARY KEY,
    layout VARCHAR(16) NOT NULL DEFAULT 'compact'
        CHECK (layout IN ('compact', 'sections')),
    show_alltime BOOLEAN NOT NULL DEFAULT TRUE,
    show_season BOOLEAN NOT NULL DEFAULT TRUE,
    show_personal BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
