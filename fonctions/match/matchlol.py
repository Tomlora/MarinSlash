"""
Classe MatchLol principale - Assemble tous les mixins.
"""

import pickle
import aiohttp
import pandas as pd


from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd
from fonctions.timer import timer

# Import des mixins
from .matchlol_base import MatchLolBase
from .matchlol_team import MatchLolTeamData
from .external_data import ExternalDataMixin
from .save_data import SaveDataMixin
from .timeline import TimelineMixin
from .analysis import AdvancedAnalysisMixin
from .detection import DetectionMixin, ObjectifsMixin
from .badges import BadgesMixin
from .image import ImageGenerationMixin
from .special_modes import ArenaModeMixin, SwarmModeMixin, ClashModeMixin
from .scoring import ScoringMixin
from .ganks import GankAnalysisMixin


def get_profile_emoji(profile: str) -> str:
        """Retourne un emoji pour le profil de champion."""
        emojis = {
            'TANK': '🛡️',
            'FIGHTER': '⚔️',
            'ASSASSIN': '🗡️',
            'MAGE': '🔮',
            'MARKSMAN': '🏹',
            'SUPPORT_UTILITY': '💚',
            'UNKNOWN': '❓',
        }
        return emojis.get(profile.upper(), '❓')


def get_profile_name_fr(profile: str) -> str:
        """Retourne le nom français du profil."""
        names = {
            'TANK': 'Tank',
            'FIGHTER': 'Bruiser',
            'ASSASSIN': 'Assassin',
            'MAGE': 'Mage',
            'MARKSMAN': 'Tireur',
            'SUPPORT_UTILITY': 'Enchanteur',
            'UNKNOWN': 'Inconnu',
        }
        return names.get(profile.upper(), profile)





class MatchLol(
    MatchLolBase,
    MatchLolTeamData,
    ExternalDataMixin,
    SaveDataMixin,
    TimelineMixin,
    AdvancedAnalysisMixin,
    DetectionMixin,
    ObjectifsMixin,
    BadgesMixin,
    ImageGenerationMixin,
    ArenaModeMixin,
    SwarmModeMixin,
    ClashModeMixin,
    ScoringMixin,
    GankAnalysisMixin
):
    """
    Classe principale pour l'analyse des matchs League of Legends.
    
    Hérite de tous les mixins pour fournir:
    - Récupération des données Riot (MatchLolBase)
    - Extraction des données d'équipe (MatchLolTeamData)
    - Données externes UGG/Mobalytics (ExternalDataMixin)
    - Sauvegarde en BDD (SaveDataMixin)
    - Analyse de la timeline (TimelineMixin)
    - Analyses avancées (AdvancedAnalysisMixin)
    - Détection de joueurs (DetectionMixin)
    - Objectifs personnels (ObjectifsMixin)
    - Calcul des badges (BadgesMixin)
    - Génération d'images (ImageGenerationMixin)
    - Modes spéciaux Arena/Swarm/Clash (ArenaModeMixin, SwarmModeMixin, ClashModeMixin)
    """

    def __init__(self, 
                 id_compte, 
                 riot_id, 
                 riot_tag, 
                 idgames: int,
                 queue: int = 0,
                 index: int = None,
                 count: int = None,
                 identifiant_game=None,
                 me=None):
        """
        Initialise l'analyse d'un match.
        
        Parameters
        ----------
        id_compte : int
            ID du compte dans la BDD
        riot_id : str
            Riot ID du joueur
        riot_tag : str
            Tag Riot du joueur
        idgames : int
            Numéro de la game (0 = plus récente)
        queue : int, optional
            Type de queue (0 = toutes), by default 0
        index : int, optional
            Index de départ, by default None
        count : int, optional
            Nombre de games à chercher, by default None
        identifiant_game : str, optional
            ID spécifique d'une game
        me : dict, optional
            Données du joueur déjà chargées
        """
        # Appel du constructeur de base avec les bons paramètres
        super().__init__(
            id_compte=id_compte,
            riot_id=riot_id,
            riot_tag=riot_tag,
            idgames=idgames,
            queue=queue,
            index=index,
            count=count,
            identifiant_game=identifiant_game,
            me=me
        )
        
        # Chargement du modèle de scoring
        try:
            with open('model/model_scoring.pkl', 'rb') as f:
                self.model = pickle.load(f)
        except FileNotFoundError:
            self.model = None

    @timer
    async def run(self, embed=None, difLP=0, save=True):
        """
        Exécute l'analyse complète du match.
        
        Parameters
        ----------
        embed : discord.Embed, optional
            Embed Discord pour les résultats
        difLP : int
            Différence de LP
            
        Returns
        -------
        embed : discord.Embed
            Embed enrichi avec les résultats
        """
        # Session HTTP
        self.session = aiohttp.ClientSession()
        self.save = save

        try:
            # 1. Récupération des données Riot
            # await self.get_data_riot()

            # 2. Préparation des données de base
            await self.prepare_data()

            # 3. Données d'équipe
            await self._extract_team_data()
            await self._extract_comparison_data()
            await self._extract_masteries()
            await self._load_items_data()
            await self._load_rank_data_riot()

            
            # 4. Modes spéciaux
            if self.thisQ == 'ARENA 2v2':
                await self.prepare_data_arena()
            elif self.thisQ == 'SWARM':
                await self.prepare_data_swarm()
            elif self.thisQ in ['CLASH', 'CLASH ARAM']:
                await self.prepare_data_clash()

            # 5. Données externes (si activé)
            self.n_moba = 1 if self.thisId <= 4 else 0
            self.team = 0 if self.thisId <= 4 else 1
            
            if self.moba_ok:
                await self._load_rank_data()
                await self._calculate_team_averages()
                try:
                    
                    await self.prepare_data_moba()
                except Exception:
                    try:
                        await self.prepare_data_ugg()
                    except Exception:
                        pass


            # Sauvegarde timeline pour ranked/flex/swiftplay
            if self.thisQ in ['RANKED', 'FLEX', 'SWIFTPLAY'] and self.thisTime >= 15:
                await self.save_timeline()
                await self._extract_early_game_data()

                try:
                    await self.save_timeline_event()
                except Exception:
                    print('Erreur save timeline event')

                await self.analyze_ganks()
                await self.save_gank_data()

            # stats = self.get_gank_stats_from_db(self.last_match)
            # jungler_history = self.get_jungler_stats_aggregated("Faker")            
                
            await self.calculate_all_scores()
            # await self.save_player_scoring_profiles()
            await self.save_player_scoring_data()

            # 7. Détections
            #await self.detection_joueurs_pro()
            #await self.detection_smurf()
            #await self.detection_mauvais_joueur()
            #await self.detection_first_time()
            #await self.detection_otp()
            #await self.detection_serie_victoire()
            #await self.ecart_cs_by_role()
            await self.detection_gap()

            # # 8. Sauvegarde
            # if self.save:
            #     await self.save_data()
                
            #     if self.thisQ == 'ARENA 2v2':
            #         await self.save_data_arena()
            #     elif self.thisQ == 'SWARM':
            #         await self.save_data_swarm()
            #     elif self.thisQ in ['CLASH', 'CLASH ARAM']:
            #         await self.save_data_clash()

            # 9. Badges
            await self.calcul_badges(self.save)

            # 10. Objectifs
            await self.traitement_objectif()

            # # 11. Image de résumé
            # if embed:
            #     embed = await self.resume_general(f'match_{self.last_match}', embed, difLP)

            # return embed

        except Exception as e:
            raise e
        # finally:
        #     await close_connexion()
        
    async def close_connexion(self):
        await self.session.close()

    async def get_observations(self):
        """
        Retourne les observations formatées pour Discord.
        
        Returns
        -------
        dict
            Dictionnaire contenant toutes les observations
        """
        observations = {
            'proplayers': getattr(self, 'observations_proplayers', ''),
            'smurf': getattr(self, 'observations_smurf', ''),
            'mauvais_joueur': getattr(self, 'observations_mauvais_joueur', ''),
            'first_time': getattr(self, 'first_time', ''),
            'otp': getattr(self, 'otp', ''),
            'serie': getattr(self, 'serie_victoire', ''),
            'ecart_cs': getattr(self, 'ecart_cs_txt', ''),
            'gap': getattr(self, 'txt_gap', ''),
            'badges': getattr(self, 'observations', ''),
            'badges2': getattr(self, 'observations2', ''),
        }
        return observations


    async def get_lobby_analysis(self) -> str:
        """
        Fusionne toutes les détections en un seul texte pour le field 'Analyse lobby'.
        
        Returns:
            str: Texte fusionné, vide si aucune détection.
        """
        parts = []

        # Joueurs pro
        await self.detection_joueurs_pro()
        if self.observations_proplayers:
            for line in self.observations_proplayers.strip().split('\n'):
                if line.strip():
                    parts.append(f":stadium: {line.strip()}")

        # Bons joueurs (smurfs)
        await self.detection_smurf()
        if self.observations_smurf:
            for line in self.observations_smurf.strip().split('\n'):
                if line.strip():
                    parts.append(f"💪 {line.strip()}")

        # Mauvais joueurs
        await self.detection_mauvais_joueur()
        if self.observations_mauvais_joueur:
            for line in self.observations_mauvais_joueur.strip().split('\n'):
                if line.strip():
                    parts.append(f"👎 {line.strip()}")

        # First time
        await self.detection_first_time()
        if self.first_time:
            for line in self.first_time.strip().split('\n'):
                if line.strip():
                    parts.append(f"<:worryschool:1307745643996905519> {line.strip()}")

        # OTP
        await self.detection_otp()
        if self.otp:
            for line in self.otp.strip().split('\n'):
                if line.strip():
                    parts.append(f"1️⃣ {line.strip()}")

        # Série victoire/défaite
        await self.detection_serie_victoire()
        if self.serie_victoire:
            for line in self.serie_victoire.strip().split('\n'):
                if line.strip():
                    parts.append(f"🔥 {line.strip()}")

        # Écart CS
        await self.ecart_cs_by_role()
        if self.ecart_cs_txt:
            for line in self.ecart_cs_txt.strip().split('\n'):
                if line.strip():
                    parts.append(f"👻 {line.strip()}")

        return '\n'.join(parts)

    async def get_summary(self):
        """
        Retourne un résumé des stats du match.
        
        Returns
        -------
        dict
            Dictionnaire contenant le résumé
        """
        return {
            'match_id': self.last_match,
            'champion': self.thisChampName,
            'win': self.thisWinBool,
            'kda': f'{self.thisKills}/{self.thisDeaths}/{self.thisAssists}',
            'kda_ratio': self.thisKDA,
            'cs': self.thisMinion + self.thisJungleMonsterKilled,
            'cs_min': self.thisMinionPerMin,
            'vision': self.thisVision,
            'damage': self.thisDamage,
            'damage_ratio': self.thisDamageRatio,
            'gold': self.thisGold,
            'duration': f'{self.thisTime // 60}:{self.thisTime % 60:02d}',
            'mode': self.thisQ,
            'position': self.thisPosition,
        }

    @classmethod
    async def from_match_id(cls, match_id, id_compte, riot_id, riot_tag, 
                            queue='RANKED', save=False, moba_ok=True):
        """
        Crée une instance à partir d'un ID de match.
        
        Parameters
        ----------
        match_id : str
            ID du match
        id_compte : int
            ID du compte
        riot_id : str
            Riot ID
        riot_tag : str
            Tag Riot
        queue : str
            Type de queue
        save : bool
            Sauvegarder les données
        moba_ok : bool
            Utiliser les APIs externes
            
        Returns
        -------
        MatchLol
            Instance initialisée
        """
        instance = cls(id_compte, riot_id, riot_tag, match_id, queue, 
                       me=None, save=save, moba_ok=moba_ok)
        return instance

 


    async def get_scoring_embed_field(self):
        """
        Retourne un field Discord pour l'embed avec le profil du champion.
        
        Returns:
            dict avec 'name', 'value', 'inline' ou None si pas de données
        """
        if not hasattr(self, 'player_breakdown') or self.player_breakdown is None:
            return None
        
        perf = self.get_player_performance_summary()
        breakdown = perf['breakdown']
        
        # Récupérer le profil du joueur
        if self.thisId > 4:
            id_player = self.thisId - 5
        else:
            id_player = self.thisId

        profile_info = self.get_player_scoring_profile_summary(id_player)
        profile = profile_info.get('profile', 'UNKNOWN') if profile_info else 'UNKNOWN'
        profile_emoji = get_profile_emoji(profile)
        profile_name = get_profile_name_fr(profile)
        
        # Barre visuelle pour chaque dimension
        def score_bar(score):
            filled = int(score)
            return '█' * filled + '░' * (10 - filled)
        
        # Indicateur si des ajustements sont appliqués
        adjustments = profile_info.get('adjustments', {}) if profile_info else {}
        has_adjustments = any(
            v != 1.0 for k, v in adjustments.items() 
            if k.endswith('_mult')
        ) or any(
            v != 0.0 for k, v in adjustments.items() 
            if k.endswith('_adj')
        )
        
        # adjustment_indicator = " ⚙️" if has_adjustments else ""
        
        value = f"""**Score: {perf['score']}/10** {perf['emoji']} ({perf['rank_text']})
    {profile_emoji} Profil: **{profile_name}**

    ⚔️ Combat: `{score_bar(breakdown['combat_value'])}` {breakdown['combat_value']}
    💰 Économie: `{score_bar(breakdown['economic_efficiency'])}` {breakdown['economic_efficiency']}
    🎯 Objectifs: `{score_bar(breakdown['objective_contribution'])}` {breakdown['objective_contribution']}
    ⚡ Tempo: `{score_bar(breakdown['pace_rating'])}` {breakdown['pace_rating']}
    👑 Impact: `{score_bar(breakdown['win_impact'])}` {breakdown['win_impact']}
    """
        # {perf['best_dimension_emoji']} Point fort: **{perf['best_dimension']}**
        return {
            'name': '📊 Performance',
            'value': value,
            'inline': False
        }


    # =============================================================================
    # VERSION DÉTAILLÉE AVEC PLUS D'INFOS SUR LE PROFIL
    # =============================================================================

    async def get_scoring_embed_field_detailed(self):
        """
        Version détaillée qui montre aussi les ajustements appliqués.
        
        Returns:
            dict avec 'name', 'value', 'inline' ou None si pas de données
        """
        if not hasattr(self, 'player_breakdown') or self.player_breakdown is None:
            return None
        
        perf = self.get_player_performance_summary()
        breakdown = perf['breakdown']
        
        # Récupérer le profil du joueur

        # Récupérer le profil du joueur
        if self.thisId > 4:
            id_player = self.thisId - 5
        else:
            id_player = self.thisId

        profile_info = self.get_player_scoring_profile_summary(id_player)
        profile = profile_info.get('profile', 'UNKNOWN') if profile_info else 'UNKNOWN'
        profile_emoji = get_profile_emoji(profile)
        profile_name = get_profile_name_fr(profile)
        champion = profile_info.get('champion', '') if profile_info else ''
        
        # Barre visuelle
        def score_bar(score):
            filled = int(score)
            return '█' * filled + '░' * (10 - filled)
        
        # Construire la description des ajustements
        adjustments = profile_info.get('adjustments', {}) if profile_info else {}
        adj_parts = []
        
        if adjustments.get('damage_per_min_mult', 1.0) != 1.0:
            mult = adjustments['damage_per_min_mult']
            adj_parts.append(f"DPM×{mult:.2f}")
        if adjustments.get('damage_taken_share_mult', 1.0) != 1.0:
            mult = adjustments['damage_taken_share_mult']
            adj_parts.append(f"Tank×{mult:.2f}")
        if adjustments.get('kp_mult', 1.0) != 1.0:
            mult = adjustments['kp_mult']
            adj_parts.append(f"KP×{mult:.2f}")
        if adjustments.get('vision_mult', 1.0) != 1.0:
            mult = adjustments['vision_mult']
            adj_parts.append(f"Vision×{mult:.2f}")
        
        adj_text = f" ({', '.join(adj_parts)})" if adj_parts else ""
        
        value = f"""**Score: {perf['score']}/10** {perf['emoji']} ({perf['rank_text']})
    {profile_emoji} **{champion}** → {profile_name}{adj_text}

    ⚔️ Combat: `{score_bar(breakdown['combat_value'])}` {breakdown['combat_value']}
    💰 Économie: `{score_bar(breakdown['economic_efficiency'])}` {breakdown['economic_efficiency']}
    🎯 Objectifs: `{score_bar(breakdown['objective_contribution'])}` {breakdown['objective_contribution']}
    ⚡ Tempo: `{score_bar(breakdown['pace_rating'])}` {breakdown['pace_rating']}
    👑 Impact: `{score_bar(breakdown['win_impact'])}` {breakdown['win_impact']}
    """
        
        # {perf['best_dimension_emoji']} Point fort: **{perf['best_dimension']}**
        
        return {
            'name': '📊 Performance',
            'value': value,
            'inline': False
        }


    # =============================================================================
    # FONCTIONS HELPER POUR L'AFFICHAGE DES PROFILS DANS LES LISTES
    # =============================================================================

    def format_player_with_profile(self, player_index: int, show_adjustments: bool = False) -> str:
        """
        Formate une ligne pour un joueur avec son profil.
        
        Parameters:
            player_index: Index du joueur (0-9)
            show_adjustments: Afficher les multiplicateurs appliqués
            
        Returns:
            String formaté pour Discord
        """
        try:
            from fonctions.match.champion_profiles import (
                get_profile_for_champion,
                get_profile_adjustments,
                get_champion_tags,
            )
            from utils.emoji import emote_champ_discord
            
            champion = self.thisChampNameListe[player_index] if player_index < len(self.thisChampNameListe) else ''
            riot_id = self.thisRiotIdListe[player_index] if player_index < len(self.thisRiotIdListe) else ''
            role = self.thisPositionListe[player_index] if player_index < len(self.thisPositionListe) else ''
            score = self.scores_liste[player_index] if player_index < len(self.scores_liste) else 0
            
            # Profil
            profile = get_profile_for_champion(champion, role)
            profile_emoji = get_profile_emoji(profile.value if profile else 'UNKNOWN')
            
            # Emoji champion
            champ_emoji = emote_champ_discord.get(champion.capitalize(), '')
            
            # Score emoji
            score_emoji = self.get_score_emoji(score)
            
            # Badge MVP/ACE
            badge = ''
            if player_index == self.mvp_index:
                badge = ' 🏆'
            elif player_index == self.ace_index:
                badge = ' ⭐'
            
            line = f"{champ_emoji} **{riot_id}** ({role}) {profile_emoji} `{score}` {score_emoji}{badge}"
            
            if show_adjustments:
                adj = get_profile_adjustments(role, profile)
                adj_parts = []
                if adj.damage_per_min_mult != 1.0:
                    adj_parts.append(f"DPM×{adj.damage_per_min_mult:.1f}")
                if adj.damage_taken_share_mult != 1.0:
                    adj_parts.append(f"Tank×{adj.damage_taken_share_mult:.1f}")
                if adj_parts:
                    line += f" ({', '.join(adj_parts)})"
            
            return line
            
        except Exception:
            return f"Joueur {player_index}"


    def get_team_profiles_summary(self, team: str = 'blue') -> str:
        """
        Retourne un résumé des profils d'une équipe.
        
        Parameters:
            team: 'blue' (indices 0-4) ou 'red' (indices 5-9)
            
        Returns:
            String formaté pour Discord
        """
        start = 0 if team.lower() == 'blue' else 5
        end = 5 if team.lower() == 'blue' else 10
        
        lines = []
        for i in range(start, min(end, len(self.scores_liste))):
            lines.append(self.format_player_with_profile(i))
        
        return '\n'.join(lines)




# Export pour faciliter les imports
__all__ = ['MatchLol']
