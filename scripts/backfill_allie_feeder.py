"""Rattrape ``matchs.allie_feeder`` à partir des données Riot Match-V5.

Le record « MORTS MAX D'UN COÉQUIPIER » correspond au maximum des morts
parmi les quatre coéquipiers du joueur tracké. Le joueur tracké est exclu
explicitement par son PUUID.

Par défaut, le script retraite la saison 16 pour les modes de records :
RANKED, FLEX, SWIFTPLAY et ARAM.

Exemples :
    python scripts/backfill_allie_feeder.py --dry-run
    python scripts/backfill_allie_feeder.py --season 16 --limit 10
    python scripts/backfill_allie_feeder.py --season 16 --only-zero
    python scripts/backfill_allie_feeder.py --season 15 16 --delay 1.5
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


DEFAULT_MODES = ("RANKED", "FLEX", "SWIFTPLAY", "ARAM")
DEFAULT_SEASONS = (16,)


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
    return ", ".join(f"'{value}'" for value in values)


def _riot_match_id(match_id: str) -> str:
    match_id = str(match_id)
    return match_id if "_" in match_id else f"EUW1_{match_id}"


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


def calculate_allie_feeder(match_detail: dict, analyzed_puuid: str) -> int:
    """Retourne le maximum des morts des quatre coéquipiers du joueur tracké."""
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

    team_id = tracked.get("teamId")
    allies = [
        participant
        for participant in participants
        if participant.get("teamId") == team_id
        and str(participant.get("puuid", "")) != analyzed_puuid
    ]

    if len(allies) != 4:
        raise ValueError(
            f"Nombre de coéquipiers inattendu : {len(allies)} au lieu de 4"
        )

    ally_deaths = [int(participant.get("deaths") or 0) for participant in allies]
    return max(ally_deaths, default=0)


def load_matches(
    modes: list[str],
    seasons: list[int],
    limit: int | None,
    only_zero: bool,
) -> pd.DataFrame:
    season_sql = ", ".join(str(int(season)) for season in seasons)
    limit_sql = f"LIMIT {int(limit)}" if limit else ""
    zero_filter = "AND COALESCE(m.allie_feeder, 0) = 0" if only_zero else ""

    query = f"""
        SELECT
            m.joueur AS id_compte,
            m.match_id,
            m.mode,
            m.season,
            m.allie_feeder,
            t.riot_id,
            t.riot_tagline,
            t.puuid
        FROM matchs AS m
        INNER JOIN tracker AS t
            ON t.id_compte = m.joueur
        WHERE m.mode IN ({_sql_list(modes)})
          AND m.season IN ({season_sql})
          AND m.records = TRUE
          AND t.save_records = TRUE
          AND t.banned = FALSE
          AND (
                (m.mode = 'ARAM' AND m.time >= 10)
                OR (m.mode IN ('RANKED', 'FLEX', 'SWIFTPLAY') AND m.time >= 15)
          )
          {zero_filter}
        ORDER BY m.match_id, m.joueur
        {limit_sql}
    """

    return _as_rows(lire_bdd_perso(query, index_col=None))


def update_allie_feeder(
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
                SET allie_feeder = :allie_feeder
                WHERE match_id = :match_id
                  AND joueur = :joueur
                """
            ),
            {
                "allie_feeder": int(value),
                "match_id": match_id,
                "joueur": int(id_compte),
            },
        )
    return int(result.rowcount or 0)


async def backfill(args: argparse.Namespace) -> None:
    matches = load_matches(
        modes=args.modes,
        seasons=args.season,
        limit=args.limit,
        only_zero=args.only_zero,
    )

    if matches.empty:
        print("Aucun match à retraiter.")
        return

    print(f"{len(matches)} perspective(s) à retraiter.")

    if args.dry_run:
        columns = [
            "id_compte",
            "match_id",
            "mode",
            "season",
            "allie_feeder",
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

            old_raw = row.get("allie_feeder")
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

                new_value = calculate_allie_feeder(match_cache[match_id], puuid)

                if old_value == new_value:
                    unchanged += 1
                    success += 1
                    print(f"  OK - inchangé : {new_value}")
                    continue

                rows_updated = update_allie_feeder(match_id, id_compte, new_value)
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
        description="Rattrape le record MORTS MAX D'UN COÉQUIPIER."
    )
    parser.add_argument(
        "--season",
        nargs="+",
        type=int,
        default=list(DEFAULT_SEASONS),
        help="Saison(s) à retraiter. Par défaut : 16.",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=DEFAULT_MODES,
        default=list(DEFAULT_MODES),
        help="Modes à retraiter.",
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
        "--only-zero",
        action="store_true",
        help="Ne retraite que les lignes où allie_feeder vaut NULL ou 0.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche la sélection sans appeler Riot ni modifier la BDD.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(backfill(parse_args()))
