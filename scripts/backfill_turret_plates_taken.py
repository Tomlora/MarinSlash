"""Rattrape ``matchs.turret_plates_taken`` à partir de Riot Match-V5.

Le record « plaques prises » doit utiliser le total de plaques pris pendant
l'ensemble de la partie, tel que renvoyé par
``participants[].challenges.turretPlatesTaken``. Il ne doit pas être confondu
avec ``data_timeline_palier.TURRET_PLATE_DESTROYED_30``, qui ne couvre que les
événements observés jusqu'à 30 minutes.

Par défaut, le script retraite toutes les perspectives présentes dans ``matchs``
dont ``turret_plates_taken`` est NULL. Les appels Riot sont mutualisés par
``match_id`` lorsqu'un même match existe pour plusieurs joueurs trackés.

Exemples :
    python scripts/backfill_turret_plates_taken.py --dry-run
    python scripts/backfill_turret_plates_taken.py --limit 10
    python scripts/backfill_turret_plates_taken.py --season 16 --delay 1.0
    python scripts/backfill_turret_plates_taken.py --modes RANKED FLEX SWIFTPLAY
    python scripts/backfill_turret_plates_taken.py --force

Le script crée automatiquement la colonne PostgreSQL lors d'une exécution
réelle si elle n'existe pas encore. ``--dry-run`` ne modifie jamais le schéma.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Iterable

import aiohttp
import pandas as pd
from sqlalchemy import text


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fonctions.gestion_bdd import engine, lire_bdd_perso
from utils.params import api_key_lol, region


COLUMN_NAME = "turret_plates_taken"


def _as_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise la forme historique renvoyée par ``lire_bdd_perso``."""
    if df is None or df.empty:
        return pd.DataFrame()
    if "id_compte" in df.columns:
        return df.reset_index(drop=True)
    if "id_compte" in df.index:
        return df.T.reset_index(drop=True)
    return df.reset_index(drop=True)


def _sql_list(values: Iterable[str]) -> str:
    return ", ".join(f"'{str(value).replace(chr(39), chr(39) * 2)}'" for value in values)


def _riot_match_id(match_id: str) -> str:
    match_id = str(match_id)
    return match_id if "_" in match_id else f"EUW1_{match_id}"


def column_exists() -> bool:
    query = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'matchs'
              AND column_name = :column_name
        ) AS exists
    """
    with engine.connect() as conn:
        return bool(conn.execute(text(query), {"column_name": COLUMN_NAME}).scalar())


def ensure_column_exists() -> None:
    """Ajoute la colonne sans écraser les données déjà présentes."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE public.matchs
                ADD COLUMN IF NOT EXISTS turret_plates_taken INTEGER
                """
            )
        )


async def _riot_get_match(
    session: aiohttp.ClientSession,
    match_id: str,
    *,
    max_attempts: int = 5,
) -> dict:
    riot_match_id = _riot_match_id(match_id)
    url = (
        f"https://{str(region).lower()}.api.riotgames.com"
        f"/lol/match/v5/matches/{riot_match_id}"
    )

    for attempt in range(1, max_attempts + 1):
        async with session.get(url, params={"api_key": api_key_lol}) as response:
            payload = await response.json(content_type=None)

            if response.status == 200:
                if not isinstance(payload, dict) or "info" not in payload:
                    raise RuntimeError(
                        f"Réponse Riot invalide pour {riot_match_id}: {payload}"
                    )
                return payload

            if response.status == 429 and attempt < max_attempts:
                retry_after = float(response.headers.get("Retry-After", "2"))
                print(
                    f"  Riot 429 - nouvelle tentative dans {retry_after:.1f}s "
                    f"({attempt}/{max_attempts})"
                )
                await asyncio.sleep(max(retry_after, 1.0))
                continue

            if response.status >= 500 and attempt < max_attempts:
                wait = min(2 ** attempt, 10)
                print(
                    f"  Riot HTTP {response.status} - nouvelle tentative dans {wait}s "
                    f"({attempt}/{max_attempts})"
                )
                await asyncio.sleep(wait)
                continue

            raise RuntimeError(
                f"Riot HTTP {response.status} pour {riot_match_id}: {payload}"
            )

    raise RuntimeError(f"Impossible de récupérer {riot_match_id}")


def calculate_turret_plates_taken(match_detail: dict, analyzed_puuid: str) -> int:
    """Retourne le total Riot ``turretPlatesTaken`` du joueur tracké."""
    participants = match_detail.get("info", {}).get("participants", [])

    tracked = next(
        (
            participant
            for participant in participants
            if str(participant.get("puuid", "")) == analyzed_puuid
        ),
        None,
    )
    if tracked is None:
        raise ValueError("PUUID du joueur tracké introuvable dans le match")

    challenges = tracked.get("challenges") or {}
    value = challenges.get("turretPlatesTaken", 0)

    try:
        return int(value or 0)
    except (TypeError, ValueError) as error:
        raise ValueError(f"turretPlatesTaken invalide : {value!r}") from error


def load_matches(
    modes: list[str] | None,
    seasons: list[int] | None,
    limit: int | None,
    force: bool,
    has_column: bool,
) -> pd.DataFrame:
    filters = [
        "m.match_id IS NOT NULL",
        "t.puuid IS NOT NULL",
        "t.puuid <> ''",
    ]

    if modes:
        filters.append(f"m.mode IN ({_sql_list(modes)})")
    if seasons:
        season_sql = ", ".join(str(int(season)) for season in seasons)
        filters.append(f"m.season IN ({season_sql})")
    if has_column and not force:
        filters.append("m.turret_plates_taken IS NULL")

    current_value = (
        "m.turret_plates_taken"
        if has_column
        else "NULL::INTEGER AS turret_plates_taken"
    )
    limit_sql = f"LIMIT {int(limit)}" if limit else ""

    query = f"""
        SELECT
            m.joueur AS id_compte,
            m.match_id,
            m.mode,
            m.season,
            {current_value},
            t.riot_id,
            t.riot_tagline,
            t.puuid
        FROM matchs AS m
        INNER JOIN tracker AS t
            ON t.id_compte = m.joueur
        WHERE {' AND '.join(filters)}
        ORDER BY m.match_id, m.joueur
        {limit_sql}
    """

    return _as_rows(lire_bdd_perso(query, index_col=None))


def update_turret_plates_taken(
    match_id: str,
    id_compte: int,
    value: int,
) -> int:
    """Met à jour une perspective précise du match."""
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE matchs
                SET turret_plates_taken = :turret_plates_taken
                WHERE match_id = :match_id
                  AND joueur = :joueur
                """
            ),
            {
                "turret_plates_taken": int(value),
                "match_id": match_id,
                "joueur": int(id_compte),
            },
        )
    return int(result.rowcount or 0)


async def backfill(args: argparse.Namespace) -> None:
    has_column = column_exists()

    if not args.dry_run and not has_column:
        ensure_column_exists()
        has_column = True
        print("Colonne matchs.turret_plates_taken créée.")

    matches = load_matches(
        modes=args.modes,
        seasons=args.season,
        limit=args.limit,
        force=args.force,
        has_column=has_column,
    )

    if matches.empty:
        print("Aucun match à retraiter.")
        return

    print(f"{len(matches)} perspective(s) à retraiter.")

    if args.dry_run:
        if not has_column:
            print(
                "La colonne matchs.turret_plates_taken n'existe pas encore ; "
                "elle sera créée lors d'une exécution sans --dry-run."
            )
        columns = [
            "id_compte",
            "match_id",
            "mode",
            "season",
            "turret_plates_taken",
            "riot_id",
            "riot_tagline",
        ]
        print(matches[columns].to_string(index=False))
        return

    timeout = aiohttp.ClientTimeout(total=120)
    match_cache: dict[str, dict] = {}
    success = 0
    changed = 0
    unchanged = 0
    errors = 0
    api_calls = 0

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for position, row in matches.iterrows():
            match_id = str(row["match_id"])
            id_compte = int(row["id_compte"])
            puuid = str(row["puuid"])
            riot_id = str(row["riot_id"])
            riot_tag = str(row["riot_tagline"])

            old_raw = row.get("turret_plates_taken")
            old_value = None if pd.isna(old_raw) else int(old_raw)

            print(
                f"[{position + 1}/{len(matches)}] "
                f"{riot_id}#{riot_tag} - {match_id}"
            )

            try:
                if match_id not in match_cache:
                    match_cache[match_id] = await _riot_get_match(session, match_id)
                    api_calls += 1
                    if args.delay > 0:
                        await asyncio.sleep(args.delay)

                new_value = calculate_turret_plates_taken(
                    match_cache[match_id],
                    puuid,
                )

                if old_value == new_value:
                    unchanged += 1
                    success += 1
                    print(f"  OK - inchangé : {new_value}")
                    continue

                rows_updated = update_turret_plates_taken(
                    match_id,
                    id_compte,
                    new_value,
                )
                if rows_updated != 1:
                    raise RuntimeError(
                        f"UPDATE inattendu : {rows_updated} ligne(s) modifiée(s)"
                    )

                changed += 1
                success += 1
                print(f"  MAJ - {old_value} -> {new_value}")

            except Exception as error:
                errors += 1
                print(f"  ERREUR - {type(error).__name__}: {error}")

    print(
        "Terminé : "
        f"{success} succès, {changed} modifiée(s), "
        f"{unchanged} inchangée(s), {errors} erreur(s), "
        f"{api_calls} appel(s) Riot."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rattrape matchs.turret_plates_taken depuis Riot Match-V5."
    )
    parser.add_argument(
        "--season",
        nargs="+",
        type=int,
        default=None,
        help="Saison(s) à retraiter. Par défaut : toutes les saisons.",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        default=None,
        help="Modes à retraiter. Par défaut : tous les modes présents dans matchs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximal de perspectives à traiter.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Pause après chaque nouvel appel Riot, en secondes.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recalcule aussi les lignes où turret_plates_taken est déjà renseigné.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche la sélection sans appeler Riot ni modifier la BDD/le schéma.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(backfill(parse_args()))
