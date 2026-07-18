"""Calcul des dégâts infligés par joueur pendant les teamfights."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def _event_distance(event_a: dict[str, Any], event_b: dict[str, Any]) -> float:
    """Retourne la distance entre deux événements, ou 0 si une position manque."""
    position_a = event_a.get("position")
    position_b = event_b.get("position")

    if not position_a or not position_b:
        return 0.0

    return math.hypot(
        position_a["x"] - position_b["x"],
        position_a["y"] - position_b["y"],
    )


def _group_kills_into_fights(
    kill_events: list[dict[str, Any]],
    max_gap_ms: int,
    max_distance: int,
) -> list[list[dict[str, Any]]]:
    """Regroupe les kills proches dans le temps et dans l'espace."""
    fight_groups: list[list[dict[str, Any]]] = []

    for event in kill_events:
        if not fight_groups:
            fight_groups.append([event])
            continue

        previous_event = fight_groups[-1][-1]
        close_in_time = event["timestamp"] - previous_event["timestamp"] <= max_gap_ms
        close_in_space = _event_distance(event, previous_event) <= max_distance

        if close_in_time and close_in_space:
            fight_groups[-1].append(event)
        else:
            fight_groups.append([event])

    return fight_groups


def _closest_frame(frames: list[dict[str, Any]], timestamp: int) -> dict[str, Any]:
    """Retourne la frame Riot la plus proche d'un timestamp."""
    return min(frames, key=lambda frame: abs(frame["timestamp"] - timestamp))


def _is_near_fight(
    participant_id: int,
    events: list[dict[str, Any]],
    frames: list[dict[str, Any]],
    fight_radius: int,
) -> bool:
    """Détecte une participation par proximité avec au moins un kill du combat."""
    for event in events:
        fight_position = event.get("position")
        if not fight_position:
            continue

        frame = _closest_frame(frames, event["timestamp"])
        participant_frame = frame.get("participantFrames", {}).get(str(participant_id), {})
        position = participant_frame.get("position")
        if not position:
            continue

        distance = math.hypot(
            position["x"] - fight_position["x"],
            position["y"] - fight_position["y"],
        )
        if distance <= fight_radius:
            return True

    return False


def _cumulative_champion_damage(frame: dict[str, Any], participant_id: int) -> int:
    """Lit le compteur cumulatif de dégâts aux champions d'une frame Riot."""
    participant_frame = frame.get("participantFrames", {}).get(str(participant_id), {})
    return int(
        participant_frame.get("damageStats", {}).get("totalDamageDoneToChampions", 0)
        or 0
    )


def calculate_teamfight_damage(
    match_detail: dict[str, Any],
    timeline: dict[str, Any],
    *,
    allied_team_id: int,
    max_gap_ms: int = 12_000,
    max_distance: int = 2_000,
    fight_radius: int = 2_000,
    min_players_per_team: int = 2,
) -> list[dict[str, Any]]:
    """Calcule les dégâts de chaque joueur pour les teamfights détectés.

    ``allied_team_id`` correspond à l'équipe du joueur dont le match est analysé.
    Les joueurs retournés sont ainsi étiquetés ``Allié`` ou ``Ennemi`` sans
    exposer les identifiants Riot 100 et 200 dans l'output.

    Deux mesures complémentaires sont retournées :

    ``damage_on_dead_targets``
        Dégâts précisément attribués grâce à ``victimDamageReceived``. Cette
        valeur ne couvre que les dégâts reçus par les champions morts.

    ``damage_window_estimated``
        Différence du compteur ``totalDamageDoneToChampions`` entre les frames
        entourant le combat. Cette valeur couvre aussi les survivants, mais peut
        inclure du poke réalisé dans la même fenêtre de timeline.

    Les joueurs sont considérés participants lorsqu'ils apparaissent comme
    killer, victime ou assistant, ou lorsqu'une frame les place à proximité
    d'un kill du combat.
    """
    frames = timeline.get("info", {}).get("frames", [])
    participants = match_detail.get("info", {}).get("participants", [])

    if not frames or not participants:
        return []

    team_by_pid = {
        participant["participantId"]: participant["teamId"]
        for participant in participants
    }
    if allied_team_id not in set(team_by_pid.values()):
        raise ValueError("allied_team_id ne correspond à aucune équipe du match")

    champion_by_pid = {
        participant["participantId"]: participant.get("championName", "")
        for participant in participants
    }
    player_by_pid = {
        participant["participantId"]: (
            participant.get("riotIdGameName")
            or participant.get("summonerName")
            or participant.get("championName")
            or str(participant["participantId"])
        )
        for participant in participants
    }
    puuid_by_pid = {
        participant["participantId"]: participant.get("puuid", "")
        for participant in participants
    }

    kill_events = sorted(
        (
            event
            for frame in frames
            for event in frame.get("events", [])
            if event.get("type") == "CHAMPION_KILL"
        ),
        key=lambda event: event["timestamp"],
    )

    if not kill_events:
        return []

    fight_groups = _group_kills_into_fights(
        kill_events,
        max_gap_ms=max_gap_ms,
        max_distance=max_distance,
    )
    results: list[dict[str, Any]] = []

    for events in fight_groups:
        event_involved: set[int] = set()
        for event in events:
            for participant_id in (
                event.get("killerId"),
                event.get("victimId"),
                *event.get("assistingParticipantIds", []),
            ):
                if participant_id in team_by_pid:
                    event_involved.add(participant_id)

        involved = {
            participant_id
            for participant_id in team_by_pid
            if participant_id in event_involved
            or _is_near_fight(
                participant_id,
                events,
                frames,
                fight_radius=fight_radius,
            )
        }

        involved_allies = {
            pid for pid in involved if team_by_pid[pid] == allied_team_id
        }
        involved_enemies = {
            pid for pid in involved if team_by_pid[pid] != allied_team_id
        }
        if (
            len(involved_allies) < min_players_per_team
            or len(involved_enemies) < min_players_per_team
        ):
            continue

        start_ms = min(event["timestamp"] for event in events)
        end_ms = max(event["timestamp"] for event in events)
        before_frames = [frame for frame in frames if frame["timestamp"] <= start_ms]
        after_frames = [frame for frame in frames if frame["timestamp"] >= end_ms]
        frame_before = before_frames[-1] if before_frames else frames[0]
        frame_after = after_frames[0] if after_frames else frames[-1]

        damage_on_dead_targets: defaultdict[int, dict[str, int]] = defaultdict(
            lambda: {"physical": 0, "magic": 0, "true": 0, "total": 0}
        )

        for event in events:
            victim_id = event.get("victimId")
            for damage in event.get("victimDamageReceived", []) or []:
                source_id = damage.get("participantId")
                if source_id not in team_by_pid:
                    continue
                if victim_id in team_by_pid and team_by_pid[source_id] == team_by_pid[victim_id]:
                    continue

                physical = int(damage.get("physicalDamage", 0) or 0)
                magic = int(damage.get("magicDamage", 0) or 0)
                true_damage = int(damage.get("trueDamage", 0) or 0)
                damage_on_dead_targets[source_id]["physical"] += physical
                damage_on_dead_targets[source_id]["magic"] += magic
                damage_on_dead_targets[source_id]["true"] += true_damage
                damage_on_dead_targets[source_id]["total"] += physical + magic + true_damage

        player_results = []
        for participant_id in sorted(involved):
            detailed_damage = damage_on_dead_targets[participant_id]
            damage_before = _cumulative_champion_damage(frame_before, participant_id)
            damage_after = _cumulative_champion_damage(frame_after, participant_id)

            player_results.append(
                {
                    "participant_id": participant_id,
                    "puuid": puuid_by_pid[participant_id],
                    "player": player_by_pid[participant_id],
                    "champion": champion_by_pid[participant_id],
                    "team": (
                        "Allié"
                        if team_by_pid[participant_id] == allied_team_id
                        else "Ennemi"
                    ),
                    "participation_source": (
                        "event" if participant_id in event_involved else "proximity"
                    ),
                    "damage_on_dead_targets": detailed_damage["total"],
                    "physical_damage_on_dead_targets": detailed_damage["physical"],
                    "magic_damage_on_dead_targets": detailed_damage["magic"],
                    "true_damage_on_dead_targets": detailed_damage["true"],
                    "damage_window_estimated": max(0, damage_after - damage_before),
                }
            )

        kills_allies = sum(
            team_by_pid.get(event.get("killerId")) == allied_team_id
            for event in events
        )
        kills_enemies = sum(
            event.get("killerId") in team_by_pid
            and team_by_pid[event["killerId"]] != allied_team_id
            for event in events
        )

        results.append(
            {
                "fight_id": len(results) + 1,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "start_minute": round(start_ms / 60_000, 2),
                "end_minute": round(end_ms / 60_000, 2),
                "estimation_window_start_ms": frame_before["timestamp"],
                "estimation_window_end_ms": frame_after["timestamp"],
                "kills_allies": kills_allies,
                "kills_enemies": kills_enemies,
                "players": player_results,
            }
        )

    return results


async def teamfight_damage(
    self: Any,
    max_gap_ms: int = 12_000,
    max_distance: int = 2_000,
    fight_radius: int = 2_000,
    min_players_per_team: int = 2,
) -> list[dict[str, Any]]:
    """Méthode installée sur ``MatchLol`` pour analyser sa timeline chargée."""
    if not getattr(self, "data_timeline", None):
        return []

    allied_team_id = getattr(self, "teamId", None)
    if allied_team_id is None:
        current_participant_id = getattr(self, "index_timeline", None)
        current_participant = next(
            (
                participant
                for participant in self.match_detail.get("info", {}).get("participants", [])
                if participant.get("participantId") == current_participant_id
            ),
            None,
        )
        allied_team_id = current_participant.get("teamId") if current_participant else None

    if allied_team_id is None:
        raise ValueError("Impossible de déterminer l'équipe alliée du joueur analysé")

    return calculate_teamfight_damage(
        self.match_detail,
        self.data_timeline,
        allied_team_id=allied_team_id,
        max_gap_ms=max_gap_ms,
        max_distance=max_distance,
        fight_radius=fight_radius,
        min_players_per_team=min_players_per_team,
    )


def install_teamfight_damage(match_class: type[Any]) -> None:
    """Ajoute ``teamfight_damage`` à la classe MatchLol sans modifier son MRO."""
    match_class.teamfight_damage = teamfight_damage
