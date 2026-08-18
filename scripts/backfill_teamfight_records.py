"""Rattrapage des données Teamfights nécessaires aux records enrichis.

Le script reprend le principe du notebook historique ``import data.ipynb`` :
- sélection des matchs en base ;
- cache des informations Riot par compte ;
- reconstruction d'un MatchLol avec ``identifiant_game`` ;
- rechargement des données Riot/timeline ;
- recalcul puis remplacement des lignes ``match_teamfight_damage``.

Pré-requis : exécuter d'abord la migration
``sql/migrations/20260818_add_teamfight_record_fields.sql``.

Exemples :
    python scripts/backfill_teamfight_records.py --dry-run
    python scripts/backfill_teamfight_records.py --season 15 --delay 5
    python scripts/backfill_teamfight_records.py --modes RANKED FLEX --limit 100
    python scripts/backfill_teamfight_records.py --force --season 14 15
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Iterable

import aiohttp
import pandas as pd

from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd
from fonctions.match import MatchLol
from fonctions.match.riot_api import get_summoner_by_puuid


BACKFILL_VERSION = 1
DEFAULT_MODES = ("RANKED", "FLEX", "SWIFTPLAY", "ARAM")


def _as_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise la forme historique renvoyée par lire_bdd_perso."""
    if df is None or df.empty:
        return pd.DataFrame()
    if "id_compte" in df.columns:
        return df.reset_index(drop=True)
    if "id_compte" in df.index:
        return df.T.reset_index(drop=True)
    return df.reset_index(drop=True)


def _sql_list(values: Iterable[str]) -> str:
    """Construit une liste SQL depuis des valeurs déjà validées par argparse."""
    return ", ".join(f"'{value}'" for value in values)


def load_matches(
    modes: list[str],
    seasons: list[int] | None,
    limit: int | None,
    force: bool,
) -> pd.DataFrame:
    season_filter = ""
    if seasons:
        season_filter = f"AND m.season IN ({', '.join(str(int(s)) for s in seasons)})"

    limit_sql = f"LIMIT {int(limit)}" if limit else ""
    missing_filter = ""
    if not force:
        missing_filter = f"""
          AND COALESCE(backfill.backfill_version, 0) < {BACKFILL_VERSION}
          AND (
                NOT EXISTS (
                    SELECT 1
                    FROM match_teamfight_damage existing
                    WHERE existing.match_id = m.match_id
                      AND existing.analyzed_puuid = t.puuid
                      AND existing.puuid = t.puuid
                )
                OR EXISTS (
                    SELECT 1
                    FROM match_teamfight_damage missing
                    WHERE missing.match_id = m.match_id
                      AND missing.analyzed_puuid = t.puuid
                      AND missing.puuid = t.puuid
                      AND (
                          missing.physical_damage_window_estimated IS NULL
                          OR missing.magic_damage_window_estimated IS NULL
                          OR missing.true_damage_window_estimated IS NULL
                      )
                )
          )
        """

    query = f"""
        SELECT DISTINCT
            m.joueur AS id_compte,
            m.match_id,
            m.mode,
            m.season,
            t.riot_id,
            t.riot_tagline,
            t.puuid
        FROM matchs AS m
        INNER JOIN tracker AS t
            ON t.id_compte = m.joueur
        LEFT JOIN match_teamfight_backfill_status AS backfill
            ON backfill.match_id = m.match_id
           AND backfill.analyzed_puuid = t.puuid
        WHERE m.mode IN ({_sql_list(modes)})
          AND m.records = TRUE
          AND t.save_records = TRUE
          AND t.banned = FALSE
          AND (
                (m.mode = 'ARAM' AND m.time >= 10)
                OR (m.mode IN ('RANKED', 'FLEX', 'SWIFTPLAY') AND m.time >= 15)
          )
          {season_filter}
          {missing_filter}
        ORDER BY m.match_id
        {limit_sql}
    """
    return _as_rows(lire_bdd_perso(query, index_col=None))


def mark_backfilled(match_id: str, analyzed_puuid: str, fights_count: int) -> None:
    requete_perso_bdd(
        """
        INSERT INTO match_teamfight_backfill_status (
            match_id, analyzed_puuid, backfill_version, fights_count, updated_at
        ) VALUES (
            :match_id, :analyzed_puuid, :backfill_version, :fights_count, NOW()
        )
        ON CONFLICT (match_id, analyzed_puuid)
        DO UPDATE SET
            backfill_version = EXCLUDED.backfill_version,
            fights_count = EXCLUDED.fights_count,
            updated_at = NOW()
        """,
        {
            "match_id": match_id,
            "analyzed_puuid": analyzed_puuid,
            "backfill_version": BACKFILL_VERSION,
            "fights_count": fights_count,
        },
    )


async def backfill(args: argparse.Namespace) -> None:
    matches = load_matches(args.modes, args.season, args.limit, args.force)
    if matches.empty:
        print("Aucun match à retraiter.")
        return

    print(f"{len(matches)} perspective(s) de match à retraiter.")
    if args.dry_run:
        columns = ["id_compte", "match_id", "mode", "season", "riot_id", "riot_tagline"]
        print(matches[columns].to_string(index=False))
        return

    me_cache: dict[int, dict] = {}
    success = 0
    errors = 0

    async with aiohttp.ClientSession() as cache_session:
        for position, row in matches.iterrows():
            id_compte = int(row["id_compte"])
            match_id = str(row["match_id"])
            puuid = str(row["puuid"])
            riot_id = str(row["riot_id"])
            riot_tag = str(row["riot_tagline"])

            print(f"[{position + 1}/{len(matches)}] {riot_id}#{riot_tag} - {match_id}")
            match_info = None

            try:
                if id_compte not in me_cache:
                    me_cache[id_compte] = await get_summoner_by_puuid(puuid, cache_session)

                match_info = MatchLol(
                    id_compte=id_compte,
                    riot_id=riot_id,
                    riot_tag=riot_tag,
                    idgames=0,
                    identifiant_game=match_id,
                    me=me_cache[id_compte],
                )

                await match_info.get_data_riot()
                await match_info.prepare_data()

                teamfights = await match_info.teamfight_damage()
                await match_info.save_teamfight_damage(teamfights)
                mark_backfilled(match_id, puuid, len(teamfights))

                success += 1
                print(f"  OK - {len(teamfights)} combat(s) recalculé(s)")
            except Exception as error:
                errors += 1
                print(f"  ERREUR - {type(error).__name__}: {error}")
            finally:
                session = getattr(match_info, "session", None) if match_info else None
                if session is not None and not session.closed:
                    await session.close()

            if args.delay > 0 and position + 1 < len(matches):
                await asyncio.sleep(args.delay)

    print(f"Terminé : {success} succès, {errors} erreur(s).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rattrape les données des records Teamfights.")
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=DEFAULT_MODES,
        default=list(DEFAULT_MODES),
        help="Modes à retraiter.",
    )
    parser.add_argument(
        "--season",
        nargs="*",
        type=int,
        default=None,
        help="Saisons à retraiter. Sans option : toutes les saisons éligibles.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Nombre maximal de perspectives à traiter.")
    parser.add_argument("--delay", type=float, default=3.0, help="Pause entre deux appels de match, en secondes.")
    parser.add_argument("--force", action="store_true", help="Retraite les matchs même s'ils semblent déjà à jour.")
    parser.add_argument("--dry-run", action="store_true", help="Affiche la sélection sans appeler Riot ni écrire en BDD.")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(backfill(parse_args()))
