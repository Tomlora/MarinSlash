"""
Classe MatchLol principale - Assemble tous les mixins.
"""

import pickle
import aiohttp
import pandas as pd

from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd

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
    ClashModeMixin
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
            with open('data/model_scoring.pkl', 'rb') as f:
                self.model = pickle.load(f)
        except FileNotFoundError:
            self.model = None

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

                await self.prepare_data_moba()
                # except Exception:
                #     try:
                #         await self.prepare_data_ugg()
                #     except Exception:
                #         pass

            # # 6. Timeline
            # if self.thisQ not in ['ARENA 2v2', 'SWARM']:
            #     await self.save_timeline()
            #     await self.save_timeline_event()

            # 7. Détections
            await self.detection_joueurs_pro()
            await self.detection_smurf()
            await self.detection_mauvais_joueur()
            await self.detection_first_time()
            await self.detection_otp()
            await self.detection_serie_victoire()
            await self.ecart_cs_by_role()
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


# Export pour faciliter les imports
__all__ = ['MatchLol']
