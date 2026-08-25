"""Backfill des dégâts reçus pendant les fenêtres de combat.

Complète les colonnes:
- damage_taken_frame_window
- physical_damage_taken_frame_window
- magic_damage_taken_frame_window
- true_damage_taken_frame_window

Le script recalcule les combats depuis Riot et met à jour uniquement ces colonnes.
Il refuse désormais d'écrire si le calculateur chargé ne renvoie pas explicitement
les quatre nouvelles valeurs, afin d'éviter de transformer une clé absente en 0.

Pré-requis:
    scripts/add_teamfight_damage_taken_columns.sql
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
RIOT_TAKEN_STATS = (
    "totalDamageTaken",
    "physicalDamageTaken",
    "magicDamageTaken",
    "trueDamageTaken",
)


def _load_teamfight_calculator():
    """Charge explicitement le calculateur présent dans ce checkout."""
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
    return module.calculate_teamfight_damage, module_path


calculate_teamfight_damage, CALCULATOR_PATH = _load_teamfight_calculator()


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


def _required_taken_value(player: dict, column: str) -> int:
    """Interdit le fallback silencieux vers zéro en cas de calculateur obsolète."""
    if column not in player:
        raise RuntimeError(
            f"Le calculateur {CALCULATOR_PATH} ne renvoie pas `{column}`. "
            "Le checkout local n'est probablement pas à jour avec la PR #35."
        )

    value = player[column]
    if value is None:
        raise RuntimeError(f"`{column}` vaut None pour participant_id={player.get('participant_id')}")

    return int(value)


def _build_updates(
    match_id: str,
    analyzed_puuid: str,
    teamfights: list[dict],
) -> list[dict]:
    updates: list[dict] = []

    for fight in teamfights:
        for player in fight.get("players", []):
            values = {
                column: _required_taken_value(player, column)
                for column in TAKEN_COLUMNS
            }
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
                    **values,
                }
            )

    return updates


def _frame_by_timestamp(timeline: dict, timestamp: int) -> dict | None:
    return next(
        (
            frame
            for frame in timeline.get("info", {}).get("frames", [])
            if int(frame.get("timestamp", -1)) == int(timestamp)
        ),
        None,
    )


def _debug_teamfights(
    timeline: dict,
    teamfights: list[dict],
    analyzed_puuid: str,
) -> None:
    """Affiche les compteurs Riot bruts et les deltas calculés du joueur tracké."""
    participants = timeline.get("metadata", {}).get("participants", [])
    if analyzed_puuid not in participants:
        print("  DEBUG - PUUID absent de metadata.participants")
        return

    participant_id = participants.index(analyzed_puuid) + 1
    print(f"  DEBUG - calculateur: {CALCULATOR_PATH}")
    print(f"  DEBUG - participant_id tracké: {participant_id}")

    for fight in teamfights:
        tracked = next(
            (
                player
                for player in fight.get("players", [])
                if int(player.get("participant_id", -1)) == participant_id
            ),
            None,
        )
        if tracked is None:
            continue

        start = int(fight["estimation_window_start_ms"])
        end = int(fight["estimation_window_end_ms"])
        before = _frame_by_timestamp(timeline, start) or {}
        after = _frame_by_timestamp(timeline, end) or {}
        before_stats = (
            before.get("participantFrames", {})
            .get(str(participant_id), {})
            .get("damageStats", {})
        )
        after_stats = (
            after.get("participantFrames", {})
            .get(str(participant_id), {})
            .get("damageStats", {})
        )

        print(
            f"  DEBUG fight #{fight['fight_id']} "
            f"window={start}->{end}"
        )
        for stat in RIOT_TAKEN_STATS:
            print(
                f"    {stat}: "
                f"{before_stats.get(stat, '<absent>')} -> "
                f"{after_stats.get(stat, '<absent>')}"
            )
        print(
            "    calculé: "
            + ", ".join(
                f"{column}={tracked.get(column, '<absent>')}"
                for column in TAKEN_COLUMNS
            )
        )


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
        if args.match_id and not args.force:
            print(
                "Astuce : si ce match a déjà été rempli avec des zéros, "
                "relance avec --force."
            )
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

                # Validation AVANT toute écriture.
                _build_updates(match_id, puuid, teamfights)

                if args.debug:
                    _debug_teamfights(timeline, teamfights, puuid)

                if args.inspect_only:
                    print("  INSPECT - aucune écriture BDD")
                    success += 1
                    continue

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
        help="Filtre facultatif sur les modes.",
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
        help="Ne traite qu'un match.",
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
        help="Recalcule aussi les perspectives déjà remplies.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche la sélection sans appeler Riot ni écrire en BDD.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Affiche les compteurs Riot bruts avant/après chaque fenêtre du joueur tracké.",
    )
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Recalcule et affiche éventuellement --debug, sans écrire en BDD.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(backfill(parse_args()))
