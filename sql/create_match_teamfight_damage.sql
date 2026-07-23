CREATE TABLE IF NOT EXISTS match_teamfight_damage (
    match_id VARCHAR(32) NOT NULL,
    analyzed_puuid VARCHAR(100) NOT NULL,
    fight_id SMALLINT NOT NULL CHECK (fight_id > 0),
    participant_id SMALLINT NOT NULL CHECK (participant_id BETWEEN 1 AND 10),
    puuid VARCHAR(100) NOT NULL,
    player_name TEXT NOT NULL,
    champion VARCHAR(64) NOT NULL,
    team VARCHAR(6) NOT NULL CHECK (team IN ('Allié', 'Ennemi')),
    participation_source VARCHAR(10) NOT NULL
        CHECK (participation_source IN ('event', 'proximity')),

    start_ms BIGINT NOT NULL,
    end_ms BIGINT NOT NULL,
    start_minute NUMERIC(7, 2) NOT NULL,
    end_minute NUMERIC(7, 2) NOT NULL,
    estimation_window_start_ms BIGINT NOT NULL,
    estimation_window_end_ms BIGINT NOT NULL,

    kills_allies SMALLINT NOT NULL DEFAULT 0 CHECK (kills_allies >= 0),
    kills_enemies SMALLINT NOT NULL DEFAULT 0 CHECK (kills_enemies >= 0),

    damage_on_dead_targets INTEGER NOT NULL DEFAULT 0
        CHECK (damage_on_dead_targets >= 0),
    physical_damage_on_dead_targets INTEGER NOT NULL DEFAULT 0
        CHECK (physical_damage_on_dead_targets >= 0),
    magic_damage_on_dead_targets INTEGER NOT NULL DEFAULT 0
        CHECK (magic_damage_on_dead_targets >= 0),
    true_damage_on_dead_targets INTEGER NOT NULL DEFAULT 0
        CHECK (true_damage_on_dead_targets >= 0),
    damage_window_estimated INTEGER NOT NULL DEFAULT 0
        CHECK (damage_window_estimated >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT match_teamfight_damage_pk PRIMARY KEY (
        match_id,
        analyzed_puuid,
        fight_id,
        puuid
    ),
    CONSTRAINT match_teamfight_damage_time_check CHECK (end_ms >= start_ms),
    CONSTRAINT match_teamfight_damage_window_check CHECK (
        estimation_window_end_ms >= estimation_window_start_ms
    )
);

CREATE INDEX IF NOT EXISTS idx_match_teamfight_damage_puuid
    ON match_teamfight_damage (puuid, match_id);

CREATE INDEX IF NOT EXISTS idx_match_teamfight_damage_match
    ON match_teamfight_damage (match_id, analyzed_puuid, fight_id);
