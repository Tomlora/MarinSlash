BEGIN;

-- start_minute/end_minute ne représentent pas des minutes décimales mais un
-- affichage MM.SS dans les colonnes numériques existantes.
-- Exemple : 658000 ms = 10 min 58 s => 10.58 (et non 10.97).
UPDATE match_teamfight_damage
SET
    start_minute = (
        FLOOR(start_ms::numeric / 60000)
        + FLOOR(MOD(start_ms, 60000)::numeric / 1000) / 100
    ),
    end_minute = (
        FLOOR(end_ms::numeric / 60000)
        + FLOOR(MOD(end_ms, 60000)::numeric / 1000) / 100
    )
WHERE start_ms IS NOT NULL
  AND end_ms IS NOT NULL;

COMMIT;
