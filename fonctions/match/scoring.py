"""
Mixin de scoring pour MatchLol.

Intègre deux systèmes complémentaires:
- PerformanceScorer (z-score): Score principal 1-10 pour ranking MVP/ACE
- ContributionScorer (impact): Breakdown détaillé pour insights/badges

Usage dans MatchLol:
    class MatchLol(ScoringMixin, ...):
        ...
    
    # Après prepare_data():
    await self.calculate_all_scores()
    
    # Accès aux scores:
    self.scores_liste        # [7.2, 6.5, 8.1, ...] pour les 10 joueurs
    self.mvp_index           # Index du MVP (0-9)
    self.ace_index           # Index de l'ACE (meilleur perdant)
    self.player_score        # Score du joueur principal
    self.player_rank         # Rang du joueur (1-10)
    self.player_breakdown    # ContributionBreakdown détaillé
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum
import math


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
        """Retourne la meilleure dimension du joueur."""
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
        """Retourne la dimension la plus faible."""
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
        """Retourne un emoji correspondant au point fort."""
        emoji_map = {
            'Combat': '⚔️',
            'Économie': '💰',
            'Objectifs': '🎯',
            'Tempo': '⚡',
            'Impact': '👑'
        }
        best, _ = self.get_best_dimension()
        return emoji_map.get(best, '🏆')


# =============================================================================
# CONSTANTES - BASELINES ET POIDS
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
    return (value - mean) / std


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


# =============================================================================
# MIXIN PRINCIPAL
# =============================================================================

class ScoringMixin:
    """
    Mixin de scoring pour MatchLol.
    
    Ajoute les attributs:
        - scores_liste: Liste des scores (0-10) pour les 10 joueurs
        - breakdowns_liste: Liste des ContributionBreakdown pour chaque joueur
        - mvp_index: Index du MVP
        - ace_index: Index de l'ACE (meilleur perdant)
        - player_score: Score du joueur principal
        - player_rank: Rang du joueur (1 = MVP)
        - player_breakdown: Breakdown détaillé du joueur principal
    """
    
    def _init_scoring_attributes(self):
        """Initialise les attributs de scoring."""
        self.scores_liste = []
        self.breakdowns_liste = []
        self.mvp_index = 0
        self.ace_index = 5
        self.player_score = 5.0
        self.player_rank = 5
        self.player_breakdown = None
    
    async def calculate_all_scores(self):
        """
        Calcule les scores de tous les joueurs.
        
        À appeler après _extract_team_data().
        """
        self._init_scoring_attributes()
        
        # Protection: vérifier que les données existent
        if not hasattr(self, 'thisKillsListe') or not self.thisKillsListe:
            return
        
        nb_players = min(len(self.thisKillsListe), getattr(self, 'nb_joueur', 10))
        
        for i in range(nb_players):
            # Score z-score (principal)
            score = self._calculate_zscore_for_player(i)
            self.scores_liste.append(round(score, 1))
            
            # Breakdown contribution (détaillé)
            breakdown = self._calculate_breakdown_for_player(i)
            self.breakdowns_liste.append(breakdown)
        
        # Identifier MVP et ACE
        self._identify_mvp_ace()
        
        # Stats du joueur principal
        if hasattr(self, 'thisId') and self.thisId < len(self.scores_liste):
            self.player_score = self.scores_liste[self.thisId]
            self.player_breakdown = self.breakdowns_liste[self.thisId]
            self.player_rank = self._get_player_rank(self.thisId)
    
    def _calculate_zscore_for_player(self, i: int) -> float:
        """Calcule le score z-score pour un joueur."""
        # Récupération du rôle
        role_str = self.thisPositionListe[i] if i < len(self.thisPositionListe) else 'MID'
        role = normalize_position(role_str)
        if role == Role.UNKNOWN:
            role = Role.MID
        
        baseline = ROLE_BASELINES.get(role, ROLE_BASELINES[Role.MID])
        weights = ROLE_WEIGHTS.get(role, ROLE_WEIGHTS[Role.MID])
        
        # Durée de la game
        game_minutes = max(getattr(self, 'thisTime', 25), 5)
        
        # Stats du joueur
        kills = self.thisKillsListe[i]
        deaths = self.thisDeathsListe[i]
        assists = self.thisAssistsListe[i]
        cs = self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]
        damage = self.thisDamageListe[i]
        gold = self.thisGoldListe[i]
        vision = self.thisVisionListe[i]
        damage_taken = self.thisDamageTakenListe[i]
        
        # Stats d'équipe
        if i < 5:
            team_kills = max(getattr(self, 'thisTeamKills', 1), 1)
            team_damage = max(getattr(self, 'thisDamage_team1', 1), 1)
            team_tank = max(getattr(self, 'thisTank_team1', 1), 1)
        else:
            team_kills = max(getattr(self, 'thisTeamKillsOp', 1), 1)
            team_damage = max(getattr(self, 'thisDamage_team2', 1), 1)
            team_tank = max(getattr(self, 'thisTank_team2', 1), 1)
        
        # Métriques calculées
        cs_per_min = cs / game_minutes
        damage_per_min = damage / game_minutes
        gold_per_min = gold / game_minutes
        vision_per_min = vision / game_minutes
        
        damage_share = damage / team_damage
        damage_taken_share = damage_taken / team_tank
        kp = (kills + assists) / team_kills
        
        if deaths == 0:
            kda = (kills + assists) * 1.5
        else:
            kda = (kills + assists) / deaths
        
        # Calcul des z-scores
        z_scores = {
            'kda': calculate_z_score(kda, baseline.kda[0], baseline.kda[1]),
            'cs_per_min': calculate_z_score(cs_per_min, baseline.cs_per_min[0], baseline.cs_per_min[1]),
            'damage_per_min': calculate_z_score(damage_per_min, baseline.damage_per_min[0], baseline.damage_per_min[1]),
            'damage_share': calculate_z_score(damage_share, baseline.damage_share[0], baseline.damage_share[1]),
            'gold_per_min': calculate_z_score(gold_per_min, baseline.gold_per_min[0], baseline.gold_per_min[1]),
            'vision_score_per_min': calculate_z_score(vision_per_min, baseline.vision_score_per_min[0], baseline.vision_score_per_min[1]),
            'kp': calculate_z_score(kp, baseline.kp[0], baseline.kp[1]),
            'damage_taken_share': calculate_z_score(damage_taken_share, baseline.damage_taken_share[0], baseline.damage_taken_share[1]),
        }
        
        # Inversion pour damage_taken_share (moins = mieux, sauf tank)
        if role not in [Role.TOP, Role.SUPPORT]:
            z_scores['damage_taken_share'] = -z_scores['damage_taken_share']
        
        # Z-score pondéré
        weighted_z = sum(z_scores[metric] * weights[metric] for metric in weights)
        
        # Conversion en score 1-10
        return sigmoid_transform(weighted_z)
    
    def _calculate_breakdown_for_player(self, i: int) -> ContributionBreakdown:
        """Calcule le breakdown détaillé pour un joueur."""
        # Récupération du rôle
        role_str = self.thisPositionListe[i] if i < len(self.thisPositionListe) else 'MID'
        role = normalize_position(role_str)
        if role == Role.UNKNOWN:
            role = Role.MID
        
        game_minutes = max(getattr(self, 'thisTime', 25), 5)
        
        # Stats du joueur
        kills = self.thisKillsListe[i]
        deaths = self.thisDeathsListe[i]
        assists = self.thisAssistsListe[i]
        cs = self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]
        damage = self.thisDamageListe[i]
        gold = self.thisGoldListe[i]
        vision = self.thisVisionListe[i]
        
        # Stats d'équipe
        if i < 5:
            team_kills = max(getattr(self, 'thisTeamKills', 1), 1)
            team_deaths = max(getattr(self, 'thisTeamKillsOp', 1), 1)
            team_damage = max(getattr(self, 'thisDamage_team1', 1), 1)
            team_gold = max(getattr(self, 'thisGold_team1', 1), 1)
            enemy_gold = max(getattr(self, 'thisGold_team2', 1), 1)
        else:
            team_kills = max(getattr(self, 'thisTeamKillsOp', 1), 1)
            team_deaths = max(getattr(self, 'thisTeamKills', 1), 1)
            team_damage = max(getattr(self, 'thisDamage_team2', 1), 1)
            team_gold = max(getattr(self, 'thisGold_team2', 1), 1)
            enemy_gold = max(getattr(self, 'thisGold_team1', 1), 1)
        
        # --- DIMENSION 1: COMBAT VALUE ---
        kp = (kills + assists) / team_kills
        kp_score = linear_scale(kp, 0.3, 0.8, 0, 10)
        
        death_share = deaths / max(team_deaths, 1)
        death_score = linear_scale(1 - death_share, 0.5, 1.0, 0, 10)
        
        if deaths == 0:
            kda = (kills + assists) * 1.5
        else:
            kda = (kills + assists) / deaths
        kda_score = linear_scale(kda, 1.0, 6.0, 0, 10)
        
        combat_value = kp_score * 0.35 + death_score * 0.30 + kda_score * 0.35
        
        # --- DIMENSION 2: ECONOMIC EFFICIENCY ---
        dpg = damage / max(gold, 1)
        dpg_score = linear_scale(dpg, 1.0, 3.0, 0, 10)
        
        gold_share = gold / team_gold
        damage_share = damage / team_damage
        efficiency_ratio = damage_share / gold_share if gold_share > 0 else 1.0
        efficiency_score = linear_scale(efficiency_ratio, 0.6, 1.4, 0, 10)
        
        cs_per_min = cs / game_minutes
        expected_cs = {'ADC': 8.0, 'MID': 8.0, 'TOP': 7.0, 'JUNGLE': 5.5, 'SUPPORT': 1.5}
        expected = expected_cs.get(role.value, 6.0)
        cs_ratio = cs_per_min / expected if expected > 0 else 1.0
        cs_score = linear_scale(cs_ratio, 0.5, 1.2, 0, 10)
        
        if role == Role.SUPPORT:
            economic_efficiency = dpg_score * 0.5 + efficiency_score * 0.5
        else:
            economic_efficiency = dpg_score * 0.35 + efficiency_score * 0.35 + cs_score * 0.30
        
        # --- DIMENSION 3: OBJECTIVE CONTRIBUTION ---
        vision_per_min = vision / game_minutes
        expected_vision = {
            Role.SUPPORT: 2.5, Role.JUNGLE: 1.2, Role.TOP: 0.9,
            Role.MID: 0.8, Role.ADC: 0.6, Role.UNKNOWN: 1.0
        }
        vision_ratio = vision_per_min / expected_vision.get(role, 1.0)
        vision_score = linear_scale(vision_ratio, 0.5, 1.5, 0, 10)
        
        # Simplification: on n'a pas les objectives participated ici
        objective_contribution = vision_score
        
        # --- DIMENSION 4: PACE RATING ---
        gold_per_min = gold / game_minutes
        damage_per_min = damage / game_minutes
        
        expected_gpm = {
            Role.ADC: 420, Role.MID: 400, Role.TOP: 380,
            Role.JUNGLE: 360, Role.SUPPORT: 260, Role.UNKNOWN: 350
        }
        gpm_ratio = gold_per_min / expected_gpm.get(role, 350)
        gpm_score = linear_scale(gpm_ratio, 0.7, 1.3, 0, 10)
        
        expected_dpm = {
            Role.ADC: 700, Role.MID: 650, Role.TOP: 550,
            Role.JUNGLE: 480, Role.SUPPORT: 250, Role.UNKNOWN: 500
        }
        dpm_ratio = damage_per_min / expected_dpm.get(role, 500)
        dpm_score = linear_scale(dpm_ratio, 0.7, 1.3, 0, 10)
        
        pace_rating = gpm_score * 0.5 + dpm_score * 0.5
        
        # --- DIMENSION 5: WIN IMPACT ---
        gold_advantage = (team_gold - enemy_gold) / max(enemy_gold, 1)
        advantage_score = linear_scale(gold_advantage, -0.2, 0.2, 0, 10)
        
        contribution_to_lead = gold_share * 10
        
        win_impact = advantage_score * 0.4 + contribution_to_lead * 0.3 + kp_score * 0.3
        
        # --- SCORE FINAL ---
        weights = DIMENSION_WEIGHTS.get(role, DIMENSION_WEIGHTS[Role.UNKNOWN])
        final_score = (
            combat_value * weights['combat_value'] +
            economic_efficiency * weights['economic_efficiency'] +
            objective_contribution * weights['objective_contribution'] +
            pace_rating * weights['pace_rating'] +
            win_impact * weights['win_impact']
        )
        
        # Clamp 1-10
        final_score = max(1.0, min(10.0, final_score))
        
        return ContributionBreakdown(
            combat_value=round(combat_value, 1),
            economic_efficiency=round(economic_efficiency, 1),
            objective_contribution=round(objective_contribution, 1),
            pace_rating=round(pace_rating, 1),
            win_impact=round(win_impact, 1),
            final_score=round(final_score, 1)
        )
    
    def _identify_mvp_ace(self):
        """Identifie le MVP (meilleur global) et l'ACE (meilleur perdant)."""
        if not self.scores_liste:
            return
        
        # MVP = meilleur score global
        self.mvp_index = max(range(len(self.scores_liste)), key=lambda i: self.scores_liste[i])
        
        # ACE = meilleur de l'équipe perdante
        # On détermine l'équipe gagnante via thisWinBool
        if hasattr(self, 'thisWinBool'):
            if self.thisWinBool:
                # Notre équipe a gagné, les perdants sont indices 5-9
                losing_indices = range(5, min(10, len(self.scores_liste)))
            else:
                # Notre équipe a perdu, les perdants sont indices 0-4
                losing_indices = range(0, min(5, len(self.scores_liste)))
            
            if losing_indices:
                self.ace_index = max(losing_indices, key=lambda i: self.scores_liste[i])
        else:
            # Fallback: ACE = meilleur de l'équipe adverse (indices 5-9)
            if len(self.scores_liste) > 5:
                self.ace_index = max(range(5, len(self.scores_liste)), key=lambda i: self.scores_liste[i])
    
    def _get_player_rank(self, player_index: int) -> int:
        """Retourne le rang d'un joueur (1 = MVP, 10 = dernier)."""
        if not self.scores_liste:
            return 5
        
        sorted_indices = sorted(range(len(self.scores_liste)), 
                                key=lambda i: self.scores_liste[i], reverse=True)
        
        for rank, idx in enumerate(sorted_indices, 1):
            if idx == player_index:
                return rank
        return len(self.scores_liste)
    
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
    
    def get_player_performance_summary(self) -> dict:
        """Retourne un résumé de la performance du joueur."""
        if not hasattr(self, 'player_breakdown') or self.player_breakdown is None:
            return {}
        
        best_dim, best_val = self.player_breakdown.get_best_dimension()
        worst_dim, worst_val = self.player_breakdown.get_weakest_dimension()
        
        return {
            'score': self.player_score,
            'rank': self.player_rank,
            'rank_text': self.get_rank_text(self.player_rank),
            'emoji': self.get_score_emoji(self.player_score),
            'best_dimension': best_dim,
            'best_dimension_score': best_val,
            'best_dimension_emoji': self.player_breakdown.get_badge_emoji(),
            'worst_dimension': worst_dim,
            'worst_dimension_score': worst_val,
            'is_mvp': self.player_rank == 1,
            'is_ace': hasattr(self, 'thisId') and self.thisId == self.ace_index,
            'breakdown': self.player_breakdown.to_dict()
        }
    
    def get_performance_summary_for_player(self, player_index: int) -> dict:
        """
        Retourne un résumé de la performance pour un joueur spécifique.
        
        Parameters:
            player_index: Index du joueur (0-9)
            
        Returns:
            Dict avec score, rank, breakdown, dimensions, etc.
        """
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
            'team': 'blue' if player_index < 5 else 'red',
            'role': self.thisPositionListe[player_index] if player_index < len(self.thisPositionListe) else 'UNKNOWN',
            'score': score,
            'rank': rank,
            'rank_text': self.get_rank_text(rank),
            'emoji': self.get_score_emoji(score),
            'best_dimension': best_dim,
            'best_dimension_score': best_val,
            'best_dimension_emoji': breakdown.get_badge_emoji(),
            'worst_dimension': worst_dim,
            'worst_dimension_score': worst_val,
            'is_mvp': player_index == self.mvp_index,
            'is_ace': player_index == self.ace_index,
            'breakdown': breakdown.to_dict()
        }
    
    def get_all_players_performance_summary(self) -> List[dict]:
        """
        Retourne un résumé de la performance pour tous les joueurs.
        
        Returns:
            Liste de dicts avec score, rank, breakdown pour chaque joueur (0-9)
        """
        if not hasattr(self, 'scores_liste') or not self.scores_liste:
            return []
        
        return [
            self.get_performance_summary_for_player(i) 
            for i in range(len(self.scores_liste))
        ]


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    # Test du mixin avec des données simulées
    class MockMatch(ScoringMixin):
        def __init__(self):
            self.thisTime = 28
            self.thisId = 2  # Mid de l'équipe bleue
            self.thisWinBool = True
            self.thisTeamKills = 32
            self.thisTeamKillsOp = 18
            self.thisDamage_team1 = 88000
            self.thisDamage_team2 = 55000
            self.thisTank_team1 = 75000
            self.thisTank_team2 = 82000
            self.thisGold_team1 = 65000
            self.thisGold_team2 = 52000
            
            # Données des 10 joueurs
            self.thisPositionListe = ['TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT'] * 2
            self.thisKillsListe = [4, 8, 12, 6, 2, 3, 4, 5, 4, 2]
            self.thisDeathsListe = [3, 4, 2, 5, 4, 6, 5, 4, 5, 6]
            self.thisAssistsListe = [8, 14, 6, 8, 18, 6, 8, 5, 4, 10]
            self.thisMinionListe = [180, 40, 220, 240, 25, 160, 35, 200, 210, 20]
            self.thisJungleMonsterKilledListe = [20, 140, 10, 5, 0, 15, 120, 8, 3, 0]
            self.thisDamageListe = [18000, 16000, 32000, 22000, 8000, 14000, 12000, 18000, 16000, 6000]
            self.thisGoldListe = [11000, 12500, 15000, 14000, 9500, 9000, 10000, 12000, 11500, 8000]
            self.thisVisionListe = [22, 40, 18, 14, 85, 18, 32, 15, 12, 55]
            self.thisDamageTakenListe = [22000, 18000, 14000, 12000, 16000, 24000, 20000, 16000, 14000, 15000]
    
    match = MockMatch()
    
    import asyncio
    asyncio.run(match.calculate_all_scores())
    
    print("=" * 60)
    print("Scores de tous les joueurs:")
    print("=" * 60)
    for i, (score, breakdown) in enumerate(zip(match.scores_liste, match.breakdowns_liste)):
        role = match.thisPositionListe[i]
        team = "Blue" if i < 5 else "Red"
        best_dim, _ = breakdown.get_best_dimension()
        print(f"  {team} {role:<8} Score: {score}/10  | Best: {best_dim}")
    
    print(f"\n🏆 MVP: Index {match.mvp_index} ({match.thisPositionListe[match.mvp_index]})")
    print(f"⭐ ACE: Index {match.ace_index} ({match.thisPositionListe[match.ace_index]})")
    
    print("\n" + "=" * 60)
    print("Performance du joueur principal (Mid Blue):")
    print("=" * 60)
    summary = match.get_player_performance_summary()
    print(f"  Score: {summary['score']}/10 {summary['emoji']}")
    print(f"  Rang: {summary['rank_text']}")
    print(f"  Point fort: {summary['best_dimension']} ({summary['best_dimension_score']}/10) {summary['best_dimension_emoji']}")
    print(f"  Point faible: {summary['worst_dimension']} ({summary['worst_dimension_score']}/10)")
    print(f"  MVP: {summary['is_mvp']}")
    
    print("\n" + "=" * 60)
    print("get_all_players_performance_summary():")
    print("=" * 60)
    all_summaries = match.get_all_players_performance_summary()
    print(all_summaries[0])
    for s in all_summaries:
        mvp_ace = "👑 MVP" if s['is_mvp'] else ("⭐ ACE" if s['is_ace'] else "")
        print(f"  {s['team']:<4} {s['role']:<8} {s['emoji']} {s['score']}/10 ({s['rank_text']:<5}) | {s['best_dimension_emoji']} {s['best_dimension']:<10} {mvp_ace}")
