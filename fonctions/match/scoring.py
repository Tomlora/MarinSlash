"""
Mixin de scoring pour MatchLol - VERSION 4.0.

Intègre deux systèmes complémentaires avec logique d'ajustement unifiée:
- Statistiques : z-scores bornés, 70 % de la note MVP/ACE
- Contribution : cinq dimensions, 30 % de la note MVP/ACE

Les ratios BDD et la durée ajustent les références du rôle. L'utilité ne
demande que les capacités pertinentes pour le kit/profil. Le calcul effectif
et ses courbes provisoires sont dans scoring_v4.py. Voir docs/matchlol-scoring-v4.md.

Usage dans MatchLol:
    class MatchLol(ScoringMixin, ...):
        ...
    
    # Après prepare_data():
    await self.calculate_all_scores()
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import math

from .scoring_inputs import game_minutes, participant_indices, extract_early_game, tracked_index, storage_index

SCORING_VERSION = "4.0"
STATISTICAL_WEIGHT = 0.70
CONTRIBUTION_WEIGHT = 0.30

from fonctions.match.champion_profiles import (
    get_profile_for_champion,
    get_profile_adjustments,
    ChampionProfile,
    load_champion_tags
)


# =============================================================================
# ENUMS ET DATACLASSES
# =============================================================================

class Role(Enum):
    TOP = "TOP"
    JUNGLE = "JUNGLE"
    MID = "MID"
    ADC = "ADC"
    SUPPORT = "SUPPORT"
    UNKNOWN = "UNKNOWN"


@dataclass
class RoleStats:
    """Statistiques de référence pour un rôle (moyenne, écart-type)."""
    kills: Tuple[float, float]
    deaths: Tuple[float, float]
    assists: Tuple[float, float]
    kda: Tuple[float, float]
    cs_per_min: Tuple[float, float]
    damage_per_min: Tuple[float, float]
    damage_share: Tuple[float, float]
    gold_per_min: Tuple[float, float]
    vision_score_per_min: Tuple[float, float]
    kp: Tuple[float, float]
    damage_taken_share: Tuple[float, float]


@dataclass
class ContributionBreakdown:
    """Détail des scores par dimension."""
    combat_value: float
    economic_efficiency: float
    objective_contribution: float
    pace_rating: float
    win_impact: float
    final_score: float
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'combat_value': self.combat_value,
            'economic_efficiency': self.economic_efficiency,
            'objective_contribution': self.objective_contribution,
            'pace_rating': self.pace_rating,
            'win_impact': self.win_impact,
            'final_score': self.final_score
        }
    
    def get_best_dimension(self) -> Tuple[str, float]:
        dims = {
            'Combat': self.combat_value,
            'Économie': self.economic_efficiency,
            'Objectifs': self.objective_contribution,
            'Tempo': self.pace_rating,
            'Impact': self.win_impact
        }
        best = max(dims, key=dims.get)
        return best, dims[best]
    
    def get_weakest_dimension(self) -> Tuple[str, float]:
        dims = {
            'Combat': self.combat_value,
            'Économie': self.economic_efficiency,
            'Objectifs': self.objective_contribution,
            'Tempo': self.pace_rating,
            'Impact': self.win_impact
        }
        worst = min(dims, key=dims.get)
        return worst, dims[worst]
    
    def get_badge_emoji(self) -> str:
        emoji_map = {
            'Combat': '⚔️',
            'Économie': '💰',
            'Objectifs': '🎯',
            'Tempo': '⚡',
            'Impact': '👑'
        }
        best, _ = self.get_best_dimension()
        return emoji_map.get(best, '🏆')


@dataclass
class PlayerMetrics:
    """Métriques calculées pour un joueur - Structure centralisée."""
    # === IDENTITÉ ===
    player_index: int
    champion: str = ""
    role: str = "UNKNOWN"
    role_enum: Role = Role.UNKNOWN
    
    # === STATS BRUTES ===
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    cs: int = 0
    damage: int = 0
    gold: int = 0
    vision: int = 0
    damage_taken: int = 0
    turret_damage: int = 0
    objective_damage: int = 0
    turrets_killed: int = 0
    pinks: int = 0
    
    # === STATS D'ÉQUIPE ===
    team_kills: int = 1
    team_deaths: int = 1
    team_damage: int = 1
    team_tank: int = 1
    team_gold: int = 1
    enemy_gold: int = 1
    
    # === MÉTRIQUES DÉRIVÉES ===
    game_minutes: float = 25.0
    cs_per_min: float = 0.0
    damage_per_min: float = 0.0
    gold_per_min: float = 0.0
    vision_per_min: float = 0.0
    damage_share: float = 0.0
    damage_taken_share: float = 0.0
    kp: float = 0.0
    kda: float = 0.0
    death_share: float = 0.0
    gold_share: float = 0.0
    dpg: float = 0.0
    
    # === OBJECTIFS (TIMELINE) ===
    objectives_participated: float = 0.0
    dragon_participation: int = 0
    baron_participation: int = 0
    herald_participation: int = 0
    tower_participation: float = 0.0
    first_objective_bonus: float = 0.0
    total_objectives: float = 0.0
    timeline_available: bool = False
    gold_15_available: bool = False
    cs_15_available: bool = False
    ally_healing: Optional[float] = None
    ally_shielding: Optional[float] = None
    cc_seconds: Optional[float] = None
    utility_score: float = 5.0
    utility_available: bool = False
    utility_references: dict = field(default_factory=dict)
    utility_parts: list = field(default_factory=list)
    objective_opportunities: dict = field(default_factory=dict)
    objective_presence: dict = field(default_factory=dict)
    observed_team_kills: int = 0
    scoring_supported: bool = True
    performance_score: float = 5.0
    explanation_context: dict = field(default_factory=dict)
    
    # === EARLY GAME ===
    gold_at_15: int = 0
    cs_at_15: int = 0
    gold_diff_15: int = 0
    cs_diff_15: int = 0
    has_first_blood: bool = False
    has_first_blood_assist: bool = False
    has_first_tower: bool = False
    has_first_tower_assist: bool = False
    solo_kills: int = 0
    early_solo_kills: int = 0
    opponent_index: Optional[int] = None
    
    # === PROFIL CHAMPION ===
    profile: str = "UNKNOWN"
    champion_tags: List[str] = field(default_factory=list)
    
    # === MULTIPLICATEURS DE PROFIL ===
    dpm_mult: float = 1.0
    dmg_share_mult: float = 1.0
    cs_mult: float = 1.0
    gpm_mult: float = 1.0
    vision_mult: float = 1.0
    kp_mult: float = 1.0
    tank_mult: float = 1.0
    
    # === AJUSTEMENTS DE POIDS ===
    combat_weight_adj: float = 0.0
    economic_weight_adj: float = 0.0
    objective_weight_adj: float = 0.0
    tempo_weight_adj: float = 0.0
    impact_weight_adj: float = 0.0
    
    # === Z-SCORES ===
    z_kda: float = 0.0
    z_cs_per_min: float = 0.0
    z_damage_per_min: float = 0.0
    z_damage_share: float = 0.0
    z_gold_per_min: float = 0.0
    z_vision_per_min: float = 0.0
    z_kp: float = 0.0
    z_damage_taken_share: float = 0.0
    weighted_z: float = 0.0
    
    # === SCORES INTERMÉDIAIRES COMBAT ===
    kp_score: float = 0.0
    death_score: float = 0.0
    kda_score: float = 0.0
    tank_efficiency_score: float = 0.0
    
    # === SCORES INTERMÉDIAIRES ÉCONOMIE ===
    dpg_score: float = 0.0
    efficiency_score: float = 0.0
    cs_score: float = 0.0
    
    # === SCORES INTERMÉDIAIRES OBJECTIFS ===
    vision_score: float = 0.0
    turret_score: float = 0.0
    obj_damage_score: float = 0.0
    pink_score: float = 0.0
    obj_participation_score: float = 0.0
    dragon_score: float = 0.0
    baron_score: float = 0.0
    turrets_killed_score: float = 0.0
    tower_participation_score: float = 0.0
    
    # === SCORES INTERMÉDIAIRES TEMPO ===
    gpm_relative_score: float = 0.0
    dpm_relative_score: float = 0.0
    fb_score: float = 0.0
    ft_score: float = 0.0
    gold_15_score: float = 0.0
    cs_15_score: float = 0.0
    solo_kills_score: float = 0.0
    early_pressure_score: float = 0.0
    
    
    # === SCORES INTERMÉDIAIRES IMPACT ===
    advantage_score: float = 0.0
    contribution_to_lead: float = 0.0
    
    # === POIDS FINAUX ===
    final_combat_weight: float = 0.0
    final_economic_weight: float = 0.0
    final_objective_weight: float = 0.0
    final_tempo_weight: float = 0.0
    final_impact_weight: float = 0.0
    
    # === SCORES FINAUX ===
    zscore_score: float = 5.0
    combat_value: float = 0.0
    economic_efficiency: float = 0.0
    objective_contribution: float = 0.0
    pace_rating: float = 0.0
    win_impact: float = 0.0
    breakdown_score: float = 5.0


# =============================================================================
# CONSTANTES - BASELINES Z-SCORE
# =============================================================================

ROLE_BASELINES: Dict[Role, RoleStats] = {
    Role.TOP: RoleStats(
        kills=(5.5, 2.5), deaths=(5.0, 2.0), assists=(6.0, 3.0),
        kda=(2.5, 1.2), cs_per_min=(7.0, 1.5), damage_per_min=(600, 200),
        damage_share=(0.22, 0.06), gold_per_min=(400, 80),
        vision_score_per_min=(0.8, 0.3), kp=(0.50, 0.15),
        damage_taken_share=(0.25, 0.08),
    ),
    Role.JUNGLE: RoleStats(
        kills=(6.0, 3.0), deaths=(5.5, 2.0), assists=(8.0, 3.5),
        kda=(2.8, 1.3), cs_per_min=(5.5, 1.2), damage_per_min=(500, 180),
        damage_share=(0.18, 0.05), gold_per_min=(380, 75),
        vision_score_per_min=(1.0, 0.4), kp=(0.60, 0.12),
        damage_taken_share=(0.22, 0.07),
    ),
    Role.MID: RoleStats(
        kills=(6.5, 3.0), deaths=(4.5, 2.0), assists=(6.5, 3.0),
        kda=(3.0, 1.5), cs_per_min=(7.5, 1.5), damage_per_min=(650, 220),
        damage_share=(0.25, 0.07), gold_per_min=(420, 85),
        vision_score_per_min=(0.7, 0.3), kp=(0.55, 0.12),
        damage_taken_share=(0.18, 0.06),
    ),
    Role.ADC: RoleStats(
        kills=(7.0, 3.5), deaths=(5.0, 2.0), assists=(7.0, 3.0),
        kda=(3.0, 1.5), cs_per_min=(8.0, 1.5), damage_per_min=(700, 250),
        damage_share=(0.28, 0.08), gold_per_min=(430, 90),
        vision_score_per_min=(0.6, 0.25), kp=(0.60, 0.12),
        damage_taken_share=(0.15, 0.05),
    ),
    Role.SUPPORT: RoleStats(
        kills=(2.0, 1.5), deaths=(5.5, 2.0), assists=(11.0, 4.0),
        kda=(2.8, 1.5), cs_per_min=(1.2, 0.8), damage_per_min=(250, 120),
        damage_share=(0.08, 0.03), gold_per_min=(260, 50),
        vision_score_per_min=(2.0, 0.6), kp=(0.65, 0.12),
        damage_taken_share=(0.18, 0.06),
    ),
}

ROLE_WEIGHTS: Dict[Role, Dict[str, float]] = {
    Role.TOP: {
        'kda': 0.15, 'cs_per_min': 0.15, 'damage_per_min': 0.20,
        'damage_share': 0.15, 'gold_per_min': 0.10, 'vision_score_per_min': 0.05,
        'kp': 0.10, 'damage_taken_share': 0.10,
    },
    Role.JUNGLE: {
        'kda': 0.15, 'cs_per_min': 0.10, 'damage_per_min': 0.15,
        'damage_share': 0.10, 'gold_per_min': 0.10, 'vision_score_per_min': 0.15,
        'kp': 0.20, 'damage_taken_share': 0.05,
    },
    Role.MID: {
        'kda': 0.15, 'cs_per_min': 0.15, 'damage_per_min': 0.25,
        'damage_share': 0.15, 'gold_per_min': 0.10, 'vision_score_per_min': 0.05,
        'kp': 0.10, 'damage_taken_share': 0.05,
    },
    Role.ADC: {
        'kda': 0.15, 'cs_per_min': 0.20, 'damage_per_min': 0.25,
        'damage_share': 0.15, 'gold_per_min': 0.10, 'vision_score_per_min': 0.05,
        'kp': 0.10, 'damage_taken_share': 0.00,
    },
    Role.SUPPORT: {
        'kda': 0.10, 'cs_per_min': 0.00, 'damage_per_min': 0.05,
        'damage_share': 0.00, 'gold_per_min': 0.05, 'vision_score_per_min': 0.35,
        'kp': 0.30, 'damage_taken_share': 0.15,
    },
}

DIMENSION_WEIGHTS: Dict[Role, Dict[str, float]] = {
    Role.TOP: {
        'combat_value': 0.25, 'economic_efficiency': 0.20,
        'objective_contribution': 0.15, 'pace_rating': 0.15, 'win_impact': 0.25,
    },
    Role.JUNGLE: {
        'combat_value': 0.20, 'economic_efficiency': 0.15,
        'objective_contribution': 0.30, 'pace_rating': 0.15, 'win_impact': 0.20,
    },
    Role.MID: {
        'combat_value': 0.25, 'economic_efficiency': 0.25,
        'objective_contribution': 0.10, 'pace_rating': 0.15, 'win_impact': 0.25,
    },
    Role.ADC: {
        'combat_value': 0.20, 'economic_efficiency': 0.30,
        'objective_contribution': 0.10, 'pace_rating': 0.15, 'win_impact': 0.25,
    },
    Role.SUPPORT: {
        'combat_value': 0.15, 'economic_efficiency': 0.10,
        'objective_contribution': 0.25, 'pace_rating': 0.20, 'win_impact': 0.30,
    },
    Role.UNKNOWN: {
        'combat_value': 0.20, 'economic_efficiency': 0.20,
        'objective_contribution': 0.20, 'pace_rating': 0.20, 'win_impact': 0.20,
    },
}


# =============================================================================
# BASELINES BREAKDOWN - Harmonisées avec Z-Score
# =============================================================================

BREAKDOWN_BASELINES: Dict[str, Dict[str, Tuple[float, float]]] = {
    'kp': {'min': 0.30, 'max': 0.80},
    'death_share': {'min': 0.10, 'max': 0.40},
    'kda': {'min': 1.0, 'max': 6.0},
    'dpg': {'min': 1.0, 'max': 3.0},
    'efficiency': {'min': 0.4, 'max': 1.4},
    'cs_ratio': {'min': 0.5, 'max': 1.2},
    'vision_ratio': {'min': 0.5, 'max': 1.5},
    'turret_damage': {'min': 0, 'max': 8000},
    'obj_damage': {'min': 0, 'max': 20000},
    'pink_ratio': {'min': 0.3, 'max': 1.5},
    'obj_participation': {'min': 0.1, 'max': 0.6},
    'dragon': {'min': 0, 'max': 4},
    'baron': {'min': 0, 'max': 2},
    'turrets_killed': {'min': 0, 'max': 4},
    'tower_participation': {'min': 0, 'max': 5},
    'resource_ratio': {'min': 0.7, 'max': 1.3},
    'gold_diff_15': {'min': -1500, 'max': 1500},
    'cs_diff_15': {'min': -30, 'max': 30},
    'solo_kills': {'min': 0, 'max': 3},
    'gold_advantage': {'min': -0.2, 'max': 0.2},
    'tank_efficiency': {'min': 1.0, 'max': 4.0},
    'contribution_to_lead' : {'min': 0.70, 'max': 1.30},

}

EXPECTED_CS_BY_ROLE: Dict[str, float] = {
    'ADC': 8.0, 'MID': 8.0, 'TOP': 7.0, 'JUNGLE': 5.5, 'SUPPORT': 1.5, 'UNKNOWN': 6.0,
}

EXPECTED_VISION_BY_ROLE: Dict[Role, float] = {
    Role.SUPPORT: 2.5, Role.JUNGLE: 1.2, Role.TOP: 0.9,
    Role.MID: 0.8, Role.ADC: 0.6, Role.UNKNOWN: 1.0,
}

EXPECTED_PINKS_BY_ROLE: Dict[Role, int] = {
    Role.SUPPORT: 4, Role.JUNGLE: 3, Role.TOP: 2,
    Role.MID: 2, Role.ADC: 1, Role.UNKNOWN: 2,
}


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def normalize_position(position: str) -> Role:
    """Normalise le nom de la position vers l'enum Role."""
    if not position:
        return Role.UNKNOWN
    mapping = {
        "TOP": Role.TOP,
        "JUNGLE": Role.JUNGLE, "JGL": Role.JUNGLE,
        "MIDDLE": Role.MID, "MID": Role.MID,
        "BOTTOM": Role.ADC, "ADC": Role.ADC,
        "UTILITY": Role.SUPPORT, "SUPPORT": Role.SUPPORT, "SUPP": Role.SUPPORT,
    }
    return mapping.get(position.upper(), Role.UNKNOWN)


def calculate_z_score(value: float, mean: float, std: float) -> float:
    """Calcule le z-score d'une valeur."""
    if std == 0 or std is None:
        return 0.0
    return max(-3.0, min(3.0, (value - mean) / std))


def sigmoid_transform(weighted_z: float, k: float = 1.2) -> float:
    """Transforme un z-score pondéré en score 1-10 via une sigmoïde."""
    return 1 + 9 / (1 + math.exp(-k * weighted_z))


def linear_scale(value: float, min_val: float, max_val: float,
                 out_min: float = 0, out_max: float = 10) -> float:
    """Scale linéaire avec clamp."""
    if max_val == min_val:
        return (out_min + out_max) / 2
    scaled = (value - min_val) / (max_val - min_val) * (out_max - out_min) + out_min
    return max(out_min, min(out_max, scaled))


def linear_scale_adjusted(value: float, min_val: float, max_val: float,
                          multiplier: float = 1.0,
                          out_min: float = 0, out_max: float = 10) -> float:
    """
    Scale linéaire avec bornes ajustées par un multiplicateur.
    
    HARMONISATION: Cette fonction applique la même logique que le z-score:
    - Z-Score: baseline ajustée = baseline * mult
    - Breakdown: bornes ajustées = bornes * mult
    """
    adj_min = min_val * multiplier
    adj_max = max_val * multiplier
    
    if adj_max == adj_min:
        return (out_min + out_max) / 2
    
    scaled = (value - adj_min) / (adj_max - adj_min) * (out_max - out_min) + out_min
    return max(out_min, min(out_max, scaled))


def linear_scale_inverted_adjusted(value: float, min_val: float, max_val: float,
                                   multiplier: float = 1.0,
                                   out_min: float = 0, out_max: float = 10) -> float:
    """
    Scale linéaire inversé avec bornes ajustées.
    Utilisé pour les métriques où moins = mieux (death_share pour non-tanks).
    """
    adj_min = min_val * multiplier
    adj_max = max_val * multiplier
    
    if adj_max == adj_min:
        return (out_min + out_max) / 2
    
    scaled = (adj_max - value) / (adj_max - adj_min) * (out_max - out_min) + out_min
    return max(out_min, min(out_max, scaled))


# =============================================================================
# MIXIN PRINCIPAL
# =============================================================================

class ScoringMixin:
    """Mixin de scoring pour MatchLol."""
    
    def _extract_objective_participations_from_timeline(self):
        """Credit all recorded participants equally, in display order."""
        count = len(self.thisKillsListe)
        names = ('thisObjectivesParticipatedListe', 'thisDragonParticipationListe',
                 'thisBaronParticipationListe', 'thisHeraldParticipationListe',
                 'thisTowerParticipationListe', 'thisFirstObjectiveBonusListe')
        for name in names:
            setattr(self, name, [0.0] * count)
        self.thisTotalObjectives = 0.0
        self.scoring_objective_opportunities = {100: {'epic': 0, 'tower': 0}, 200: {'epic': 0, 'tower': 0}}
        self.scoring_objective_presence = [{'epic': 0, 'tower': 0} for _ in range(count)]
        id_teams = {p.get('participantId'): p.get('teamId') for p in
                    getattr(self, 'match_detail', {}).get('info', {}).get('participants', [])}
        mapping = participant_indices(self)
        timeline = getattr(self, 'data_timeline', None)
        frames = timeline.get('info', {}).get('frames', []) if isinstance(timeline, dict) else []
        weights = {'DRAGON': 1.0, 'BARON_NASHOR': 2.0, 'BARON': 2.0,
                   'RIFTHERALD': 1.0, 'HORDE': 0.5, 'ATAKHAN': 2.0}
        lists = {'DRAGON': 'thisDragonParticipationListe', 'BARON_NASHOR': 'thisBaronParticipationListe',
                 'BARON': 'thisBaronParticipationListe', 'RIFTHERALD': 'thisHeraldParticipationListe',
                 'TOWER': 'thisTowerParticipationListe'}
        for frame in frames:
            for event in frame.get('events', []):
                kind = event.get('type')
                if kind == 'ELITE_MONSTER_KILL':
                    objective = event.get('monsterType')
                    weight = weights.get(objective, 0)
                elif kind == 'BUILDING_KILL' and event.get('buildingType') == 'TOWER_BUILDING':
                    objective, weight = 'TOWER', 0.5
                else:
                    continue
                if not weight:
                    continue
                self.thisTotalObjectives += weight
                participants = set(event.get('assistingParticipantIds') or [])
                participants.add(event.get('killerId'))
                team = id_teams.get(event.get('killerId'))
                if team not in (100, 200):
                    team = next((id_teams.get(pid) for pid in participants if id_teams.get(pid) in (100, 200)), None)
                if team not in (100, 200):
                    team = (300-event['teamId'] if objective == 'TOWER' and event.get('teamId') in (100, 200)
                            else event.get('killerTeamId'))
                category = 'tower' if objective == 'TOWER' else 'epic'
                if team in (100, 200):
                    self.scoring_objective_opportunities[team][category] += 1
                for pid in participants:
                    index = mapping.get(pid)
                    if index is not None:
                        if team in (100, 200) and id_teams.get(pid) == team:
                            self.scoring_objective_presence[index][category] += 1
                        self.thisObjectivesParticipatedListe[index] += weight
                        if objective in lists:
                            getattr(self, lists[objective])[index] += 1
        # No last-hit bonus: a jungler smiting an objective does not invalidate
        # the contribution of allies present in Riot's assistingParticipantIds.

    def _init_scoring_attributes(self):
        """Initialise les attributs de scoring."""
        self.scores_liste = []
        self.raw_scores_liste = []
        self.mvp_indices = []
        self.ace_indices = []
        self.breakdowns_liste = []
        self.player_metrics_liste: List[PlayerMetrics] = []
        self.mvp_index = -1
        self.ace_index = -1
        self.player_score = 5.0
        self.player_rank = 5
        self.player_breakdown = None

    def _build_player_metrics(self, i: int) -> PlayerMetrics:
        """Construit l'objet PlayerMetrics avec toutes les métriques calculées une seule fois."""
        metrics = PlayerMetrics(player_index=i)
        
        # === IDENTITÉ ===
        metrics.champion = self.thisChampNameListe[i] if i < len(self.thisChampNameListe) else ""
        metrics.role = self.thisPositionListe[i] if i < len(self.thisPositionListe) else "UNKNOWN"
        metrics.role_enum = normalize_position(metrics.role)
        metrics.role = metrics.role_enum.value
        if metrics.role_enum == Role.UNKNOWN:
            metrics.role_enum = Role.MID
        
        # === STATS BRUTES ===
        metrics.kills = self.thisKillsListe[i]
        metrics.deaths = self.thisDeathsListe[i]
        metrics.assists = self.thisAssistsListe[i]
        metrics.cs = self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]
        metrics.damage = self.thisDamageListe[i]
        metrics.gold = self.thisGoldListe[i]
        metrics.vision = self.thisVisionListe[i]
        metrics.damage_taken = self.thisDamageTakenListe[i]
        
        if hasattr(self, 'thisDamageTurretsListe') and i < len(self.thisDamageTurretsListe):
            metrics.turret_damage = self.thisDamageTurretsListe[i]
        if hasattr(self, 'thisDamageObjectivesListe') and i < len(self.thisDamageObjectivesListe):
            metrics.objective_damage = self.thisDamageObjectivesListe[i]
        if hasattr(self, 'thisTurretsKillsPersoListe') and i < len(self.thisTurretsKillsPersoListe):
            metrics.turrets_killed = self.thisTurretsKillsPersoListe[i]
        if hasattr(self, 'thisPinkListe') and i < len(self.thisPinkListe):
            metrics.pinks = self.thisPinkListe[i]
        
        # === STATS D'ÉQUIPE ===
        if i < 5:
            metrics.team_kills = max(getattr(self, 'thisTeamKills', 1), 1)
            metrics.team_deaths = max(sum(self.thisDeathsListe[:5]), 1)
            metrics.team_damage = max(getattr(self, 'thisDamage_team1', 1), 1)
            metrics.team_tank = max(getattr(self, 'thisTank_team1', 1), 1)
            metrics.team_gold = max(getattr(self, 'thisGold_team1', 1), 1)
            metrics.enemy_gold = max(getattr(self, 'thisGold_team2', 1), 1)
        else:
            metrics.team_kills = max(getattr(self, 'thisTeamKillsOp', 1), 1)
            metrics.team_deaths = max(sum(self.thisDeathsListe[5:]), 1)
            metrics.team_damage = max(getattr(self, 'thisDamage_team2', 1), 1)
            metrics.team_tank = max(getattr(self, 'thisTank_team2', 1), 1)
            metrics.team_gold = max(getattr(self, 'thisGold_team2', 1), 1)
            metrics.enemy_gold = max(getattr(self, 'thisGold_team1', 1), 1)
        
        # === MÉTRIQUES DÉRIVÉES ===
        metrics.game_minutes = game_minutes(self)
        metrics.cs_per_min = metrics.cs / metrics.game_minutes
        metrics.damage_per_min = metrics.damage / metrics.game_minutes
        metrics.gold_per_min = metrics.gold / metrics.game_minutes
        metrics.vision_per_min = metrics.vision / metrics.game_minutes
        metrics.damage_share = metrics.damage / metrics.team_damage
        metrics.damage_taken_share = metrics.damage_taken / metrics.team_tank
        metrics.kp = min(1.0, (metrics.kills + metrics.assists) / metrics.team_kills)
        metrics.death_share = metrics.deaths / max(metrics.team_deaths, 1)
        metrics.gold_share = metrics.gold / metrics.team_gold
        metrics.dpg = metrics.damage / max(metrics.gold, 1)
        
        metrics.kda = (metrics.kills + metrics.assists) / max(metrics.deaths, 1)
        metrics.observed_team_kills = sum(self.thisKillsListe[(0 if i < 5 else 5):(5 if i < 5 else 10)])
        metrics.timeline_available = getattr(self, 'scoring_timeline_available', False)
        team = getattr(self, 'thisTeamIdListe', [100]*5+[200]*5)[i]
        metrics.objective_opportunities = dict(getattr(self, 'scoring_objective_opportunities', {}).get(team, {}))
        presence = getattr(self, 'scoring_objective_presence', [])
        metrics.objective_presence = dict(presence[i]) if i < len(presence) else {}
        metrics.scoring_supported = metrics.role != 'UNKNOWN' and getattr(self, 'thisQ', '') in ('RANKED', 'FLEX', 'NORMAL', 'SWIFTPLAY', 'CLASH')
        participants = getattr(self, 'scoring_participants', [])
        if i < len(participants):
            participant = participants[i]
            metrics.ally_healing = participant.get('totalHealsOnTeammates')
            metrics.ally_shielding = participant.get('totalDamageShieldedOnTeammates')
            metrics.cc_seconds = participant.get('timeCCingOthers')
        
        # === OBJECTIFS (TIMELINE) ===
        if hasattr(self, 'thisObjectivesParticipatedListe') and i < len(self.thisObjectivesParticipatedListe):
            metrics.objectives_participated = self.thisObjectivesParticipatedListe[i]
        if hasattr(self, 'thisDragonParticipationListe') and i < len(self.thisDragonParticipationListe):
            metrics.dragon_participation = self.thisDragonParticipationListe[i]
        if hasattr(self, 'thisBaronParticipationListe') and i < len(self.thisBaronParticipationListe):
            metrics.baron_participation = self.thisBaronParticipationListe[i]
        if hasattr(self, 'thisHeraldParticipationListe') and i < len(self.thisHeraldParticipationListe):
            metrics.herald_participation = self.thisHeraldParticipationListe[i]
        if hasattr(self, 'thisTowerParticipationListe') and i < len(self.thisTowerParticipationListe):
            metrics.tower_participation = self.thisTowerParticipationListe[i]
        if hasattr(self, 'thisFirstObjectiveBonusListe') and i < len(self.thisFirstObjectiveBonusListe):
            metrics.first_objective_bonus = self.thisFirstObjectiveBonusListe[i]
        metrics.total_objectives = getattr(self, 'thisTotalObjectives', 0)
        
        # === EARLY GAME ===
        if hasattr(self, 'thisGoldAt15Liste') and i < len(self.thisGoldAt15Liste):
            metrics.gold_at_15 = self.thisGoldAt15Liste[i]
        if hasattr(self, 'thisCsAt15Liste') and i < len(self.thisCsAt15Liste):
            metrics.cs_at_15 = self.thisCsAt15Liste[i]
        if hasattr(self, 'thisSoloKillsListe') and i < len(self.thisSoloKillsListe):
            metrics.solo_kills = self.thisSoloKillsListe[i]
            metrics.early_solo_kills = self.thisEarlySoloKillsListe[i]
        
        if hasattr(self, 'firstBloodKillIndex') and self.firstBloodKillIndex == i:
            metrics.has_first_blood = True
        if hasattr(self, 'firstBloodAssistIndices') and i in getattr(self, 'firstBloodAssistIndices', []):
            metrics.has_first_blood_assist = True
        if hasattr(self, 'firstTowerKillIndex') and self.firstTowerKillIndex == i:
            metrics.has_first_tower = True
        if hasattr(self, 'firstTowerAssistIndices') and i in getattr(self, 'firstTowerAssistIndices', []):
            metrics.has_first_tower_assist = True
        
        metrics.opponent_index = self._find_lane_opponent(i)
        
        if metrics.opponent_index is not None:
            if hasattr(self, 'thisGoldAt15Liste') and metrics.opponent_index < len(self.thisGoldAt15Liste):
                metrics.gold_diff_15 = metrics.gold_at_15 - self.thisGoldAt15Liste[metrics.opponent_index]
            if hasattr(self, 'thisCsAt15Liste') and metrics.opponent_index < len(self.thisCsAt15Liste):
                metrics.cs_diff_15 = metrics.cs_at_15 - self.thisCsAt15Liste[metrics.opponent_index]
        
        if metrics.opponent_index is not None:
            opponent = metrics.opponent_index
            gold_available = getattr(self, 'thisEarlyGoldAvailableListe', [])
            cs_available = getattr(self, 'thisEarlyCsAvailableListe', [])
            metrics.gold_15_available = bool(gold_available and gold_available[i] and gold_available[opponent])
            metrics.cs_15_available = bool(cs_available and cs_available[i] and cs_available[opponent])

        # === PROFIL CHAMPION ===
        try:
            from fonctions.match.champion_profiles import (
                get_profile_for_champion,
                get_profile_adjustments,
                get_champion_tags,
            )
            
            metrics.champion_tags = get_champion_tags(metrics.champion) or []
            profile = get_profile_for_champion(metrics.champion, metrics.role)
            metrics.profile = profile.value if profile else 'UNKNOWN'
            
            adj = get_profile_adjustments(metrics.role, profile)
            metrics.dpm_mult = adj.damage_per_min_mult
            metrics.dmg_share_mult = adj.damage_share_mult
            metrics.cs_mult = adj.cs_per_min_mult
            metrics.gpm_mult = adj.gold_per_min_mult
            metrics.vision_mult = adj.vision_mult
            metrics.kp_mult = adj.kp_mult
            metrics.tank_mult = adj.damage_taken_share_mult
            metrics.combat_weight_adj = adj.combat_weight_adj
            metrics.economic_weight_adj = adj.economic_weight_adj
            metrics.objective_weight_adj = adj.objective_weight_adj
            metrics.tempo_weight_adj = adj.tempo_weight_adj
            metrics.impact_weight_adj = adj.impact_weight_adj
        except Exception:
            pass
        
        from .scoring_v4 import compute_utility
        compute_utility(metrics)
        return metrics

    def _calculate_zscores(self, metrics: PlayerMetrics):
        from .scoring_v4 import statistical_score
        statistical_score(metrics)

    def _calculate_breakdown_scores(self, metrics: PlayerMetrics):
        from .scoring_v4 import contribution_score, references
        start = 0 if metrics.player_index < 5 else 5
        expected = sum(references(m)['gold'] for m in self.player_metrics_liste[start:start+5])
        metrics.expected_gold_share = references(metrics)['gold']/expected if expected else .2
        metrics.gold_share_ratio = metrics.gold_share/metrics.expected_gold_share
        contribution_score(metrics)

    async def calculate_all_scores(self):
        """Calcule les scores de tous les joueurs."""
        self._init_scoring_attributes()
        
        if not hasattr(self, 'thisKillsListe') or not self.thisKillsListe:
            return
        
        extract_early_game(self)
        self._extract_objective_participations_from_timeline()
        
        nb_players = min(len(self.thisKillsListe), getattr(self, 'nb_joueur', 10))
        
        self.player_metrics_liste = [self._build_player_metrics(i) for i in range(nb_players)]
        for metrics in self.player_metrics_liste:
            self._calculate_zscores(metrics)
            self._calculate_breakdown_scores(metrics)
            
            metrics.performance_score = (
                STATISTICAL_WEIGHT * metrics.zscore_score +
                CONTRIBUTION_WEIGHT * metrics.breakdown_score)
            self.raw_scores_liste.append(metrics.performance_score)
            self.scores_liste.append(round(metrics.performance_score, 1))
            
            breakdown = ContributionBreakdown(
                combat_value=round(metrics.combat_value, 1),
                economic_efficiency=round(metrics.economic_efficiency, 1),
                objective_contribution=round(metrics.objective_contribution, 1),
                pace_rating=round(metrics.pace_rating, 1),
                win_impact=round(metrics.win_impact, 1),
                final_score=round(metrics.breakdown_score, 1)
            )
            self.breakdowns_liste.append(breakdown)
        
        self._identify_mvp_ace()
        
        if hasattr(self, 'thisId'):
            index = tracked_index(self)
            if 0 <= index < len(self.scores_liste):
                self.player_score = self.scores_liste[index]
                self.player_breakdown = self.breakdowns_liste[index]
                self.player_rank = self._get_player_rank(index)

    def _ranking_scores(self):
        raw = getattr(self, 'raw_scores_liste', [])
        return [round(v, 12) for v in (raw if len(raw) == len(self.scores_liste) else self.scores_liste)]

    def _identify_mvp_ace(self):
        """Equal full-precision scores share rank; IDs select a stable representative."""
        scores = self._ranking_scores()
        if not scores:
            return
        self.mvp_indices = [i for i, score in enumerate(scores) if score == max(scores)]
        ids = getattr(self, 'thisParticipantIdListe', list(range(len(scores))))
        self.mvp_index = min(self.mvp_indices, key=lambda i: ids[i])
        losing = list(range(5, len(scores))) if getattr(self, 'thisWinBool', False) else list(range(min(5, len(scores))))
        self.ace_indices = [i for i in losing if scores[i] == max(scores[j] for j in losing)] if losing else []
        self.ace_index = min(self.ace_indices, key=lambda i: ids[i]) if self.ace_indices else -1

    def _get_player_rank(self, player_index: int) -> int:
        scores = self._ranking_scores()
        if not 0 <= player_index < len(scores):
            return 5
        return 1 + sum(value > scores[player_index] for value in scores)

    def get_score_emoji(self, score: float) -> str:
        """Retourne un emoji basé sur le score."""
        if score >= 9.0:
            return '🏆'
        elif score >= 8.0:
            return '⭐'
        elif score >= 7.0:
            return '✅'
        elif score >= 5.0:
            return '➖'
        elif score >= 3.0:
            return '⚠️'
        else:
            return '❌'
    
    def get_rank_text(self, rank: int) -> str:
        """Retourne le texte du rang."""
        if rank == 1:
            return "MVP"
        elif rank <= 3:
            return f"Top {rank}"
        elif rank >= 9:
            return "Worst"
        else:
            return f"#{rank}"

    def get_performance_summary_for_player(self, player_index: int) -> dict:
        """Retourne un résumé de la performance pour un joueur spécifique."""
        if not hasattr(self, 'scores_liste') or player_index >= len(self.scores_liste):
            return {}
        
        if not hasattr(self, 'breakdowns_liste') or player_index >= len(self.breakdowns_liste):
            return {}
        
        score = self.scores_liste[player_index]
        breakdown = self.breakdowns_liste[player_index]
        rank = self._get_player_rank(player_index)
        
        best_dim, best_val = breakdown.get_best_dimension()
        worst_dim, worst_val = breakdown.get_weakest_dimension()
        
        return {
            'index': player_index,
            'team': 'blue' if getattr(self, 'thisTeamIdListe', [100] * 5 + [200] * 5)[player_index] == 100 else 'red',
            'role': self.thisPositionListe[player_index] if player_index < len(self.thisPositionListe) else 'UNKNOWN',
            'score': score,
            'scoring_version': SCORING_VERSION,
            'scoring_supported': self.player_metrics_liste[player_index].scoring_supported,
            'statistical_score': round(self.player_metrics_liste[player_index].zscore_score, 2),
            'contribution_score': round(self.player_metrics_liste[player_index].breakdown_score, 2),
            'utility_score': round(self.player_metrics_liste[player_index].utility_score, 2),
            'timeline_available': self.player_metrics_liste[player_index].timeline_available,
            'scoring_inputs': {
                'ally_healing': self.player_metrics_liste[player_index].ally_healing,
                'ally_shielding': self.player_metrics_liste[player_index].ally_shielding,
                'cc_seconds': self.player_metrics_liste[player_index].cc_seconds,
                'early_solo_kills': self.player_metrics_liste[player_index].early_solo_kills,
                'utility_available': self.player_metrics_liste[player_index].utility_available,
                'gold_15_available': self.player_metrics_liste[player_index].gold_15_available,
                'cs_15_available': self.player_metrics_liste[player_index].cs_15_available,
            },
            'rank': rank,
            'rank_text': self.get_rank_text(rank),
            'emoji': self.get_score_emoji(score),
            'best_dimension': best_dim,
            'best_dimension_score': best_val,
            'best_dimension_emoji': breakdown.get_badge_emoji(),
            'worst_dimension': worst_dim,
            'worst_dimension_score': worst_val,
            'is_mvp': player_index in self.mvp_indices,
            'is_ace': player_index in self.ace_indices,
            'breakdown': breakdown.to_dict()
        }

    def get_all_players_performance_summary(self) -> List[dict]:
        """Retourne un résumé de la performance pour tous les joueurs."""
        if not hasattr(self, 'scores_liste') or not self.scores_liste:
            return []
        
        return [
            self.get_performance_summary_for_player(i) 
            for i in range(len(self.scores_liste))
        ]

    def get_player_scoring_profile_summary(self, player_index: int) -> dict:
        """Retourne un résumé du profil de scoring appliqué à un joueur."""
        if hasattr(self, 'player_metrics_liste') and player_index < len(self.player_metrics_liste):
            m = self.player_metrics_liste[player_index]
            return {
                'champion': m.champion,
                'role': m.role,
                'tags': m.champion_tags,
                'profile': m.profile,
                'adjustments': {
                    'damage_per_min_mult': m.dpm_mult,
                    'damage_share_mult': m.dmg_share_mult,
                    'cs_per_min_mult': m.cs_mult,
                    'gold_per_min_mult': m.gpm_mult,
                    'vision_mult': m.vision_mult,
                    'kp_mult': m.kp_mult,
                    'damage_taken_share_mult': m.tank_mult,
                    'combat_weight_adj': m.combat_weight_adj,
                    'economic_weight_adj': m.economic_weight_adj,
                    'objective_weight_adj': m.objective_weight_adj,
                    'tempo_weight_adj': m.tempo_weight_adj,
                    'impact_weight_adj': m.impact_weight_adj,
                }
            }
        return {}


    def _find_lane_opponent(self, player_index: int) -> Optional[int]:
        """Trouve l'adversaire direct d'un joueur (même rôle, équipe adverse)."""
        if not hasattr(self, 'thisPositionListe') or player_index >= len(self.thisPositionListe):
            return None
        
        my_role = self.thisPositionListe[player_index].upper()
        if normalize_position(my_role) == Role.UNKNOWN:
            return None
        
        role_map = {'BOTTOM': 'ADC', 'UTILITY': 'SUPPORT', 'MIDDLE': 'MID'}
        my_role = role_map.get(my_role, my_role)
        
        if player_index < 5:
            search_range = range(5, 10)
        else:
            search_range = range(0, 5)
        
        for opp_index in search_range:
            if opp_index < len(self.thisPositionListe):
                opp_role = self.thisPositionListe[opp_index].upper()
                opp_role = role_map.get(opp_role, opp_role)
                if opp_role == my_role:
                    return opp_index
        
        return None

    async def save_player_scoring_data(self):
        """
        Sauvegarde TOUTES les données de scoring (métriques, intermédiaires, finaux) dans la BDD.
        À appeler après calculate_all_scores().
        """
        try:
            from fonctions.gestion_bdd import requete_perso_bdd
            
            match_id = getattr(self, 'last_match', None)
            if not match_id:
                return
            
            if not hasattr(self, 'player_metrics_liste') or not self.player_metrics_liste:
                return
            
            for metrics in self.player_metrics_liste:
                riot_id = self.thisRiotIdListe[metrics.player_index] if metrics.player_index < len(self.thisRiotIdListe) else ''
                riot_tag = self.thisRiotTagListe[metrics.player_index] if metrics.player_index < len(self.thisRiotTagListe) else ''
                tags_str = '{' + ','.join(metrics.champion_tags) + '}' if metrics.champion_tags else '{}'
                
                query = """
                    INSERT INTO match_player_scoring_data (
                        match_id, player_index, riot_id, riot_tag, champion, role,
                        kills, deaths, assists, cs, damage, gold, vision, damage_taken,
                        turret_damage, objective_damage, turrets_killed, pinks,
                        team_kills, team_deaths, team_damage, team_tank, team_gold, enemy_gold,
                        game_minutes, cs_per_min, damage_per_min, gold_per_min, vision_per_min,
                        damage_share, damage_taken_share, kp, kda, death_share, gold_share, dpg,
                        objectives_participated, dragon_participation, baron_participation,
                        herald_participation, tower_participation, first_objective_bonus,
                        gold_at_15, cs_at_15, gold_diff_15, cs_diff_15,
                        has_first_blood, has_first_blood_assist, has_first_tower, has_first_tower_assist,
                        solo_kills,
                        champion_tags, profile,
                        dpm_mult, dmg_share_mult, cs_mult, gpm_mult, vision_mult, kp_mult, tank_mult,
                        combat_weight_adj, economic_weight_adj, objective_weight_adj,
                        tempo_weight_adj, impact_weight_adj,
                        z_kda, z_cs_per_min, z_damage_per_min, z_damage_share,
                        z_gold_per_min, z_vision_per_min, z_kp, z_damage_taken_share, weighted_z,
                        kp_score, death_score, kda_score,
                        dpg_score, efficiency_score, cs_score,
                        vision_score, turret_score, obj_damage_score, pink_score,
                        obj_participation_score, dragon_score, baron_score,
                        turrets_killed_score, tower_participation_score,
                        gpm_relative_score, dpm_relative_score, fb_score, ft_score,
                        gold_15_score, cs_15_score, solo_kills_score, early_pressure_score,
                        advantage_score, contribution_to_lead,
                        final_combat_weight, final_economic_weight, final_objective_weight,
                        final_tempo_weight, final_impact_weight,
                        zscore_score, combat_value, economic_efficiency, objective_contribution,
                        pace_rating, win_impact, breakdown_score, tank_efficiency_score,
                        gold_share_ratio, expected_gold_share
                    ) VALUES (
                        :match_id, :player_index, :riot_id, :riot_tag, :champion, :role,
                        :kills, :deaths, :assists, :cs, :damage, :gold, :vision, :damage_taken,
                        :turret_damage, :objective_damage, :turrets_killed, :pinks,
                        :team_kills, :team_deaths, :team_damage, :team_tank, :team_gold, :enemy_gold,
                        :game_minutes, :cs_per_min, :damage_per_min, :gold_per_min, :vision_per_min,
                        :damage_share, :damage_taken_share, :kp, :kda, :death_share, :gold_share, :dpg,
                        :objectives_participated, :dragon_participation, :baron_participation,
                        :herald_participation, :tower_participation, :first_objective_bonus,
                        :gold_at_15, :cs_at_15, :gold_diff_15, :cs_diff_15,
                        :has_first_blood, :has_first_blood_assist, :has_first_tower, :has_first_tower_assist,
                        :solo_kills,
                        :champion_tags, :profile,
                        :dpm_mult, :dmg_share_mult, :cs_mult, :gpm_mult, :vision_mult, :kp_mult, :tank_mult,
                        :combat_weight_adj, :economic_weight_adj, :objective_weight_adj,
                        :tempo_weight_adj, :impact_weight_adj,
                        :z_kda, :z_cs_per_min, :z_damage_per_min, :z_damage_share,
                        :z_gold_per_min, :z_vision_per_min, :z_kp, :z_damage_taken_share, :weighted_z,
                        :kp_score, :death_score, :kda_score,
                        :dpg_score, :efficiency_score, :cs_score,
                        :vision_score, :turret_score, :obj_damage_score, :pink_score,
                        :obj_participation_score, :dragon_score, :baron_score,
                        :turrets_killed_score, :tower_participation_score,
                        :gpm_relative_score, :dpm_relative_score, :fb_score, :ft_score,
                        :gold_15_score, :cs_15_score, :solo_kills_score, :early_pressure_score,
                        :advantage_score, :contribution_to_lead,
                        :final_combat_weight, :final_economic_weight, :final_objective_weight,
                        :final_tempo_weight, :final_impact_weight,
                        :zscore_score, :combat_value, :economic_efficiency, :objective_contribution,
                        :pace_rating, :win_impact, :breakdown_score, :tank_efficiency_score,
                        :gold_share_ratio, :expected_gold_share
                    )
                    ON CONFLICT (match_id, player_index) DO UPDATE SET
                        riot_id = EXCLUDED.riot_id, riot_tag = EXCLUDED.riot_tag,
                        champion = EXCLUDED.champion, role = EXCLUDED.role,
                        kills = EXCLUDED.kills, deaths = EXCLUDED.deaths, assists = EXCLUDED.assists,
                        cs = EXCLUDED.cs, damage = EXCLUDED.damage, gold = EXCLUDED.gold,
                        vision = EXCLUDED.vision, damage_taken = EXCLUDED.damage_taken,
                        turret_damage = EXCLUDED.turret_damage, objective_damage = EXCLUDED.objective_damage,
                        turrets_killed = EXCLUDED.turrets_killed, pinks = EXCLUDED.pinks,
                        team_kills = EXCLUDED.team_kills, team_deaths = EXCLUDED.team_deaths,
                        team_damage = EXCLUDED.team_damage, team_tank = EXCLUDED.team_tank,
                        team_gold = EXCLUDED.team_gold, enemy_gold = EXCLUDED.enemy_gold,
                        game_minutes = EXCLUDED.game_minutes, cs_per_min = EXCLUDED.cs_per_min,
                        damage_per_min = EXCLUDED.damage_per_min, gold_per_min = EXCLUDED.gold_per_min,
                        vision_per_min = EXCLUDED.vision_per_min, damage_share = EXCLUDED.damage_share,
                        damage_taken_share = EXCLUDED.damage_taken_share, kp = EXCLUDED.kp,
                        kda = EXCLUDED.kda, death_share = EXCLUDED.death_share,
                        gold_share = EXCLUDED.gold_share, dpg = EXCLUDED.dpg,
                        objectives_participated = EXCLUDED.objectives_participated,
                        dragon_participation = EXCLUDED.dragon_participation,
                        baron_participation = EXCLUDED.baron_participation,
                        herald_participation = EXCLUDED.herald_participation,
                        tower_participation = EXCLUDED.tower_participation,
                        first_objective_bonus = EXCLUDED.first_objective_bonus,
                        gold_at_15 = EXCLUDED.gold_at_15, cs_at_15 = EXCLUDED.cs_at_15,
                        gold_diff_15 = EXCLUDED.gold_diff_15, cs_diff_15 = EXCLUDED.cs_diff_15,
                        has_first_blood = EXCLUDED.has_first_blood,
                        has_first_blood_assist = EXCLUDED.has_first_blood_assist,
                        has_first_tower = EXCLUDED.has_first_tower,
                        has_first_tower_assist = EXCLUDED.has_first_tower_assist,
                        solo_kills = EXCLUDED.solo_kills,
                        champion_tags = EXCLUDED.champion_tags, profile = EXCLUDED.profile,
                        dpm_mult = EXCLUDED.dpm_mult, dmg_share_mult = EXCLUDED.dmg_share_mult,
                        cs_mult = EXCLUDED.cs_mult, gpm_mult = EXCLUDED.gpm_mult,
                        vision_mult = EXCLUDED.vision_mult, kp_mult = EXCLUDED.kp_mult,
                        tank_mult = EXCLUDED.tank_mult,
                        combat_weight_adj = EXCLUDED.combat_weight_adj,
                        economic_weight_adj = EXCLUDED.economic_weight_adj,
                        objective_weight_adj = EXCLUDED.objective_weight_adj,
                        tempo_weight_adj = EXCLUDED.tempo_weight_adj,
                        impact_weight_adj = EXCLUDED.impact_weight_adj,
                        z_kda = EXCLUDED.z_kda, z_cs_per_min = EXCLUDED.z_cs_per_min,
                        z_damage_per_min = EXCLUDED.z_damage_per_min,
                        z_damage_share = EXCLUDED.z_damage_share,
                        z_gold_per_min = EXCLUDED.z_gold_per_min,
                        z_vision_per_min = EXCLUDED.z_vision_per_min,
                        z_kp = EXCLUDED.z_kp, z_damage_taken_share = EXCLUDED.z_damage_taken_share,
                        weighted_z = EXCLUDED.weighted_z,
                        kp_score = EXCLUDED.kp_score, death_score = EXCLUDED.death_score,
                        kda_score = EXCLUDED.kda_score, dpg_score = EXCLUDED.dpg_score,
                        efficiency_score = EXCLUDED.efficiency_score, cs_score = EXCLUDED.cs_score,
                        vision_score = EXCLUDED.vision_score, turret_score = EXCLUDED.turret_score,
                        obj_damage_score = EXCLUDED.obj_damage_score, pink_score = EXCLUDED.pink_score,
                        obj_participation_score = EXCLUDED.obj_participation_score,
                        dragon_score = EXCLUDED.dragon_score, baron_score = EXCLUDED.baron_score,
                        turrets_killed_score = EXCLUDED.turrets_killed_score,
                        tower_participation_score = EXCLUDED.tower_participation_score,
                        gpm_relative_score = EXCLUDED.gpm_relative_score,
                        dpm_relative_score = EXCLUDED.dpm_relative_score,
                        fb_score = EXCLUDED.fb_score, ft_score = EXCLUDED.ft_score,
                        gold_15_score = EXCLUDED.gold_15_score, cs_15_score = EXCLUDED.cs_15_score,
                        solo_kills_score = EXCLUDED.solo_kills_score,
                        early_pressure_score = EXCLUDED.early_pressure_score,
                        advantage_score = EXCLUDED.advantage_score,
                        contribution_to_lead = EXCLUDED.contribution_to_lead,
                        final_combat_weight = EXCLUDED.final_combat_weight,
                        final_economic_weight = EXCLUDED.final_economic_weight,
                        final_objective_weight = EXCLUDED.final_objective_weight,
                        final_tempo_weight = EXCLUDED.final_tempo_weight,
                        final_impact_weight = EXCLUDED.final_impact_weight,
                        zscore_score = EXCLUDED.zscore_score, combat_value = EXCLUDED.combat_value,
                        economic_efficiency = EXCLUDED.economic_efficiency,
                        objective_contribution = EXCLUDED.objective_contribution,
                        pace_rating = EXCLUDED.pace_rating, win_impact = EXCLUDED.win_impact,
                        breakdown_score = EXCLUDED.breakdown_score,
                        tank_efficiency_score = EXCLUDED.tank_efficiency_score,
                        gold_share_ratio = EXCLUDED.gold_share_ratio,
                        expected_gold_share = EXCLUDED.expected_gold_share
                """
                
                params = {
                    'match_id': match_id,
                    'player_index': storage_index(self, metrics.player_index),
                    'riot_id': riot_id,
                    'riot_tag': riot_tag,
                    'champion': metrics.champion,
                    'role': metrics.role,
                    'kills': metrics.kills,
                    'deaths': metrics.deaths,
                    'assists': metrics.assists,
                    'cs': metrics.cs,
                    'damage': metrics.damage,
                    'gold': metrics.gold,
                    'vision': metrics.vision,
                    'damage_taken': metrics.damage_taken,
                    'turret_damage': metrics.turret_damage,
                    'objective_damage': metrics.objective_damage,
                    'turrets_killed': metrics.turrets_killed,
                    'pinks': metrics.pinks,
                    'team_kills': metrics.team_kills,
                    'team_deaths': metrics.team_deaths,
                    'team_damage': metrics.team_damage,
                    'team_tank': metrics.team_tank,
                    'team_gold': metrics.team_gold,
                    'enemy_gold': metrics.enemy_gold,
                    'game_minutes': round(metrics.game_minutes, 2),
                    'cs_per_min': round(metrics.cs_per_min, 2),
                    'damage_per_min': round(metrics.damage_per_min, 2),
                    'gold_per_min': round(metrics.gold_per_min, 2),
                    'vision_per_min': round(metrics.vision_per_min, 2),
                    'damage_share': round(metrics.damage_share, 4),
                    'damage_taken_share': round(metrics.damage_taken_share, 4),
                    'kp': round(metrics.kp, 4),
                    'kda': round(metrics.kda, 2),
                    'death_share': round(metrics.death_share, 4),
                    'gold_share': round(metrics.gold_share, 4),
                    'dpg': round(metrics.dpg, 4),
                    'objectives_participated': round(metrics.objectives_participated, 2),
                    'dragon_participation': metrics.dragon_participation,
                    'baron_participation': metrics.baron_participation,
                    'herald_participation': metrics.herald_participation,
                    'tower_participation': round(metrics.tower_participation, 2),
                    'first_objective_bonus': round(metrics.first_objective_bonus, 2),
                    'gold_at_15': metrics.gold_at_15,
                    'cs_at_15': metrics.cs_at_15,
                    'gold_diff_15': metrics.gold_diff_15,
                    'cs_diff_15': metrics.cs_diff_15,
                    'has_first_blood': metrics.has_first_blood,
                    'has_first_blood_assist': metrics.has_first_blood_assist,
                    'has_first_tower': metrics.has_first_tower,
                    'has_first_tower_assist': metrics.has_first_tower_assist,
                    'solo_kills': metrics.solo_kills,
                    'champion_tags': tags_str,
                    'profile': metrics.profile,
                    'dpm_mult': round(metrics.dpm_mult, 4),
                    'dmg_share_mult': round(metrics.dmg_share_mult, 4),
                    'cs_mult': round(metrics.cs_mult, 4),
                    'gpm_mult': round(metrics.gpm_mult, 4),
                    'vision_mult': round(metrics.vision_mult, 4),
                    'kp_mult': round(metrics.kp_mult, 4),
                    'tank_mult': round(metrics.tank_mult, 4),
                    'combat_weight_adj': round(metrics.combat_weight_adj, 4),
                    'economic_weight_adj': round(metrics.economic_weight_adj, 4),
                    'objective_weight_adj': round(metrics.objective_weight_adj, 4),
                    'tempo_weight_adj': round(metrics.tempo_weight_adj, 4),
                    'impact_weight_adj': round(metrics.impact_weight_adj, 4),
                    'z_kda': round(metrics.z_kda, 4),
                    'z_cs_per_min': round(metrics.z_cs_per_min, 4),
                    'z_damage_per_min': round(metrics.z_damage_per_min, 4),
                    'z_damage_share': round(metrics.z_damage_share, 4),
                    'z_gold_per_min': round(metrics.z_gold_per_min, 4),
                    'z_vision_per_min': round(metrics.z_vision_per_min, 4),
                    'z_kp': round(metrics.z_kp, 4),
                    'z_damage_taken_share': round(metrics.z_damage_taken_share, 4),
                    'weighted_z': round(metrics.weighted_z, 4),
                    'kp_score': round(metrics.kp_score, 2),
                    'death_score': round(metrics.death_score, 2),
                    'kda_score': round(metrics.kda_score, 2),
                    'dpg_score': round(metrics.dpg_score, 2),
                    'efficiency_score': round(metrics.efficiency_score, 2),
                    'cs_score': round(metrics.cs_score, 2),
                    'vision_score': round(metrics.vision_score, 2),
                    'turret_score': round(metrics.turret_score, 2),
                    'obj_damage_score': round(metrics.obj_damage_score, 2),
                    'pink_score': round(metrics.pink_score, 2),
                    'obj_participation_score': round(metrics.obj_participation_score, 2),
                    'dragon_score': round(metrics.dragon_score, 2),
                    'baron_score': round(metrics.baron_score, 2),
                    'turrets_killed_score': round(metrics.turrets_killed_score, 2),
                    'tower_participation_score': round(metrics.tower_participation_score, 2),
                    'gpm_relative_score': round(metrics.gpm_relative_score, 2),
                    'dpm_relative_score': round(metrics.dpm_relative_score, 2),
                    'fb_score': round(metrics.fb_score, 2),
                    'ft_score': round(metrics.ft_score, 2),
                    'gold_15_score': round(metrics.gold_15_score, 2),
                    'cs_15_score': round(metrics.cs_15_score, 2),
                    'solo_kills_score': round(metrics.solo_kills_score, 2),
                    'early_pressure_score': round(metrics.early_pressure_score, 2),
                    'advantage_score': round(metrics.advantage_score, 2),
                    'contribution_to_lead': round(metrics.contribution_to_lead, 2),
                    'final_combat_weight': round(metrics.final_combat_weight, 4),
                    'final_economic_weight': round(metrics.final_economic_weight, 4),
                    'final_objective_weight': round(metrics.final_objective_weight, 4),
                    'final_tempo_weight': round(metrics.final_tempo_weight, 4),
                    'final_impact_weight': round(metrics.final_impact_weight, 4),
                    'zscore_score': round(metrics.zscore_score, 2),
                    'combat_value': round(metrics.combat_value, 2),
                    'economic_efficiency': round(metrics.economic_efficiency, 2),
                    'objective_contribution': round(metrics.objective_contribution, 2),
                    'pace_rating': round(metrics.pace_rating, 2),
                    'win_impact': round(metrics.win_impact, 2),
                    'breakdown_score': round(metrics.breakdown_score, 2),
                    'tank_efficiency_score' : round(metrics.tank_efficiency_score, 2),
                    'gold_share_ratio' : round(metrics.gold_share_ratio, 4),
                    'expected_gold_share' : round(metrics.expected_gold_share, 4)
                }
                
                requete_perso_bdd(query, params)
                
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des données de scoring: {e}")



    async def save_player_scoring_profiles(self):
            """
            Sauvegarde les profils et ratios appliqués à chaque joueur dans la BDD.
            
            À appeler après calculate_all_scores().
            Sauvegarde dans la table match_player_scoring_profile.
            """
            try:
                from fonctions.gestion_bdd import requete_perso_bdd
                from fonctions.match.champion_profiles import (
                    get_profile_for_champion,
                    get_profile_adjustments,
                    get_champion_tags,
                    load_champion_tags,
                    load_profile_adjustments,
                    ChampionProfile
                )
                
                # S'assurer que les caches sont chargés
                load_champion_tags()
                load_profile_adjustments()
                
                match_id = getattr(self, 'last_match', None)
                if not match_id:
                    return
                
                nb_players = min(len(self.thisKillsListe), 10)
                
                for i in range(nb_players):
                    # Infos joueur
                    riot_id = self.thisRiotIdListe[i] if i < len(self.thisRiotIdListe) else ''
                    riot_tag = self.thisRiotTagListe[i] if i < len(self.thisRiotTagListe) else ''
                    champion = self.thisChampNameListe[i] if i < len(self.thisChampNameListe) else ''
                    role = self.thisPositionListe[i] if i < len(self.thisPositionListe) else 'UNKNOWN'
                    
                    # Récupérer les tags et le profil
                    tags = get_champion_tags(champion)
                    tags_str = '{' + ','.join(tags) + '}' if tags else ''
                    profile = get_profile_for_champion(champion, role)
                    profile_str = profile.value if profile else 'UNKNOWN'
                    
                    # Récupérer les ajustements
                    adj = get_profile_adjustments(role, profile)
                    
                    # Calculer les poids finaux (après ajustement et normalisation)
                    base_weights = DIMENSION_WEIGHTS.get(normalize_position(role), DIMENSION_WEIGHTS[Role.UNKNOWN])
                    
                    adjusted_weights = {
                        'combat_value': max(0, base_weights['combat_value'] + adj.combat_weight_adj),
                        'economic_efficiency': max(0, base_weights['economic_efficiency'] + adj.economic_weight_adj),
                        'objective_contribution': max(0, base_weights['objective_contribution'] + adj.objective_weight_adj),
                        'pace_rating': max(0, base_weights['pace_rating'] + adj.tempo_weight_adj),
                        'win_impact': max(0, base_weights['win_impact'] + adj.impact_weight_adj),
                    }
                    
                    total_weight = sum(adjusted_weights.values())
                    if total_weight > 0:
                        final_weights = {k: v / total_weight for k, v in adjusted_weights.items()}
                    else:
                        final_weights = adjusted_weights
                    
                    # Score final
                    final_score = self.scores_liste[i] if i < len(self.scores_liste) else 0
                    
                    # Requête INSERT/UPDATE
                    query = """
                        INSERT INTO match_player_scoring_profile (
                            match_id, player_index, riot_id, riot_tag, champion, role,
                            champion_tags, profile,
                            damage_per_min_mult, damage_share_mult, cs_per_min_mult,
                            gold_per_min_mult, vision_mult, kp_mult, damage_taken_share_mult,
                            combat_weight_adj, economic_weight_adj, objective_weight_adj,
                            tempo_weight_adj, impact_weight_adj,
                            final_combat_weight, final_economic_weight, final_objective_weight,
                            final_tempo_weight, final_impact_weight,
                            final_score
                        ) VALUES (
                            :match_id, :player_index, :riot_id, :riot_tag, :champion, :role,
                            :champion_tags, :profile,
                            :dpm_mult, :dmg_share_mult, :cs_mult,
                            :gpm_mult, :vision_mult, :kp_mult, :tank_mult,
                            :combat_adj, :eco_adj, :obj_adj,
                            :tempo_adj, :impact_adj,
                            :final_combat, :final_eco, :final_obj,
                            :final_tempo, :final_impact,
                            :final_score
                        )
                        ON CONFLICT (match_id, player_index) DO UPDATE SET
                            riot_id = EXCLUDED.riot_id,
                            riot_tag = EXCLUDED.riot_tag,
                            champion = EXCLUDED.champion,
                            role = EXCLUDED.role,
                            champion_tags = EXCLUDED.champion_tags,
                            profile = EXCLUDED.profile,
                            damage_per_min_mult = EXCLUDED.damage_per_min_mult,
                            damage_share_mult = EXCLUDED.damage_share_mult,
                            cs_per_min_mult = EXCLUDED.cs_per_min_mult,
                            gold_per_min_mult = EXCLUDED.gold_per_min_mult,
                            vision_mult = EXCLUDED.vision_mult,
                            kp_mult = EXCLUDED.kp_mult,
                            damage_taken_share_mult = EXCLUDED.damage_taken_share_mult,
                            combat_weight_adj = EXCLUDED.combat_weight_adj,
                            economic_weight_adj = EXCLUDED.economic_weight_adj,
                            objective_weight_adj = EXCLUDED.objective_weight_adj,
                            tempo_weight_adj = EXCLUDED.tempo_weight_adj,
                            impact_weight_adj = EXCLUDED.impact_weight_adj,
                            final_combat_weight = EXCLUDED.final_combat_weight,
                            final_economic_weight = EXCLUDED.final_economic_weight,
                            final_objective_weight = EXCLUDED.final_objective_weight,
                            final_tempo_weight = EXCLUDED.final_tempo_weight,
                            final_impact_weight = EXCLUDED.final_impact_weight,
                            final_score = EXCLUDED.final_score
                    """
                    
                    params = {
                        'match_id': match_id,
                        'player_index': storage_index(self, i),
                        'riot_id': riot_id,
                        'riot_tag': riot_tag,
                        'champion': champion,
                        'role': role,
                        'champion_tags': tags_str,
                        'profile': profile_str,
                        'dpm_mult': adj.damage_per_min_mult,
                        'dmg_share_mult': adj.damage_share_mult,
                        'cs_mult': adj.cs_per_min_mult,
                        'gpm_mult': adj.gold_per_min_mult,
                        'vision_mult': adj.vision_mult,
                        'kp_mult': adj.kp_mult,
                        'tank_mult': adj.damage_taken_share_mult,
                        'combat_adj': adj.combat_weight_adj,
                        'eco_adj': adj.economic_weight_adj,
                        'obj_adj': adj.objective_weight_adj,
                        'tempo_adj': adj.tempo_weight_adj,
                        'impact_adj': adj.impact_weight_adj,
                        'final_combat': round(final_weights['combat_value'], 4),
                        'final_eco': round(final_weights['economic_efficiency'], 4),
                        'final_obj': round(final_weights['objective_contribution'], 4),
                        'final_tempo': round(final_weights['pace_rating'], 4),
                        'final_impact': round(final_weights['win_impact'], 4),
                        'final_score': final_score,
                    }
                    
                    requete_perso_bdd(query, params)
                    
            except Exception as e:
                print(f"Erreur lors de la sauvegarde des profils de scoring: {e}")



    def get_player_performance_summary(self) -> dict:
        if not getattr(self, 'scores_liste', []):
            return {}
        return self.get_performance_summary_for_player(tracked_index(self))
