"""Détection hybride des ganks.

La position Riot n'est échantillonnée qu'au niveau des frames (en pratique
~1/min), donc elle ne peut pas être la condition principale d'un gank. Ce
module conserve les événements ``CHAMPION_KILL`` exacts et ajoute des tentatives
sans kill lorsqu'un intervalle de frames montre simultanément :

* un delta significatif de dégâts aux champions du jungler ;
* une activité de combat concentrée sur une lane ;
* éventuellement une position du jungler sur cette lane, utilisée comme bonus
  de confiance et non comme prérequis.

Le résultat est un taux de succès *observé* : un passage très bref sans dégâts,
sans kill et invisible aux deux frames adjacentes reste indétectable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd

from .ganks import (
    GamePhase,
    GankAnalysisMixin as LegacyGankAnalysisMixin,
    GankEvent,
    Lane,
    LaneGankStats,
    get_lane_from_position,
)


OUTCOME_SUCCESS = "success"
OUTCOME_TRADE = "trade"
OUTCOME_FAILED = "failed"
OUTCOME_JUNGLER_DEATH = "jungler_death"

SOURCE_EXACT = "exact_event"
SOURCE_SAMPLED = "sampled_combat"
SOURCE_INFERRED = "inferred_combat"

ALGORITHM_VERSION = 2


@dataclass
class HybridGankEvent(GankEvent):
    """Tentative de gank avec provenance et niveau de confiance."""

    gank_id: int = 0
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    outcome: str = OUTCOME_FAILED
    detection_source: str = SOURCE_EXACT
    confidence: float = 1.0

    kills_for: int = 0
    kills_against: int = 0
    jungler_kills: int = 0
    jungler_assists: int = 0
    jungler_deaths: int = 0
    participants_allies: Optional[int] = None
    participants_enemies: Optional[int] = None
    is_teamfight: bool = False

    jungler_damage_delta: int = 0
    lane_activity_delta: int = 0
    position_evidence: str = "none"

    def __post_init__(self) -> None:
        if self.start_ms is None:
            self.start_ms = self.timestamp
        if self.end_ms is None:
            self.end_ms = self.timestamp
        self.confidence = round(max(0.0, min(float(self.confidence), 1.0)), 3)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "gank_id": self.gank_id,
                "start_ms": self.start_ms,
                "end_ms": self.end_ms,
                "outcome": self.outcome,
                "detection_source": self.detection_source,
                "confidence": self.confidence,
                "kills_for": self.kills_for,
                "kills_against": self.kills_against,
                "jungler_kills": self.jungler_kills,
                "jungler_assists": self.jungler_assists,
                "jungler_deaths": self.jungler_deaths,
                "participants_allies": self.participants_allies,
                "participants_enemies": self.participants_enemies,
                "is_teamfight": self.is_teamfight,
                "jungler_damage_delta": self.jungler_damage_delta,
                "lane_activity_delta": self.lane_activity_delta,
                "position_evidence": self.position_evidence,
                "algorithm_version": ALGORITHM_VERSION,
            }
        )
        return data


def _role_to_lane(role: str) -> Optional[Lane]:
    role = str(role or "").upper()
    if role == "TOP":
        return Lane.TOP
    if role in {"MIDDLE", "MID"}:
        return Lane.MID
    if role in {"BOTTOM", "BOT", "UTILITY", "SUPPORT"}:
        return Lane.BOT
    return None


class HybridGankAnalysisMixin(LegacyGankAnalysisMixin):
    """Version 2 de la détection des ganks."""

    EPISODE_GAP_MS = 20_000
    COUNTER_GANK_WINDOW_MS = 15_000
    MAX_FRAME_INTERVAL_MS = 90_000

    MIN_JUNGLER_DAMAGE_DELTA = 120
    MIN_LANE_ACTIVITY_WITH_POSITION = 150
    MIN_LANE_ACTIVITY_INFERRED = 250
    MIN_NORMALIZED_ACTIVITY_INFERRED = 100
    MIN_INFERRED_DOMINANCE = 1.45
    MIN_CONFIDENCE = 0.65

    def _hybrid_frames(self) -> List[Dict[str, Any]]:
        if isinstance(self.data_timeline, list):
            return self.data_timeline
        return self.data_timeline.get("info", {}).get("frames", [])

    def _hybrid_participants(self) -> List[Dict[str, Any]]:
        return self.match_detail.get("info", {}).get("participants", [])

    def _hybrid_team_by_pid(self) -> Dict[int, int]:
        return {
            int(participant["participantId"]): int(participant["teamId"])
            for participant in self._hybrid_participants()
            if participant.get("participantId") is not None
            and participant.get("teamId") is not None
        }

    def _hybrid_lane_participants(self) -> Dict[Lane, List[int]]:
        lanes = {Lane.TOP: [], Lane.MID: [], Lane.BOT: []}
        for participant in self._hybrid_participants():
            lane = _role_to_lane(
                participant.get("teamPosition") or participant.get("individualPosition")
            )
            if lane is not None and participant.get("participantId") is not None:
                lanes[lane].append(int(participant["participantId"]))
        return lanes

    @staticmethod
    def _hybrid_participant_frame(
        frame: Dict[str, Any], participant_id: int
    ) -> Dict[str, Any]:
        participant_frames = frame.get("participantFrames", {})
        return (
            participant_frames.get(
                str(participant_id), participant_frames.get(participant_id, {})
            )
            or {}
        )

    @classmethod
    def _hybrid_champion_damage(
        cls, frame: Dict[str, Any], participant_id: int
    ) -> int:
        participant_frame = cls._hybrid_participant_frame(frame, participant_id)
        return int(
            participant_frame.get("damageStats", {}).get(
                "totalDamageDoneToChampions", 0
            )
            or 0
        )

    @classmethod
    def _hybrid_position_lane(
        cls, frame: Dict[str, Any], participant_id: int
    ) -> Lane:
        position = (
            cls._hybrid_participant_frame(frame, participant_id).get("position", {})
            or {}
        )
        return get_lane_from_position(position.get("x", 0), position.get("y", 0))

    @staticmethod
    def _hybrid_damage_source_ids(event: Dict[str, Any]) -> set[int]:
        source_ids: set[int] = set()
        for damage in event.get("victimDamageReceived", []) or []:
            source_id = damage.get("participantId")
            if source_id is None:
                continue
            total = sum(
                int(damage.get(key, 0) or 0)
                for key in ("physicalDamage", "magicDamage", "trueDamage")
            )
            if total > 0:
                source_ids.add(int(source_id))
        return source_ids

    @classmethod
    def _hybrid_event_participants(cls, event: Dict[str, Any]) -> set[int]:
        involved: set[int] = set()
        for participant_id in (
            event.get("killerId"),
            event.get("victimId"),
            *(event.get("assistingParticipantIds", []) or []),
        ):
            if participant_id:
                involved.add(int(participant_id))
        involved |= cls._hybrid_damage_source_ids(event)
        return involved

    def _hybrid_lane_kill_episodes(
        self,
    ) -> List[tuple[Lane, List[Dict[str, Any]]]]:
        events_by_lane: Dict[Lane, List[Dict[str, Any]]] = {
            Lane.TOP: [],
            Lane.MID: [],
            Lane.BOT: [],
        }
        for frame in self._hybrid_frames():
            for event in frame.get("events", []):
                if event.get("type") != "CHAMPION_KILL":
                    continue
                position = event.get("position", {}) or {}
                lane = get_lane_from_position(
                    position.get("x", 0), position.get("y", 0)
                )
                if lane != Lane.JUNGLE:
                    events_by_lane[lane].append(event)

        episodes: List[tuple[Lane, List[Dict[str, Any]]]] = []
        for lane, lane_events in events_by_lane.items():
            lane_events.sort(key=lambda event: int(event.get("timestamp", 0)))
            current: List[Dict[str, Any]] = []
            for event in lane_events:
                if not current:
                    current = [event]
                    continue
                gap = int(event.get("timestamp", 0)) - int(
                    current[-1].get("timestamp", 0)
                )
                if gap <= self.EPISODE_GAP_MS:
                    current.append(event)
                else:
                    episodes.append((lane, current))
                    current = [event]
            if current:
                episodes.append((lane, current))

        episodes.sort(key=lambda item: int(item[1][0].get("timestamp", 0)))
        return episodes

    def _collect_exact_ganks(
        self,
        jungler_id: int,
        team_id: int,
        enemy_jungler_id: Optional[int],
    ) -> List[HybridGankEvent]:
        team_by_pid = self._hybrid_team_by_pid()
        jungler_champion = (
            (self._get_jungler_info().get(team_id) or {}).get("championName")
            or "Unknown"
        )
        result: List[HybridGankEvent] = []

        for lane, events in self._hybrid_lane_kill_episodes():
            core: set[int] = set()
            for event in events:
                core |= self._hybrid_event_participants(event)

            # La victime jungler est désormais un signal exact de tentative ratée.
            if jungler_id not in core:
                continue

            allies = {pid for pid in core if team_by_pid.get(pid) == team_id}
            enemies = {
                pid
                for pid in core
                if team_by_pid.get(pid) not in {None, team_id}
            }

            # 3v3+ : skirmish/teamfight, pas gank. 3v2/2v3 restent possibles.
            is_teamfight = min(len(allies), len(enemies)) >= 3
            if is_teamfight:
                continue

            kills_for = sum(
                team_by_pid.get(event.get("killerId")) == team_id for event in events
            )
            kills_against = sum(
                event.get("killerId") in team_by_pid
                and team_by_pid[event["killerId"]] != team_id
                for event in events
            )
            jungler_kills = sum(
                event.get("killerId") == jungler_id for event in events
            )
            jungler_deaths = sum(
                event.get("victimId") == jungler_id for event in events
            )
            jungler_assists = sum(
                jungler_id in (event.get("assistingParticipantIds", []) or [])
                for event in events
            )

            if kills_for > 0 and kills_against == 0:
                outcome = OUTCOME_SUCCESS
            elif kills_for > 0 and kills_against > 0:
                outcome = OUTCOME_TRADE
            elif jungler_deaths > 0:
                outcome = OUTCOME_JUNGLER_DEATH
            else:
                outcome = OUTCOME_FAILED

            victim_id = next(
                (
                    int(event.get("victimId"))
                    for event in events
                    if event.get("victimId") in team_by_pid
                    and team_by_pid[event["victimId"]] != team_id
                ),
                int(events[0].get("victimId", 0) or 0),
            )
            start_ms = int(events[0].get("timestamp", 0))
            end_ms = int(events[-1].get("timestamp", start_ms))

            result.append(
                HybridGankEvent(
                    timestamp=start_ms,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    lane=lane,
                    successful=kills_for > 0,
                    outcome=outcome,
                    detection_source=SOURCE_EXACT,
                    confidence=1.0,
                    jungler_participant_id=jungler_id,
                    jungler_champion=jungler_champion,
                    victim_id=victim_id,
                    is_counter_gank=(
                        enemy_jungler_id is not None and enemy_jungler_id in core
                    ),
                    kills_for=kills_for,
                    kills_against=kills_against,
                    jungler_kills=jungler_kills,
                    jungler_assists=jungler_assists,
                    jungler_deaths=jungler_deaths,
                    participants_allies=len(allies),
                    participants_enemies=len(enemies),
                    is_teamfight=False,
                    position_evidence="exact_event",
                )
            )

        return result

    def _hybrid_jungler_has_kill_event_between(
        self, jungler_id: int, start_ms: int, end_ms: int
    ) -> bool:
        """Évite d'attribuer à une lane un delta expliqué par un kill exact ailleurs."""
        for frame in self._hybrid_frames():
            for event in frame.get("events", []):
                if event.get("type") != "CHAMPION_KILL":
                    continue
                timestamp = int(event.get("timestamp", 0))
                if (
                    start_ms < timestamp <= end_ms
                    and jungler_id in self._hybrid_event_participants(event)
                ):
                    return True
        return False

    def _hybrid_lane_activity(
        self,
        before: Dict[str, Any],
        after: Dict[str, Any],
        lane_participants: Dict[Lane, List[int]],
    ) -> tuple[Dict[Lane, int], Dict[Lane, float]]:
        raw: Dict[Lane, int] = {}
        normalized: Dict[Lane, float] = {}
        for lane in (Lane.TOP, Lane.MID, Lane.BOT):
            participant_ids = lane_participants[lane]
            deltas = [
                max(
                    0,
                    self._hybrid_champion_damage(after, participant_id)
                    - self._hybrid_champion_damage(before, participant_id),
                )
                for participant_id in participant_ids
            ]
            raw[lane] = sum(deltas)
            # BOT a quatre laners contre deux TOP/MID : normaliser évite un biais bot.
            normalized[lane] = (
                raw[lane] / len(participant_ids) if participant_ids else 0.0
            )
        return raw, normalized

    @staticmethod
    def _hybrid_position_evidence(
        start_lane: Lane, end_lane: Lane, chosen_lane: Lane
    ) -> str:
        start_match = start_lane == chosen_lane
        end_match = end_lane == chosen_lane
        if start_match and end_match:
            return "both"
        if start_match:
            return "start"
        if end_match:
            return "end"
        return "none"

    def _infer_failed_ganks(
        self,
        jungler_id: int,
        team_id: int,
        exact_ganks: List[HybridGankEvent],
    ) -> List[HybridGankEvent]:
        frames = sorted(
            self._hybrid_frames(), key=lambda frame: int(frame.get("timestamp", 0))
        )
        if len(frames) < 2:
            return []

        lane_participants = self._hybrid_lane_participants()
        jungler_champion = (
            (self._get_jungler_info().get(team_id) or {}).get("championName")
            or "Unknown"
        )
        inferred: List[HybridGankEvent] = []

        for before, after in zip(frames, frames[1:]):
            start_ms = int(before.get("timestamp", 0))
            end_ms = int(after.get("timestamp", 0))
            interval = end_ms - start_ms
            if interval <= 0 or interval > self.MAX_FRAME_INTERVAL_MS:
                continue

            if self._hybrid_jungler_has_kill_event_between(
                jungler_id, start_ms, end_ms
            ):
                continue

            if any(
                gank.start_ms is not None
                and gank.end_ms is not None
                and gank.start_ms <= end_ms
                and gank.end_ms >= start_ms
                for gank in exact_ganks
            ):
                continue

            jungler_damage_delta = max(
                0,
                self._hybrid_champion_damage(after, jungler_id)
                - self._hybrid_champion_damage(before, jungler_id),
            )
            if jungler_damage_delta < self.MIN_JUNGLER_DAMAGE_DELTA:
                continue

            raw_activity, normalized_activity = self._hybrid_lane_activity(
                before, after, lane_participants
            )
            start_lane = self._hybrid_position_lane(before, jungler_id)
            end_lane = self._hybrid_position_lane(after, jungler_id)
            sampled_lanes = [
                lane for lane in (start_lane, end_lane) if lane != Lane.JUNGLE
            ]

            chosen_lane: Optional[Lane] = None
            detection_source = SOURCE_INFERRED

            if sampled_lanes:
                chosen_lane = max(
                    set(sampled_lanes),
                    key=lambda lane: normalized_activity.get(lane, 0.0),
                )
                if (
                    raw_activity.get(chosen_lane, 0)
                    < self.MIN_LANE_ACTIVITY_WITH_POSITION
                ):
                    continue
                detection_source = SOURCE_SAMPLED
            else:
                ranked_lanes = sorted(
                    (Lane.TOP, Lane.MID, Lane.BOT),
                    key=lambda lane: normalized_activity.get(lane, 0.0),
                    reverse=True,
                )
                chosen_lane = ranked_lanes[0]
                best = normalized_activity[chosen_lane]
                second = normalized_activity[ranked_lanes[1]]
                raw_best = raw_activity[chosen_lane]
                dominance = best / max(second, 1.0)
                if (
                    raw_best < self.MIN_LANE_ACTIVITY_INFERRED
                    or best < self.MIN_NORMALIZED_ACTIVITY_INFERRED
                    or dominance < self.MIN_INFERRED_DOMINANCE
                ):
                    continue

            evidence = self._hybrid_position_evidence(
                start_lane, end_lane, chosen_lane
            )
            confidence = 0.45
            if jungler_damage_delta >= 250:
                confidence += 0.10
            if jungler_damage_delta >= 450:
                confidence += 0.10
            if evidence == "both":
                confidence += 0.30
            elif evidence in {"start", "end"}:
                confidence += 0.22

            lane_norm = normalized_activity[chosen_lane]
            if lane_norm >= 150:
                confidence += 0.10
            elif lane_norm >= 100:
                confidence += 0.05

            if detection_source == SOURCE_INFERRED:
                other_norms = [
                    normalized_activity[lane]
                    for lane in (Lane.TOP, Lane.MID, Lane.BOT)
                    if lane != chosen_lane
                ]
                dominance = lane_norm / max(max(other_norms), 1.0)
                confidence += 0.15 if dominance >= 2.0 else 0.10

            confidence = min(confidence, 0.95)
            if confidence < self.MIN_CONFIDENCE:
                continue

            inferred.append(
                HybridGankEvent(
                    timestamp=(start_ms + end_ms) // 2,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    lane=chosen_lane,
                    successful=False,
                    outcome=OUTCOME_FAILED,
                    detection_source=detection_source,
                    confidence=confidence,
                    jungler_participant_id=jungler_id,
                    jungler_champion=jungler_champion,
                    jungler_damage_delta=jungler_damage_delta,
                    lane_activity_delta=raw_activity[chosen_lane],
                    position_evidence=evidence,
                )
            )

        return self._merge_adjacent_inferred_ganks(inferred)

    @staticmethod
    def _merge_adjacent_inferred_ganks(
        ganks: List[HybridGankEvent],
    ) -> List[HybridGankEvent]:
        """Fusionne les intervalles de frames contigus sur une même lane."""
        if not ganks:
            return []

        ordered = sorted(
            ganks, key=lambda gank: (gank.start_ms or 0, gank.lane.value)
        )
        merged = [ordered[0]]
        for current in ordered[1:]:
            previous = merged[-1]
            if (
                current.lane == previous.lane
                and previous.end_ms is not None
                and current.start_ms is not None
                and current.start_ms <= previous.end_ms
            ):
                previous.end_ms = max(
                    previous.end_ms, current.end_ms or previous.end_ms
                )
                previous.timestamp = (
                    (previous.start_ms or 0) + (previous.end_ms or 0)
                ) // 2
                previous.jungler_damage_delta += current.jungler_damage_delta
                previous.lane_activity_delta += current.lane_activity_delta
                previous.confidence = max(previous.confidence, current.confidence)
                if previous.position_evidence == "none":
                    previous.position_evidence = current.position_evidence
                if current.detection_source == SOURCE_SAMPLED:
                    previous.detection_source = SOURCE_SAMPLED
            else:
                merged.append(current)
        return merged

    def _collect_observed_ganks(
        self,
        jungler_id: int,
        team_id: int,
        enemy_jungler_id: Optional[int],
    ) -> List[HybridGankEvent]:
        exact = self._collect_exact_ganks(jungler_id, team_id, enemy_jungler_id)
        inferred = self._infer_failed_ganks(jungler_id, team_id, exact)
        ganks = sorted(
            exact + inferred, key=lambda gank: (gank.timestamp, gank.lane.value)
        )
        for index, gank in enumerate(ganks, start=1):
            gank.gank_id = index
        return ganks

    # Même nom que l'ancienne méthode pour préserver les éventuels appels externes.
    def _collect_lane_kills_with_jungler(
        self, jungler_id: int, team_id: int
    ) -> List[HybridGankEvent]:
        enemy_team_id = 200 if team_id == 100 else 100
        enemy_jungler = self._get_jungler_info().get(enemy_team_id) or {}
        return self._collect_observed_ganks(
            jungler_id, team_id, enemy_jungler.get("participantId")
        )

    @staticmethod
    def _hybrid_detection_counts(
        ganks: List[HybridGankEvent],
    ) -> Dict[str, int]:
        exact = sum(gank.detection_source == SOURCE_EXACT for gank in ganks)
        return {
            "exact": exact,
            "inferred": len(ganks) - exact,
            "failed": sum(not gank.successful for gank in ganks),
            "high_confidence": sum(gank.confidence >= 0.80 for gank in ganks),
        }

    @staticmethod
    def _hybrid_overlap_with_margin(
        first: HybridGankEvent,
        second: HybridGankEvent,
        margin_ms: int,
    ) -> bool:
        first_start = first.start_ms if first.start_ms is not None else first.timestamp
        first_end = first.end_ms if first.end_ms is not None else first.timestamp
        second_start = (
            second.start_ms if second.start_ms is not None else second.timestamp
        )
        second_end = second.end_ms if second.end_ms is not None else second.timestamp
        return (
            first_start <= second_end + margin_ms
            and second_start <= first_end + margin_ms
        )

    def _compute_timing_insights(
        self,
        ally_ganks: List[HybridGankEvent],
        enemy_ganks: List[HybridGankEvent],
    ) -> Dict[str, Any]:
        timing = super()._compute_timing_insights(ally_ganks, enemy_ganks)
        for side, ganks in (("ally", ally_ganks), ("enemy", enemy_ganks)):
            if not ganks or not timing[side].get("first_gank"):
                continue
            first = min(ganks, key=lambda gank: gank.timestamp)
            timing[side]["first_gank"].update(
                {
                    "outcome": first.outcome,
                    "detection_source": first.detection_source,
                    "confidence": first.confidence,
                }
            )
        return timing

    async def analyze_ganks(self, team_id: int = None) -> Dict[str, Any]:
        """Analyse les tentatives observées pour les deux junglers."""
        if team_id is None:
            team_id = 100 if self.thisId < 5 else 200
        enemy_team_id = 200 if team_id == 100 else 100

        junglers = self._get_jungler_info()
        ally_jgl = junglers.get(team_id)
        enemy_jgl = junglers.get(enemy_team_id)
        if not ally_jgl or not enemy_jgl:
            self.gank_stats = {"error": "Junglers non trouvés"}
            return self.gank_stats

        self.ally_ganks = self._collect_observed_ganks(
            ally_jgl["participantId"], team_id, enemy_jgl["participantId"]
        )
        self.enemy_ganks = self._collect_observed_ganks(
            enemy_jgl["participantId"], enemy_team_id, ally_jgl["participantId"]
        )

        # Counter-gank = même lane et fenêtres qui se recouvrent (avec 15s de marge).
        for ally_gank in self.ally_ganks:
            for enemy_gank in self.enemy_ganks:
                if (
                    ally_gank.lane == enemy_gank.lane
                    and self._hybrid_overlap_with_margin(
                        ally_gank, enemy_gank, self.COUNTER_GANK_WINDOW_MS
                    )
                ):
                    ally_gank.is_counter_gank = True
                    enemy_gank.is_counter_gank = True

        self.lane_gank_stats = {
            Lane.TOP: LaneGankStats(),
            Lane.MID: LaneGankStats(),
            Lane.BOT: LaneGankStats(),
        }
        for gank in self.ally_ganks:
            lane_stats = self.lane_gank_stats[gank.lane]
            lane_stats.ganks_made += 1
            lane_stats.ganks_made_by_phase[gank.game_phase] += 1
            if gank.successful:
                lane_stats.ganks_made_successful += 1

        for gank in self.enemy_ganks:
            lane_stats = self.lane_gank_stats[gank.lane]
            lane_stats.ganks_received += 1
            lane_stats.ganks_received_by_phase[gank.game_phase] += 1
            if gank.successful:
                lane_stats.ganks_received_successful += 1

        total_made = len(self.ally_ganks)
        total_received = len(self.enemy_ganks)
        successful_made = sum(gank.successful for gank in self.ally_ganks)
        successful_received = sum(gank.successful for gank in self.enemy_ganks)
        ally_detection = self._hybrid_detection_counts(self.ally_ganks)
        enemy_detection = self._hybrid_detection_counts(self.enemy_ganks)
        counter_ganks = sum(gank.is_counter_gank for gank in self.ally_ganks)

        timing = self._compute_timing_insights(self.ally_ganks, self.enemy_ganks)
        self.ally_jungler_style = timing["ally"]["style"]
        self.enemy_jungler_style = timing["enemy"]["style"]

        observed_success_rate = (
            round(successful_made / total_made, 2) if total_made else 0
        )
        observed_received_rate = (
            round(successful_received / total_received, 2) if total_received else 0
        )

        self.gank_stats = {
            "algorithm_version": ALGORITHM_VERSION,
            "team_id": team_id,
            "ally_jungler": ally_jgl,
            "enemy_jungler": enemy_jgl,
            "summary": {
                "total_ganks_made": total_made,
                "total_ganks_received": total_received,
                "differential": total_made - total_received,
                "successful_made": successful_made,
                "successful_received": successful_received,
                # Anciens noms conservés pour ne pas casser les usages existants.
                "success_rate_made": observed_success_rate,
                "death_rate_received": observed_received_rate,
                "observed_success_rate_made": observed_success_rate,
                "observed_death_rate_received": observed_received_rate,
                "failed_made": ally_detection["failed"],
                "failed_received": enemy_detection["failed"],
                "exact_attempts_made": ally_detection["exact"],
                "exact_attempts_received": enemy_detection["exact"],
                "inferred_attempts_made": ally_detection["inferred"],
                "inferred_attempts_received": enemy_detection["inferred"],
                "high_confidence_made": ally_detection["high_confidence"],
                "high_confidence_received": enemy_detection["high_confidence"],
                "counter_ganks": counter_ganks,
            },
            "by_lane": {
                lane.value: self.lane_gank_stats[lane].to_dict()
                for lane in (Lane.TOP, Lane.MID, Lane.BOT)
            },
            "timing": timing,
            "insights": {
                "most_ganked_by_ally": (
                    max(
                        (Lane.TOP, Lane.MID, Lane.BOT),
                        key=lambda lane: self.lane_gank_stats[lane].ganks_made,
                    ).value
                    if total_made
                    else None
                ),
                "most_targeted_by_enemy": (
                    max(
                        (Lane.TOP, Lane.MID, Lane.BOT),
                        key=lambda lane: self.lane_gank_stats[lane].ganks_received,
                    ).value
                    if total_received
                    else None
                ),
                "jungle_dominance": (
                    "ally"
                    if total_made > total_received
                    else "enemy"
                    if total_received > total_made
                    else "even"
                ),
                "ally_style": self.ally_jungler_style,
                "enemy_style": self.enemy_jungler_style,
            },
            "events": {
                "ally": [gank.to_dict() for gank in self.ally_ganks],
                "enemy": [gank.to_dict() for gank in self.enemy_ganks],
            },
        }
        return self.gank_stats

    async def _save_gank_summary(self) -> None:
        """Sauvegarde toutes les colonnes, y compris lors d'un recalcul."""
        stats = self.gank_stats
        summary = stats["summary"]
        timing = stats["timing"]
        ally_first = timing["ally"].get("first_gank") or {}
        enemy_first = timing["enemy"].get("first_gank") or {}

        sql = """
        INSERT INTO match_gank_summary (
            match_id, team_id,
            ally_jungler_id, ally_jungler_champion, ally_jungler_name,
            enemy_jungler_id, enemy_jungler_champion, enemy_jungler_name,
            total_ganks_made, total_ganks_received, differential,
            successful_made, successful_received,
            success_rate_made, death_rate_received, counter_ganks,
            most_ganked_by_ally, most_targeted_by_enemy,
            jungle_dominance, ally_style, enemy_style,
            ally_first_gank_time, ally_first_gank_lane, ally_first_gank_success,
            enemy_first_gank_time, enemy_first_gank_lane, enemy_first_gank_success,
            first_to_gank, early_winner,
            failed_made, failed_received,
            exact_attempts_made, exact_attempts_received,
            inferred_attempts_made, inferred_attempts_received,
            high_confidence_made, high_confidence_received,
            observed_success_rate_made, observed_death_rate_received,
            algorithm_version
        ) VALUES (
            :match_id, :team_id,
            :ally_jungler_id, :ally_jungler_champion, :ally_jungler_name,
            :enemy_jungler_id, :enemy_jungler_champion, :enemy_jungler_name,
            :total_ganks_made, :total_ganks_received, :differential,
            :successful_made, :successful_received,
            :success_rate_made, :death_rate_received, :counter_ganks,
            :most_ganked_by_ally, :most_targeted_by_enemy,
            :jungle_dominance, :ally_style, :enemy_style,
            :ally_first_gank_time, :ally_first_gank_lane, :ally_first_gank_success,
            :enemy_first_gank_time, :enemy_first_gank_lane, :enemy_first_gank_success,
            :first_to_gank, :early_winner,
            :failed_made, :failed_received,
            :exact_attempts_made, :exact_attempts_received,
            :inferred_attempts_made, :inferred_attempts_received,
            :high_confidence_made, :high_confidence_received,
            :observed_success_rate_made, :observed_death_rate_received,
            :algorithm_version
        )
        ON CONFLICT (match_id, team_id) DO UPDATE SET
            ally_jungler_id = EXCLUDED.ally_jungler_id,
            ally_jungler_champion = EXCLUDED.ally_jungler_champion,
            ally_jungler_name = EXCLUDED.ally_jungler_name,
            enemy_jungler_id = EXCLUDED.enemy_jungler_id,
            enemy_jungler_champion = EXCLUDED.enemy_jungler_champion,
            enemy_jungler_name = EXCLUDED.enemy_jungler_name,
            total_ganks_made = EXCLUDED.total_ganks_made,
            total_ganks_received = EXCLUDED.total_ganks_received,
            differential = EXCLUDED.differential,
            successful_made = EXCLUDED.successful_made,
            successful_received = EXCLUDED.successful_received,
            success_rate_made = EXCLUDED.success_rate_made,
            death_rate_received = EXCLUDED.death_rate_received,
            counter_ganks = EXCLUDED.counter_ganks,
            most_ganked_by_ally = EXCLUDED.most_ganked_by_ally,
            most_targeted_by_enemy = EXCLUDED.most_targeted_by_enemy,
            jungle_dominance = EXCLUDED.jungle_dominance,
            ally_style = EXCLUDED.ally_style,
            enemy_style = EXCLUDED.enemy_style,
            ally_first_gank_time = EXCLUDED.ally_first_gank_time,
            ally_first_gank_lane = EXCLUDED.ally_first_gank_lane,
            ally_first_gank_success = EXCLUDED.ally_first_gank_success,
            enemy_first_gank_time = EXCLUDED.enemy_first_gank_time,
            enemy_first_gank_lane = EXCLUDED.enemy_first_gank_lane,
            enemy_first_gank_success = EXCLUDED.enemy_first_gank_success,
            first_to_gank = EXCLUDED.first_to_gank,
            early_winner = EXCLUDED.early_winner,
            failed_made = EXCLUDED.failed_made,
            failed_received = EXCLUDED.failed_received,
            exact_attempts_made = EXCLUDED.exact_attempts_made,
            exact_attempts_received = EXCLUDED.exact_attempts_received,
            inferred_attempts_made = EXCLUDED.inferred_attempts_made,
            inferred_attempts_received = EXCLUDED.inferred_attempts_received,
            high_confidence_made = EXCLUDED.high_confidence_made,
            high_confidence_received = EXCLUDED.high_confidence_received,
            observed_success_rate_made = EXCLUDED.observed_success_rate_made,
            observed_death_rate_received = EXCLUDED.observed_death_rate_received,
            algorithm_version = EXCLUDED.algorithm_version
        """

        params = {
            "match_id": self.last_match,
            "team_id": stats["team_id"],
            "ally_jungler_id": stats["ally_jungler"]["participantId"],
            "ally_jungler_champion": stats["ally_jungler"]["championName"],
            "ally_jungler_name": stats["ally_jungler"]["summonerName"],
            "enemy_jungler_id": stats["enemy_jungler"]["participantId"],
            "enemy_jungler_champion": stats["enemy_jungler"]["championName"],
            "enemy_jungler_name": stats["enemy_jungler"]["summonerName"],
            **summary,
            "most_ganked_by_ally": stats["insights"]["most_ganked_by_ally"],
            "most_targeted_by_enemy": stats["insights"]["most_targeted_by_enemy"],
            "jungle_dominance": stats["insights"]["jungle_dominance"],
            "ally_style": stats["insights"]["ally_style"],
            "enemy_style": stats["insights"]["enemy_style"],
            "ally_first_gank_time": ally_first.get("timestamp"),
            "ally_first_gank_lane": ally_first.get("lane"),
            "ally_first_gank_success": ally_first.get("successful"),
            "enemy_first_gank_time": enemy_first.get("timestamp"),
            "enemy_first_gank_lane": enemy_first.get("lane"),
            "enemy_first_gank_success": enemy_first.get("successful"),
            "first_to_gank": timing["comparison"]["first_to_gank"],
            "early_winner": timing["comparison"]["early_winner"],
            "algorithm_version": ALGORITHM_VERSION,
        }
        requete_perso_bdd(sql, params)

    async def _save_gank_events(self) -> None:
        """Remplace les anciens événements du match par les tentatives V2."""
        team_id = self.gank_stats["team_id"]
        enemy_team_id = 200 if team_id == 100 else 100

        requete_perso_bdd(
            "DELETE FROM match_gank_events WHERE match_id = :match_id",
            {"match_id": self.last_match},
        )

        sql = """
        INSERT INTO match_gank_events (
            match_id, team_id, gank_id,
            timestamp_ms, timestamp_formatted, start_ms, end_ms,
            game_phase, lane, jungler_id, jungler_champion,
            successful, outcome, detection_source, confidence,
            is_counter_gank, victim_id,
            kills_for, kills_against,
            jungler_kills, jungler_assists, jungler_deaths,
            participants_allies, participants_enemies, is_teamfight,
            jungler_damage_delta, lane_activity_delta, position_evidence,
            algorithm_version
        ) VALUES (
            :match_id, :team_id, :gank_id,
            :timestamp_ms, :timestamp_formatted, :start_ms, :end_ms,
            :game_phase, :lane, :jungler_id, :jungler_champion,
            :successful, :outcome, :detection_source, :confidence,
            :is_counter_gank, :victim_id,
            :kills_for, :kills_against,
            :jungler_kills, :jungler_assists, :jungler_deaths,
            :participants_allies, :participants_enemies, :is_teamfight,
            :jungler_damage_delta, :lane_activity_delta, :position_evidence,
            :algorithm_version
        )
        """

        def save(team: int, gank: HybridGankEvent) -> None:
            requete_perso_bdd(
                sql,
                {
                    "match_id": self.last_match,
                    "team_id": team,
                    "gank_id": gank.gank_id,
                    "timestamp_ms": gank.timestamp,
                    "timestamp_formatted": gank.timestamp_formatted,
                    "start_ms": gank.start_ms,
                    "end_ms": gank.end_ms,
                    "game_phase": gank.game_phase.value,
                    "lane": gank.lane.value,
                    "jungler_id": gank.jungler_participant_id,
                    "jungler_champion": gank.jungler_champion,
                    "successful": gank.successful,
                    "outcome": gank.outcome,
                    "detection_source": gank.detection_source,
                    "confidence": gank.confidence,
                    "is_counter_gank": gank.is_counter_gank,
                    "victim_id": gank.victim_id,
                    "kills_for": gank.kills_for,
                    "kills_against": gank.kills_against,
                    "jungler_kills": gank.jungler_kills,
                    "jungler_assists": gank.jungler_assists,
                    "jungler_deaths": gank.jungler_deaths,
                    "participants_allies": gank.participants_allies,
                    "participants_enemies": gank.participants_enemies,
                    "is_teamfight": gank.is_teamfight,
                    "jungler_damage_delta": gank.jungler_damage_delta,
                    "lane_activity_delta": gank.lane_activity_delta,
                    "position_evidence": gank.position_evidence,
                    "algorithm_version": ALGORITHM_VERSION,
                },
            )

        for gank in self.ally_ganks:
            save(team_id, gank)
        for gank in self.enemy_ganks:
            save(enemy_team_id, gank)

    @staticmethod
    def get_jungler_aggregated_stats(
        jungler_name: str, limit: int = 20
    ) -> Dict[str, Any]:
        sql = """
        SELECT
            ally_jungler_champion,
            COUNT(*) AS games,
            AVG(total_ganks_made) AS avg_ganks,
            AVG(COALESCE(observed_success_rate_made, success_rate_made)) AS avg_success_rate,
            AVG(differential) AS avg_differential,
            AVG(COALESCE(inferred_attempts_made, 0)) AS avg_inferred_attempts,
            SUM(CASE WHEN jungle_dominance = 'ally' THEN 1 ELSE 0 END) AS games_dominant
        FROM match_gank_summary
        WHERE ally_jungler_name = :jungler_name
        GROUP BY ally_jungler_champion
        ORDER BY games DESC
        LIMIT :limit
        """
        result = lire_bdd_perso(
            sql,
            format="dict",
            params={"jungler_name": jungler_name, "limit": limit},
        )
        return result if result else {}


def install_hybrid_ganks(match_class: type[Any]) -> None:
    """Installe la V2 sur ``MatchLol`` sans dupliquer toute la classe principale."""

    # Les méthodes non redéfinies (save_gank_data, stats lane/phase, lecteurs BDD)
    # continuent de venir du mixin historique. Celles-ci constituent le cœur V2.
    for name, value in HybridGankAnalysisMixin.__dict__.items():
        if name.startswith("__"):
            continue
        if name.isupper() or callable(value) or isinstance(value, (staticmethod, classmethod)):
            setattr(match_class, name, value)
