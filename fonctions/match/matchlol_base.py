"""
Classe principale matchlol - Partie 1: Initialisation et récupération des données.
"""

import os
import sys
import traceback
import pickle
import math
import warnings

import pandas as pd
import numpy as np
import aiohttp
import sqlalchemy.exc
from sqlalchemy.exc import IntegrityError
from PIL import Image, ImageDraw
from io import BytesIO

from fonctions.gestion_bdd import (
    lire_bdd, get_data_bdd, requete_perso_bdd, lire_bdd_perso, sauvegarde_bdd
)
from fonctions.channels_discord import mention
from fonctions.api_calls import getPlayerStats, getRanks, update_ugg, get_role, get_player_match_history
from fonctions.api_moba import (
    update_moba, get_mobalytics, get_player_match_history_moba,
    get_role_stats, get_wr_ranked, detect_win_streak,
    get_stat_champion_by_player_mobalytics, get_rank_moba
)
from utils.lol import elo_lp, dict_points, dict_id_q
from utils.emoji import emote_champ_discord, emote_rank_discord
from utils.params import api_key_lol, region, my_region

from .riot_api import (
    get_version, get_champ_list, get_summoner_by_riot_id,
    get_summonerinfo_by_puuid, get_list_matchs_with_me,
    get_match_detail, get_match_timeline, get_data_rank,
    get_image, get_data_champ_tags
)
from .utils import fix_temps, dict_data, charger_font, load_timeline
from .masteries import get_masteries_old, get_stat_champion_by_player

warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None


class MatchLolBase:
    """Classe de base pour le traitement des matchs LoL."""

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
        Initialise la classe pour traiter un match.

        Parameters
        ----------
        id_compte : int
            ID du compte dans la base de données
        riot_id : str
            Riot ID du joueur
        riot_tag : str
            Tag Riot du joueur
        idgames : int
            Numéro de la game (0 = plus récente)
        queue : int, optional
            Type de queue (0 = toutes), by default 0
        index : int, optional
            Index de départ de la recherche, by default None (sera 0)
        count : int, optional
            Nombre de games à chercher, by default None (sera True pour l'API)
        identifiant_game : str, optional
            ID spécifique d'une game, by default None
        me : dict, optional
            Données du joueur déjà chargées, by default None
        """
        self.id_compte = id_compte
        self.riot_id = riot_id
        self.riot_tag = riot_tag
        self.idgames = idgames
        self.queue = queue
        # Valeurs par défaut comme dans l'original
        self.index = index  # None par défaut
        self.count = count  # None par défaut (sera True dans l'API)
        self.params_me = {'api_key': api_key_lol}
        self.model = ''

        if identifiant_game is None:
            self.identifiant_game = identifiant_game
        else:
            self.identifiant_game = str(identifiant_game)
            if 'EUW' not in self.identifiant_game:
                self.identifiant_game = f'EUW1_{self.identifiant_game}'
        self.me = me

        # Chargement des paramètres
        params = lire_bdd_perso('select * from settings', format='dict', index_col='parametres')

        self.ugg = params['update_ugg']['value']
        self.season = int(params['saison']['value'])
        self.last_season = params['last_season']['value']
        self.split = int(params['split']['value'])
        self.season_ugg = int(params['season_ugg']['value'])
        self.season_ugg_min = int(params['season_ugg_min']['value'])
        self.activate_mobalytics = str(params['data_mobalytics']['value'])

        self.list_season_ugg = list(range(self.season_ugg_min, self.season_ugg + 1))
        
        # Initialisation des attributs par défaut pour éviter les AttributeError
        self._init_default_attributes()

    def _init_default_attributes(self):
        """Initialise tous les attributs par défaut pour éviter les AttributeError."""
        # Attributs de base
        self.moba_ok = True
        self.session = None
        self.puuid = None
        self.info_account = None
        self.my_matches = []
        self.last_match = None
        self.match_detail_stats = None
        self.avatar = 0
        self.level_summoner = 0
        self.version = {}
        self.current_champ_list = {}
        self.match_detail = None
        self.thisQId = 0
        self.thisQ = 'OTHER'
        self.nb_joueur = 10
        self.data_timeline = ''
        self.index_timeline = 0
        self.liste_puuid = []
        self.liste_account_id = []
        
        # Attributs du joueur
        self.thisId = 0
        self.champ_dict = {}
        self.dic = {}
        self.match_detail_participants = {}
        self.match_detail_challenges = {}
        self.thisPosition = ''
        self.summonerName = ''
        self.timestamp = ''
        self.thisChamp = 0
        self.thisChampName = ''
        self.thisKills = 0
        self.thisDeaths = 0
        self.thisAssists = 0
        self.thisDouble = 0
        self.thisTriple = 0
        self.thisQuadra = 0
        self.thisPenta = 0
        self.thisWinId = False
        self.thisWin = ''
        self.thisWinBool = False
        self.thisTime = 0
        self.thisTimeLiving = 0
        self.time_CC = 0
        self.largest_crit = 0
        self.teamId = 100
        
        # Dégâts
        self.thisDamage = 0
        self.thisDamageNoFormat = 0
        self.thisDamageAP = 0
        self.thisDamageAPNoFormat = 0
        self.thisDamageAD = 0
        self.thisDamageADNoFormat = 0
        self.thisDamageTrue = 0
        self.thisDamageTrueNoFormat = 0
        self.thisDamageTrueAllNoFormat = 0
        self.thisDamageADAllNoFormat = 0
        self.thisDamageAPAllNoFormat = 0
        self.thisDamageAllNoFormat = 0
        self.thisDamageTaken = 0
        self.thisDamageTakenNoFormat = 0
        self.thisDamageTakenAD = 0
        self.thisDamageTakenADNoFormat = 0
        self.thisDamageTakenAP = 0
        self.thisDamageTakenAPNoFormat = 0
        self.thisDamageTakenTrue = 0
        self.thisDamageTakenTrueNoFormat = 0
        
        # Vision et farm
        self.thisVision = 0
        self.thisJungleMonsterKilled = 0
        self.thisMinion = 0
        self.thisPink = 0
        self.thisWards = 0
        self.thisWardsKilled = 0
        self.thisGold = 0
        self.thisGoldNoFormat = 0
        
        # Stats par minute
        self.thisMinionPerMin = 0
        self.thisVisionPerMin = 0
        self.thisGoldPerMinute = 0
        self.thisDamagePerMinute = 0
        self.thisDamageTrueAllPerMinute = 0
        self.thisDamageADAllPerMinute = 0
        self.thisDamageAPAllPerMinute = 0
        self.thisDamageAllPerMinute = 0
        self.damage_per_kills = 0
        self.thisKDA = 0
        self.kills_min = 0
        self.deaths_min = 0
        self.assists_min = 0
        
        # Stats avancées
        self.thisSpellUsed = 0
        self.thisbuffsVolees = 0
        self.thisSpellsDodged = 0
        self.thisSoloKills = 0
        self.thisDanceHerald = 0
        self.thisPerfectGame = 0
        self.thisJUNGLEafter10min = 0
        self.thisCSafter10min = 0
        self.thisKillingSprees = 0
        self.thisDamageSelfMitigated = 0
        self.thisDamageTurrets = 0
        self.thisDamageObjectives = 0
        self.thisGoldEarned = 0
        self.thisKillsSeries = 0
        self.thisTotalHealed = 0
        self.thisTotalShielded = 0
        self.thisTotalOnTeammates = 0
        self.thisTurretsKillsPerso = 0
        self.thisTurretsLost = 0
        self.thisTimeSpendDead = 0
        self.thisTimeSpendAlive = 0
        self.first_tower_time = 999
        
        # Stats optionnelles
        self.thisAtakhanTeam = 0
        self.thisCSAdvantageOnLane = 0
        self.thisLevelAdvantage = 0
        self.AFKTeam = 0
        self.AFKTeamBool = False
        self.thisSkillshot_dodged = 0
        self.thisSkillshot_hit = 0
        self.thisSkillshot_dodged_per_min = 0
        self.thisSkillshot_hit_per_min = 0
        self.thisTurretPlatesTaken = 0
        self.ControlWardInRiver = 0
        self.thisVisionAdvantage = 0
        self.earliestDrake = 0
        self.earliestBaron = 0
        self.participation_tower = 0
        self.petales_sanglants = 0
        self.enemy_immobilisation = 0
        self.totaltimeCCdealt = 0
        self.snowball = 0
        
        # Sorts et items
        self.spell1 = 0
        self.spell2 = 0
        self.thisPing = 0
        self.item = {}
        self.thisItems = []
        
        # Pings
        self.pings_allin = 0
        self.pings_assistsme = 0
        self.pings_basics = 0
        self.pings_command = 0
        self.pings_danger = 0
        self.pings_ennemymissing = 0
        self.pings_ennemy_vision = 0
        self.pings_get_back = 0
        self.pings_hold = 0
        self.pings_onmyway = 0
        
        # Sorts lancés
        self.s1cast = 0
        self.s2cast = 0
        self.s3cast = 0
        self.s4cast = 0
        
        # Stats équipe
        self.thisBaronPerso = 0
        self.thisElderPerso = 0
        self.thisBaronTeam = 0
        self.thisDragonTeam = 0
        self.thisHordeTeam = 0
        self.thisHeraldTeam = 0
        self.thisTowerTeam = 0
        self.thisInhibTeam = 0
        self.thisTurretsKillsTeam = 0
        self.thisTeamKills = 0
        self.thisTeamKillsOp = 0
        self.trade_efficience = 0
        
        # Ratios
        self.thisKP = 0
        self.thisDamageRatio = 0
        self.thisDamageTakenRatio = 0
        self.gold_share = 0
        self.ecart_gold_team = 0
        self.DamageGoldRatio = 0
        self.killsratio = 0
        self.deathsratio = 0
        self.solokillsratio = 0
        self.thisAllieFeeder = 0
        
        # Listes
        self.thisDoubleListe = []
        self.thisTripleListe = []
        self.thisQuadraListe = []
        self.thisPentaListe = []
        
        # Ecarts
        self.ecart_kills = 0
        self.ecart_morts = 0
        self.ecart_assists = 0
        self.ecart_dmg = 0
        self.ecart_top_gold = 0
        self.ecart_jgl_gold = 0
        self.ecart_mid_gold = 0
        self.ecart_adc_gold = 0
        self.ecart_supp_gold = 0
        self.ecart_top_cs = 0
        self.ecart_jgl_cs = 0
        self.ecart_mid_cs = 0
        self.ecart_adc_cs = 0
        self.ecart_supp_cs = 0
        
        # Timeline timestamps
        self.timestamp_fourth_dragon = 0
        self.timestamp_first_elder = 0
        self.timestamp_first_horde = 0
        self.timestamp_doublekill = 0
        self.timestamp_triplekill = 0
        self.timestamp_quadrakill = 0
        self.timestamp_pentakill = 0
        self.timestamp_niveau_max = 0
        self.timestamp_first_blood = 0
        
        # Timeline paliers
        self.total_cs_20 = 0
        self.total_cs_30 = 0
        self.total_gold_20 = 0
        self.total_gold_30 = 0
        self.totalDamageTaken_10 = 0
        self.totalDamageTaken_20 = 0
        self.totalDamageTaken_30 = 0
        self.trade_efficience_10 = 0
        self.trade_efficience_20 = 0
        self.trade_efficience_30 = 0
        self.totalDamageDone_10 = 0
        self.totalDamageDone_20 = 0
        self.totalDamageDone_30 = 0
        self.assists_10 = 0
        self.assists_20 = 0
        self.assists_30 = 0
        self.deaths_10 = 0
        self.deaths_20 = 0
        self.deaths_30 = 0
        self.champion_kill_10 = 0
        self.champion_kill_20 = 0
        self.champion_kill_30 = 0
        self.level_10 = 0
        self.level_20 = 0
        self.level_30 = 0
        self.jgl_20 = 0
        self.jgl_30 = 0
        self.WARD_KILL_10 = 0
        self.WARD_KILL_20 = 0
        self.WARD_KILL_30 = 0
        self.WARD_PLACED_10 = 0
        self.WARD_PLACED_20 = 0
        self.WARD_PLACED_30 = 0
        
        # Stats max timeline
        self.max_abilityHaste = 0
        self.max_ap = 0
        self.max_armor = 0
        self.max_ad = 0
        self.currentgold = 0
        self.max_hp = 0
        self.max_mr = 0
        self.movement_speed = 0
        
        # Ranked
        self.thisTier = ' '
        self.thisRank = ' '
        self.thisLP = 0
        self.thisVictory = 0
        self.thisLoose = 0
        self.thisWinrateStat = 0
        
        # URLs
        self.url_game = ''
        
        # Observations (pour badges/détections)
        self.observations = ''
        self.observations2 = ''
        self.observations_proplayers = ''
        self.observations_smurf = ''
        self.observations_mauvais_joueur = ''
        self.first_time = ''
        self.otp = ''
        self.serie_victoire = ''
        self.ecart_cs_txt = ''
        self.txt_gap = ''
        
        # Badges
        self.badges = []

    async def get_data_riot(self):
        """
        Récupère les infos de base:
        - ID du joueur
        - ID de la game
        - Version du jeu
        - Liste des champions
        """
        self.session = aiohttp.ClientSession()

        # Construction des paramètres de requête
        # index=None et count=None correspondent aux valeurs par défaut de l'API
        self.params_my_match = {'api_key': api_key_lol}
        
        if self.index is not None:
            self.params_my_match['start'] = self.index
        if self.count is not None:
            self.params_my_match['count'] = self.count
        if self.queue != 0:
            self.params_my_match['queue'] = self.queue

        if self.me is None:
            self.me = await get_summoner_by_riot_id(self.session, self.riot_id, self.riot_tag)

        self.puuid = self.me['puuid']
        self.info_account = await get_summonerinfo_by_puuid(self.puuid, self.session)

        # Recherche de l'ID de la game
        if self.identifiant_game is None:
            self.my_matches = await get_list_matchs_with_me(self.session, self.me, self.params_my_match)
            self.last_match = self.my_matches[self.idgames]
        else:
            self.last_match = self.identifiant_game

        # Détail du match sélectionné
        self.match_detail_stats = await get_match_detail(self.session, self.last_match, self.params_me)

        self.avatar = self.info_account['profileIconId']
        self.level_summoner = self.info_account['summonerLevel']

        # Version du jeu et champions
        self.version = await get_version(self.session)
        self.current_champ_list = await get_champ_list(self.session, self.version)

        self.match_detail = pd.DataFrame(self.match_detail_stats)

        self.thisQId = self.match_detail['info']['queueId']
        self.thisQ = dict_id_q.get(self.thisQId, 'OTHER')

        if self.thisQ == 'ARENA 2v2':
            self.nb_joueur = 8
        elif self.thisQ == 'SWARM':
            self.nb_joueur = 3
        else:
            self.nb_joueur = 10

        # Timeline du match
        if self.thisQ in ['RANKED', 'FLEX', 'SWIFTPLAY']:
            self.data_timeline = await get_match_timeline(self.session, self.last_match)
            self.index_timeline = self.data_timeline['metadata']['participants'].index(self.puuid) + 1
        else:
            self.data_timeline = ''
            self.index_timeline = 0

        self.liste_puuid = self.match_detail['metadata']['participants']
        self.liste_account_id = [
            self.match_detail['info']['participants'][i]['summonerId']
            for i in range(self.nb_joueur)
        ]

    async def prepare_data(self):
        """Récupère et prépare les données complètes de la game."""
        # Dictionnaire des champions
        self.champ_dict = {}
        for key in self.current_champ_list['data']:
            row = self.current_champ_list['data'][key]
            self.champ_dict[row['key']] = row['id']

        # Mapping des participants
        try:
            self.dic = {
                (self.match_detail['info']['participants'][i]['riotIdGameName']).lower().replace(" ", "") +
                "#" + (self.match_detail['info']['participants'][i]['riotIdTagline'].upper()): i
                for i in range(self.nb_joueur)
            }
        except KeyError:
            # Ancienne game sans Riot ID
            self.dic = {
                (self.match_detail['info']['participants'][i]['summonerName']).lower().replace(" ", ""): i
                for i in range(self.nb_joueur)
            }

        # Identification du joueur
        try:
            self.thisId = self.dic[
                self.riot_id.lower().replace(" ", "") + "#" + self.riot_tag.upper()
            ]
        except KeyError:
            # Changement de pseudo - utiliser le PUUID
            self.dic = {
                self.match_detail['metadata']['participants'][i]: i
                for i in range(self.nb_joueur)
            }
            self.thisId = self.dic[self.puuid]

        self.match_detail_participants = self.match_detail['info']['participants'][self.thisId]
        self.match_detail_challenges = self.match_detail_participants['challenges']
        self.thisPosition = self.match_detail_participants['teamPosition']

        # Normalisation des positions
        position_mapping = {
            "MIDDLE": "MID",
            "BOTTOM": "ADC",
            "UTILITY": "SUPPORT"
        }
        self.thisPosition = position_mapping.get(str(self.thisPosition), self.thisPosition)

        # Extraction des données du participant
        await self._extract_participant_data()
        await self._extract_team_data()
        await self._extract_comparison_data()
        await self._extract_masteries()

    async def _extract_participant_data(self):
        """Extrait les données du participant principal."""
        p = self.match_detail_participants
        c = self.match_detail_challenges

        try:
            self.summonerName = p['summonerName'].lower().replace(' ', '')
        except KeyError:
            self.summonerName = p['riotIdGameName'].lower().replace(' ', '')

        self.timestamp = str(self.match_detail['info']['gameCreation'])[:-3]
        self.thisChamp = p['championId']
        self.thisDouble = p['doubleKills']
        self.thisTriple = p['tripleKills']
        self.thisQuadra = p['quadraKills']
        self.thisPenta = p['pentaKills']
        self.thisChampName = self.champ_dict[str(self.thisChamp)]
        self.thisKills = p['kills']
        self.thisDeaths = p['deaths']
        self.thisAssists = p['assists']
        self.thisWinId = p['win']
        self.thisTimeLiving = fix_temps(round((int(p['longestTimeSpentLiving']) / 60), 2))
        self.thisWin = ' '
        self.thisTime = fix_temps(round((int(self.match_detail['info']['gameDuration']) / 60), 2))
        self.time_CC = p['timeCCingOthers']
        self.largest_crit = p['largestCriticalStrike']
        self.teamId = p['teamId']

        # Si le joueur n'est pas mort, le temps est à 0
        if self.thisTimeLiving == 0:
            self.thisTimeLiving = self.thisTime

        # Dégâts
        self.thisDamage = p['totalDamageDealtToChampions']
        self.thisDamageNoFormat = p['totalDamageDealtToChampions']
        self.thisDamageAP = p['magicDamageDealtToChampions']
        self.thisDamageAPNoFormat = p['magicDamageDealtToChampions']
        self.thisDamageAD = p['physicalDamageDealtToChampions']
        self.thisDamageADNoFormat = p['physicalDamageDealtToChampions']
        self.thisDamageTrue = p['trueDamageDealtToChampions']
        self.thisDamageTrueNoFormat = p['trueDamageDealtToChampions']
        self.thisDamageTrueAllNoFormat = p['trueDamageDealt']
        self.thisDamageADAllNoFormat = p['physicalDamageDealt']
        self.thisDamageAPAllNoFormat = p['magicDamageDealt']
        self.thisDamageAllNoFormat = p['totalDamageDealt']

        # Multikills par équipe
        self.thisDoubleListe = dict_data(self.thisId, self.match_detail, 'doubleKills')
        self.thisTripleListe = dict_data(self.thisId, self.match_detail, 'tripleKills')
        self.thisQuadraListe = dict_data(self.thisId, self.match_detail, 'quadraKills')
        self.thisPentaListe = dict_data(self.thisId, self.match_detail, 'pentaKills')

        # Temps mort/vivant
        self.thisTimeSpendDead = fix_temps(round(float(p['totalTimeSpentDead']) / 60, 2))
        self.thisTimeSpendAlive = fix_temps(round(self.thisTime - self.thisTimeSpendDead, 2))

        # Première tour
        try:
            self.first_tower_time = c['firstTurretKilledTime']
            self.first_tower_time = fix_temps(round((self.first_tower_time / 60), 2))
        except KeyError:
            self.first_tower_time = 999

        # Dégâts subis
        self.thisDamageTaken = int(p['totalDamageTaken'])
        self.thisDamageTakenNoFormat = int(p['totalDamageTaken'])
        self.thisDamageTakenAD = int(p['physicalDamageTaken'])
        self.thisDamageTakenADNoFormat = int(p['physicalDamageTaken'])
        self.thisDamageTakenAP = int(p['magicDamageTaken'])
        self.thisDamageTakenAPNoFormat = int(p['magicDamageTaken'])
        self.thisDamageTakenTrue = int(p['trueDamageTaken'])
        self.thisDamageTakenTrueNoFormat = int(p['trueDamageTaken'])

        # Vision et farm
        self.thisVision = p['visionScore']
        self.thisJungleMonsterKilled = p['neutralMinionsKilled']
        self.thisMinion = p['totalMinionsKilled'] + self.thisJungleMonsterKilled
        self.thisPink = p['visionWardsBoughtInGame']
        self.thisWards = p['wardsPlaced']
        self.thisWardsKilled = p['wardsKilled']
        self.thisGold = int(p['goldEarned'])
        self.thisGoldNoFormat = int(p['goldEarned'])

        # Sorts
        self.spell1 = p['summoner1Id']
        self.spell2 = p['summoner2Id']

        # Pings
        try:
            self.thisPing = p['basicPings']
        except Exception:
            self.thisPing = 0

        # Items
        self.item = p
        self.thisItems = [self.item[f'item{i}'] for i in range(6)]

        # Statistiques par minute
        self.thisMinionPerMin = round((self.thisMinion / self.thisTime), 2)
        self.thisVisionPerMin = round((self.thisVision / self.thisTime), 2)
        self.thisGoldPerMinute = round((self.thisGold / self.thisTime), 2)
        self.thisDamagePerMinute = round(int(p['totalDamageDealtToChampions']) / self.thisTime, 0)
        self.thisDamageTrueAllPerMinute = round(int(p['trueDamageDealt']) / self.thisTime, 0)
        self.thisDamageADAllPerMinute = round(int(p['physicalDamageDealt']) / self.thisTime, 0)
        self.thisDamageAPAllPerMinute = round(int(p['magicDamageDealt']) / self.thisTime, 0)
        self.thisDamageAllPerMinute = round(int(p['totalDamageDealt']) / self.thisTime, 0)

        self.damage_per_kills = round((self.thisDamage / self.thisKills), 0) if self.thisKills != 0 else 0

        # KDA
        if int(self.thisDeaths) >= 1:
            self.thisKDA = float(round(c['kda'], 2))
        else:
            self.thisKDA = 0

        self.kills_min = np.round(self.thisKills / self.thisTime, 2)
        self.deaths_min = np.round(self.thisDeaths / self.thisTime, 2)
        self.assists_min = np.round(self.thisAssists / self.thisTime, 2)

        # Stats avancées
        self.thisSpellUsed = c['abilityUses']
        self.thisbuffsVolees = c['buffsStolen']
        self.thisSpellsDodged = c['dodgeSkillShotsSmallWindow']
        self.thisSoloKills = c['soloKills']
        self.thisDanceHerald = c['dancedWithRiftHerald']
        self.thisPerfectGame = c['perfectGame']
        self.thisJUNGLEafter10min = int(c['jungleCsBefore10Minutes'])
        self.thisCSafter10min = c['laneMinionsFirst10Minutes'] + self.thisJUNGLEafter10min
        self.thisKillingSprees = p['killingSprees']
        self.thisDamageSelfMitigated = p['damageSelfMitigated']
        self.thisDamageTurrets = p['damageDealtToTurrets']
        self.thisDamageObjectives = p['damageDealtToObjectives']
        self.thisGoldEarned = p['goldEarned']
        self.thisKillsSeries = p['largestKillingSpree']
        self.thisTotalHealed = p['totalHeal']
        self.thisTotalShielded = p['totalDamageShieldedOnTeammates']
        self.thisTotalOnTeammates = p['totalHealsOnTeammates']
        self.thisTurretsKillsPerso = p['turretKills']
        self.thisTurretsLost = p['turretsLost']

        # Pings détaillés
        self.pings_allin = p['allInPings']
        self.pings_assistsme = p['assistMePings']
        self.pings_basics = p['basicPings']
        self.pings_command = p['commandPings']
        self.pings_danger = p['dangerPings']
        self.pings_ennemymissing = p['enemyMissingPings']
        self.pings_ennemy_vision = p['enemyVisionPings']
        self.pings_get_back = p['getBackPings']
        self.pings_hold = p['holdPings']
        self.pings_onmyway = p['onMyWayPings']

        # Sorts lancés
        self.s1cast = p['spell1Casts']
        self.s2cast = p['spell2Casts']
        self.s3cast = p['spell3Casts']
        self.s4cast = p['spell4Casts']

        # Stats d'équipe personnelles
        self.thisBaronPerso = c['teamBaronKills']
        self.thisElderPerso = c['teamElderDragonKills']

        # Trade efficience
        try:
            self.trade_efficience = round(self.thisDamageNoFormat / self.thisDamageTakenNoFormat * 100, 2)
        except ZeroDivisionError:
            self.trade_efficience = 0
            
        url_match = self.last_match[5:]
        url_participant = int(self.thisId) + 1   
        self.url_game = f'https://www.leagueofgraphs.com/fr/match/euw/{url_match}#{url_participant}'
    
        self.thisStats = await get_data_rank(self.session, self.puuid)
        self._profil_ranked()

        # Stats optionnelles avec gestion d'erreur
        self._extract_optional_stats()

    def _extract_optional_stats(self):
        """Extrait les statistiques optionnelles avec gestion des erreurs."""
        c = self.match_detail_challenges

        try:
            self.thisAtakhanTeam = self.match_detail['info']['teams'][self.team if hasattr(self, 'team') else 0]['objectives']['atakhan']['kills']
        except:
            self.thisAtakhanTeam = 0

        try:
            self.thisCSAdvantageOnLane = round(c['maxCsAdvantageOnLaneOpponent'], 0)
        except Exception:
            self.thisCSAdvantageOnLane = 0

        try:
            self.thisLevelAdvantage = c['maxLevelLeadLaneOpponent']
        except Exception:
            self.thisLevelAdvantage = 0

        try:
            self.AFKTeam = c['hadAfkTeammate']
            self.AFKTeamBool = True
        except Exception:
            self.AFKTeam = 0
            self.AFKTeamBool = False

        self.thisSkillshot_dodged = c['skillshotsDodged']
        self.thisSkillshot_hit = c['skillshotsHit']
        self.thisSkillshot_dodged_per_min = round((self.thisSkillshot_dodged / self.thisTime), 2)
        self.thisSkillshot_hit_per_min = round((self.thisSkillshot_hit / self.thisTime), 2)

        try:
            self.thisTurretPlatesTaken = c['turretPlatesTaken']
        except Exception:
            self.thisTurretPlatesTaken = 0

        try:
            self.ControlWardInRiver = round(c['controlWardTimeCoverageInRiverOrEnemyHalf'], 2)
        except Exception:
            self.ControlWardInRiver = 0

        try:
            self.thisVisionAdvantage = round(c['visionScoreAdvantageLaneOpponent'] * 100, 2)
        except Exception:
            self.thisVisionAdvantage = 0

        try:
            self.earliestDrake = fix_temps(round(c['earliestDragonTakedown'] / 60, 2))
        except Exception:
            self.earliestDrake = 0

        try:
            self.earliestBaron = fix_temps(round(c['earliestBaron'] / 60, 2))
        except Exception:
            self.earliestBaron = 0

        try:
            self.participation_tower = round((self.thisTurretsKillsPerso / self.thisTurretsKillsTeam) * 100, 2)
        except Exception:
            self.participation_tower = 0

        try:
            self.petales_sanglants = c['InfernalScalePickup']
        except:
            self.petales_sanglants = 0

        self.enemy_immobilisation = c['enemyChampionImmobilizations']
        self.totaltimeCCdealt = fix_temps(round((int(self.match_detail_participants['totalTimeCCDealt']) / 60), 2))

        # Victoire/Défaite
        if str(self.thisWinId) == 'True':
            self.thisWin = "GAGNER"
            self.thisWinBool = True
        else:
            self.thisWin = "PERDRE"
            self.thisWinBool = False

        # Snowball ARAM
        if self.thisQ in ['ARAM', 'CLASH ARAM']:
            try:
                self.snowball = self.match_detail_challenges['snowballsHit']
            except Exception:
                self.snowball = 0
        else:
            self.snowball = -1

    def _profil_ranked(self):
        # Variables principales du joueur (inchangées)
        
        stats_mode = "RANKED_FLEX_SR" if self.thisQ == 'FLEX' else "RANKED_SOLO_5x5"
        try:
            for i in range(len(self.thisStats)):
                if str(self.thisStats[i]['queueType']) == stats_mode:
                    self.i = i
                    break
            self.thisWinrate = int(self.thisStats[self.i]['wins']) / (
                int(self.thisStats[self.i]['wins']) + int(self.thisStats[self.i]['losses']))
            self.thisWinrateStat = str(int(self.thisWinrate * 100))
            self.thisRank = str(self.thisStats[self.i]['rank'])
            self.thisTier = str(self.thisStats[self.i]['tier'])
            self.thisLP = str(self.thisStats[self.i]['leaguePoints'])
            self.thisVictory = str(self.thisStats[self.i]['wins'])
            self.thisLoose = str(self.thisStats[self.i]['losses'])
            self.thisWinStreak = str(self.thisStats[self.i]['hotStreak'])
        except (IndexError, AttributeError):
            self.thisWinrate = '0'
            self.thisWinrateStat = '0'
            self.thisRank = 'En placement'
            self.thisTier = " "
            self.thisLP = '0'
            self.thisVictory = '0'
            self.thisLoose = '0'
            self.thisWinStreak = '0'
        except KeyError:
            if self.thisQ == 'ARAM':
                self.thisWinrate = '0'
                self.thisWinrateStat = '0'
                self.thisRank = 'Inconnu'
                self.thisTier = " "
                self.thisLP = '0'
                self.thisVictory = '0'
                self.thisLoose = '0'
                self.thisWinStreak = '0'
            else:
                data_joueur = lire_bdd_perso(f'SELECT * from suivi_s{self.season} where index = {self.id_compte}').T
                self.thisWinrate = int(data_joueur['wins'].values[0]) / (
                    int(data_joueur['wins'].values[0]) + int(data_joueur['losses'].values[0]))
                self.thisWinrateStat = str(int(self.thisWinrate * 100))
                self.thisRank = str(data_joueur['rank'].values[0])
                self.thisTier = str(data_joueur['tier'].values[0])
                self.thisLP = str(data_joueur['LP'].values[0])
                self.thisVictory = str(data_joueur['wins'].values[0])
                self.thisLoose = str(data_joueur['losses'].values[0])
                self.thisWinStreak = str(data_joueur['serie'].values[0])