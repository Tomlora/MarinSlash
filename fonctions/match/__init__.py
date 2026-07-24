"""
Module match - Analyse des matchs League of Legends.

Ce module fournit une architecture modulaire pour:
- Récupérer les données des matchs via l'API Riot
- Analyser les performances des joueurs
- Calculer des statistiques avancées
- Générer des résumés visuels
- Sauvegarder en base de données

Structure des modules:
- utils.py: Utilitaires généraux (fonts, helpers)
- riot_api.py: Appels à l'API Riot Games
- records.py: Gestion des records
- masteries.py: Maîtrises et stats joueur
- matchlol_base.py: Classe de base avec données participant
- matchlol_team.py: Données d'équipe et comparaisons
- external_data.py: Données UGG/Mobalytics
- save_data.py: Sauvegarde en BDD
- timeline.py: Analyse de la timeline
- analysis.py: Analyses avancées (skirmishes, roam, etc.)
- teamfight_damage.py: Dégâts par joueur pendant les teamfights
- teamfight_storage.py: Sauvegarde PostgreSQL des dégâts de teamfight
- detection.py: Détection de patterns joueurs
- badges.py: Calcul des badges et scoring
- image.py: Génération d'images
- image_modern.py: Nouveau récapitulatif moderne sélectionnable en BDD
- special_modes.py: Modes Arena, Swarm, Clash
- matchlol.py: Classe principale assemblant tout

Usage:
    from fonctions.match import MatchLol
    
    match = MatchLol(
        id_compte=123,
        riot_id='PlayerName',
        riot_tag='EUW',
        idgames='EUW1_123456789',
        queue='RANKED'
    )
    embed = await match.run(embed, difLP=15)
"""

from .matchlol import MatchLol
from .image_modern import install_modern_recap
from .teamfight_damage import calculate_teamfight_damage, install_teamfight_damage
from .teamfight_storage import install_teamfight_storage
from .timeline_persistence import install_timeline_persistence
from .riot_api import (
    get_version,
    get_champ_list,
    get_match_detail,
    get_match_timeline,
    get_summoner_by_riot_id,
    get_league_by_puuid,
    get_champion_masteries,
    get_image,
    get_spectator,
)
from .records import (
    get_id_account_bdd,
    trouver_records,
    trouver_records_multiples,
    top_records,
)
from .masteries import (
    get_masteries_old,
    get_stat_champion_by_player,
    detect_duos,
    get_spectator_data,
)
from .utils import (
    mode,
    fix_temps,
    range_value,
    range_value_arena,
    charger_font,
    dict_data,
    dict_data_swarm,
    load_timeline,
)

# Ajoute le sélecteur legacy/modern à MatchLol tout en conservant la méthode
# historique comme fallback.
install_modern_recap(MatchLol)

# Ajoute le calcul puis la sauvegarde automatique des dégâts de teamfight.
install_teamfight_damage(MatchLol)
install_teamfight_storage(MatchLol)

# Persiste les champs calculés depuis la timeline après l'insertion du match.
install_timeline_persistence(MatchLol)

__all__ = [
    # Classe principale
    'MatchLol',
    
    # API Riot
    'get_version',
    'get_champ_list',
    'get_match_detail',
    'get_match_timeline',
    'get_summoner_by_riot_id',
    'get_league_by_puuid',
    'get_champion_masteries',
    'get_image',
    'get_spectator',
    
    # Records
    'get_id_account_bdd',
    'trouver_records',
    'trouver_records_multiples',
    'top_records',
    
    # Masteries
    'get_masteries_old',
    'get_stat_champion_by_player',
    'detect_duos',
    'get_spectator_data',

    # Teamfights
    'calculate_teamfight_damage',
    
    # Utils
    'mode',
    'fix_temps',
    'range_value',
    'range_value_arena',
    'charger_font',
    'dict_data',
    'dict_data_swarm',
    'load_timeline',
]
