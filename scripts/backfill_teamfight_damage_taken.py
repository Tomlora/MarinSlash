"""Backfill des dégâts reçus pendant les fenêtres de combat.

Le script complète les quatre colonnes ajoutées à ``match_teamfight_damage`` :

- ``damage_taken_frame_window``
- ``physical_damage_taken_frame_window``
- ``magic_damage_taken_frame_window``
- ``true_damage_taken_frame_window``

Il sélectionne par défaut toutes les perspectives qui possèdent déjà des lignes
Teamfight mais au moins une de ces valeurs à NULL, recharge le match et la
timeline Riot, recalcule les combats avec ``calculate_teamfight_damage`` puis
met à jour uniquement les nouvelles colonnes.

La mise à jour d'une perspective est transactionnelle : si les combats
recalculés ne correspondent pas aux lignes existantes, rien n'est validé pour
cette perspective.

Pré-requis : exécuter d'abord ``scripts/add_teamfight_damage_taken_columns.sql``.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
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
TAKEN_COLUMNS = (
    "damage_taken_frame_window",
    "physical_damage_taken_frame_window",
    "magic_damage_taken_frame_window",
    "true_damage_taken_frame_window",
)


def _load_teamfight_calculator():
    """Charge teamfight_damage.py sans exécuter fonctions.match.__init__."""
    module_path = REPO_ROOT / "fonctions" / "match" / "teamfight_damage.py"
    if not module_path.exists():
        raise ImportError(f"Fichier introuvable : {module_path}")

    spec = importlib.util.spec_from_file_location(
        "_teamfight_damage_taken_backfill",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossible de charger {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.calculate_teamfight_damage


calculate_teamfight_damage = _load_teamfight_calculator()


def _as_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise la forme historique renvoyée par lire_bdd_perso."""
    if df is None or df.empty:
        return pd.DataFrame()
    return df.T.reset_index(drop=True) if len(df.index) and not len(df.columns) else df.reset_index(drop=True)


def _sql_list(values: Iterable[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _riot_match_id(match_id: str) -> str:
    match_id = str(match_id)
    return match_id if "_" in match_id else f"EUW1_{match_id}"


async def _riot_get(session: aiohttp.ClientSession, path: str) -> dict:
    url = f"https://{str(region).lower()}.api.riotgames.com{path}"
    async with session.get(url, params={"api_key": api_key_lol}) as response:
        payload = await response.json(content_type=None)
        if response.status != 200:
            raise RuntimeError(
                f"Riot HTTP {response.status} sur {path}: {payload}"
            )
        if not isinstance(payload, dict):
            raise RuntimeError(f"Réponse Riot invalide sur {path}")
        return payload


async def get_match_detail(session: aiohttp.ClientSession, match_id: str) -> dict:
    riot_id = _riot_match_id(match_id)
    return await _riot_get(session, f"/lol/match/v5/matches/{riot_id}")


async def get_match_timeline(session: aiohttp.ClientSession, match_id: str) -> dict:
    riot_id = _riot_match_id(match_id)
    return await _riot_get(session, f"/lol/match/v5/matches/{riot_id}/timeline")


def load_matches(
    modes: list[str] | None,
    seasons: list[int] | None,
    limit: int | None,
    force: bool,
    match_id: str | None,
) -> pd.DataFrame:
    filters = []

    if not force:
        filters.append(
            "(" + " OR ".join(f"tf.{column} IS NULL" for column in TAKEN_COLUMNS) + ")"
        )

    if modes:
        filters.append(f"m.mode IN ({_sql_list(modes)})")

    if seasons:
        filters.append(
            f"m.season IN ({', '.join(str(int(season)) for season in seasons)})"
        )

    params = {}
    if match_id:
        filters.append("CAST(tf.match_id AS TEXT) = :match_id")
        params["match_id"] = str(match_id).replace("EUW1_", "")

    where_sql = " AND ".join(filters) if filters else "TRUE"
    limit_sql = f"LIMIT {int(limit)}" if limit else ""

    query = f"""
        SELECT DISTINCT
            tf.match_id,
            tf.analyzed_puuid,
            m.mode,
            m.season,
            t.riot_id,
            t.riot_tagline
        FROM match_teamfight_damage AS tf
        LEFT JOIN tracker AS t
            ON t.puuid = tf.analyzed_puuid
        LEFT JOIN matchs AS m
            ON CAST(m.match_id AS TEXT) = CAST(tf.match_id AS TEXT)
           AND (t.id_compte IS NULL OR m.joueur = t.id_compte)
        WHERE {where_sql}
        ORDER BY tf.match_id, tf.analyzed_puuid
        {limit_sql}
    """

    df = lire_bdd_perso(query, index_col=None, params=params or None)
    if df is None or df.empty:
        return pd.DataFrame()

    # lire_bdd_perso transpose historiquement le résultat.
    if "match_id" in df.index and "match_id" not in df.columns:
        df = df.T
    return df.reset_index(drop=True)


def _tracked_team_id(match_detail: dict, analyzed_puuid: str) -> int:
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
        raise ValueError("PUUID du joueur introuvable dans le détail du match")
    return int(tracked["teamId"])


def _build_updates(
    match_id: str,
    analyzed_puuid: str,
    teamfights: list[dict],
) -> list[dict]:
    updates: list[dict] = []

    for fight in teamfights:
        for player in fight.get("players", []):
            updates.append(
                {
                    "match_id": match_id,
                    "analyzed_puuid": analyzed_puuid,
                    "fight_id": int(fight["fight_id"]),
                    "participant_id": int(player["participant_id"]),
                    "estimation_window_start_ms": int(
                        fight["estimation_window_start_ms"]
                    ),
                    "estimation_window_end_ms": int(
                        fight["estimation_window_end_ms"]
                    ),
                    "damage_taken_frame_window": int(
                        player.get("damage_taken_frame_window", 0) or 0
                    ),
                    "physical_damage_taken_frame_window": int(
                        player.get("physical_damage_taken_frame_window", 0) or 0
                    ),
                    "magic_damage_taken_frame_window": int(
                        player.get("magic_damage_taken_frame_window", 0) or 0
                    ),
                    "true_damage_taken_frame_window": int(
                        player.get("true_damage_taken_frame_window", 0) or 0
                    ),
                }
            )

    return updates


UPDATE_SQL = text(
    """
    UPDATE match_teamfight_damage
    SET
        damage_taken_frame_window = :damage_taken_frame_window,
        physical_damage_taken_frame_window = :physical_damage_taken_frame_window,
        magic_damage_taken_frame_window = :magic_damage_taken_frame_window,
        true_damage_taken_frame_window = :true_damage_taken_frame_window
    WHERE CAST(match_id AS TEXT) = CAST(:match_id AS TEXT)
      AND analyzed_puuid = :analyzed_puuid
      AND fight_id = :fight_id
      AND participant_id = :participant_id
      AND estimation_window_start_ms = :estimation_window_start_ms
      AND estimation_window_end_ms = :estimation_window_end_ms
    """
)


REMAINING_SQL = text(
    """
    SELECT COUNT(*)
    FROM match_teamfight_damage
    WHERE CAST(match_id AS TEXT) = CAST(:match_id AS TEXT)
      AND analyzed_puuid = :analyzed_puuid
      AND (
            damage_taken_frame_window IS NULL
         OR physical_damage_taken_frame_window IS NULL
         OR magic_damage_taken_frame_window IS NULL
         OR true_damage_taken_frame_window IS NULL
      )
    """
)


def save_backfill(
    match_id: str,
    analyzed_puuid: str,
    teamfights: list[dict],
) -> int:
    """Met à jour une perspective et rollback si des lignes restent incomplètes."""
    updates = _build_updates(match_id, analyzed_puuid, teamfights)
    if not updates:
        raise RuntimeError("Aucun combat recalculé pour cette perspective")

    with engine.begin() as conn:
        result = conn.execute(UPDATE_SQL, updates)
        remaining = int(
            conn.execute(
                REMAINING_SQL,
                {"match_id": match_id, "analyzed_puuid": analyzed_puuid},
            ).scalar_one()
        )

        if remaining > 0:
            raise RuntimeError(
                f"{remaining} ligne(s) restent sans dégâts reçus ; "
                "les fight_id/fenêtres recalculés ne correspondent pas complètement "
                "aux données existantes"
            )

        return int(result.rowcount or 0)


async def backfill(args: argparse.Namespace) -> None:
    matches = load_matches(
        args.modes,
        args.season,
        args.limit,
        args.force,
        args.match_id,
    )
    if matches.empty:
        print("Aucune perspective de match à retraiter.")
        return

    print(f"{len(matches)} perspective(s) de match à retraiter.")

    if args.dry_run:
        columns = [
            column
            for column in (
                "match_id",
                "mode",
                "season",
                "riot_id",
                "riot_tagline",
                "analyzed_puuid",
            )
            if column in matches.columns
        ]
        print(matches[columns].to_string(index=False))
        return

    success = 0
    errors = 0
    timeout = aiohttp.ClientTimeout(total=120)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for position, row in matches.iterrows():
            match_id = str(row["match_id"])
            puuid = str(row["analyzed_puuid"])
            riot_id = str(row.get("riot_id") or "?")
            riot_tag = str(row.get("riot_tagline") or "?")

            print(
                f"[{position + 1}/{len(matches)}] "
                f"{riot_id}#{riot_tag} - {match_id}"
            )

            try:
                match_detail = await get_match_detail(session, match_id)
                timeline = await get_match_timeline(session, match_id)

                timeline_participants = timeline.get("metadata", {}).get(
                    "participants", []
                )
                if puuid not in timeline_participants:
                    raise ValueError("PUUID du joueur introuvable dans la timeline")

                allied_team_id = _tracked_team_id(match_detail, puuid)
                teamfights = calculate_teamfight_damage(
                    match_detail,
                    timeline,
                    allied_team_id=allied_team_id,
                )
                updated = save_backfill(match_id, puuid, teamfights)

                success += 1
                print(
                    f"  OK - {len(teamfights)} combat(s), "
                    f"{updated} ligne(s) mise(s) à jour"
                )
            except Exception as error:
                errors += 1
                print(f"  ERREUR - {type(error).__name__}: {error}")

            if args.delay > 0 and position + 1 < len(matches):
                await asyncio.sleep(args.delay)

    print(f"Terminé : {success} succès, {errors} erreur(s).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Complète les dégâts reçus des données Teamfight existantes."
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=DEFAULT_MODES,
        default=None,
        help="Filtre facultatif sur les modes. Sans option : toutes les lignes Teamfight.",
    )
    parser.add_argument(
        "--season",
        nargs="*",
        type=int,
        default=None,
        help="Filtre facultatif sur les saisons.",
    )
    parser.add_argument(
        "--match-id",
        type=str,
        default=None,
        help="Ne traite qu'un match, pratique pour tester avant le backfill complet.",
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
        default=3.0,
        help="Pause entre deux perspectives, en secondes.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recalcule aussi les perspectives dont les quatre colonnes sont déjà remplies.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche la sélection sans appeler Riot ni écrire en BDD.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(backfill(parse_args()))
