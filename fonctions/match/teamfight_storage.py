"""Persistance PostgreSQL des dégâts par joueur pendant les teamfights."""

from __future__ import annotations

from functools import wraps
from typing import Any

from fonctions.gestion_bdd import requete_perso_bdd


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
    """Sauvegarde une ligne par joueur et par teamfight."""
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
            estimation_window_start_ms, estimation_window_end_ms,
            kills_allies, kills_enemies,
            damage_on_dead_targets,
            physical_damage_on_dead_targets,
            magic_damage_on_dead_targets,
            true_damage_on_dead_targets,
            damage_window_estimated
        ) VALUES (
            :match_id, :analyzed_puuid, :fight_id, :participant_id, :puuid,
            :player_name, :champion, :team, :participation_source,
            :start_ms, :end_ms, :start_minute, :end_minute,
            :estimation_window_start_ms, :estimation_window_end_ms,
            :kills_allies, :kills_enemies,
            :damage_on_dead_targets,
            :physical_damage_on_dead_targets,
            :magic_damage_on_dead_targets,
            :true_damage_on_dead_targets,
            :damage_window_estimated
        )
    """

    for fight in teamfights:
        fight_values = {
            "match_id": match_id,
            "analyzed_puuid": analyzed_puuid,
            "fight_id": fight["fight_id"],
            "start_ms": fight["start_ms"],
            "end_ms": fight["end_ms"],
            "start_minute": fight["start_minute"],
            "end_minute": fight["end_minute"],
            "estimation_window_start_ms": fight["estimation_window_start_ms"],
            "estimation_window_end_ms": fight["estimation_window_end_ms"],
            "kills_allies": fight["kills_allies"],
            "kills_enemies": fight["kills_enemies"],
        }

        for player in fight["players"]:
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
                    "damage_window_estimated": player["damage_window_estimated"],
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
