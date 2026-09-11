"""Crée les vues PostgreSQL exposant le peak Elo SoloQ des comptes suivis.

Deux vues sont créées :

- ``public.v_peak_elo`` : meilleur Elo SoloQ historique de chaque compte ;
- ``public.v_peak_elo_season`` : meilleur Elo SoloQ de chaque compte pour
  chaque saison où il possède un historique ranked valide.

Le peak Elo est calculé à partir de l'historique ``public.matchs`` et uniquement
sur les parties ``RANKED`` afin de ne pas mélanger la SoloQ avec la Flex.

L'ordre de comparaison est :
    tier > division > LP

Pour MASTER / GRANDMASTER / CHALLENGER, la division n'est pas prise en compte.
En cas d'égalité parfaite, la ligne la plus récente est conservée.

``v_peak_elo`` garde tous les comptes de ``tracker``. Un compte sans historique
SoloQ valide aura simplement les colonnes ``peak_*`` à NULL.

``v_peak_elo_season`` contient une ligne par couple ``id_compte`` / ``season``
présent dans l'historique SoloQ.

Usage :
    python scripts/create_peak_elo_view.py

La commande est idempotente grâce à ``CREATE OR REPLACE VIEW``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fonctions.gestion_bdd import engine


VIEW_NAME = "public.v_peak_elo"
VIEW_SEASON_NAME = "public.v_peak_elo_season"

VIEW_SQL = f"""
CREATE OR REPLACE VIEW {VIEW_NAME} AS
WITH ranked_history AS (
    SELECT
        m.id AS match_row_id,
        m.joueur AS id_compte,
        m.match_id,
        m.season,
        m.datetime AS peak_datetime,
        UPPER(TRIM(m.tier::text)) AS tier,
        UPPER(TRIM(m.rank::text)) AS rank,
        COALESCE(m.lp, 0)::integer AS lp,
        CASE UPPER(TRIM(m.tier::text))
            WHEN 'IRON' THEN 1
            WHEN 'BRONZE' THEN 2
            WHEN 'SILVER' THEN 3
            WHEN 'GOLD' THEN 4
            WHEN 'PLATINUM' THEN 5
            WHEN 'EMERALD' THEN 6
            WHEN 'DIAMOND' THEN 7
            WHEN 'MASTER' THEN 8
            WHEN 'GRANDMASTER' THEN 9
            WHEN 'CHALLENGER' THEN 10
            ELSE 0
        END AS tier_order,
        CASE
            WHEN UPPER(TRIM(m.tier::text)) IN ('MASTER', 'GRANDMASTER', 'CHALLENGER') THEN 0
            ELSE CASE UPPER(TRIM(m.rank::text))
                WHEN 'IV' THEN 1
                WHEN 'III' THEN 2
                WHEN 'II' THEN 3
                WHEN 'I' THEN 4
                ELSE 0
            END
        END AS division_order
    FROM public.matchs AS m
    WHERE UPPER(TRIM(m.mode::text)) = 'RANKED'
      AND UPPER(TRIM(m.tier::text)) IN (
          'IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM',
          'EMERALD', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER'
      )
),
ranked_peaks AS (
    SELECT
        ranked_history.*,
        ROW_NUMBER() OVER (
            PARTITION BY id_compte
            ORDER BY
                tier_order DESC,
                division_order DESC,
                lp DESC,
                peak_datetime DESC NULLS LAST,
                match_row_id DESC
        ) AS rn
    FROM ranked_history
)
SELECT
    t.id_compte,
    t.puuid,
    t.riot_id,
    t.riot_tagline,
    t.server_id,
    p.tier AS peak_tier,
    p.rank AS peak_rank,
    p.lp AS peak_lp,
    CASE
        WHEN p.tier IS NULL THEN NULL
        WHEN p.tier IN ('MASTER', 'GRANDMASTER', 'CHALLENGER')
            THEN CONCAT(p.tier, ' ', p.lp, ' LP')
        ELSE CONCAT(p.tier, ' ', p.rank, ' ', p.lp, ' LP')
    END AS peak_elo,
    p.season AS peak_season,
    p.peak_datetime,
    p.match_id AS peak_match_id
FROM public.tracker AS t
LEFT JOIN ranked_peaks AS p
    ON p.id_compte = t.id_compte
   AND p.rn = 1;
"""

VIEW_SEASON_SQL = f"""
CREATE OR REPLACE VIEW {VIEW_SEASON_NAME} AS
WITH ranked_history AS (
    SELECT
        m.id AS match_row_id,
        m.joueur AS id_compte,
        m.match_id,
        m.season,
        m.datetime AS peak_datetime,
        UPPER(TRIM(m.tier::text)) AS tier,
        UPPER(TRIM(m.rank::text)) AS rank,
        COALESCE(m.lp, 0)::integer AS lp,
        CASE UPPER(TRIM(m.tier::text))
            WHEN 'IRON' THEN 1
            WHEN 'BRONZE' THEN 2
            WHEN 'SILVER' THEN 3
            WHEN 'GOLD' THEN 4
            WHEN 'PLATINUM' THEN 5
            WHEN 'EMERALD' THEN 6
            WHEN 'DIAMOND' THEN 7
            WHEN 'MASTER' THEN 8
            WHEN 'GRANDMASTER' THEN 9
            WHEN 'CHALLENGER' THEN 10
            ELSE 0
        END AS tier_order,
        CASE
            WHEN UPPER(TRIM(m.tier::text)) IN ('MASTER', 'GRANDMASTER', 'CHALLENGER') THEN 0
            ELSE CASE UPPER(TRIM(m.rank::text))
                WHEN 'IV' THEN 1
                WHEN 'III' THEN 2
                WHEN 'II' THEN 3
                WHEN 'I' THEN 4
                ELSE 0
            END
        END AS division_order
    FROM public.matchs AS m
    WHERE UPPER(TRIM(m.mode::text)) = 'RANKED'
      AND m.season IS NOT NULL
      AND UPPER(TRIM(m.tier::text)) IN (
          'IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM',
          'EMERALD', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER'
      )
),
ranked_peaks AS (
    SELECT
        ranked_history.*,
        ROW_NUMBER() OVER (
            PARTITION BY id_compte, season
            ORDER BY
                tier_order DESC,
                division_order DESC,
                lp DESC,
                peak_datetime DESC NULLS LAST,
                match_row_id DESC
        ) AS rn
    FROM ranked_history
)
SELECT
    t.id_compte,
    t.puuid,
    t.riot_id,
    t.riot_tagline,
    t.server_id,
    p.season,
    p.tier AS peak_tier,
    p.rank AS peak_rank,
    p.lp AS peak_lp,
    CASE
        WHEN p.tier IN ('MASTER', 'GRANDMASTER', 'CHALLENGER')
            THEN CONCAT(p.tier, ' ', p.lp, ' LP')
        ELSE CONCAT(p.tier, ' ', p.rank, ' ', p.lp, ' LP')
    END AS peak_elo,
    p.peak_datetime,
    p.match_id AS peak_match_id
FROM ranked_peaks AS p
INNER JOIN public.tracker AS t
    ON t.id_compte = p.id_compte
WHERE p.rn = 1;
"""


def create_peak_elo_views() -> None:
    """Crée ou remplace les vues globales et par saison du peak Elo."""
    with engine.begin() as connection:
        connection.execute(text(VIEW_SQL))
        connection.execute(text(VIEW_SEASON_SQL))


if __name__ == "__main__":
    create_peak_elo_views()
    print(f"Vue {VIEW_NAME} créée / mise à jour avec succès.")
    print(f"Vue {VIEW_SEASON_NAME} créée / mise à jour avec succès.")
