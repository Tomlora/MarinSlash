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
- ganks.py: Implémentation historique de l'analyse des ganks
- ganks_hybrid.py: Détection hybride des tentatives de gank
- gank_laning_rules.py: Règles V3 phase de lane (<14 min, succès strict)
- gank_recap.py: Insight de focus jungle dans le récap
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

import pickle
from pathlib import Path

from .matchlol import MatchLol
from .image_modern import install_modern_recap
from .teamfight_damage import calculate_teamfight_damage, install_teamfight_damage
from .teamfight_storage import install_teamfight_storage
from .timeline_persistence import install_timeline_persistence
from .ganks import GankAnalysisMixin as LegacyGankAnalysisMixin
from .ganks_hybrid import install_hybrid_ganks
from .gank_laning_rules import install_gank_laning_rules
from .gank_recap import install_gank_recap
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


def _install_scoring_model_fallback(match_class):
    """Garantit que le modèle legacy de calcul_scoring est disponible."""
    original_init = match_class.__init__
    if getattr(original_init, '_scoring_model_fallback_installed', False):
        return

    model_path = Path(__file__).resolve().parents[2] / 'model' / 'scoring_rf.pkl'

    def init_with_scoring_model(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        # matchlol.py référence historiquement model/model_scoring.pkl, absent du
        # dépôt. prepare_data_moba recharge ensuite scoring_rf.pkl dans certains
        # chemins, mais l'ARAM peut atteindre le récap sans ce second chargement.
        if getattr(self, 'model', None) is None:
            with model_path.open('rb') as model_file:
                self.model = pickle.load(model_file)

    init_with_scoring_model._scoring_model_fallback_installed = True
    match_class.__init__ = init_with_scoring_model


def _install_aram_performance_consistency(match_class):
    """Aligne le badge MVP ARAM sur le classement affiché dans l'image legacy."""
    original_add_performance = match_class._add_performance_calcul
    if getattr(original_add_performance, '_aram_model_consistency_installed', False):
        return

    def add_performance_consistent(self):
        if getattr(self, 'thisQ', None) not in ['ARAM', 'CLASH ARAM']:
            return original_add_performance(self)

        nb_players = min(
            int(getattr(self, 'nb_joueur', 10) or 10),
            len(getattr(self, 'thisKillsListe', []) or []),
        )
        if nb_players <= 0:
            return None

        # L'image ARAM historique classe les prédictions du RandomForest par ordre
        # croissant. On reproduit exactement cette convention, y compris pour les
        # égalités (première position du score dans la liste triée).
        legacy_scores = []
        for i in range(nb_players):
            prediction = self.calcul_scoring(i)
            try:
                value = float(prediction[0])
            except (TypeError, IndexError):
                value = float(prediction)
            legacy_scores.append(value)

        sorted_scores = sorted(legacy_scores)
        legacy_ranks = [sorted_scores.index(score) + 1 for score in legacy_scores]

        tracked_index = None
        tracked_puuid = str(getattr(self, 'puuid', '') or '')
        for i, puuid in enumerate((getattr(self, 'thisPuuidListe', []) or [])[:nb_players]):
            if tracked_puuid and str(puuid or '') == tracked_puuid:
                tracked_index = i
                break

        # Même repli que le reste du code : quand l'équipe du joueur a été remise
        # en première position, un participant Riot 6-10 devient un index 0-4.
        if tracked_index is None:
            this_id = int(getattr(self, 'thisId', 0) or 0)
            tracked_index = this_id - 5 if this_id > 4 else this_id

        if not 0 <= tracked_index < nb_players:
            return None

        legacy_rank = legacy_ranks[tracked_index]
        self.aram_legacy_rank = legacy_rank
        self.player_rank = legacy_rank
        self.mvp_index = legacy_ranks.index(1)

        if legacy_rank == 1:
            if 'MVP' not in self.badges:
                self.badges.append('MVP')
            self.observations += (
                f"\n🏆 **MVP** de la partie ! "
                f"Classement modèle ARAM : **1/{nb_players}**\n"
            )
        elif legacy_rank <= 3:
            self.observations += (
                f"\n📊 Modèle ARAM : **Top {legacy_rank}/{nb_players}** de la partie\n"
            )

        # Les badges de dimensions et MVP/ACE du ScoringMixin reposent sur des
        # baselines de rôles. En ARAM les positions TOP/JUNGLE/MID/ADC/SUPPORT sont
        # artificielles, donc on ne les utilise pas pour attribuer le MVP.
        return None

    add_performance_consistent._aram_model_consistency_installed = True
    match_class._add_performance_calcul = add_performance_consistent


# Le récap legacy appelle BadgesMixin.calcul_scoring(), qui exige self.model.
# On installe donc le fallback avant la création des MatchLol par les cogs.
_install_scoring_model_fallback(MatchLol)

# En ARAM, le classement MVP du texte doit rester identique à celui de l'image.
_install_aram_performance_consistency(MatchLol)

# Ajoute le sélecteur legacy/modern à MatchLol tout en conservant la méthode
# historique comme fallback.
install_modern_recap(MatchLol)

# Remplace la détection historique « kill du jungler = gank » par la V2 hybride.
# La position à la minute devient un signal optionnel, combiné aux événements
# exacts et aux deltas de dégâts entre frames.
install_hybrid_ganks(MatchLol)

# V3 : on ne conserve comme ganks que les tentatives de phase de lane (<14:00),
# un trade n'est plus un succès et le rappel des tentatives ratées est augmenté.
# Cette installation doit intervenir APRES install_hybrid_ganks, puisqu'elle
# enveloppe la méthode _collect_observed_ganks installée par la V2.
install_gank_laning_rules(MatchLol)

# _compute_timing_insights utilise super() dans la classe hybride lorsqu'elle est
# instanciée directement. MatchLol reçoit les méthodes par installation dynamique,
# donc on conserve ici l'implémentation historique compatible pour l'agrégation
# temporelle. Elle reçoit désormais uniquement les événements filtrés V3.
MatchLol._compute_timing_insights = LegacyGankAnalysisMixin._compute_timing_insights

# Installe directement l'insight de focus jungle sur MatchLol. L'appel identique
# dans cogs/ganks.py reste sans effet supplémentaire grâce au garde idempotent.
install_gank_recap(MatchLol)

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
