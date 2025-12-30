"""
Mixin d'analyse des ganks pour MatchLol.

Analyse la pression jungle en détectant les ganks effectués et subis
à partir des données timeline.

Usage dans MatchLol:
    class MatchLol(GankAnalysisMixin, ScoringMixin, ...):
        ...
    
    # Après avoir récupéré la timeline:
    await self.analyze_ganks()
    
    # Accès aux données:
    self.gank_stats           # Stats complètes de ganks
    self.ally_jungler_style   # Style du jungler allié
    self.gank_differential    # Différentiel de ganks par lane
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd


# =============================================================================
# ENUMS ET DATACLASSES
# =============================================================================

class Lane(Enum):
    TOP = "top"
    MID = "mid"
    BOT = "bot"
    JUNGLE = "jungle"


class GamePhase(Enum):
    EARLY = "early"      # 0-14 min
    MID = "mid"          # 14-30 min
    LATE = "late"        # 30+ min


# Seuils en millisecondes
PHASE_THRESHOLDS = {
    GamePhase.EARLY: (0, 14 * 60 * 1000),                    # 0-14 min
    GamePhase.MID: (14 * 60 * 1000, 30 * 60 * 1000),         # 14-30 min
    GamePhase.LATE: (30 * 60 * 1000, float('inf'))           # 30+ min
}


@dataclass
class GankEvent:
    """Représente un événement de gank."""
    timestamp: int
    lane: Lane
    successful: bool
    jungler_participant_id: int
    victim_ids: List[int] = field(default_factory=list)
    is_counter_gank: bool = False
    
    @property
    def game_phase(self) -> GamePhase:
        for phase, (start, end) in PHASE_THRESHOLDS.items():
            if start <= self.timestamp < end:
                return phase
        return GamePhase.LATE
    
    @property
    def timestamp_formatted(self) -> str:
        minutes = self.timestamp // 60000
        seconds = (self.timestamp % 60000) // 1000
        return f"{minutes}:{seconds:02d}"
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "timestamp_formatted": self.timestamp_formatted,
            "game_phase": self.game_phase.value,
            "lane": self.lane.value,
            "successful": self.successful,
            "is_counter_gank": self.is_counter_gank,
            "victims": self.victim_ids
        }


@dataclass
class LaneGankStats:
    """Statistiques de ganks pour une lane."""
    ganks_made: int = 0
    ganks_made_successful: int = 0
    ganks_received: int = 0
    ganks_received_successful: int = 0
    
    @property
    def gank_differential(self) -> int:
        return self.ganks_made - self.ganks_received
    
    @property
    def success_rate_made(self) -> float:
        return self.ganks_made_successful / self.ganks_made if self.ganks_made > 0 else 0
    
    @property
    def death_rate_received(self) -> float:
        return self.ganks_received_successful / self.ganks_received if self.ganks_received > 0 else 0
    
    def to_dict(self) -> Dict:
        return {
            "ganks_made": self.ganks_made,
            "ganks_made_successful": self.ganks_made_successful,
            "ganks_received": self.ganks_received,
            "ganks_received_successful": self.ganks_received_successful,
            "differential": self.gank_differential,
            "success_rate_made": round(self.success_rate_made, 2),
            "death_rate_received": round(self.death_rate_received, 2)
        }


@dataclass
class PhaseGankStats:
    """Stats de gank pour une phase de jeu spécifique."""
    total: int = 0
    successful: int = 0
    by_lane: Dict[Lane, int] = field(default_factory=lambda: {Lane.TOP: 0, Lane.MID: 0, Lane.BOT: 0})
    
    @property
    def success_rate(self) -> float:
        return self.successful / self.total if self.total > 0 else 0
    
    def to_dict(self) -> Dict:
        return {
            "total": self.total,
            "successful": self.successful,
            "success_rate": round(self.success_rate, 2),
            "by_lane": {l.value: c for l, c in self.by_lane.items()}
        }


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def get_map_zone(x: int, y: int) -> Lane:
    """
    Détermine la zone de la map basée sur les coordonnées.
    Map SR: environ 0-15000 sur chaque axe.
    """
    nx = x / 15000
    ny = y / 15000
    
    dist_to_mid = abs(ny - nx)
    lane_width = 0.15
    
    # Mid lane - corridor diagonal
    if dist_to_mid < lane_width and 0.2 < nx < 0.8:
        return Lane.MID
    
    # Top lane - bord supérieur et gauche
    if (ny > 0.75 and nx < 0.5) or (nx < 0.25 and ny > 0.5):
        return Lane.TOP
    
    # Bot lane - bord inférieur et droit
    if (ny < 0.25 and nx > 0.5) or (nx > 0.75 and ny < 0.5):
        return Lane.BOT
    
    return Lane.JUNGLE


def get_jungler_style(phase_stats: Dict[GamePhase, PhaseGankStats]) -> str:
    """
    Identifie le style de jeu du jungler basé sur la distribution temporelle des ganks.
    
    Returns:
        - "early_aggro": Focus early game agressif (50%+ des ganks en early)
        - "balanced": Répartition équilibrée entre les phases
        - "mid_focused": Focus sur le mid game
        - "late_scaler": Peu de ganks early, style farming/scaling
        - "passive": Très peu de ganks
    """
    early = phase_stats[GamePhase.EARLY].total
    mid = phase_stats[GamePhase.MID].total
    late = phase_stats[GamePhase.LATE].total
    total = early + mid + late
    
    if total == 0:
        return "passive"
    
    early_ratio = early / total
    mid_ratio = mid / total
    
    if early_ratio >= 0.5:
        return "early_aggro"
    elif early_ratio >= 0.3 and mid_ratio >= 0.4:
        return "balanced"
    elif mid_ratio >= 0.5:
        return "mid_focused"
    else:
        return "late_scaler"


# =============================================================================
# MIXIN POUR MATCHLOL
# =============================================================================

class GankAnalysisMixin:
    """
    Mixin pour analyser les ganks dans MatchLol.
    
    Requiert que la classe MatchLol ait:
    - self.match_detail: Données du match
    - self.data_timeline: Données timeline (à récupérer si non présent)
    - self.thisId: Index du joueur principal (0-9)
    """
    
    # Constantes de détection
    GANK_COOLDOWN_MS = 30000       # 30 secondes entre deux ganks sur la même lane
    GANK_MAX_DURATION_MS = 20000   # Durée max d'un gank (sinon c'est un "hold")
    GANK_SUCCESS_WINDOW_MS = 15000 # Fenêtre pour détecter un kill après entrée sur lane
    COUNTER_GANK_WINDOW_MS = 15000 # Fenêtre pour détecter un counter-gank
    
    def _get_team_participants_for_ganks(self) -> Dict[int, Dict]:
        """Retourne les participants par équipe avec leurs rôles."""
        participants = self.match_detail.get("info", {}).get("participants", [])
        
        teams = {100: {}, 200: {}}
        
        for p in participants:
            team_id = p.get("teamId")
            role = p.get("teamPosition") or p.get("individualPosition")
            participant_id = p.get("participantId")
            
            teams[team_id][role] = {
                "participantId": participant_id,
                "championName": p.get("championName"),
                "summonerName": p.get("summonerName", p.get("riotIdGameName", "Unknown"))
            }
            teams[team_id][participant_id] = role
        
        return teams
    
    def _collect_kill_events(self) -> List[Dict]:
        """Collecte tous les events de kills depuis la timeline."""
        frames = self.data_timeline.get("info", {}).get("frames", [])
        kill_events = []
        
        for frame in frames:
            for event in frame.get("events", []):
                if event.get("type") == "CHAMPION_KILL":
                    kill_events.append({
                        "timestamp": event.get("timestamp"),
                        "position": event.get("position", {}),
                        "killerId": event.get("killerId"),
                        "victimId": event.get("victimId"),
                        "assistingParticipantIds": event.get("assistingParticipantIds", [])
                    })
        
        return kill_events
    
    def _detect_ganks_for_jungler(
        self,
        jungler_participant_id: int,
        kill_events: List[Dict]
    ) -> List[GankEvent]:
        """Détecte les ganks d'un jungler spécifique."""
        frames = self.data_timeline.get("info", {}).get("frames", [])
        ganks = []
        
        previous_zone = Lane.JUNGLE
        lane_entry_time = None
        current_lane = None
        
        last_gank_time = {Lane.TOP: -60000, Lane.MID: -60000, Lane.BOT: -60000}
        
        for frame in frames:
            timestamp = frame.get("timestamp", 0)
            participant_frames = frame.get("participantFrames", {})
            
            jungler_frame = participant_frames.get(str(jungler_participant_id))
            if not jungler_frame:
                continue
            
            position = jungler_frame.get("position", {})
            x, y = position.get("x", 0), position.get("y", 0)
            
            current_zone = get_map_zone(x, y)
            
            # Détection d'entrée sur une lane depuis la jungle
            if previous_zone == Lane.JUNGLE and current_zone in [Lane.TOP, Lane.MID, Lane.BOT]:
                if timestamp - last_gank_time[current_zone] > self.GANK_COOLDOWN_MS:
                    lane_entry_time = timestamp
                    current_lane = current_zone
            
            # Gank terminé ?
            if lane_entry_time is not None and current_lane is not None:
                time_on_lane = timestamp - lane_entry_time
                
                if current_zone == Lane.JUNGLE or time_on_lane > self.GANK_MAX_DURATION_MS:
                    # Vérifier si gank réussi
                    successful = False
                    victim_ids = []
                    
                    for kill_event in kill_events:
                        kill_time = kill_event["timestamp"]
                        if lane_entry_time <= kill_time <= lane_entry_time + self.GANK_SUCCESS_WINDOW_MS:
                            kill_pos = kill_event["position"]
                            kill_zone = get_map_zone(kill_pos.get("x", 0), kill_pos.get("y", 0))
                            
                            if kill_zone == current_lane:
                                if (kill_event["killerId"] == jungler_participant_id or
                                    jungler_participant_id in kill_event["assistingParticipantIds"]):
                                    successful = True
                                    victim_ids.append(kill_event["victimId"])
                    
                    gank = GankEvent(
                        timestamp=lane_entry_time,
                        lane=current_lane,
                        successful=successful,
                        jungler_participant_id=jungler_participant_id,
                        victim_ids=victim_ids
                    )
                    ganks.append(gank)
                    
                    last_gank_time[current_lane] = lane_entry_time
                    lane_entry_time = None
                    current_lane = None
            
            previous_zone = current_zone
        
        return ganks
    
    def _analyze_gank_timing(self, ganks: List[GankEvent]) -> Dict[GamePhase, PhaseGankStats]:
        """Analyse la distribution temporelle des ganks par phase de jeu."""
        phase_stats = {
            GamePhase.EARLY: PhaseGankStats(),
            GamePhase.MID: PhaseGankStats(),
            GamePhase.LATE: PhaseGankStats()
        }
        
        for gank in ganks:
            phase = gank.game_phase
            phase_stats[phase].total += 1
            if gank.successful:
                phase_stats[phase].successful += 1
            phase_stats[phase].by_lane[gank.lane] += 1
        
        return phase_stats
    
    def _get_timing_insights(
        self,
        ally_ganks: List[GankEvent],
        enemy_ganks: List[GankEvent]
    ) -> Dict:
        """Génère des insights sur les patterns de timing des ganks."""
        ally_timing = self._analyze_gank_timing(ally_ganks)
        enemy_timing = self._analyze_gank_timing(enemy_ganks)
        
        # Premier gank de chaque jungler
        first_ally_gank = min(ally_ganks, key=lambda g: g.timestamp) if ally_ganks else None
        first_enemy_gank = min(enemy_ganks, key=lambda g: g.timestamp) if enemy_ganks else None
        
        # Temps moyen entre les ganks
        def avg_time_between_ganks(ganks: List[GankEvent]) -> Optional[float]:
            if len(ganks) < 2:
                return None
            sorted_ganks = sorted(ganks, key=lambda g: g.timestamp)
            intervals = [sorted_ganks[i+1].timestamp - sorted_ganks[i].timestamp
                        for i in range(len(sorted_ganks) - 1)]
            return sum(intervals) / len(intervals) / 1000  # en secondes
        
        # Pic d'activité (fenêtre de 5 min avec le plus de ganks)
        def find_peak_activity(ganks: List[GankEvent], window_ms: int = 5 * 60 * 1000) -> Optional[Dict]:
            if not ganks:
                return None
            
            max_count = 0
            peak_start = 0
            
            for gank in ganks:
                count = sum(1 for g in ganks if gank.timestamp <= g.timestamp < gank.timestamp + window_ms)
                if count > max_count:
                    max_count = count
                    peak_start = gank.timestamp
            
            return {
                "start": peak_start,
                "start_formatted": f"{peak_start // 60000}:{(peak_start % 60000) // 1000:02d}",
                "end_formatted": f"{(peak_start + window_ms) // 60000}:{((peak_start + window_ms) % 60000) // 1000:02d}",
                "count": max_count
            }
        
        return {
            "ally": {
                "style": get_jungler_style(ally_timing),
                "first_gank": {
                    "timestamp": first_ally_gank.timestamp,
                    "timestamp_formatted": first_ally_gank.timestamp_formatted,
                    "lane": first_ally_gank.lane.value,
                    "successful": first_ally_gank.successful
                } if first_ally_gank else None,
                "avg_time_between_ganks": avg_time_between_ganks(ally_ganks),
                "peak_activity": find_peak_activity(ally_ganks),
                "by_phase": {phase.value: stats.to_dict() for phase, stats in ally_timing.items()}
            },
            "enemy": {
                "style": get_jungler_style(enemy_timing),
                "first_gank": {
                    "timestamp": first_enemy_gank.timestamp,
                    "timestamp_formatted": first_enemy_gank.timestamp_formatted,
                    "lane": first_enemy_gank.lane.value,
                    "successful": first_enemy_gank.successful
                } if first_enemy_gank else None,
                "avg_time_between_ganks": avg_time_between_ganks(enemy_ganks),
                "peak_activity": find_peak_activity(enemy_ganks),
                "by_phase": {phase.value: stats.to_dict() for phase, stats in enemy_timing.items()}
            },
            "comparison": {
                "first_to_gank": "ally" if (first_ally_gank and first_enemy_gank and
                                            first_ally_gank.timestamp < first_enemy_gank.timestamp) else
                                ("enemy" if first_enemy_gank else ("ally" if first_ally_gank else "none")),
                "early_game_winner": "ally" if ally_timing[GamePhase.EARLY].total > enemy_timing[GamePhase.EARLY].total else
                                    ("enemy" if enemy_timing[GamePhase.EARLY].total > ally_timing[GamePhase.EARLY].total else "even")
            }
        }
    
    async def analyze_ganks(self, team_id: int = None) -> Dict:
        """
        Analyse complète de la pression jungle.
        
        Args:
            team_id: 100 (blue) ou 200 (red). Si None, utilise l'équipe du joueur principal.
        
        Returns:
            Statistiques complètes de ganks (effectués et subis) par lane.
        
        Attributs mis à jour:
            self.gank_stats: Dict complet des statistiques
            self.ally_ganks: Liste des GankEvent alliés
            self.enemy_ganks: Liste des GankEvent ennemis
            self.lane_gank_stats: Dict[Lane, LaneGankStats]
            self.ally_jungler_style: str
            self.enemy_jungler_style: str
        """
        # Déterminer l'équipe si non spécifiée
        if team_id is None:
            # thisId 0-4 = équipe 1 (100), 5-9 = équipe 2 (200)
            team_id = 100 if self.thisId < 5 else 200
        
        self._analyzed_team_id = team_id
        enemy_team_id = 200 if team_id == 100 else 100
        
        teams = self._get_team_participants_for_ganks()
        
        # Trouver les junglers
        ally_jungler_info = teams[team_id].get("JUNGLE", {})
        enemy_jungler_info = teams[enemy_team_id].get("JUNGLE", {})
        
        ally_jungler_id = ally_jungler_info.get("participantId")
        enemy_jungler_id = enemy_jungler_info.get("participantId")
        
        if not ally_jungler_id or not enemy_jungler_id:
            self.gank_stats = {"error": "Impossible de trouver les junglers"}
            return self.gank_stats
        
        kill_events = self._collect_kill_events()
        
        # Détecter les ganks des deux junglers
        self.ally_ganks = self._detect_ganks_for_jungler(ally_jungler_id, kill_events)
        self.enemy_ganks = self._detect_ganks_for_jungler(enemy_jungler_id, kill_events)
        
        # Stats par lane
        self.lane_gank_stats = {
            Lane.TOP: LaneGankStats(),
            Lane.MID: LaneGankStats(),
            Lane.BOT: LaneGankStats()
        }
        
        for gank in self.ally_ganks:
            self.lane_gank_stats[gank.lane].ganks_made += 1
            if gank.successful:
                self.lane_gank_stats[gank.lane].ganks_made_successful += 1
        
        for gank in self.enemy_ganks:
            self.lane_gank_stats[gank.lane].ganks_received += 1
            if gank.successful:
                self.lane_gank_stats[gank.lane].ganks_received_successful += 1
        
        # Détecter les counter-ganks
        counter_ganks = 0
        for ally_gank in self.ally_ganks:
            for enemy_gank in self.enemy_ganks:
                if (ally_gank.lane == enemy_gank.lane and
                    abs(ally_gank.timestamp - enemy_gank.timestamp) < self.COUNTER_GANK_WINDOW_MS):
                    counter_ganks += 1
                    ally_gank.is_counter_gank = True
                    enemy_gank.is_counter_gank = True
        
        # Stats globales
        total_ganks_made = sum(s.ganks_made for s in self.lane_gank_stats.values())
        total_ganks_received = sum(s.ganks_received for s in self.lane_gank_stats.values())
        total_successful_made = sum(s.ganks_made_successful for s in self.lane_gank_stats.values())
        total_successful_received = sum(s.ganks_received_successful for s in self.lane_gank_stats.values())
        
        most_ganked_lane = max(self.lane_gank_stats.keys(), key=lambda l: self.lane_gank_stats[l].ganks_made) if total_ganks_made > 0 else None
        most_targeted_lane = max(self.lane_gank_stats.keys(), key=lambda l: self.lane_gank_stats[l].ganks_received) if total_ganks_received > 0 else None
        
        # Analyse temporelle
        timing_insights = self._get_timing_insights(self.ally_ganks, self.enemy_ganks)
        
        # Stocker les styles pour accès rapide
        self.ally_jungler_style = timing_insights["ally"]["style"]
        self.enemy_jungler_style = timing_insights["enemy"]["style"]
        
        # Construire le résultat complet
        self.gank_stats = {
            "team_id": team_id,
            "ally_jungler": {
                "participantId": ally_jungler_id,
                "champion": ally_jungler_info.get("championName"),
                "name": ally_jungler_info.get("summonerName")
            },
            "enemy_jungler": {
                "participantId": enemy_jungler_id,
                "champion": enemy_jungler_info.get("championName"),
                "name": enemy_jungler_info.get("summonerName")
            },
            "summary": {
                "total_ganks_made": total_ganks_made,
                "total_ganks_received": total_ganks_received,
                "gank_differential": total_ganks_made - total_ganks_received,
                "ganks_made_successful": total_successful_made,
                "ganks_received_successful": total_successful_received,
                "success_rate_made": round(total_successful_made / total_ganks_made, 2) if total_ganks_made > 0 else 0,
                "death_rate_received": round(total_successful_received / total_ganks_received, 2) if total_ganks_received > 0 else 0,
                "counter_ganks": counter_ganks
            },
            "by_lane": {
                lane.value: self.lane_gank_stats[lane].to_dict()
                for lane in [Lane.TOP, Lane.MID, Lane.BOT]
            },
            "timing": timing_insights,
            "insights": {
                "most_ganked_by_ally": most_ganked_lane.value if most_ganked_lane else None,
                "most_targeted_by_enemy": most_targeted_lane.value if most_targeted_lane else None,
                "jungle_dominance": "ally" if total_ganks_made > total_ganks_received else
                                   ("enemy" if total_ganks_received > total_ganks_made else "even"),
                "ally_jungler_style": self.ally_jungler_style,
                "enemy_jungler_style": self.enemy_jungler_style
            },
            "gank_events": {
                "ally_ganks": [g.to_dict() for g in sorted(self.ally_ganks, key=lambda x: x.timestamp)],
                "enemy_ganks": [g.to_dict() for g in sorted(self.enemy_ganks, key=lambda x: x.timestamp)]
            }
        }
        
        return self.gank_stats
    
    def get_lane_gank_summary(self, lane: str) -> Dict:
        """
        Retourne un résumé des ganks pour une lane spécifique.
        
        Args:
            lane: "top", "mid", ou "bot"
        """
        lane_enum = Lane(lane.lower())
        stats = self.lane_gank_stats.get(lane_enum)
        
        if not stats:
            return {"error": f"Lane {lane} non trouvée"}
        
        ally_lane_ganks = [g for g in self.ally_ganks if g.lane == lane_enum]
        enemy_lane_ganks = [g for g in self.enemy_ganks if g.lane == lane_enum]
        
        return {
            "lane": lane,
            "stats": stats.to_dict(),
            "ally_ganks_timeline": [
                {"time": g.timestamp_formatted, "phase": g.game_phase.value, "success": g.successful}
                for g in sorted(ally_lane_ganks, key=lambda x: x.timestamp)
            ],
            "enemy_ganks_timeline": [
                {"time": g.timestamp_formatted, "phase": g.game_phase.value, "success": g.successful}
                for g in sorted(enemy_lane_ganks, key=lambda x: x.timestamp)
            ]
        }
    
    def get_player_gank_pressure(self, participant_id: int = None) -> Dict:
        """
        Retourne la pression de gank subie/reçue par un joueur spécifique.
        
        Args:
            participant_id: ID du participant (1-10). Si None, utilise le joueur principal.
        """
        if participant_id is None:
            participant_id = self.thisId + 1  # thisId est 0-indexed, participantId est 1-indexed
        
        # Trouver la lane du joueur
        teams = self._get_team_participants_for_ganks()
        player_role = None
        player_team = None
        
        for team_id, team_data in teams.items():
            if participant_id in team_data:
                player_role = team_data[participant_id]
                player_team = team_id
                break
        
        if not player_role or player_role == "JUNGLE":
            return {"error": "Joueur non trouvé ou est jungler"}
        
        # Mapper le rôle vers la lane
        role_to_lane = {
            "TOP": Lane.TOP,
            "JUNGLE": Lane.JUNGLE,
            "MID": Lane.MID,
            "ADC": Lane.BOT,
            "SUPPORT": Lane.BOT
        }
        
        player_lane = role_to_lane.get(player_role, Lane.MID)
        
        # Compter les ganks qui ont ciblé ce joueur
        ganks_received_by_player = [
            g for g in self.enemy_ganks
            if g.lane == player_lane
        ]
        
        deaths_from_ganks = [
            g for g in ganks_received_by_player
            if participant_id in g.victim_ids
        ]
        
        return {
            "participant_id": participant_id,
            "role": player_role,
            "lane": player_lane.value,
            "ganks_in_lane": len(ganks_received_by_player),
            "deaths_from_ganks": len(deaths_from_ganks),
            "survival_rate": 1 - (len(deaths_from_ganks) / len(ganks_received_by_player)) if ganks_received_by_player else 1,
            "gank_timeline": [
                {
                    "time": g.timestamp_formatted,
                    "phase": g.game_phase.value,
                    "died": participant_id in g.victim_ids
                }
                for g in sorted(ganks_received_by_player, key=lambda x: x.timestamp)
            ]
        }
    
    # =========================================================================
    # MÉTHODES DE SAUVEGARDE BDD
    # =========================================================================
    
    async def save_gank_data(self) -> bool:
        """
        Sauvegarde toutes les données de ganks dans la BDD.
        
        Returns:
            True si sauvegarde réussie, False sinon.
        """
        if not hasattr(self, 'gank_stats') or "error" in self.gank_stats:
            return False
        
        try:
            # 1. Sauvegarder le résumé
            await self._save_gank_summary()
            
            # 2. Sauvegarder les événements de gank
            await self._save_gank_events()
            
            # 3. Sauvegarder les stats par lane
            await self._save_gank_lane_stats()
            
            # 4. Sauvegarder les stats par phase
            await self._save_gank_phase_stats()
            
            return True
            
        except Exception as e:
            print(f"Erreur sauvegarde ganks: {e}")
            return False
    
    async def _save_gank_summary(self):
        """Sauvegarde le résumé des ganks."""
        stats = self.gank_stats
        timing = stats["timing"]
        
        # Extraire les données de timing allié
        ally_timing = timing["ally"]
        ally_first = ally_timing.get("first_gank") or {}
        ally_peak = ally_timing.get("peak_activity") or {}
        
        # Extraire les données de timing ennemi
        enemy_timing = timing["enemy"]
        enemy_first = enemy_timing.get("first_gank") or {}
        enemy_peak = enemy_timing.get("peak_activity") or {}
        
        sql = """
        INSERT INTO match_gank_summary (
            match_id, team_id,
            ally_jungler_participant_id, ally_jungler_champion, ally_jungler_name,
            enemy_jungler_participant_id, enemy_jungler_champion, enemy_jungler_name,
            total_ganks_made, total_ganks_received, gank_differential,
            ganks_made_successful, ganks_received_successful,
            success_rate_made, death_rate_received, counter_ganks,
            most_ganked_lane_by_ally, most_targeted_lane_by_enemy,
            jungle_dominance, ally_jungler_style, enemy_jungler_style,
            ally_first_gank_timestamp, ally_first_gank_lane, ally_first_gank_successful,
            ally_avg_time_between_ganks, ally_peak_activity_start, ally_peak_activity_count,
            enemy_first_gank_timestamp, enemy_first_gank_lane, enemy_first_gank_successful,
            enemy_avg_time_between_ganks, enemy_peak_activity_start, enemy_peak_activity_count,
            first_to_gank, early_game_winner
        ) VALUES (
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s
        )
        ON CONFLICT (match_id, team_id) DO UPDATE SET
            total_ganks_made = EXCLUDED.total_ganks_made,
            total_ganks_received = EXCLUDED.total_ganks_received,
            gank_differential = EXCLUDED.gank_differential,
            ganks_made_successful = EXCLUDED.ganks_made_successful,
            ganks_received_successful = EXCLUDED.ganks_received_successful,
            success_rate_made = EXCLUDED.success_rate_made,
            death_rate_received = EXCLUDED.death_rate_received,
            counter_ganks = EXCLUDED.counter_ganks
        """
        
        params = (
            self.last_match, self._analyzed_team_id,
            stats["ally_jungler"]["participantId"],
            stats["ally_jungler"]["champion"],
            stats["ally_jungler"]["name"],
            stats["enemy_jungler"]["participantId"],
            stats["enemy_jungler"]["champion"],
            stats["enemy_jungler"]["name"],
            stats["summary"]["total_ganks_made"],
            stats["summary"]["total_ganks_received"],
            stats["summary"]["gank_differential"],
            stats["summary"]["ganks_made_successful"],
            stats["summary"]["ganks_received_successful"],
            stats["summary"]["success_rate_made"],
            stats["summary"]["death_rate_received"],
            stats["summary"]["counter_ganks"],
            stats["insights"]["most_ganked_by_ally"],
            stats["insights"]["most_targeted_by_enemy"],
            stats["insights"]["jungle_dominance"],
            stats["insights"]["ally_jungler_style"],
            stats["insights"]["enemy_jungler_style"],
            ally_first.get("timestamp"),
            ally_first.get("lane"),
            ally_first.get("successful"),
            ally_timing.get("avg_time_between_ganks"),
            ally_peak.get("start"),
            ally_peak.get("count"),
            enemy_first.get("timestamp"),
            enemy_first.get("lane"),
            enemy_first.get("successful"),
            enemy_timing.get("avg_time_between_ganks"),
            enemy_peak.get("start"),
            enemy_peak.get("count"),
            timing["comparison"]["first_to_gank"],
            timing["comparison"]["early_game_winner"]
        )
        
        requete_perso_bdd(sql, params)
    
    async def _save_gank_events(self):
        """Sauvegarde tous les événements de gank."""
        # Supprimer les anciens events pour ce match
        delete_sql = "DELETE FROM match_gank_events WHERE match_id = %s"
        requete_perso_bdd(delete_sql, (self.last_match,))
        
        # Insérer les ganks alliés
        for gank in self.ally_ganks:
            self._insert_gank_event(gank, self._analyzed_team_id)
        
        # Insérer les ganks ennemis
        enemy_team_id = 200 if self._analyzed_team_id == 100 else 100
        for gank in self.enemy_ganks:
            self._insert_gank_event(gank, enemy_team_id)
    
    def _insert_gank_event(self, gank: GankEvent, team_id: int):
        """Insère un événement de gank dans la BDD."""
        sql = """
        INSERT INTO match_gank_events (
            match_id, team_id, timestamp_ms, timestamp_formatted,
            game_phase, lane, jungler_participant_id,
            successful, is_counter_gank, victim_ids
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        params = (
            self.last_match,
            team_id,
            gank.timestamp,
            gank.timestamp_formatted,
            gank.game_phase.value,
            gank.lane.value,
            gank.jungler_participant_id,
            gank.successful,
            gank.is_counter_gank,
            gank.victim_ids  # PostgreSQL supporte les arrays
        )
        
        requete_perso_bdd(sql, params)
    
    async def _save_gank_lane_stats(self):
        """Sauvegarde les statistiques par lane."""
        for lane, stats in self.lane_gank_stats.items():
            sql = """
            INSERT INTO match_gank_lane_stats (
                match_id, team_id, lane,
                ganks_made, ganks_made_successful,
                ganks_received, ganks_received_successful,
                differential, success_rate_made, death_rate_received,
                ganks_made_early, ganks_made_mid, ganks_made_late,
                ganks_received_early, ganks_received_mid, ganks_received_late
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (match_id, team_id, lane) DO UPDATE SET
                ganks_made = EXCLUDED.ganks_made,
                ganks_made_successful = EXCLUDED.ganks_made_successful,
                ganks_received = EXCLUDED.ganks_received,
                ganks_received_successful = EXCLUDED.ganks_received_successful,
                differential = EXCLUDED.differential,
                success_rate_made = EXCLUDED.success_rate_made,
                death_rate_received = EXCLUDED.death_rate_received,
                ganks_made_early = EXCLUDED.ganks_made_early,
                ganks_made_mid = EXCLUDED.ganks_made_mid,
                ganks_made_late = EXCLUDED.ganks_made_late,
                ganks_received_early = EXCLUDED.ganks_received_early,
                ganks_received_mid = EXCLUDED.ganks_received_mid,
                ganks_received_late = EXCLUDED.ganks_received_late
            """
            
            params = (
                self.last_match,
                self._analyzed_team_id,
                lane.value,
                stats.ganks_made,
                stats.ganks_made_successful,
                stats.ganks_received,
                stats.ganks_received_successful,
                stats.gank_differential,
                stats.success_rate_made,
                stats.death_rate_received,
                stats.ganks_made_by_phase[GamePhase.EARLY],
                stats.ganks_made_by_phase[GamePhase.MID],
                stats.ganks_made_by_phase[GamePhase.LATE],
                stats.ganks_received_by_phase[GamePhase.EARLY],
                stats.ganks_received_by_phase[GamePhase.MID],
                stats.ganks_received_by_phase[GamePhase.LATE]
            )
            
            requete_perso_bdd(sql, params)
    
    async def _save_gank_phase_stats(self):
        """Sauvegarde les statistiques par phase de jeu."""
        # Stats allié
        for phase, stats in self._ally_phase_stats.items():
            self._insert_phase_stats(phase, stats, is_ally=True)
        
        # Stats ennemi
        for phase, stats in self._enemy_phase_stats.items():
            self._insert_phase_stats(phase, stats, is_ally=False)
    
    def _insert_phase_stats(self, phase: GamePhase, stats: PhaseGankStats, is_ally: bool):
        """Insère les stats d'une phase dans la BDD."""
        sql = """
        INSERT INTO match_gank_phase_stats (
            match_id, team_id, is_ally, phase,
            total_ganks, successful_ganks, success_rate,
            ganks_top, ganks_mid, ganks_bot
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (match_id, team_id, is_ally, phase) DO UPDATE SET
            total_ganks = EXCLUDED.total_ganks,
            successful_ganks = EXCLUDED.successful_ganks,
            success_rate = EXCLUDED.success_rate,
            ganks_top = EXCLUDED.ganks_top,
            ganks_mid = EXCLUDED.ganks_mid,
            ganks_bot = EXCLUDED.ganks_bot
        """
        
        params = (
            self.last_match,
            self._analyzed_team_id,
            is_ally,
            phase.value,
            stats.total,
            stats.successful,
            stats.success_rate,
            stats.by_lane[Lane.TOP],
            stats.by_lane[Lane.MID],
            stats.by_lane[Lane.BOT]
        )
        
        requete_perso_bdd(sql, params)
    
    # =========================================================================
    # MÉTHODES DE LECTURE BDD
    # =========================================================================
    
    @staticmethod
    def get_gank_stats_from_db(match_id: str, team_id: int = None) -> Optional[Dict]:
        """
        Récupère les stats de ganks depuis la BDD.
        
        Args:
            match_id: ID du match
            team_id: ID de l'équipe (optionnel, retourne les deux si None)
        """
        if team_id:
            sql = "SELECT * FROM match_gank_summary WHERE match_id = %s AND team_id = %s"
            result = lire_bdd_perso(sql, (match_id, team_id), format='dict')
        else:
            sql = "SELECT * FROM match_gank_summary WHERE match_id = %s"
            result = lire_bdd_perso(sql, (match_id,), format='dict')
        
        return result if result else None
    
    @staticmethod
    def get_jungler_stats_aggregated(jungler_name: str, limit: int = 20) -> Dict:
        """
        Récupère les statistiques agrégées d'un jungler sur plusieurs matchs.
        
        Args:
            jungler_name: Nom du jungler
            limit: Nombre de matchs à analyser
        """
        sql = """
        SELECT 
            ally_jungler_name,
            ally_jungler_champion,
            COUNT(*) as games,
            AVG(total_ganks_made) as avg_ganks,
            AVG(success_rate_made) as avg_success_rate,
            AVG(gank_differential) as avg_differential,
            ally_jungler_style,
            COUNT(*) FILTER (WHERE jungle_dominance = 'ally') as games_dominant
        FROM match_gank_summary
        WHERE ally_jungler_name = %s
        GROUP BY ally_jungler_name, ally_jungler_champion, ally_jungler_style
        ORDER BY games DESC
        LIMIT %s
        """
        
        result = lire_bdd_perso(sql, (jungler_name, limit), format='dict')
        return result if result else {}
    
    @staticmethod
    def get_lane_gank_history(match_id: str) -> List[Dict]:
        """Récupère l'historique des ganks par lane pour un match."""
        sql = """
        SELECT * FROM match_gank_lane_stats 
        WHERE match_id = %s 
        ORDER BY lane
        """
        result = lire_bdd_perso(sql, (match_id,), format='dict')
        return result if result else []
    
    @staticmethod
    def get_gank_events_timeline(match_id: str) -> List[Dict]:
        """Récupère tous les événements de gank pour un match."""
        sql = """
        SELECT * FROM match_gank_events 
        WHERE match_id = %s 
        ORDER BY timestamp_ms
        """
        result = lire_bdd_perso(sql, (match_id,), format='dict')
        return result if result else []