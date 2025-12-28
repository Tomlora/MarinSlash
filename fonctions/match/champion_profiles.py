"""
Profils de champions pour ajuster le scoring selon le type de champion joué.

Un Ornn TOP (tank) et une Fiora TOP (carry) n'ont pas les mêmes attentes.
Ce module permet d'ajuster les baselines et les poids selon le profil du champion.
"""

from enum import Enum
from typing import Dict, Tuple, Optional
from dataclasses import dataclass


class ChampionProfile(Enum):
    """Profil de champion basé sur les tags."""
    TANK = "TANK"
    FIGHTER = "FIGHTER"
    ASSASSIN = "ASSASSIN"
    MAGE = "MAGE"
    MARKSMAN = "MARKSMAN"
    SUPPORT_UTILITY = "SUPPORT_UTILITY"
    UNKNOWN = "UNKNOWN"


# =============================================================================
# MAPPING DES TAGS VERS PROFILS
# =============================================================================

# Tags Riot -> Profil principal
TAG_TO_PROFILE = {
    "Tank": ChampionProfile.TANK,
    "Fighter": ChampionProfile.FIGHTER,
    "Assassin": ChampionProfile.ASSASSIN,
    "Mage": ChampionProfile.MAGE,
    "Marksman": ChampionProfile.MARKSMAN,
    "Support": ChampionProfile.SUPPORT_UTILITY,
}


def parse_tags(tags_str: str) -> list:
    """Parse le string de tags '{Tag1,Tag2}' en liste."""
    if not tags_str:
        return []
    # Enlever les accolades et split
    cleaned = tags_str.strip('{}')
    if not cleaned:
        return []
    return [t.strip() for t in cleaned.split(',')]


def get_champion_profile(tags: list, role: str) -> ChampionProfile:
    """
    Détermine le profil d'un champion selon ses tags ET son rôle.
    
    La logique dépend du rôle car les attentes varient :
    - Un Mage SUPPORT (Brand) est un "carry support"
    - Un Tank SUPPORT (Leona) est un "engage support"
    - Un Tank TOP (Ornn) a des attentes différentes d'un Fighter TOP (Fiora)
    """
    if not tags:
        return ChampionProfile.UNKNOWN
    
    primary_tag = tags[0]
    secondary_tag = tags[1] if len(tags) > 1 else None
    
    role = role.upper()
    
    # === SUPPORT ===
    if role == "SUPPORT":
        # Support avec tag Mage en premier = carry support (Brand, Zyra, Vel'Koz)
        if primary_tag == "Mage":
            return ChampionProfile.MAGE  # Carry support
        # Support avec tag Tank = engage support (Leona, Nautilus)
        elif primary_tag == "Tank":
            return ChampionProfile.TANK
        # Support avec tag Assassin = roaming support (Pyke)
        elif primary_tag == "Support" and secondary_tag == "Assassin":
            return ChampionProfile.ASSASSIN
        # Support avec tag Marksman = poke/carry (Senna)
        elif secondary_tag == "Marksman":
            return ChampionProfile.MARKSMAN
        # Support utilitaire par défaut (Lulu, Janna, Soraka)
        else:
            return ChampionProfile.SUPPORT_UTILITY
    
    # === TOP ===
    elif role == "TOP":
        # Tank TOP (Ornn, Shen, Malphite)
        if primary_tag == "Tank":
            return ChampionProfile.TANK
        # Fighter/Assassin = carry (Fiora, Camille, Riven)
        elif primary_tag == "Fighter":
            if secondary_tag == "Assassin":
                return ChampionProfile.ASSASSIN  # Carry aggro
            elif secondary_tag == "Tank":
                return ChampionProfile.FIGHTER  # Bruiser
            else:
                return ChampionProfile.FIGHTER
        # Mage TOP (Kennen, Rumble)
        elif primary_tag == "Mage":
            return ChampionProfile.MAGE
        # Marksman TOP (Quinn, Vayne top)
        elif primary_tag == "Marksman":
            return ChampionProfile.MARKSMAN
        else:
            return ChampionProfile.FIGHTER
    
    # === JUNGLE ===
    elif role == "JUNGLE":
        # Tank JGL (Sejuani, Rammus, Zac)
        if primary_tag == "Tank":
            return ChampionProfile.TANK
        # Assassin JGL (Kha'Zix, Evelynn, Rengar)
        elif primary_tag == "Assassin":
            return ChampionProfile.ASSASSIN
        # Fighter JGL (Lee Sin, Vi, Xin Zhao)
        elif primary_tag == "Fighter":
            if secondary_tag == "Assassin":
                return ChampionProfile.ASSASSIN
            elif secondary_tag == "Tank":
                return ChampionProfile.TANK
            else:
                return ChampionProfile.FIGHTER
        # Mage JGL (Karthus, Taliyah)
        elif primary_tag == "Mage":
            return ChampionProfile.MAGE
        # Marksman JGL (Kindred, Graves)
        elif primary_tag == "Marksman":
            return ChampionProfile.MARKSMAN
        else:
            return ChampionProfile.FIGHTER
    
    # === MID ===
    elif role == "MID":
        # Assassin MID (Zed, Talon, Katarina)
        if primary_tag == "Assassin":
            return ChampionProfile.ASSASSIN
        # Mage MID (Orianna, Syndra, Viktor)
        elif primary_tag == "Mage":
            return ChampionProfile.MAGE
        # Fighter MID (Yasuo, Yone)
        elif primary_tag == "Fighter":
            return ChampionProfile.FIGHTER
        else:
            return ChampionProfile.MAGE
    
    # === ADC ===
    elif role in ["ADC", "BOTTOM"]:
        # Marksman standard
        if primary_tag == "Marksman":
            if secondary_tag == "Assassin":
                return ChampionProfile.ASSASSIN  # Samira, Lucian, Tristana
            else:
                return ChampionProfile.MARKSMAN
        # Mage ADC (Ziggs, Cassio bot)
        elif primary_tag == "Mage":
            return ChampionProfile.MAGE
        # Fighter ADC (Yasuo bot)
        elif primary_tag == "Fighter":
            return ChampionProfile.FIGHTER
        else:
            return ChampionProfile.MARKSMAN
    
    # Fallback
    return TAG_TO_PROFILE.get(primary_tag, ChampionProfile.UNKNOWN)


# =============================================================================
# AJUSTEMENTS PAR PROFIL ET RÔLE
# =============================================================================

@dataclass
class ProfileAdjustments:
    """Ajustements des attentes pour un profil de champion."""
    # Multiplicateurs pour les baselines (1.0 = pas de changement)
    damage_per_min_mult: float = 1.0
    damage_share_mult: float = 1.0
    cs_per_min_mult: float = 1.0
    gold_per_min_mult: float = 1.0
    vision_mult: float = 1.0
    kp_mult: float = 1.0
    damage_taken_share_mult: float = 1.0
    
    # Ajustements des poids des dimensions (additifs, peuvent être négatifs)
    combat_weight_adj: float = 0.0
    economic_weight_adj: float = 0.0
    objective_weight_adj: float = 0.0
    tempo_weight_adj: float = 0.0
    impact_weight_adj: float = 0.0


# Ajustements par (Rôle, Profil) - Cache chargé depuis la BDD
_PROFILE_ADJUSTMENTS_CACHE: Dict[Tuple[str, ChampionProfile], ProfileAdjustments] = {}


def clear_caches():
    """Vide tous les caches pour forcer un rechargement depuis la BDD."""
    global _CHAMPION_TAGS_CACHE, _PROFILE_ADJUSTMENTS_CACHE
    _CHAMPION_TAGS_CACHE = {}
    _PROFILE_ADJUSTMENTS_CACHE = {}


def load_profile_adjustments() -> Dict[Tuple[str, ChampionProfile], ProfileAdjustments]:
    """
    Charge les ajustements de profil depuis la base de données.
    
    Returns:
        Dict[(role, profile), ProfileAdjustments]
    """
    global _PROFILE_ADJUSTMENTS_CACHE
    
    if _PROFILE_ADJUSTMENTS_CACHE:
        return _PROFILE_ADJUSTMENTS_CACHE
    
    try:
        from fonctions.gestion_bdd import lire_bdd_perso
        
        df = lire_bdd_perso(
            "SELECT * FROM scoring_profile_ratios",
            index_col=None
        ).T
        
        for _, row in df.iterrows():
            role = row.get('role', '').upper()
            profile_str = row.get('profile', '').upper()
            
            # Convertir le string en enum
            try:
                profile = ChampionProfile(profile_str)
            except ValueError:
                continue
            
            adjustments = ProfileAdjustments(
                damage_per_min_mult=float(row.get('damage_per_min_mult', 1.0)),
                damage_share_mult=float(row.get('damage_share_mult', 1.0)),
                cs_per_min_mult=float(row.get('cs_per_min_mult', 1.0)),
                gold_per_min_mult=float(row.get('gold_per_min_mult', 1.0)),
                vision_mult=float(row.get('vision_mult', 1.0)),
                kp_mult=float(row.get('kp_mult', 1.0)),
                damage_taken_share_mult=float(row.get('damage_taken_share_mult', 1.0)),
                combat_weight_adj=float(row.get('combat_weight_adj', 0.0)),
                economic_weight_adj=float(row.get('economic_weight_adj', 0.0)),
                objective_weight_adj=float(row.get('objective_weight_adj', 0.0)),
                tempo_weight_adj=float(row.get('tempo_weight_adj', 0.0)),
                impact_weight_adj=float(row.get('impact_weight_adj', 0.0)),
            )
            
            _PROFILE_ADJUSTMENTS_CACHE[(role, profile)] = adjustments
                
    except Exception as e:
        print(f"Warning: Error loading profile adjustments from database: {e}")
        # Fallback sur les valeurs par défaut hardcodées
        _load_default_profile_adjustments()
    
    return _PROFILE_ADJUSTMENTS_CACHE


def _load_default_profile_adjustments():
    """Charge les valeurs par défaut si la BDD n'est pas disponible."""
    global _PROFILE_ADJUSTMENTS_CACHE
    
    defaults = {
        # === TOP LANE ===
        ("TOP", ChampionProfile.TANK): ProfileAdjustments(
            damage_per_min_mult=0.75, damage_share_mult=0.80, cs_per_min_mult=0.90,
            damage_taken_share_mult=1.30, combat_weight_adj=-0.05, objective_weight_adj=0.05,
        ),
        ("TOP", ChampionProfile.FIGHTER): ProfileAdjustments(damage_taken_share_mult=1.10),
        ("TOP", ChampionProfile.ASSASSIN): ProfileAdjustments(
            damage_per_min_mult=1.15, damage_share_mult=1.10, cs_per_min_mult=1.05,
            damage_taken_share_mult=0.80, combat_weight_adj=0.05, economic_weight_adj=0.05,
        ),
        ("TOP", ChampionProfile.MAGE): ProfileAdjustments(
            damage_per_min_mult=1.10, damage_share_mult=1.05, damage_taken_share_mult=0.70, vision_mult=1.10,
        ),
        ("TOP", ChampionProfile.MARKSMAN): ProfileAdjustments(
            damage_per_min_mult=1.20, damage_share_mult=1.15, cs_per_min_mult=1.10,
            damage_taken_share_mult=0.60, combat_weight_adj=0.05, tempo_weight_adj=0.05,
        ),
        
        # === JUNGLE ===
        ("JUNGLE", ChampionProfile.TANK): ProfileAdjustments(
            damage_per_min_mult=0.70, damage_share_mult=0.75, damage_taken_share_mult=1.30,
            kp_mult=1.10, combat_weight_adj=-0.05, objective_weight_adj=0.10,
        ),
        ("JUNGLE", ChampionProfile.FIGHTER): ProfileAdjustments(damage_taken_share_mult=1.05),
        ("JUNGLE", ChampionProfile.ASSASSIN): ProfileAdjustments(
            damage_per_min_mult=1.15, damage_share_mult=1.10, damage_taken_share_mult=0.70,
            kp_mult=0.95, combat_weight_adj=0.10, objective_weight_adj=-0.05,
        ),
        ("JUNGLE", ChampionProfile.MAGE): ProfileAdjustments(
            damage_per_min_mult=1.10, damage_share_mult=1.05, cs_per_min_mult=1.10,
            damage_taken_share_mult=0.60, tempo_weight_adj=0.05,
        ),
        ("JUNGLE", ChampionProfile.MARKSMAN): ProfileAdjustments(
            damage_per_min_mult=1.15, damage_share_mult=1.10, damage_taken_share_mult=0.65,
            combat_weight_adj=0.05, tempo_weight_adj=0.05,
        ),
        
        # === MID LANE ===
        ("MID", ChampionProfile.MAGE): ProfileAdjustments(),
        ("MID", ChampionProfile.ASSASSIN): ProfileAdjustments(
            damage_per_min_mult=0.90, cs_per_min_mult=0.90, kp_mult=1.15,
            combat_weight_adj=0.10, economic_weight_adj=-0.10, tempo_weight_adj=0.05,
        ),
        ("MID", ChampionProfile.FIGHTER): ProfileAdjustments(
            damage_per_min_mult=1.05, damage_taken_share_mult=1.20, cs_per_min_mult=1.05, combat_weight_adj=0.05,
        ),
        
        # === ADC ===
        ("ADC", ChampionProfile.MARKSMAN): ProfileAdjustments(),
        ("ADC", ChampionProfile.ASSASSIN): ProfileAdjustments(
            damage_per_min_mult=1.05, kp_mult=1.10, cs_per_min_mult=0.95, combat_weight_adj=0.05,
        ),
        ("ADC", ChampionProfile.MAGE): ProfileAdjustments(cs_per_min_mult=0.95, vision_mult=1.10),
        
        # === SUPPORT ===
        ("SUPPORT", ChampionProfile.TANK): ProfileAdjustments(
            damage_per_min_mult=0.80, damage_taken_share_mult=1.40, kp_mult=1.10, vision_mult=0.90,
            combat_weight_adj=0.05, objective_weight_adj=0.05,
        ),
        ("SUPPORT", ChampionProfile.SUPPORT_UTILITY): ProfileAdjustments(
            damage_per_min_mult=0.60, damage_share_mult=0.50, damage_taken_share_mult=0.80,
            vision_mult=1.15, kp_mult=1.05, objective_weight_adj=0.10, combat_weight_adj=-0.10,
        ),
        ("SUPPORT", ChampionProfile.MAGE): ProfileAdjustments(
            damage_per_min_mult=1.80, damage_share_mult=1.50, damage_taken_share_mult=0.70,
            vision_mult=0.85, kp_mult=1.05, combat_weight_adj=0.15, economic_weight_adj=0.10, objective_weight_adj=-0.10,
        ),
        ("SUPPORT", ChampionProfile.ASSASSIN): ProfileAdjustments(
            damage_per_min_mult=1.20, kp_mult=1.20, gold_per_min_mult=1.10, vision_mult=0.80,
            combat_weight_adj=0.15, tempo_weight_adj=0.10, objective_weight_adj=-0.10,
        ),
        ("SUPPORT", ChampionProfile.MARKSMAN): ProfileAdjustments(
            damage_per_min_mult=1.40, damage_share_mult=1.20, gold_per_min_mult=1.10, vision_mult=0.95,
            combat_weight_adj=0.05, tempo_weight_adj=0.05,
        ),
    }
    
    _PROFILE_ADJUSTMENTS_CACHE.update(defaults)


def get_profile_adjustments(role: str, profile: ChampionProfile) -> ProfileAdjustments:
    """Récupère les ajustements pour un rôle et profil donnés."""
    # Charger depuis la BDD si pas encore fait
    if not _PROFILE_ADJUSTMENTS_CACHE:
        load_profile_adjustments()
    
    role = role.upper()
    if role == "BOTTOM":
        role = "ADC"
    elif role == "UTILITY":
        role = "SUPPORT"
    elif role == "MIDDLE":
        role = "MID"
    
    key = (role, profile)
    return _PROFILE_ADJUSTMENTS_CACHE.get(key, ProfileAdjustments())


# =============================================================================
# CHARGEMENT DES DONNÉES CHAMPIONS
# =============================================================================

# Cache des tags par champion
_CHAMPION_TAGS_CACHE: Dict[str, list] = {}


def load_champion_tags() -> Dict[str, list]:
    """
    Charge les tags des champions depuis la base de données.
    
    Returns:
        Dict[champion_name, list[tags]]
    """
    global _CHAMPION_TAGS_CACHE
    
    if _CHAMPION_TAGS_CACHE:
        return _CHAMPION_TAGS_CACHE
    
    try:
        from fonctions.gestion_bdd import lire_bdd_perso
        
        df = lire_bdd_perso(
            "SELECT name, tags FROM data_champion_tag",
            index_col=None
        ).T
        
        for _, row in df.iterrows():
            name = row.get('name', '').strip()
            tags_str = row.get('tags', '')
            if name:
                # Normaliser le nom (minuscules, sans espaces)
                name_normalized = name.lower().replace(' ', '').replace("'", "")
                tags = parse_tags(tags_str)
                _CHAMPION_TAGS_CACHE[name_normalized] = tags
                # Garder aussi la version originale
                _CHAMPION_TAGS_CACHE[name.lower()] = tags
                
    except Exception as e:
        print(f"Warning: Error loading champion tags from database: {e}")
    
    return _CHAMPION_TAGS_CACHE


def get_champion_tags(champion_name: str) -> list:
    """Récupère les tags d'un champion par son nom."""
    if not _CHAMPION_TAGS_CACHE:
        load_champion_tags()
    
    # Normaliser le nom
    name_normalized = champion_name.lower().replace(' ', '').replace("'", "")
    
    return _CHAMPION_TAGS_CACHE.get(name_normalized, [])


def get_profile_for_champion(champion_name: str, role: str) -> ChampionProfile:
    """
    Détermine le profil d'un champion selon son nom et son rôle.
    
    Parameters:
        champion_name: Nom du champion (ex: "Ornn", "Fiora")
        role: Rôle joué (ex: "TOP", "SUPPORT")
    
    Returns:
        ChampionProfile correspondant
    """
    tags = get_champion_tags(champion_name)
    return get_champion_profile(tags, role)


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    # Test avec quelques champions
    test_cases = [
        ("Ornn", "TOP"),
        ("Fiora", "TOP"),
        ("Kennen", "TOP"),
        ("Sejuani", "JUNGLE"),
        ("Kha'Zix", "JUNGLE"),
        ("Lee Sin", "JUNGLE"),
        ("Karthus", "JUNGLE"),
        ("Zed", "MID"),
        ("Orianna", "MID"),
        ("Yasuo", "MID"),
        ("Jinx", "ADC"),
        ("Samira", "ADC"),
        ("Leona", "SUPPORT"),
        ("Lulu", "SUPPORT"),
        ("Brand", "SUPPORT"),
        ("Pyke", "SUPPORT"),
        ("Senna", "SUPPORT"),
    ]
    
    # Charger les tags et les ratios depuis la BDD
    load_champion_tags()
    load_profile_adjustments()
    
    print("=" * 80)
    print("Test des profils de champions")
    print("=" * 80)
    print(f"{'Champion':<15} {'Role':<10} {'Tags':<25} {'Profile':<20}")
    print("-" * 80)
    
    for champ, role in test_cases:
        tags = get_champion_tags(champ)
        profile = get_profile_for_champion(champ, role)
        adjustments = get_profile_adjustments(role, profile)
        
        tags_str = ', '.join(tags) if tags else 'N/A'
        print(f"{champ:<15} {role:<10} {tags_str:<25} {profile.value:<20}")
        
        # Afficher les ajustements non-standard
        if adjustments.damage_per_min_mult != 1.0:
            print(f"    → DPM x{adjustments.damage_per_min_mult:.2f}")
        if adjustments.damage_taken_share_mult != 1.0:
            print(f"    → Tank x{adjustments.damage_taken_share_mult:.2f}")
        if adjustments.combat_weight_adj != 0:
            print(f"    → Combat weight {adjustments.combat_weight_adj:+.2f}")
