"""Calcul des dégâts infligés par joueur pendant les combats."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
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
    """Détecte une participation probable par proximité avec un kill du combat."""
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


def _cumulative_champion_damage(
    frame: dict[str, Any],
    participant_id: int,
    stat: str = "totalDamageDoneToChampions",
) -> int:
    """Lit un compteur cumulatif de dégâts aux champions d'une frame Riot."""
    participant_frame = frame.get("participantFrames", {}).get(str(participant_id), {})
    return int(participant_frame.get("damageStats", {}).get(stat, 0) or 0)


def _damage_window(
    frame_before: dict[str, Any],
    frame_after: dict[str, Any],
    participant_id: int,
    stat: str,
) -> int:
    """Retourne le delta positif d'un compteur de dégâts sur la fenêtre du combat."""
    before = _cumulative_champion_damage(frame_before, participant_id, stat)
    after = _cumulative_champion_damage(frame_after, participant_id, stat)
    return max(0, after - before)


def _fight_category(allies: int, enemies: int) -> str:
    """Classe un combat à partir des participants confirmés (core)."""
    if allies == 1 and enemies == 1:
        return "duel"
    if min(allies, enemies) >= 3:
        return "teamfight"
    if min(allies, enemies) == 1 and allies != enemies:
        return "outnumbered"
    return "skirmish"


def _participation_source(
    participant_id: int,
    event_involved: set[int],
    damage_involved: set[int],
) -> str:
    """Explique pourquoi un joueur est considéré participant."""
    in_event = participant_id in event_involved
    in_damage = participant_id in damage_involved
    if in_event and in_damage:
        return "event+damage"
    if in_event:
        return "event"
    if in_damage:
        return "damage"
    return "proximity"


def calculate_teamfight_damage(
    match_detail: dict[str, Any],
    timeline: dict[str, Any],
    *,
    allied_team_id: int,
    max_gap_ms: int = 12_000,
    max_distance: int = 2_000,
    fight_radius: int = 2_000,
    min_players_per_team: int = 1,
) -> list[dict[str, Any]]:
    """Calcule les dégâts et statistiques de chaque combat détecté.

    La détection conserve désormais les duels et combats asymétriques (1v2,
    2v1, etc.). Les participants ``core`` sont ceux confirmés par un événement
    de kill (killer/victime/assist) ou par ``victimDamageReceived``. Les joueurs
    uniquement proches du combat sont conservés séparément comme participants
    probables et ne modifient pas le ``fight_type``.

    ``damage_on_dead_targets`` est exact pour les cibles mortes présentes dans
    les événements Riot. Les champs ``*_damage_window_estimated`` sont des
    estimations par différence de compteurs entre les mêmes frames et ne doivent
    pas être additionnés entre combats qui partagent la même fenêtre.
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
        damage_involved: set[int] = set()
        damage_on_dead_targets: defaultdict[int, dict[str, int]] = defaultdict(
            lambda: {"physical": 0, "magic": 0, "true": 0, "total": 0}
        )
        damaged_victims_by_source: defaultdict[int, set[int]] = defaultdict(set)

        for event in events:
            for participant_id in (
                event.get("killerId"),
                event.get("victimId"),
                *event.get("assistingParticipantIds", []),
            ):
                if participant_id in team_by_pid:
                    event_involved.add(participant_id)

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
                total = physical + magic + true_damage

                damage_involved.add(source_id)
                damage_on_dead_targets[source_id]["physical"] += physical
                damage_on_dead_targets[source_id]["magic"] += magic
                damage_on_dead_targets[source_id]["true"] += true_damage
                damage_on_dead_targets[source_id]["total"] += total
                if total > 0 and victim_id in team_by_pid:
                    damaged_victims_by_source[source_id].add(victim_id)

        core_involved = event_involved | damage_involved
        core_allies_set = {
            pid for pid in core_involved if team_by_pid[pid] == allied_team_id
        }
        core_enemies_set = {
            pid for pid in core_involved if team_by_pid[pid] != allied_team_id
        }
        if (
            len(core_allies_set) < min_players_per_team
            or len(core_enemies_set) < min_players_per_team
        ):
            continue

        proximity_involved = {
            participant_id
            for participant_id in team_by_pid
            if participant_id not in core_involved
            and _is_near_fight(
                participant_id,
                events,
                frames,
                fight_radius=fight_radius,
            )
        }
        involved = core_involved | proximity_involved
        involved_allies = {
            pid for pid in involved if team_by_pid[pid] == allied_team_id
        }
        involved_enemies = {
            pid for pid in involved if team_by_pid[pid] != allied_team_id
        }

        first_kill_ms = min(event["timestamp"] for event in events)
        last_kill_ms = max(event["timestamp"] for event in events)
        before_frames = [frame for frame in frames if frame["timestamp"] <= first_kill_ms]
        after_frames = [frame for frame in frames if frame["timestamp"] >= last_kill_ms]
        frame_before = before_frames[-1] if before_frames else frames[0]
        frame_after = after_frames[0] if after_frames else frames[-1]

        allied_kills = sum(
            team_by_pid.get(event.get("killerId")) == allied_team_id
            for event in events
        )
        enemy_kills = sum(
            event.get("killerId") in team_by_pid
            and team_by_pid[event["killerId"]] != allied_team_id
            for event in events
        )
        winner = (
            "Allié"
            if allied_kills > enemy_kills
            else "Ennemi"
            if enemy_kills > allied_kills
            else "Égalité"
        )

        core_allies = len(core_allies_set)
        core_enemies = len(core_enemies_set)
        is_outnumbered = core_allies != core_enemies
        outnumbered_team = (
            "Allié"
            if core_allies < core_enemies
            else "Ennemi"
            if core_enemies < core_allies
            else None
        )
        won_while_outnumbered = bool(
            outnumbered_team is not None and winner == outnumbered_team
        )

        team_damage_totals: defaultdict[int, int] = defaultdict(int)
        for source_id, values in damage_on_dead_targets.items():
            team_damage_totals[team_by_pid[source_id]] += values["total"]

        player_results = []
        for participant_id in sorted(involved):
            detailed_damage = damage_on_dead_targets[participant_id]
            damage_frame_window = _damage_window(
                frame_before,
                frame_after,
                participant_id,
                "totalDamageDoneToChampions",
            )
            physical_damage_window = _damage_window(
                frame_before,
                frame_after,
                participant_id,
                "physicalDamageDoneToChampions",
            )
            magic_damage_window = _damage_window(
                frame_before,
                frame_after,
                participant_id,
                "magicDamageDoneToChampions",
            )
            true_damage_window = _damage_window(
                frame_before,
                frame_after,
                participant_id,
                "trueDamageDoneToChampions",
            )
            participant_team_id = team_by_pid[participant_id]

            fight_kills = sum(event.get("killerId") == participant_id for event in events)
            fight_deaths = sum(event.get("victimId") == participant_id for event in events)
            fight_assists = sum(
                participant_id in (event.get("assistingParticipantIds", []) or [])
                for event in events
            )
            team_dead_target_damage = team_damage_totals[participant_team_id]
            damage_share = (
                detailed_damage["total"] / team_dead_target_damage
                if team_dead_target_damage > 0
                else 0.0
            )

            player_results.append(
                {
                    "participant_id": participant_id,
                    "puuid": puuid_by_pid[participant_id],
                    "player": player_by_pid[participant_id],
                    "champion": champion_by_pid[participant_id],
                    "team": "Allié" if participant_team_id == allied_team_id else "Ennemi",
                    "participation_source": _participation_source(
                        participant_id,
                        event_involved,
                        damage_involved,
                    ),
                    "is_core_participant": participant_id in core_involved,
                    "is_proximity_participant": participant_id in proximity_involved,
                    "was_killer": fight_kills > 0,
                    "was_victim": fight_deaths > 0,
                    "was_assistant": fight_assists > 0,
                    "was_damage_source": participant_id in damage_involved,
                    "fight_kills": fight_kills,
                    "fight_deaths": fight_deaths,
                    "fight_assists": fight_assists,
                    "survived": fight_deaths == 0,
                    "enemies_damaged_count": len(damaged_victims_by_source[participant_id]),
                    "damage_on_dead_targets": detailed_damage["total"],
                    "physical_damage_on_dead_targets": detailed_damage["physical"],
                    "magic_damage_on_dead_targets": detailed_damage["magic"],
                    "true_damage_on_dead_targets": detailed_damage["true"],
                    "damage_share_on_dead_targets": round(damage_share, 4),
                    "damage_window_estimated": damage_frame_window,
                    "damage_frame_window": damage_frame_window,
                    "physical_damage_window_estimated": physical_damage_window,
                    "magic_damage_window_estimated": magic_damage_window,
                    "true_damage_window_estimated": true_damage_window,
                }
            )

        results.append(
            {
                "fight_id": len(results) + 1,
                # Compatibilité: start/end restent les bornes du premier/dernier kill.
                "start_ms": first_kill_ms,
                "end_ms": last_kill_ms,
                "start_minute": round(first_kill_ms / 60_000, 2),
                "end_minute": round(last_kill_ms / 60_000, 2),
                "first_kill_ms": first_kill_ms,
                "last_kill_ms": last_kill_ms,
                "kill_span_ms": last_kill_ms - first_kill_ms,
                "estimation_window_start_ms": frame_before["timestamp"],
                "estimation_window_end_ms": frame_after["timestamp"],
                "kills_allies": allied_kills,
                "kills_enemies": enemy_kills,
                "allied_kills": allied_kills,
                "enemy_kills": enemy_kills,
                "winner": winner,
                "core_allies": core_allies,
                "core_enemies": core_enemies,
                "participants_allies": len(involved_allies),
                "participants_enemies": len(involved_enemies),
                "proximity_allies": len(involved_allies - core_allies_set),
                "proximity_enemies": len(involved_enemies - core_enemies_set),
                "fight_type": f"{core_allies}v{core_enemies}",
                "fight_type_with_proximity": f"{len(involved_allies)}v{len(involved_enemies)}",
                "fight_category": _fight_category(core_allies, core_enemies),
                "is_teamfight": min(core_allies, core_enemies) >= 3,
                "is_outnumbered": is_outnumbered,
                "outnumbered_team": outnumbered_team,
                "won_while_outnumbered": won_while_outnumbered,
                "players": player_results,
            }
        )

    window_counts = Counter(
        (
            fight["estimation_window_start_ms"],
            fight["estimation_window_end_ms"],
        )
        for fight in results
    )
    for fight in results:
        window_key = (
            fight["estimation_window_start_ms"],
            fight["estimation_window_end_ms"],
        )
        fight["shared_window_fight_count"] = window_counts[window_key]
        fight["shared_damage_window"] = window_counts[window_key] > 1

    return results


async def teamfight_damage(
    self: Any,
    max_gap_ms: int = 12_000,
    max_distance: int = 2_000,
    fight_radius: int = 2_000,
    min_players_per_team: int = 1,
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
