"""
Mixin d'analyse des ganks pour MatchLol.

Détecte les ganks basés sur les KILLS impliquant le jungler sur une lane.
Méthode fiable à 100% car basée sur des événements avec timestamp exact.

Usage dans MatchLol:
    class MatchLol(GankAnalysisMixin, ScoringMixin, ...):
        ...
    
    # Après avoir récupéré la timeline:
    await self.analyze_ganks()
    
    # Accès aux données:
    self.gank_stats           # Stats complètes de ganks
    self.ally_jungler_style   # Style du jungler allié
    self.enemy_jungler_style  # Style du jungler ennemi
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
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


PHASE_THRESHOLDS_MS = {
    GamePhase.EARLY: (0, 14 * 60 * 1000),
    GamePhase.MID: (14 * 60 * 1000, 30 * 60 * 1000),
    GamePhase.LATE: (30 * 60 * 1000, float('inf'))
}


@dataclass
class GankEvent:
    """Représente un événement de gank (kill impliquant le jungler sur une lane)."""
    timestamp: int
    lane: Lane
    successful: bool  # True si l'ennemi meurt, False si un allié meurt
    jungler_participant_id: int
    jungler_champion: str = ""
    victim_id: int = 0
    is_counter_gank: bool = False
    
    @property
    def game_phase(self) -> GamePhase:
        for phase, (start, end) in PHASE_THRESHOLDS_MS.items():
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
            "jungler": self.jungler_champion,
            "victim_id": self.victim_id,
            "is_counter_gank": self.is_counter_gank
        }


@dataclass
class LaneGankStats:
    """Statistiques de ganks pour une lane."""
    ganks_made: int = 0
    ganks_made_successful: int = 0
    ganks_received: int = 0
    ganks_received_successful: int = 0
    ganks_made_by_phase: Dict[GamePhase, int] = field(default_factory=lambda: {
        GamePhase.EARLY: 0, GamePhase.MID: 0, GamePhase.LATE: 0
    })
    ganks_received_by_phase: Dict[GamePhase, int] = field(default_factory=lambda: {
        GamePhase.EARLY: 0, GamePhase.MID: 0, GamePhase.LATE: 0
    })
    
    @property
    def differential(self) -> int:
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
            "differential": self.differential,
            "success_rate_made": round(self.success_rate_made, 2),
            "death_rate_received": round(self.death_rate_received, 2),
            "by_phase_made": {p.value: c for p, c in self.ganks_made_by_phase.items()},
            "by_phase_received": {p.value: c for p, c in self.ganks_received_by_phase.items()}
        }


@dataclass 
class PhaseGankStats:
    """Stats de gank pour une phase de jeu."""
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

def get_lane_from_position(x: int, y: int) -> Lane:
    """
    Détermine la lane basée sur les coordonnées du kill.
    Map SR: 0-15000 sur chaque axe.
    """
    nx = x / 15000
    ny = y / 15000
    
    # TOP: coin supérieur gauche
    if (ny > 0.65 and nx < 0.55) or (nx < 0.30 and ny > 0.45):
        return Lane.TOP
    
    # BOT: coin inférieur droit
    if (ny < 0.35 and nx > 0.45) or (nx > 0.70 and ny < 0.55):
        return Lane.BOT
    
    # MID: diagonale centrale
    if abs(ny - nx) < 0.20 and 0.20 < nx < 0.80:
        return Lane.MID
    
    return Lane.JUNGLE


def get_jungler_style(phase_stats: Dict[GamePhase, PhaseGankStats]) -> str:
    """
    Identifie le style de jeu du jungler.
    
    Returns:
        - "early_aggro": 50%+ des ganks en early
        - "balanced": Répartition équilibrée
        - "mid_focused": Focus mid game
        - "late_scaler": Peu de ganks early
        - "passive": Très peu de ganks total
    """
    early = phase_stats[GamePhase.EARLY].total
    mid = phase_stats[GamePhase.MID].total
    late = phase_stats[GamePhase.LATE].total
    total = early + mid + late
    
    if total < 2:
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
    
    Détection basée sur les KILLS impliquant le jungler sur une lane.
    Un gank = le jungler participe (kill ou assist) à un kill sur TOP/MID/BOT.
    
    Requiert:
    - self.match_detail: Données du match
    - self.data_timeline: Données timeline
    - self.thisId: Index du joueur principal (0-9)
    - self.last_match: ID du match
    """
    
    GANK_COOLDOWN_MS = 20000  # 20s entre deux ganks comptés séparément
    COUNTER_GANK_WINDOW_MS = 15000  # Fenêtre pour détecter un counter-gank
    
    def _get_jungler_info(self) -> Dict:
        """Retourne les infos des junglers des deux équipes."""
        participants = self.match_detail.get("info", {}).get("participants", [])
        
        junglers = {100: None, 200: None}
        
        for p in participants:
            role = p.get("teamPosition") or p.get("individualPosition")
            if role == "JUNGLE":
                team_id = p.get("teamId")
                junglers[team_id] = {
                    "participantId": p.get("participantId"),
                    "championName": p.get("championName"),
                    "summonerName": p.get("summonerName", p.get("riotIdGameName", "Unknown"))
                }
        
        return junglers
    
    def _collect_lane_kills_with_jungler(self, jungler_id: int, team_id: int) -> List[GankEvent]:
        """
        Collecte tous les kills sur lane impliquant le jungler.
        
        Args:
            jungler_id: participantId du jungler
            team_id: 100 ou 200
        
        Returns:
            Liste de GankEvent
        """
        # Récupérer le nom du champion du jungler
        junglers = self._get_jungler_info()
        jungler_champion = junglers.get(team_id, {}).get("championName", "Unknown")
        
        # Parser la timeline selon sa structure
        if isinstance(self.data_timeline, list):
            frames = self.data_timeline
        else:
            frames = self.data_timeline.get("info", {}).get("frames", [])
        
        ganks = []
        last_gank_time = {Lane.TOP: -60000, Lane.MID: -60000, Lane.BOT: -60000}
        
        for frame in frames:
            for event in frame.get("events", []):
                if event.get("type") != "CHAMPION_KILL":
                    continue
                
                ts = event.get("timestamp", 0)
                killer_id = event.get("killerId")
                victim_id = event.get("victimId")
                assists = event.get("assistingParticipantIds", [])
                pos = event.get("position", {})
                
                # Le jungler est-il impliqué ?
                jungler_is_killer = killer_id == jungler_id
                jungler_assisted = jungler_id in assists
                
                if not jungler_is_killer and not jungler_assisted:
                    continue
                
                # Déterminer la lane
                lane = get_lane_from_position(pos.get("x", 0), pos.get("y", 0))
                
                # Ignorer les kills en jungle
                if lane == Lane.JUNGLE:
                    continue
                
                # Vérifier le cooldown
                if ts - last_gank_time[lane] < self.GANK_COOLDOWN_MS:
                    continue
                
                # Déterminer si c'est un gank réussi (ennemi tué) ou raté (allié tué)
                # Équipe 100 = participants 1-5, Équipe 200 = participants 6-10
                victim_is_enemy = (victim_id > 5) if team_id == 100 else (victim_id <= 5)
                
                gank = GankEvent(
                    timestamp=ts,
                    lane=lane,
                    successful=victim_is_enemy,
                    jungler_participant_id=jungler_id,
                    jungler_champion=jungler_champion,
                    victim_id=victim_id
                )
                ganks.append(gank)
                last_gank_time[lane] = ts
        
        return ganks
    
    def _compute_phase_stats(self, ganks: List[GankEvent]) -> Dict[GamePhase, PhaseGankStats]:
        """Calcule les stats par phase de jeu."""
        stats = {
            GamePhase.EARLY: PhaseGankStats(),
            GamePhase.MID: PhaseGankStats(),
            GamePhase.LATE: PhaseGankStats()
        }
        
        for gank in ganks:
            phase = gank.game_phase
            stats[phase].total += 1
            if gank.successful:
                stats[phase].successful += 1
            if gank.lane in stats[phase].by_lane:
                stats[phase].by_lane[gank.lane] += 1
        
        return stats
    
    def _compute_timing_insights(
        self,
        ally_ganks: List[GankEvent],
        enemy_ganks: List[GankEvent]
    ) -> Dict:
        """Génère des insights sur le timing des ganks."""
        
        ally_phase = self._compute_phase_stats(ally_ganks)
        enemy_phase = self._compute_phase_stats(enemy_ganks)
        
        # Stocker pour la sauvegarde
        self._ally_phase_stats = ally_phase
        self._enemy_phase_stats = enemy_phase
        
        first_ally = min(ally_ganks, key=lambda g: g.timestamp) if ally_ganks else None
        first_enemy = min(enemy_ganks, key=lambda g: g.timestamp) if enemy_ganks else None
        
        def avg_interval(ganks: List[GankEvent]) -> Optional[float]:
            if len(ganks) < 2:
                return None
            sorted_g = sorted(ganks, key=lambda g: g.timestamp)
            intervals = [sorted_g[i+1].timestamp - sorted_g[i].timestamp for i in range(len(sorted_g)-1)]
            return round(sum(intervals) / len(intervals) / 1000, 1)  # En secondes
        
        return {
            "ally": {
                "style": get_jungler_style(ally_phase),
                "first_gank": {
                    "timestamp": first_ally.timestamp,
                    "formatted": first_ally.timestamp_formatted,
                    "lane": first_ally.lane.value,
                    "successful": first_ally.successful
                } if first_ally else None,
                "avg_interval_seconds": avg_interval(ally_ganks),
                "by_phase": {p.value: s.to_dict() for p, s in ally_phase.items()}
            },
            "enemy": {
                "style": get_jungler_style(enemy_phase),
                "first_gank": {
                    "timestamp": first_enemy.timestamp,
                    "formatted": first_enemy.timestamp_formatted,
                    "lane": first_enemy.lane.value,
                    "successful": first_enemy.successful
                } if first_enemy else None,
                "avg_interval_seconds": avg_interval(enemy_ganks),
                "by_phase": {p.value: s.to_dict() for p, s in enemy_phase.items()}
            },
            "comparison": {
                "first_to_gank": "ally" if (first_ally and first_enemy and first_ally.timestamp < first_enemy.timestamp)
                                 else ("enemy" if first_enemy else ("ally" if first_ally else "none")),
                "early_winner": "ally" if ally_phase[GamePhase.EARLY].total > enemy_phase[GamePhase.EARLY].total
                               else ("enemy" if enemy_phase[GamePhase.EARLY].total > ally_phase[GamePhase.EARLY].total else "even")
            }
        }
    
    async def analyze_ganks(self, team_id: int = None) -> Dict:
        """
        Analyse complète des ganks.
        
        Args:
            team_id: 100 ou 200. Si None, déduit de thisId.
        
        Returns:
            Dict avec toutes les stats de ganks.
        
        Attributs mis à jour:
            self.gank_stats
            self.ally_ganks
            self.enemy_ganks
            self.lane_gank_stats
            self.ally_jungler_style
            self.enemy_jungler_style
        """
        # Déterminer l'équipe
        if team_id is None:
            team_id = 100 if self.thisId < 5 else 200
        enemy_team_id = 200 if team_id == 100 else 100
        
        # Récupérer les junglers
        junglers = self._get_jungler_info()
        
        ally_jgl = junglers.get(team_id)
        enemy_jgl = junglers.get(enemy_team_id)
        
        if not ally_jgl or not enemy_jgl:
            self.gank_stats = {"error": "Junglers non trouvés"}
            return self.gank_stats
        
        # Collecter les ganks
        self.ally_ganks = self._collect_lane_kills_with_jungler(
            ally_jgl["participantId"], team_id
        )
        self.enemy_ganks = self._collect_lane_kills_with_jungler(
            enemy_jgl["participantId"], enemy_team_id
        )
        
        # Stats par lane
        self.lane_gank_stats = {
            Lane.TOP: LaneGankStats(),
            Lane.MID: LaneGankStats(),
            Lane.BOT: LaneGankStats()
        }
        
        for gank in self.ally_ganks:
            self.lane_gank_stats[gank.lane].ganks_made += 1
            self.lane_gank_stats[gank.lane].ganks_made_by_phase[gank.game_phase] += 1
            if gank.successful:
                self.lane_gank_stats[gank.lane].ganks_made_successful += 1
        
        for gank in self.enemy_ganks:
            self.lane_gank_stats[gank.lane].ganks_received += 1
            self.lane_gank_stats[gank.lane].ganks_received_by_phase[gank.game_phase] += 1
            if gank.successful:
                self.lane_gank_stats[gank.lane].ganks_received_successful += 1
        
        # Détecter les counter-ganks
        counter_ganks = 0
        for ag in self.ally_ganks:
            for eg in self.enemy_ganks:
                if ag.lane == eg.lane and abs(ag.timestamp - eg.timestamp) < self.COUNTER_GANK_WINDOW_MS:
                    counter_ganks += 1
                    ag.is_counter_gank = True
                    eg.is_counter_gank = True
        
        # Totaux
        total_made = len(self.ally_ganks)
        total_received = len(self.enemy_ganks)
        successful_made = sum(1 for g in self.ally_ganks if g.successful)
        successful_received = sum(1 for g in self.enemy_ganks if g.successful)
        
        # Timing
        timing = self._compute_timing_insights(self.ally_ganks, self.enemy_ganks)
        
        self.ally_jungler_style = timing["ally"]["style"]
        self.enemy_jungler_style = timing["enemy"]["style"]
        
        # Construire le résultat
        self.gank_stats = {
            "team_id": team_id,
            "ally_jungler": ally_jgl,
            "enemy_jungler": enemy_jgl,
            "summary": {
                "total_ganks_made": total_made,
                "total_ganks_received": total_received,
                "differential": total_made - total_received,
                "successful_made": successful_made,
                "successful_received": successful_received,
                "success_rate_made": round(successful_made / total_made, 2) if total_made > 0 else 0,
                "death_rate_received": round(successful_received / total_received, 2) if total_received > 0 else 0,
                "counter_ganks": counter_ganks
            },
            "by_lane": {
                lane.value: self.lane_gank_stats[lane].to_dict()
                for lane in [Lane.TOP, Lane.MID, Lane.BOT]
            },
            "timing": timing,
            "insights": {
                "most_ganked_by_ally": max(
                    [Lane.TOP, Lane.MID, Lane.BOT],
                    key=lambda l: self.lane_gank_stats[l].ganks_made
                ).value if total_made > 0 else None,
                "most_targeted_by_enemy": max(
                    [Lane.TOP, Lane.MID, Lane.BOT],
                    key=lambda l: self.lane_gank_stats[l].ganks_received
                ).value if total_received > 0 else None,
                "jungle_dominance": "ally" if total_made > total_received 
                                   else ("enemy" if total_received > total_made else "even"),
                "ally_style": self.ally_jungler_style,
                "enemy_style": self.enemy_jungler_style
            },
            "events": {
                "ally": [g.to_dict() for g in self.ally_ganks],
                "enemy": [g.to_dict() for g in self.enemy_ganks]
            }
        }
        
        return self.gank_stats
    
    # =========================================================================
    # MÉTHODES DE SAUVEGARDE BDD
    # =========================================================================
    
    async def save_gank_data(self) -> bool:
        """Sauvegarde toutes les données de ganks."""
        if not hasattr(self, 'gank_stats') or "error" in self.gank_stats:
            return False
        
        try:
            await self._save_gank_summary()
            await self._save_gank_events()
            await self._save_gank_lane_stats()
            await self._save_gank_phase_stats()
            return True
        except Exception as e:
            print(f"Erreur sauvegarde ganks: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _save_gank_summary(self):
        """Sauvegarde le résumé global."""
        stats = self.gank_stats
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
            first_to_gank, early_winner
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
            :first_to_gank, :early_winner
        )
        ON CONFLICT (match_id, team_id) DO UPDATE SET
            total_ganks_made = EXCLUDED.total_ganks_made,
            total_ganks_received = EXCLUDED.total_ganks_received,
            differential = EXCLUDED.differential,
            successful_made = EXCLUDED.successful_made,
            successful_received = EXCLUDED.successful_received,
            success_rate_made = EXCLUDED.success_rate_made,
            death_rate_received = EXCLUDED.death_rate_received,
            counter_ganks = EXCLUDED.counter_ganks
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
            "total_ganks_made": stats["summary"]["total_ganks_made"],
            "total_ganks_received": stats["summary"]["total_ganks_received"],
            "differential": stats["summary"]["differential"],
            "successful_made": stats["summary"]["successful_made"],
            "successful_received": stats["summary"]["successful_received"],
            "success_rate_made": stats["summary"]["success_rate_made"],
            "death_rate_received": stats["summary"]["death_rate_received"],
            "counter_ganks": stats["summary"]["counter_ganks"],
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
            "early_winner": timing["comparison"]["early_winner"]
        }
        
        requete_perso_bdd(sql, params)
    
    async def _save_gank_events(self):
        """Sauvegarde les événements de gank."""
        team_id = self.gank_stats["team_id"]
        enemy_team_id = 200 if team_id == 100 else 100
        
        # Supprimer les anciens
        requete_perso_bdd(
            "DELETE FROM match_gank_events WHERE match_id = :match_id",
            {"match_id": self.last_match}
        )
        
        # Insérer les nouveaux
        sql = """
        INSERT INTO match_gank_events (
            match_id, team_id, timestamp_ms, timestamp_formatted,
            game_phase, lane, jungler_id, jungler_champion,
            successful, is_counter_gank, victim_id
        ) VALUES (
            :match_id, :team_id, :timestamp_ms, :timestamp_formatted,
            :game_phase, :lane, :jungler_id, :jungler_champion,
            :successful, :is_counter_gank, :victim_id
        )
        """
        
        for gank in self.ally_ganks:
            requete_perso_bdd(sql, {
                "match_id": self.last_match,
                "team_id": team_id,
                "timestamp_ms": gank.timestamp,
                "timestamp_formatted": gank.timestamp_formatted,
                "game_phase": gank.game_phase.value,
                "lane": gank.lane.value,
                "jungler_id": gank.jungler_participant_id,
                "jungler_champion": gank.jungler_champion,
                "successful": gank.successful,
                "is_counter_gank": gank.is_counter_gank,
                "victim_id": gank.victim_id
            })
        
        for gank in self.enemy_ganks:
            requete_perso_bdd(sql, {
                "match_id": self.last_match,
                "team_id": enemy_team_id,
                "timestamp_ms": gank.timestamp,
                "timestamp_formatted": gank.timestamp_formatted,
                "game_phase": gank.game_phase.value,
                "lane": gank.lane.value,
                "jungler_id": gank.jungler_participant_id,
                "jungler_champion": gank.jungler_champion,
                "successful": gank.successful,
                "is_counter_gank": gank.is_counter_gank,
                "victim_id": gank.victim_id
            })
    
    async def _save_gank_lane_stats(self):
        """Sauvegarde les stats par lane."""
        team_id = self.gank_stats["team_id"]
        
        sql = """
        INSERT INTO match_gank_lane_stats (
            match_id, team_id, lane,
            ganks_made, ganks_made_successful,
            ganks_received, ganks_received_successful,
            differential, success_rate_made, death_rate_received,
            made_early, made_mid, made_late,
            received_early, received_mid, received_late
        ) VALUES (
            :match_id, :team_id, :lane,
            :ganks_made, :ganks_made_successful,
            :ganks_received, :ganks_received_successful,
            :differential, :success_rate_made, :death_rate_received,
            :made_early, :made_mid, :made_late,
            :received_early, :received_mid, :received_late
        )
        ON CONFLICT (match_id, team_id, lane) DO UPDATE SET
            ganks_made = EXCLUDED.ganks_made,
            ganks_made_successful = EXCLUDED.ganks_made_successful,
            ganks_received = EXCLUDED.ganks_received,
            ganks_received_successful = EXCLUDED.ganks_received_successful,
            differential = EXCLUDED.differential,
            success_rate_made = EXCLUDED.success_rate_made,
            death_rate_received = EXCLUDED.death_rate_received,
            made_early = EXCLUDED.made_early,
            made_mid = EXCLUDED.made_mid,
            made_late = EXCLUDED.made_late,
            received_early = EXCLUDED.received_early,
            received_mid = EXCLUDED.received_mid,
            received_late = EXCLUDED.received_late
        """
        
        for lane, stats in self.lane_gank_stats.items():
            requete_perso_bdd(sql, {
                "match_id": self.last_match,
                "team_id": team_id,
                "lane": lane.value,
                "ganks_made": stats.ganks_made,
                "ganks_made_successful": stats.ganks_made_successful,
                "ganks_received": stats.ganks_received,
                "ganks_received_successful": stats.ganks_received_successful,
                "differential": stats.differential,
                "success_rate_made": stats.success_rate_made,
                "death_rate_received": stats.death_rate_received,
                "made_early": stats.ganks_made_by_phase[GamePhase.EARLY],
                "made_mid": stats.ganks_made_by_phase[GamePhase.MID],
                "made_late": stats.ganks_made_by_phase[GamePhase.LATE],
                "received_early": stats.ganks_received_by_phase[GamePhase.EARLY],
                "received_mid": stats.ganks_received_by_phase[GamePhase.MID],
                "received_late": stats.ganks_received_by_phase[GamePhase.LATE]
            })
    
    async def _save_gank_phase_stats(self):
        """Sauvegarde les stats par phase."""
        if not hasattr(self, '_ally_phase_stats'):
            return
        
        team_id = self.gank_stats["team_id"]
        
        sql = """
        INSERT INTO match_gank_phase_stats (
            match_id, team_id, is_ally, phase,
            total_ganks, successful_ganks, success_rate,
            ganks_top, ganks_mid, ganks_bot
        ) VALUES (
            :match_id, :team_id, :is_ally, :phase,
            :total_ganks, :successful_ganks, :success_rate,
            :ganks_top, :ganks_mid, :ganks_bot
        )
        ON CONFLICT (match_id, team_id, is_ally, phase) DO UPDATE SET
            total_ganks = EXCLUDED.total_ganks,
            successful_ganks = EXCLUDED.successful_ganks,
            success_rate = EXCLUDED.success_rate,
            ganks_top = EXCLUDED.ganks_top,
            ganks_mid = EXCLUDED.ganks_mid,
            ganks_bot = EXCLUDED.ganks_bot
        """
        
        for phase, stats in self._ally_phase_stats.items():
            requete_perso_bdd(sql, {
                "match_id": self.last_match,
                "team_id": team_id,
                "is_ally": True,
                "phase": phase.value,
                "total_ganks": stats.total,
                "successful_ganks": stats.successful,
                "success_rate": stats.success_rate,
                "ganks_top": stats.by_lane[Lane.TOP],
                "ganks_mid": stats.by_lane[Lane.MID],
                "ganks_bot": stats.by_lane[Lane.BOT]
            })
        
        for phase, stats in self._enemy_phase_stats.items():
            requete_perso_bdd(sql, {
                "match_id": self.last_match,
                "team_id": team_id,
                "is_ally": False,
                "phase": phase.value,
                "total_ganks": stats.total,
                "successful_ganks": stats.successful,
                "success_rate": stats.success_rate,
                "ganks_top": stats.by_lane[Lane.TOP],
                "ganks_mid": stats.by_lane[Lane.MID],
                "ganks_bot": stats.by_lane[Lane.BOT]
            })
    
    # =========================================================================
    # MÉTHODES DE LECTURE BDD (statiques)
    # =========================================================================
    
    @staticmethod
    def get_gank_summary(match_id: str, team_id: int = None) -> Optional[Dict]:
        """Récupère le résumé des ganks depuis la BDD."""
        if team_id:
            sql = "SELECT * FROM match_gank_summary WHERE match_id = :match_id AND team_id = :team_id"
            params = {"match_id": match_id, "team_id": team_id}
        else:
            sql = "SELECT * FROM match_gank_summary WHERE match_id = :match_id"
            params = {"match_id": match_id}
        
        result = lire_bdd_perso(sql, format='dict', params=params)
        return result if result else None
    
    @staticmethod
    def get_gank_events(match_id: str) -> List[Dict]:
        """Récupère tous les événements de gank d'un match."""
        sql = """
        SELECT * FROM match_gank_events 
        WHERE match_id = :match_id 
        ORDER BY timestamp_ms
        """
        result = lire_bdd_perso(sql, format='dict', params={"match_id": match_id})
        return result if result else []
    
    @staticmethod
    def get_jungler_aggregated_stats(jungler_name: str, limit: int = 20) -> Dict:
        """Récupère les stats agrégées d'un jungler."""
        sql = """
        SELECT 
            ally_jungler_champion,
            COUNT(*) as games,
            AVG(total_ganks_made) as avg_ganks,
            AVG(success_rate_made) as avg_success_rate,
            AVG(differential) as avg_differential,
            SUM(CASE WHEN jungle_dominance = 'ally' THEN 1 ELSE 0 END) as games_dominant
        FROM match_gank_summary
        WHERE ally_jungler_name = :jungler_name
        GROUP BY ally_jungler_champion
        ORDER BY games DESC
        LIMIT :limit
        """
        result = lire_bdd_perso(sql, format='dict', params={"jungler_name": jungler_name, "limit": limit})
        return result if result else {}


