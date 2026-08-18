"""Rattrapage des données Teamfights nécessaires aux records enrichis.

Le script reprend le principe du notebook historique ``import data.ipynb`` :
- sélection des matchs en base ;
- récupération directe du détail de match + timeline Riot ;
- recalcul via ``calculate_teamfight_damage`` ;
- remplacement atomique des lignes ``match_teamfight_damage`` ;
- marquage de la perspective dans ``match_teamfight_backfill_status``.

Le script charge directement les modules source nécessaires et n'importe pas
``fonctions.match`` / ``MatchLol``. Cela évite d'initialiser tous les mixins et
renderers du bot pour un simple rattrapage de données.

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
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterable

import aiohttp
import pandas as pd
from sqlalchemy import text


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fonctions.gestion_bdd import engine, lire_bdd_perso
from utils.params import api_key_lol


BACKFILL_VERSION = 1
DEFAULT_MODES = ("RANKED", "FLEX", "SWIFTPLAY", "ARAM")


def _load_source_module(module_name: str, relative_path: str) -> ModuleType:
    """Charge un fichier Python sans exécuter ``fonctions.match.__init__``."""
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossible de charger {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_RIOT_API = _load_source_module(
    "_teamfight_backfill_riot_api",
    "fonctions/match/riot_api.py",
)
_TEAMFIGHT_DAMAGE = _load_source_module(
    "_teamfight_backfill_damage",
    "fonctions/match/teamfight_damage.py",
)

get_match_detail = _RIOT_API.get_match_detail
get_match_timeline = _RIOT_API.get_match_timeline
calculate_teamfight_damage = _TEAMFIGHT_DAMAGE.calculate_teamfight_damage


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
    """Construit une liste SQL depuis les valeurs validées par argparse."""
    return ", ".join(f"'{value}'" for value in values)


def _timestamp_ms_to_mmss_decimal(timestamp_ms: int) -> float:
    """Encode 658000 ms en 10.58, comme ``teamfight_time.py``."""
    total_seconds = max(0, int(timestamp_ms)) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return round(minutes + seconds / 100, 2)


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


def _validate_riot_payload(payload: dict, label: str) -> None:
    if not isinstance(payload, dict):
        raise RuntimeError(f"Réponse Riot invalide pour {label}")
    if label == "match" and "info" not in payload:
        raise RuntimeError(f"Réponse Riot invalide pour le match : {payload}")
    if label == "timeline" and "info" not in payload:
        raise RuntimeError(f"Réponse Riot invalide pour la timeline : {payload}")


def _build_rows(
    match_id: str,
    analyzed_puuid: str,
    teamfights: list[dict],
) -> list[dict]:
    rows: list[dict] = []

    for fight in teamfights:
        allied_kills = fight.get("allied_kills", fight.get("kills_allies", 0))
        enemy_kills = fight.get("enemy_kills", fight.get("kills_enemies", 0))
        start_minute = _timestamp_ms_to_mmss_decimal(fight["start_ms"])
        end_minute = _timestamp_ms_to_mmss_decimal(fight["end_ms"])

        fight_values = {
            "match_id": match_id,
            "analyzed_puuid": analyzed_puuid,
            "fight_id": fight["fight_id"],
            "start_ms": fight["start_ms"],
            "end_ms": fight["end_ms"],
            "start_minute": start_minute,
            "end_minute": end_minute,
            "first_kill_ms": fight.get("first_kill_ms", fight["start_ms"]),
            "last_kill_ms": fight.get("last_kill_ms", fight["end_ms"]),
            "kill_span_ms": fight.get(
                "kill_span_ms",
                max(0, fight["end_ms"] - fight["start_ms"]),
            ),
            "estimation_window_start_ms": fight["estimation_window_start_ms"],
            "estimation_window_end_ms": fight["estimation_window_end_ms"],
            "kills_allies": fight.get("kills_allies", allied_kills),
            "kills_enemies": fight.get("kills_enemies", enemy_kills),
            "allied_kills": allied_kills,
            "enemy_kills": enemy_kills,
            "winner": fight.get("winner"),
            "core_allies": fight.get("core_allies"),
            "core_enemies": fight.get("core_enemies"),
            "participants_allies": fight.get("participants_allies"),
            "participants_enemies": fight.get("participants_enemies"),
            "proximity_allies": fight.get("proximity_allies"),
            "proximity_enemies": fight.get("proximity_enemies"),
            "fight_type": fight.get("fight_type"),
            "fight_type_with_proximity": fight.get("fight_type_with_proximity"),
            "fight_category": fight.get("fight_category"),
            "is_teamfight": fight.get("is_teamfight", False),
            "is_outnumbered": fight.get("is_outnumbered", False),
            "outnumbered_team": fight.get("outnumbered_team"),
            "won_while_outnumbered": fight.get("won_while_outnumbered", False),
            "shared_damage_window": fight.get("shared_damage_window", False),
            "shared_window_fight_count": fight.get("shared_window_fight_count", 1),
        }

        for player in fight.get("players", []):
            damage_frame_window = player.get(
                "damage_frame_window",
                player.get("damage_window_estimated", 0),
            )
            rows.append(
                {
                    **fight_values,
                    "participant_id": player["participant_id"],
                    "puuid": player["puuid"],
                    "player_name": player["player"],
                    "champion": player["champion"],
                    "team": player["team"],
                    "participation_source": player["participation_source"],
                    "is_core_participant": player.get("is_core_participant", True),
                    "is_proximity_participant": player.get(
                        "is_proximity_participant",
                        False,
                    ),
                    "was_killer": player.get("was_killer", False),
                    "was_victim": player.get("was_victim", False),
                    "was_assistant": player.get("was_assistant", False),
                    "was_damage_source": player.get("was_damage_source", False),
                    "fight_kills": player.get("fight_kills", 0),
                    "fight_deaths": player.get("fight_deaths", 0),
                    "fight_assists": player.get("fight_assists", 0),
                    "survived": player.get("survived", True),
                    "enemies_damaged_count": player.get("enemies_damaged_count", 0),
                    "damage_on_dead_targets": player.get(
                        "damage_on_dead_targets",
                        0,
                    ),
                    "physical_damage_on_dead_targets": player.get(
                        "physical_damage_on_dead_targets",
                        0,
                    ),
                    "magic_damage_on_dead_targets": player.get(
                        "magic_damage_on_dead_targets",
                        0,
                    ),
                    "true_damage_on_dead_targets": player.get(
                        "true_damage_on_dead_targets",
                        0,
                    ),
                    "damage_share_on_dead_targets": player.get(
                        "damage_share_on_dead_targets",
                        0.0,
                    ),
                    "damage_window_estimated": player.get(
                        "damage_window_estimated",
                        damage_frame_window,
                    ),
                    "damage_frame_window": damage_frame_window,
                    "physical_damage_window_estimated": player.get(
                        "physical_damage_window_estimated",
                        0,
                    ),
                    "magic_damage_window_estimated": player.get(
                        "magic_damage_window_estimated",
                        0,
                    ),
                    "true_damage_window_estimated": player.get(
                        "true_damage_window_estimated",
                        0,
                    ),
                }
            )

    return rows


INSERT_TEAMFIGHT_SQL = text(
    """
    INSERT INTO match_teamfight_damage (
        match_id, analyzed_puuid, fight_id, participant_id, puuid,
        player_name, champion, team, participation_source,
        start_ms, end_ms, start_minute, end_minute,
        first_kill_ms, last_kill_ms, kill_span_ms,
        estimation_window_start_ms, estimation_window_end_ms,
        kills_allies, kills_enemies, allied_kills, enemy_kills, winner,
        core_allies, core_enemies,
        participants_allies, participants_enemies,
        proximity_allies, proximity_enemies,
        fight_type, fight_type_with_proximity, fight_category,
        is_teamfight, is_outnumbered, outnumbered_team,
        won_while_outnumbered, shared_damage_window, shared_window_fight_count,
        is_core_participant, is_proximity_participant,
        was_killer, was_victim, was_assistant, was_damage_source,
        fight_kills, fight_deaths, fight_assists, survived,
        enemies_damaged_count,
        damage_on_dead_targets,
        physical_damage_on_dead_targets,
        magic_damage_on_dead_targets,
        true_damage_on_dead_targets,
        damage_share_on_dead_targets,
        damage_window_estimated, damage_frame_window,
        physical_damage_window_estimated,
        magic_damage_window_estimated,
        true_damage_window_estimated
    ) VALUES (
        :match_id, :analyzed_puuid, :fight_id, :participant_id, :puuid,
        :player_name, :champion, :team, :participation_source,
        :start_ms, :end_ms, :start_minute, :end_minute,
        :first_kill_ms, :last_kill_ms, :kill_span_ms,
        :estimation_window_start_ms, :estimation_window_end_ms,
        :kills_allies, :kills_enemies, :allied_kills, :enemy_kills, :winner,
        :core_allies, :core_enemies,
        :participants_allies, :participants_enemies,
        :proximity_allies, :proximity_enemies,
        :fight_type, :fight_type_with_proximity, :fight_category,
        :is_teamfight, :is_outnumbered, :outnumbered_team,
        :won_while_outnumbered, :shared_damage_window, :shared_window_fight_count,
        :is_core_participant, :is_proximity_participant,
        :was_killer, :was_victim, :was_assistant, :was_damage_source,
        :fight_kills, :fight_deaths, :fight_assists, :survived,
        :enemies_damaged_count,
        :damage_on_dead_targets,
        :physical_damage_on_dead_targets,
        :magic_damage_on_dead_targets,
        :true_damage_on_dead_targets,
        :damage_share_on_dead_targets,
        :damage_window_estimated, :damage_frame_window,
        :physical_damage_window_estimated,
        :magic_damage_window_estimated,
        :true_damage_window_estimated
    )
    """
)


def save_backfill(
    match_id: str,
    analyzed_puuid: str,
    teamfights: list[dict],
) -> None:
    """Remplace les lignes d'une perspective et marque le backfill atomiquement."""
    rows = _build_rows(match_id, analyzed_puuid, teamfights)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM match_teamfight_damage
                WHERE match_id = :match_id
                  AND analyzed_puuid = :analyzed_puuid
                """
            ),
            {
                "match_id": match_id,
                "analyzed_puuid": analyzed_puuid,
            },
        )

        if rows:
            conn.execute(INSERT_TEAMFIGHT_SQL, rows)

        conn.execute(
            text(
                """
                INSERT INTO match_teamfight_backfill_status (
                    match_id,
                    analyzed_puuid,
                    backfill_version,
                    fights_count,
                    updated_at
                ) VALUES (
                    :match_id,
                    :analyzed_puuid,
                    :backfill_version,
                    :fights_count,
                    NOW()
                )
                ON CONFLICT (match_id, analyzed_puuid)
                DO UPDATE SET
                    backfill_version = EXCLUDED.backfill_version,
                    fights_count = EXCLUDED.fights_count,
                    updated_at = NOW()
                """
            ),
            {
                "match_id": match_id,
                "analyzed_puuid": analyzed_puuid,
                "backfill_version": BACKFILL_VERSION,
                "fights_count": len(teamfights),
            },
        )


async def backfill(args: argparse.Namespace) -> None:
    matches = load_matches(args.modes, args.season, args.limit, args.force)
    if matches.empty:
        print("Aucun match à retraiter.")
        return

    print(f"{len(matches)} perspective(s) de match à retraiter.")

    if args.dry_run:
        columns = [
            "id_compte",
            "match_id",
            "mode",
            "season",
            "riot_id",
            "riot_tagline",
        ]
        print(matches[columns].to_string(index=False))
        return

    success = 0
    errors = 0
    timeout = aiohttp.ClientTimeout(total=120)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for position, row in matches.iterrows():
            match_id = str(row["match_id"])
            puuid = str(row["puuid"])
            riot_id = str(row["riot_id"])
            riot_tag = str(row["riot_tagline"])

            print(
                f"[{position + 1}/{len(matches)}] "
                f"{riot_id}#{riot_tag} - {match_id}"
            )

            try:
                match_detail = await get_match_detail(
                    session,
                    match_id,
                    {"api_key": api_key_lol},
                )
                _validate_riot_payload(match_detail, "match")

                timeline = await get_match_timeline(session, match_id)
                _validate_riot_payload(timeline, "timeline")

                timeline_participants = (
                    timeline.get("metadata", {}).get("participants", [])
                )
                if puuid not in timeline_participants:
                    raise ValueError(
                        "PUUID du joueur introuvable dans la timeline"
                    )

                allied_team_id = _tracked_team_id(match_detail, puuid)
                teamfights = calculate_teamfight_damage(
                    match_detail,
                    timeline,
                    allied_team_id=allied_team_id,
                )
                save_backfill(match_id, puuid, teamfights)

                success += 1
                print(
                    f"  OK - {len(teamfights)} combat(s) recalculé(s)"
                )
            except Exception as error:
                errors += 1
                print(
                    f"  ERREUR - {type(error).__name__}: {error}"
                )

            if args.delay > 0 and position + 1 < len(matches):
                await asyncio.sleep(args.delay)

    print(f"Terminé : {success} succès, {errors} erreur(s).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rattrape les données des records Teamfights."
    )
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
        help="Pause entre deux appels de match, en secondes.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Retraite les matchs même s'ils semblent déjà à jour.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche la sélection sans appeler Riot ni écrire en BDD.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(backfill(parse_args()))
