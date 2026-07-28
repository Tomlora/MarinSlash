-- Development-only Fantasy pool.
--
-- This file is intentionally NOT a migration. Run it manually on a development
-- database when testing /fantasy draft_* before real providers are installed.
-- It is idempotent and creates 8 teams + 80 synthetic players across LEC/LCS/LFL.

BEGIN;

INSERT INTO fantasy.pro_team
    (competition_code, external_id, name, short_name, active)
VALUES
    ('LEC', 'test-lec-1', 'Fantasy Test LEC One', 'TLEC1', TRUE),
    ('LEC', 'test-lec-2', 'Fantasy Test LEC Two', 'TLEC2', TRUE),
    ('LEC', 'test-lec-3', 'Fantasy Test LEC Three', 'TLEC3', TRUE),
    ('LFL', 'test-lfl-1', 'Fantasy Test LFL One', 'TLFL1', TRUE),
    ('LFL', 'test-lfl-2', 'Fantasy Test LFL Two', 'TLFL2', TRUE),
    ('LFL', 'test-lfl-3', 'Fantasy Test LFL Three', 'TLFL3', TRUE),
    ('LCS', 'test-lcs-1', 'Fantasy Test LCS One', 'TLCS1', TRUE),
    ('LCS', 'test-lcs-2', 'Fantasy Test LCS Two', 'TLCS2', TRUE)
ON CONFLICT (competition_code, external_id) DO UPDATE
SET
    name = EXCLUDED.name,
    short_name = EXCLUDED.short_name,
    active = TRUE,
    updated_at = NOW();

WITH test_teams AS (
    SELECT external_id, short_name
    FROM fantasy.pro_team
    WHERE external_id LIKE 'test-%'
),
roles(role) AS (
    VALUES ('TOP'), ('JUNGLE'), ('MID'), ('ADC'), ('SUPPORT')
),
player_numbers(n) AS (
    VALUES (1), (2)
)
INSERT INTO fantasy.pro_player (external_id, handle, role, active)
SELECT
    'fantasy-test:' || team.external_id || ':' || roles.role || ':' || player_numbers.n,
    team.short_name || '_' || roles.role || '_' || player_numbers.n,
    roles.role,
    TRUE
FROM test_teams team
CROSS JOIN roles
CROSS JOIN player_numbers
ON CONFLICT (external_id) DO UPDATE
SET
    handle = EXCLUDED.handle,
    role = EXCLUDED.role,
    active = TRUE,
    updated_at = NOW();

INSERT INTO fantasy.pro_player_team_history (player_id, team_id, valid_from)
SELECT
    player.id,
    team.id,
    NOW()
FROM fantasy.pro_player player
JOIN fantasy.pro_team team
  ON team.external_id = split_part(player.external_id, ':', 2)
WHERE player.external_id LIKE 'fantasy-test:%'
  AND NOT EXISTS (
      SELECT 1
      FROM fantasy.pro_player_team_history history
      WHERE history.player_id = player.id
        AND history.valid_until IS NULL
  );

COMMIT;

-- Example handles after seeding:
-- TLEC1_TOP_1
-- TLFL2_JUNGLE_2
-- TLCS1_MID_1
--
-- Team picks accept short names such as TLEC1, TLFL1 or TLCS1.
