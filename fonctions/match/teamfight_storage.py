"""Persistance PostgreSQL des dégâts et statistiques par combat."""

from __future__ import annotations

from functools import wraps
from typing import Any

from fonctions.gestion_bdd import requete_perso_bdd
from .teamfight_time import timestamp_ms_to_mmss_decimal


TEAMFIGHT_TABLE = "match_teamfight_damage"


def _get_analyzed_puuid(match: Any) -> str:
    """Retourne le PUUID du joueur dont le point de vue est analysé."""
    if getattr(match, "puuid", None):
        return str(match.puuid)

    participant_id = getattr(match, "index_timeline", None)
    participants = (getattr(match, "match_detail", None) or {}).get("info", {}).get(
        "participants", []
    )
    participant = next(
        (
            player
            for player in participants
            if player.get("participantId") == participant_id
        ),
        None,
    )
    return str(participant.get("puuid", "")) if participant else ""


async def save_teamfight_damage(
    self: Any,
    teamfights: list[dict[str, Any]] | None = None,
) -> bool:
    """Sauvegarde une ligne par joueur et par combat détecté."""
    if teamfights is None:
        teamfights = await self.teamfight_damage()

    match_id = getattr(self, "last_match", None)
    analyzed_puuid = _get_analyzed_puuid(self)
    if not match_id or not analyzed_puuid:
        raise ValueError("match_id ou PUUID du joueur analysé introuvable")

    # Le recalcul remplace toutes les anciennes lignes de ce point de vue.
    requete_perso_bdd(
        f"""
        DELETE FROM {TEAMFIGHT_TABLE}
        WHERE match_id = :match_id
          AND analyzed_puuid = :analyzed_puuid
        """,
        {"match_id": match_id, "analyzed_puuid": analyzed_puuid},
    )

    insert_sql = f"""
        INSERT INTO {TEAMFIGHT_TABLE} (
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
            damage_window_estimated, damage_frame_window
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
            :damage_window_estimated, :damage_frame_window
        )
    """

    for fight in teamfights:
        allied_kills = fight.get("allied_kills", fight.get("kills_allies", 0))
        enemy_kills = fight.get("enemy_kills", fight.get("kills_enemies", 0))

        # start_minute/end_minute utilisent une représentation MM.SS et non des
        # minutes décimales. Exemple : 10 min 58 s -> 10.58, jamais 10.97.
        start_minute = timestamp_ms_to_mmss_decimal(fight["start_ms"])
        end_minute = timestamp_ms_to_mmss_decimal(fight["end_ms"])
        fight["start_minute"] = start_minute
        fight["end_minute"] = end_minute

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
            "kill_span_ms": fight.get("kill_span_ms", max(0, fight["end_ms"] - fight["start_ms"])),
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

        for player in fight["players"]:
            damage_frame_window = player.get(
                "damage_frame_window",
                player.get("damage_window_estimated", 0),
            )
            requete_perso_bdd(
                insert_sql,
                {
                    **fight_values,
                    "participant_id": player["participant_id"],
                    "puuid": player["puuid"],
                    "player_name": player["player"],
                    "champion": player["champion"],
                    "team": player["team"],
                    "participation_source": player["participation_source"],
                    "is_core_participant": player.get("is_core_participant", True),
                    "is_proximity_participant": player.get("is_proximity_participant", False),
                    "was_killer": player.get("was_killer", False),
                    "was_victim": player.get("was_victim", False),
                    "was_assistant": player.get("was_assistant", False),
                    "was_damage_source": player.get("was_damage_source", False),
                    "fight_kills": player.get("fight_kills", 0),
                    "fight_deaths": player.get("fight_deaths", 0),
                    "fight_assists": player.get("fight_assists", 0),
                    "survived": player.get("survived", True),
                    "enemies_damaged_count": player.get("enemies_damaged_count", 0),
                    "damage_on_dead_targets": player["damage_on_dead_targets"],
                    "physical_damage_on_dead_targets": player[
                        "physical_damage_on_dead_targets"
                    ],
                    "magic_damage_on_dead_targets": player[
                        "magic_damage_on_dead_targets"
                    ],
                    "true_damage_on_dead_targets": player[
                        "true_damage_on_dead_targets"
                    ],
                    "damage_share_on_dead_targets": player.get("damage_share_on_dead_targets", 0.0),
                    "damage_window_estimated": player.get("damage_window_estimated", damage_frame_window),
                    "damage_frame_window": damage_frame_window,
                },
            )

    self.teamfight_damage_data = teamfights
    return True


def install_teamfight_storage(match_class: type[Any]) -> None:
    """Ajoute la sauvegarde et son déclenchement automatique à ``MatchLol``."""
    match_class.save_teamfight_damage = save_teamfight_damage

    original_run = match_class.run
    if getattr(original_run, "_teamfight_storage_installed", False):
        return

    @wraps(original_run)
    async def run_with_teamfight_storage(self: Any, *args: Any, **kwargs: Any) -> Any:
        result = await original_run(self, *args, **kwargs)

        # Les modes 5v5 utilisent dix participants. save=False reste respecté.
        should_save = (
            getattr(self, "save", True)
            and getattr(self, "nb_joueur", 0) == 10
            and bool(getattr(self, "data_timeline", None))
        )
        if should_save:
            try:
                teamfights = await self.teamfight_damage()
                await self.save_teamfight_damage(teamfights)
            except Exception as error:
                print(f"Erreur sauvegarde teamfights: {error}")

        return result

    run_with_teamfight_storage._teamfight_storage_installed = True
    match_class.run = run_with_teamfight_storage
