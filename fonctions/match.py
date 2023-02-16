import os
import pandas as pd
import warnings
from fonctions.gestion_bdd import lire_bdd, get_data_bdd, requete_perso_bdd
from fonctions.params import saison
from fonctions.channels_discord import mention
import json
import numpy as np
import sys
from PIL import Image, ImageDraw, ImageFont
import plotly.graph_objects as go
from plotly.graph_objs import Layout
import plotly.express as px
from io import BytesIO
import aiohttp
import asyncio
import pickle

# TODO : rajouter temps en vie

warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'


dict_rankid = {"Non-classe 0": 0,
               "BRONZE IV": 1,
               "BRONZE III": 2,
               "BRONZE II": 3,
               "BRONZE I": 4,
               "SILVER IV": 5,
               "SILVER III": 6,
               "SILVER II": 7,
               "SILVER I": 8,
               "GOLD IV": 9,
               "GOLD III": 10,
               "GOLD II": 11,
               "GOLD I": 12,
               "PLATINUM IV": 13,
               "PLATINUM III": 14,
               "PLATINUM II": 15,
               "PLATINUM I": 16,
               "DIAMOND IV": 17,
               "DIAMOND III": 18,
               "DIAMOND II": 19,
               "DIAMOND I": 20,
               'MASTER I': 21,
               'GRANDMASTER I': 22,
               'CHALLENGER I': 23}

elo_lp = {'IRON': 0,
          'BRONZE': 1,
          'SILVER': 2,
          'GOLD': 3,
          'PLATINUM': 4,
          'DIAMOND': 5,
          'MASTER': 6,
          'GRANDMASTER': 7,
          'CHALLENGER': 8,
          'FIRST_GAME': 0}

dict_points = {41: [11, -19],
               42: [12, -18],
               43: [13, -17],
               44: [14, -16],
               45: [15, -15],
               46: [16, -15],
               47: [17, -15],
               48: [18, -15],
               49: [19, -15],
               50: [20, -15],
               51: [21, -15],
               52: [22, -15],
               53: [23, -15],
               54: [24, -15],
               55: [25, -15],
               56: [26, -14],
               57: [27, -13],
               58: [28, -12],
               59: [29, -11]}


def trouver_records(df, category, methode='max', identifiant='joueur'):
    """
    Trouve la ligne avec le record associé

    Parameters
    ----------
    df : `dataframe`
        df avec les records
    category : `str`
        colonne où chercher le record
    methode : `str`, optional
        min ou max ?, by default 'max'
    identifiant : `str`, optional
        'joueur' ou 'discord, by default 'joueur'
        
        joueur renvoie au pseudo lol
        
        discord renvoie au mention discord

    Returns
    -------
    joueur, champion, record, url
    """

    try:
        df[category] = pd.to_numeric(df[category])
        # pas de 0. Ca veut dire qu'il n'ont pas fait l'objectif par exemple
        df = df[df[category] != 0]
        df = df[df[category] != 0.0]
        if methode == 'max':
            col = df[category].idxmax(skipna=True)
        elif methode == 'min':
            col = df[category].idxmin(skipna=True)
        lig = df.loc[col]
        
        if identifiant == 'joueur':
            joueur = lig['joueur']
        elif identifiant == 'discord':
            joueur = mention(lig['discord'], 'membre')
            
        champion = lig['champion']
        record = lig[category]
        url_game = f'https://www.leagueofgraphs.com/fr/match/euw/{str(lig["match_id"])[5:]}#participant{int(lig["id_participant"])+1}'

    except:
        return 'inconnu', 'inconnu', 0, '#'

    return joueur, champion, record, url_game

def range_value(i, liste, min: bool = False):
    if i == np.argmax(liste[:5]) or i-5 == np.argmax(liste[5:]):
        fill = (0, 128, 0)
    elif (min == True) and (i == np.argmin(liste[:5]) or i-5 == np.argmin(liste[5:])):
        fill = (220, 20, 60)
    else:
        fill = (0, 0, 0)
    return fill


async def get_image(type, name, session: aiohttp.ClientSession, resize_x=80, resize_y=80):
    url_mapping = {
        "champion": f"https://ddragon.leagueoflegends.com/cdn/12.22.1/img/champion/{name}.png",
        "tier": f"./img/{name}.png",
        "avatar": f"https://ddragon.leagueoflegends.com/cdn/12.22.1/img/profileicon/{name}.png",
        "items": f'https://ddragon.leagueoflegends.com/cdn/12.22.1/img/item/{name}.png',
        "monsters": f'./img/monsters/{name}.png',
        "epee": f'./img/epee/{name}.png',
        "gold": f'./img/money.png',
        "autre": f'{name}.png',
        "kda": f'./img/rectangle/{name}.png',
    }
    
    url = url_mapping.get(type)
    if url is None:
        raise ValueError(f"Invalid image type: {type}")
    
    if "./" in url or type == 'autre': # si c'est vrai, l'image est en local.
        img = Image.open(url)
    else:
        response = await session.get(url)
        response.raise_for_status()
        img_raw = await response.read()
        img = Image.open(BytesIO(img_raw))
    img = img.resize((resize_x, resize_y))
    
    return img

api_key_lol = os.environ.get('API_LOL')

api_moba = os.environ.get('API_moba')
url_api_moba = os.environ.get('url_moba')


my_region = 'euw1'
region = "EUROPE"


async def get_mobalytics(pseudo : str, session: aiohttp.ClientSession, match_id):
    json_data = {
        'operationName': 'LolMatchDetailsQuery',
        'variables': {
            'region': 'EUW',
            'summonerName': pseudo,
            'matchId': match_id,
        },
        'extensions': {
            'persistedQuery': {
                'version': 1,
                'sha256Hash': api_moba,
            },
        },
    }
    async with session.post(url_api_moba, headers={'authority':'app.mobalytics.gg','accept':'*/*','accept-language':'en_us','content-type':'application/json','origin':'https://app.mobalytics.gg','sec-ch-ua-mobile':'?0','sec-ch-ua-platform':'"Windows"','sec-fetch-dest':'empty','sec-fetch-mode':'cors','sec-fetch-site':'same-origin','sec-gpc':'1','x-moba-client':'mobalytics-web','x-moba-proxy-gql-ops-name':'LolMatchDetailsQuery'}, json=json_data) as session_match_detail:
        match_detail_stats = await session_match_detail.json()  # detail du match sélectionné
        
    df_moba = pd.DataFrame(match_detail_stats['data']['lol']['player']['match']['participants'])
    return df_moba, match_detail_stats


async def get_version(session: aiohttp.ClientSession):

    async with session.get(f"https://ddragon.leagueoflegends.com/realms/euw.json") as session_version:
        version = await session_version.json()

    return version

async def get_champ_list(session: aiohttp.ClientSession, version):
    champions_versions = version['n']['champion']

    async with session.get(f"https://ddragon.leagueoflegends.com/cdn/{champions_versions}/data/fr_FR/champion.json") as session_champlist:
        current_champ_list = await session_champlist.json()
    
    return current_champ_list


async def get_summoner_by_name(session: aiohttp.ClientSession, key):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{key}', params={'api_key': api_key_lol}) as session_summoner:
        me = await session_summoner.json()  # informations sur le joueur
    return me


async def get_league_by_summoner(session: aiohttp.ClientSession, me):
    async with session.get(f"https://{my_region}.api.riotgames.com/lol/league/v4/entries/by-summoner/{me['id']}",
                           params={'api_key': api_key_lol}) as session_league:
        stats = await session_league.json()
    return stats


async def get_summoner_by_puuid(session, puuid):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}', params={'api_key': api_key_lol}) as session_summoner:
        me = await session_summoner.json()
    return me


async def get_list_matchs(session: aiohttp.ClientSession, me, params):
    async with session.get(f'https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{me["puuid"]}/ids?', params=params) as session_match:
        my_matches = await session_match.json()
    return my_matches


async def get_match_detail(session: aiohttp.ClientSession, match_id, params):
    async with session.get(f'https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}', params=params) as session_match_detail:
        match_detail_stats = await session_match_detail.json()  # detail du match sélectionné
    return match_detail_stats


async def get_match_timeline(session: aiohttp.ClientSession, match_id):
    async with session.get(f'https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline', params={'api_key': api_key_lol}) as session_timeline:
        match_detail_timeline = await session_timeline.json()
    return match_detail_timeline


async def get_challenges_config(session):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/challenges/v1/challenges/config?api_key={api_key_lol}') as challenge_config:
        data_challenges = await challenge_config.json()
        return data_challenges


async def get_challenges_data_joueur(session, puuid):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/challenges/v1/player-data/{puuid}?api_key={api_key_lol}') as challenge_joueur:
        data_joueur = await challenge_joueur.json()
        return data_joueur


def dict_data(thisId: int, match_detail, info):
    try:
        if thisId > 4:
            liste = [match_detail['info']['participants'][i][info] for i in range(5, 10)] + \
                    [match_detail['info']['participants'][i][info]
                        for i in range(0, 5)]
        else:
            liste = [match_detail['info']['participants'][i][info]
                     for i in range(0, 10)]
    except:
        if thisId > 4:
            liste = [match_detail['info']['participants'][i]['challenges'][info] for i in range(5, 10)] + \
                    [match_detail['info']['participants'][i]['challenges'][info]
                        for i in range(0, 5)]

        else:
            liste = [match_detail['info']['participants'][i]
                     ['challenges'][info] for i in range(0, 10)]

    return liste


async def match_by_puuid(summonerName,
                         idgames: int,
                         session,
                         index=0,
                         queue=0,
                         count=20):
    params_me = {'api_key': api_key_lol}
    if queue == 0:
        params_my_match = {'start': index,
                           'count': count, 'api_key': api_key_lol}
    else:
        params_my_match = {'queue': queue, 'start': index,
                           'count': count, 'api_key': api_key_lol}

    me = await get_summoner_by_name(session, summonerName)
    my_matches = await get_list_matchs(session, me, params_my_match)
    last_match = my_matches[idgames]  # match n° idgames
    # detail du match sélectionné
    match_detail_stats = await get_match_detail(session, last_match, params_me)

    return last_match, match_detail_stats, me


async def getId(summonerName, session):
    try:
        last_match, match_detail_stats, me = await match_by_puuid(summonerName, 0, session)
        return str(match_detail_stats['info']['gameId'])
    except KeyError:
        data = lire_bdd('tracker', 'dict')
        return str(data[summonerName]['id'])
    except asyncio.exceptions.TimeoutError:
        data = lire_bdd('tracker', 'dict')
        return str(data[summonerName]['id'])
    except:
        print('erreur getId')
        data = lire_bdd('tracker', 'dict')
        print(sys.exc_info())
        return str(data[summonerName]['id'])


class matchlol():

    def __init__(self,
                 summonerName,
                 idgames: int,
                 queue: int = 0,
                 index: int = 0,
                 count: int = 20,
                 identifiant_game=None):
        """Class pour traiter les matchs

        Parameters
        ----------
        summonerName : `str`
            nom d'un joueur lol
        idgames : `int`
            numéro de la game -> 0 étant la plus récente
        queue : `int`, optional
            type de game : se référer à l'api riot, by default 0 (toutes les games)
        index : `int`, optional
            numéro de la game où on commence la recherche, by default 0
        count : `int`, optional
            nombre de games à afficher dans la recherche, by default 20
        identifiant_game : _type_, optional
            id d'une game. Ignore tous les paramètres précédents exceptés summonername si renseigné, by default None
        """
        self.summonerName = summonerName
        self.idgames = idgames
        self.queue = queue
        self.index = index
        self.count = count
        self.params_me = {'api_key': api_key_lol}
        self.identifiant_game = identifiant_game

    async def get_data_riot(self):
        """Récupère les infos de base : 
        - id du joueur
        - id de la game
        - version du jeu
        - liste des champions"""
        
        self.session = aiohttp.ClientSession()
        
        if self.queue == 0:
            self.params_my_match = {'start': self.index,
                                    'count': self.count, 'api_key': api_key_lol}
        else:
            self.params_my_match = {
                'queue': self.queue, 'start': self.index, 'count': self.count, 'api_key': api_key_lol}

        self.me = await get_summoner_by_name(self.session, self.summonerName)

        # on recherche l'id de la game.
        if self.identifiant_game == None:
            self.my_matches = await get_list_matchs(self.session, self.me, self.params_my_match)
            self.last_match = self.my_matches[self.idgames]  # match n° idgames
        else:  # si identifiant_game est renseigné, on l'a déjà en entrée.
            self.last_match = self.identifiant_game
        # detail du match sélectionné
        self.match_detail_stats = await get_match_detail(self.session, self.last_match, self.params_me)

        self.avatar = self.me['profileIconId']
        self.level_summoner = self.me['summonerLevel']

        # on a besoin de la version du jeu pour obtenir les champions
        self.version = await get_version(self.session)
        # get champion list
        self.current_champ_list = await get_champ_list(self.session, self.version)

    async def prepare_data(self):
        """Récupère les données de la game"""

        # Detail de chaque champion...

        self.champ_dict = {}
        for key in self.current_champ_list['data']:
            row = self.current_champ_list['data'][key]
            self.champ_dict[row['key']] = row['id']

        self.match_detail = pd.DataFrame(self.match_detail_stats)

        self.dic = {(self.match_detail['info']['participants'][i]['summonerName']).lower(
        ).replace(" ", ""): i for i in range(10)}

        # stats
        try:
            self.thisId = self.dic[
                self.summonerName.lower().replace(" ", "")]  # cherche le pseudo dans le dico et renvoie le nombre entre 0 et 9
        except KeyError: # changement de pseudo ? On va faire avec le puuid
            self.dic = {(self.match_detail['metadata']['participants'][i]) : i for i in range(10)}
            self.thisId = self.dic[self.me['puuid']]

        self.thisQId = self.match_detail['info']['queueId']
        self.match_detail_participants = self.match_detail['info']['participants'][self.thisId]
        self.match_detail_challenges = self.match_detail_participants['challenges']
        self.thisPosition = self.match_detail_participants['teamPosition']
        self.season = 13  # TODO a modifier quand changement de saison

        if (str(self.thisPosition) == "MIDDLE"):
            self.thisPosition = "MID"
        elif (str(self.thisPosition) == "BOTTOM"):
            self.thisPosition = "ADC"
        elif (str(self.thisPosition) == "UTILITY"):
            self.thisPosition = "SUPPORT"

        self.timestamp = str(self.match_detail['info']['gameCreation'])[
            :-3]  # traduire avec datetime.date.fromtimestamp()
        self.thisQ = ' '
        self.thisChamp = self.match_detail_participants['championId']
        self.thisDouble = self.match_detail_participants['doubleKills']
        self.thisTriple = self.match_detail_participants['tripleKills']
        self.thisQuadra = self.match_detail_participants['quadraKills']
        self.thisPenta = self.match_detail_participants['pentaKills']
        self.thisChampName = self.champ_dict[str(self.thisChamp)]
        self.thisKills = self.match_detail_participants['kills']
        self.thisDeaths = self.match_detail_participants['deaths']
        self.thisAssists = self.match_detail_participants['assists']
        self.thisWinId = self.match_detail_participants['win']
        self.thisTimeLiving = round(
            (int(self.match_detail_participants['longestTimeSpentLiving']) / 60), 2)
        self.thisWin = ' '
        self.thisTime = round(
            (int(self.match_detail['info']['gameDuration']) / 60), 2)
        self.thisDamage = self.match_detail_participants['totalDamageDealtToChampions']
        self.thisDamageNoFormat = self.match_detail_participants['totalDamageDealtToChampions']
        self.thisDamageAP = self.match_detail_participants['magicDamageDealtToChampions']
        self.thisDamageAPNoFormat = self.match_detail_participants['magicDamageDealtToChampions']
        self.thisDamageAD = self.match_detail_participants['physicalDamageDealtToChampions']
        self.thisDamageADNoFormat = self.match_detail_participants['physicalDamageDealtToChampions']
        self.thisDamageTrue = self.match_detail_participants['trueDamageDealtToChampions']
        self.thisDamageTrueNoFormat = self.match_detail_participants['trueDamageDealtToChampions']
        
        self.thisDoubleListe = dict_data(
            self.thisId, self.match_detail, 'doubleKills')
        self.thisTripleListe = dict_data(
            self.thisId, self.match_detail, 'tripleKills')
        self.thisQuadraListe = dict_data(
            self.thisId, self.match_detail, 'quadraKills')
        self.thisPentaListe = dict_data(
            self.thisId, self.match_detail, 'pentaKills')

        self.thisTimeSpendDead = round(
            float(self.match_detail_participants['totalTimeSpentDead'])/60, 2)

        self.thisTimeSpendAlive = round(
            self.thisTime - self.thisTimeSpendDead, 2)

        self.thisDamageTaken = int(
            self.match_detail_participants['totalDamageTaken'])
        self.thisDamageTakenNoFormat = int(
            self.match_detail_participants['totalDamageTaken'])
        self.thisDamageTakenAD = int(
            self.match_detail_participants['physicalDamageTaken'])
        self.thisDamageTakenADNoFormat = int(
            self.match_detail_participants['physicalDamageTaken'])
        self.thisDamageTakenAP = int(
            self.match_detail_participants['magicDamageTaken'])
        self.thisDamageTakenAPNoFormat = int(
            self.match_detail_participants['magicDamageTaken'])
        self.thisDamageTakenTrue = int(
            self.match_detail_participants['trueDamageTaken'])
        self.thisDamageTakenTrueNoFormat = int(
            self.match_detail_participants['trueDamageTaken'])

        self.thisVision = self.match_detail_participants['visionScore']
        self.thisJungleMonsterKilled = self.match_detail_participants['neutralMinionsKilled']
        self.thisMinion = self.match_detail_participants['totalMinionsKilled'] + \
            self.thisJungleMonsterKilled
        self.thisPink = self.match_detail_participants['visionWardsBoughtInGame']
        self.thisWards = self.match_detail_participants['wardsPlaced']
        self.thisWardsKilled = self.match_detail_participants['wardsKilled']
        self.thisGold = int(self.match_detail_participants['goldEarned'])
        self.thisGoldNoFormat = int(
            self.match_detail_participants['goldEarned'])
        
        self.spell1 = self.match_detail_participants['summoner1Id']
        self.spell2 = self.match_detail_participants['summoner2Id']

        try:
            self.thisPing = self.match_detail_participants['basicPings']
        except:
            self.thisPing = 0
            
        self.item = self.match_detail_participants

        self.thisItems = [self.item[f'item{i}'] for i in range(6)]

        # item6 = ward. Pas utile

        # on transpose les items

        with open('./obj/item.json', encoding='utf-8') as mon_fichier:
            self.data = json.load(mon_fichier)

        self.data_item = list()

        for item in self.thisItems:
            if item != 0:  # si = 0, il n'y a pas d'items
                self.data_item.append(self.data['data'][str(item)]['name'])

        self.data_item = (' | '.join(self.data_item))

        self.thisMinionPerMin = round((self.thisMinion / self.thisTime), 2)
        self.thisVisionPerMin = round((self.thisVision / self.thisTime), 2)
        self.thisGoldPerMinute = round((self.thisGold / self.thisTime), 2)
        self.thisDamagePerMinute = round(
            int(self.match_detail_participants['totalDamageDealtToChampions']) / self.thisTime, 0)

        async with self.session.get(f"https://{my_region}.api.riotgames.com/lol/league/v4/entries/by-summoner/{self.me['id']}",
                                    params=self.params_me) as session4:
            self.thisStats = await session4.json()  # detail du match sélectionné
        self.thisWinrateStat = ' '
        self.thisWinrate = ' '
        self.thisRank = ' '
        self.thisLP = ' '

        if int(self.thisDeaths) >= 1:
            self.thisKDA = float(round(self.match_detail_challenges['kda'], 2))
        else:
            self.thisKDA = 0

        # Page record 2

        self.thisSpellUsed = self.match_detail_challenges['abilityUses']
        self.thisbuffsVolees = self.match_detail_challenges['buffsStolen']
        self.thisSpellsDodged = self.match_detail_challenges['dodgeSkillShotsSmallWindow']
        self.thisSoloKills = self.match_detail_challenges['soloKills']
        self.thisDanceHerald = self.match_detail_challenges['dancedWithRiftHerald']
        self.thisPerfectGame = self.match_detail_challenges['perfectGame']
        self.thisJUNGLEafter10min = int(
            self.match_detail_challenges['jungleCsBefore10Minutes'])
        self.thisCSafter10min = self.match_detail_challenges[
            'laneMinionsFirst10Minutes'] + self.thisJUNGLEafter10min
        self.thisKillingSprees = self.match_detail_participants['killingSprees']
        self.thisDamageSelfMitigated = self.match_detail_participants['damageSelfMitigated']
        self.thisDamageTurrets = self.match_detail_participants['damageDealtToTurrets']
        self.thisDamageObjectives = self.match_detail_participants['damageDealtToObjectives']
        self.thisGoldEarned = self.match_detail_participants['goldEarned']
        self.thisKillsSeries = self.match_detail_participants['largestKillingSpree']
        self.thisTotalHealed = self.match_detail_participants['totalHeal']
        self.thisTotalShielded = self.match_detail_participants['totalDamageShieldedOnTeammates']
        self.thisTotalOnTeammates = self.match_detail_participants['totalHealsOnTeammates']
        self.thisTurretsKillsPerso = self.match_detail_participants['turretKills']
        self.thisTurretsLost = self.match_detail_participants['turretsLost']

        # Stat de team :

        self.thisBaronPerso = self.match_detail_challenges['teamBaronKills']
        self.thisElderPerso = self.match_detail_challenges['teamElderDragonKills']
        # thisHeraldPerso = match_detail_challenges['teamRiftHeraldKills']

        if self.thisId <= 4:
            self.team = 0
            self.n_moba = 1
        else:
            self.team = 1
            self.n_moba = 0

        self.team_stats = self.match_detail['info']['teams'][self.team]['objectives']

        self.thisBaronTeam = self.team_stats['baron']['kills']
        self.thisDragonTeam = self.team_stats['dragon']['kills']
        self.thisHeraldTeam = self.team_stats['riftHerald']['kills']
        self.thisTurretsKillsTeam = self.team_stats['tower']['kills']

        # A voir...

        try:  # pas dispo en aram ?
            self.thisCSAdvantageOnLane = round(
                self.match_detail_challenges['maxCsAdvantageOnLaneOpponent'], 0)
        except:
            self.thisCSAdvantageOnLane = 0

        try:
            self.thisLevelAdvantage = self.match_detail_challenges['maxLevelLeadLaneOpponent']
        except:
            self.thisLevelAdvantage = 0

        try:  # si pas d'afk, la variable n'est pas présente
            self.AFKTeam = self.match_detail_challenges['hadAfkTeammate']
            self.AFKTeamBool = True
        except:
            self.AFKTeam = 0
            self.AFKTeamBool = False

        self.thisSkillshot_dodged = self.match_detail_challenges['skillshotsDodged']
        self.thisSkillshot_hit = self.match_detail_challenges['skillshotsHit']

        try:
            self.thisTurretPlatesTaken = self.match_detail_challenges['turretPlatesTaken']
        except:
            self.thisTurretPlatesTaken = 0

        try:  # si tu n'en poses pas, tu n'as pas la stat
            self.ControlWardInRiver = round(
                self.match_detail_challenges['controlWardTimeCoverageInRiverOrEnemyHalf'], 2)
        except:
            self.ControlWardInRiver = 0

        try:
            self.thisVisionAdvantage = round(
                self.match_detail_challenges['visionScoreAdvantageLaneOpponent']*100, 2)
        except:
            self.thisVisionAdvantage = 0

        try:  # si pas d'info, la team n'a pas fait de drake
            self.earliestDrake = round(
                self.match_detail_challenges['earliestDragonTakedown'] / 60, 2)
        except:
            self.earliestDrake = 0

        try:
            self.earliestBaron = round(
                self.match_detail_challenges['earliestBaron'] / 60, 2)
        except:
            self.earliestBaron = 0

        try:
            self.participation_tower = round(
                (self.thisTurretsKillsPerso / self.thisTurretsKillsTeam)*100, 2)
        except:
            self.participation_tower = 0

        if self.thisQId == 420:
            self.thisQ = "RANKED"
        elif self.thisQId == 400:
            self.thisQ = "NORMAL"
        elif self.thisQId == 440:
            self.thisQ = "FLEX"
        elif self.thisQId == 450:
            self.thisQ = "ARAM"
        else:
            self.thisQ = "OTHER"

        if str(self.thisWinId) == 'True':
            self.thisWin = "GAGNER"
            self.thisWinBool = True
        else:
            self.thisWin = "PERDRE"
            self.thisWinBool = False

        self.thisDamageListe = dict_data(
            self.thisId, self.match_detail, 'totalDamageDealtToChampions')
        self.thisDamageTakenListe = dict_data(
            self.thisId, self.match_detail, 'totalDamageTaken')
        self.thisDamageSelfMitigatedListe = dict_data(
            self.thisId, self.match_detail, 'damageSelfMitigated')

        if self.thisQ == 'ARAM':
            try:
                self.snowball = self.match_detail_challenges['snowballsHit']
            except:
                self.snowball = 0
        else:
            self.snowball = -1

        # pseudo

        self.thisPseudoListe = dict_data(
            self.thisId, self.match_detail, 'summonerName')

        # champ id

        self.thisChampListe = dict_data(
            self.thisId, self.match_detail, 'championId')

        # champ

        self.thisChampNameListe = [
            self.champ_dict[str(champ)] for champ in self.thisChampListe]

        # total kills

        self.thisKillsListe = dict_data(
            self.thisId, self.match_detail, 'kills')

        self.thisTeamKills = 0
        self.thisTeamKillsOp = 0
        
        for i, kill in enumerate(self.thisKillsListe):
            if i < 5:
                self.thisTeamKills += kill
            else:
                self.thisTeamKillsOp += kill

        # deaths

        self.thisDeathsListe = dict_data(
            self.thisId, self.match_detail, 'deaths')

        # Alliés feeder
        self.thisAllieFeeder = np.array(self.thisDeathsListe)
        self.thisAllieFeeder = float(self.thisAllieFeeder[0:5].max())

        # assists

        self.thisAssistsListe = dict_data(
            self.thisId, self.match_detail, 'assists')

        # gold

        self.thisGoldListe = dict_data(
            self.thisId, self.match_detail, 'goldEarned')

        self.thisChampTeam1 = [self.thisChampNameListe[i] for i in range(5)]
        self.thisChampTeam2 = [self.thisChampNameListe[i]
                               for i in range(5, 10)]

        self.thisGold_team1 = sum(self.thisGoldListe[:5])
        self.thisGold_team2 = sum(self.thisGoldListe[5:10])
        
        self.gold_share = round((self.thisGoldNoFormat / self.thisGold_team1) * 100,2)

        self.thisVisionListe = dict_data(
            self.thisId, self.match_detail, 'visionScore')
        
        self.thisVisionPerMinListe = [round((self.thisVisionListe[i] / self.thisTime), 1) for i in range(10)]

        self.thisJungleMonsterKilledListe = dict_data(
            self.thisId, self.match_detail, 'neutralMinionsKilled')
        self.thisMinionListe = dict_data(
            self.thisId, self.match_detail, 'totalMinionsKilled')

        self.thisKDAListe = dict_data(self.thisId, self.match_detail, "kda")
        
        self.thisMinionPerMinListe = [round((self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]) / self.thisTime, 1) for i in range(10)]

        self.thisLevelListe = dict_data(
            self.thisId, self.match_detail, "champLevel")

        def ecart_role(ally):
            return (self.thisMinionListe[ally] + self.thisJungleMonsterKilledListe[ally]) - (
                self.thisMinionListe[ally+5] + self.thisJungleMonsterKilledListe[ally+5])

        if self.team == 0:
            self.ecart_top_gold = self.thisGoldListe[0] - self.thisGoldListe[5]
            self.ecart_jgl_gold = self.thisGoldListe[1] - self.thisGoldListe[6]
            self.ecart_mid_gold = self.thisGoldListe[2] - self.thisGoldListe[7]
            self.ecart_adc_gold = self.thisGoldListe[3] - self.thisGoldListe[8]
            self.ecart_supp_gold = self.thisGoldListe[4] - \
                self.thisGoldListe[9]

            self.ecart_top_gold_affiche = self.thisGoldListe[0] - \
                self.thisGoldListe[5]
            self.ecart_jgl_gold_affiche = self.thisGoldListe[1] - \
                self.thisGoldListe[6]
            self.ecart_mid_gold_affiche = self.thisGoldListe[2] - \
                self.thisGoldListe[7]
            self.ecart_adc_gold_affiche = self.thisGoldListe[3] - \
                self.thisGoldListe[8]
            self.ecart_supp_gold_affiche = self.thisGoldListe[4] - \
                self.thisGoldListe[9]

            self.ecart_top_vision = self.thisVisionListe[0] - \
                self.thisVisionListe[5]
            self.ecart_jgl_vision = self.thisVisionListe[1] - \
                self.thisVisionListe[6]
            self.ecart_mid_vision = self.thisVisionListe[2] - \
                self.thisVisionListe[7]
            self.ecart_adc_vision = self.thisVisionListe[3] - \
                self.thisVisionListe[8]
            self.ecart_supp_vision = self.thisVisionListe[4] - \
                self.thisVisionListe[9]

            self.ecart_top_cs = ecart_role(0)
            self.ecart_jgl_cs = ecart_role(1)
            self.ecart_mid_cs = ecart_role(2)
            self.ecart_adc_cs = ecart_role(3)
            self.ecart_supp_cs = ecart_role(4)
            
            # on crée des variables temporaires pour le kpliste, car si une team ne fait pas de kills, on va diviser par 0, ce qui n'est pas possible
            temp_team_kills = self.thisTeamKills
            temp_team_kills_op = self.thisTeamKillsOp

            if temp_team_kills == 0:
                temp_team_kills = 1
            if temp_team_kills_op == 0:
                temp_team_kills_op = 1            

        
            self.thisKPListe = [int(round((self.thisKillsListe[i] + self.thisAssistsListe[i]) / (temp_team_kills if i < 5
                                                                                                 else temp_team_kills_op), 2) * 100)
                                for i in range(10)]

        elif self.team == 1:

            self.ecart_top_gold = self.thisGoldListe[0] - self.thisGoldListe[5]
            self.ecart_jgl_gold = self.thisGoldListe[1] - self.thisGoldListe[6]
            self.ecart_mid_gold = self.thisGoldListe[2] - self.thisGoldListe[7]
            self.ecart_adc_gold = self.thisGoldListe[3] - self.thisGoldListe[8]
            self.ecart_supp_gold = self.thisGoldListe[4] - \
                self.thisGoldListe[9]

            self.ecart_top_gold_affiche = self.thisGoldListe[0] - \
                self.thisGoldListe[5]
            self.ecart_jgl_gold_affiche = self.thisGoldListe[1] - \
                self.thisGoldListe[6]
            self.ecart_mid_gold_affiche = self.thisGoldListe[2] - \
                self.thisGoldListe[7]
            self.ecart_adc_gold_affiche = self.thisGoldListe[3] - \
                self.thisGoldListe[8]
            self.ecart_supp_gold_affiche = self.thisGoldListe[4] - \
                self.thisGoldListe[9]

            self.ecart_top_vision = self.thisVisionListe[0] - \
                self.thisVisionListe[5]
            self.ecart_jgl_vision = self.thisVisionListe[1] - \
                self.thisVisionListe[6]
            self.ecart_mid_vision = self.thisVisionListe[2] - \
                self.thisVisionListe[7]
            self.ecart_adc_vision = self.thisVisionListe[3] - \
                self.thisVisionListe[8]
            self.ecart_supp_vision = self.thisVisionListe[4] - \
                self.thisVisionListe[9]

            self.ecart_top_cs = ecart_role(0)
            self.ecart_jgl_cs = ecart_role(1)
            self.ecart_mid_cs = ecart_role(2)
            self.ecart_adc_cs = ecart_role(3)
            self.ecart_supp_cs = ecart_role(4)

            # on crée des variables temporaires pour le kpliste, car si une team ne fait pas de kills, on va diviser par 0, ce qui n'est pas possible
            temp_team_kills = self.thisTeamKills
            temp_team_kills_op = self.thisTeamKillsOp

            if temp_team_kills == 0:
                temp_team_kills = 1
            if temp_team_kills_op == 0:
                temp_team_kills_op = 1            

        
            self.thisKPListe = [int(round((self.thisKillsListe[i] + self.thisAssistsListe[i]) / (temp_team_kills if i < 5
                                                                                                 else temp_team_kills_op), 2) * 100)
                                for i in range(10)]

        self.adversaire_direct = {"TOP": self.ecart_top_gold, "JUNGLE": self.ecart_jgl_gold,
                                  "MID": self.ecart_mid_gold, "ADC": self.ecart_adc_gold, "SUPPORT": self.ecart_supp_gold}

        try:
            self.ecart_gold = self.adversaire_direct[self.thisPosition]
        except KeyError:
            self.ecart_gold = "Indisponible"

        # mise en forme
        
        variables_format = [self.thisGold_team1,
                     self.thisGold_team2,
                     self.ecart_top_gold,
                     self.ecart_jgl_gold,
                     self.ecart_mid_gold,
                     self.ecart_adc_gold,
                     self.ecart_supp_gold,
                     self.thisGold,
                     self.thisDamage,
                     self.thisDamageAD,
                     self.thisDamageAP,
                     self.thisDamageTrue,
                     self.thisDamageTaken,
                     self.thisDamageTakenAD,
                     self.thisDamageTakenAP,
                     self.thisDamageTakenTrue,
                     self.thisDamageObjectives]

        for var in variables_format:
            var = "{:,}".format(var).replace(',', ' ').replace('.', ',')

        if self.ecart_gold != "Indisponible":  # si nombre
            self.ecart_gold = "{:,}".format(
                self.ecart_gold).replace(',', ' ').replace('.', ',')

        self.thisDamageSelfMitigatedFormat = "{:,}".format(
            self.thisDamageSelfMitigated).replace(',', ' ').replace('.', ',')
        self.thisTimeLiving = str(self.thisTimeLiving).replace(".", "m")
        self.thisTotalOnTeammatesFormat = "{:,}".format(
            self.thisTotalOnTeammates).replace(',', ' ').replace('.', ',')


        try:
            self.thisKP = int(
                round((self.thisKills + self.thisAssists) / (self.thisTeamKills), 2) * 100)
        except:
            self.thisKP = 0

        # thisDamageRatio = round((float(thisDamage) / float(thisTeamDamage)) * 100, 2)
        self.thisDamageRatio = round(
            (self.match_detail_challenges['teamDamagePercentage']) * 100, 2)
        self.thisDamageTakenRatio = round(
            (self.match_detail_challenges['damageTakenOnTeamPercentage']) * 100, 2)

        self.thisDamageRatioListe = dict_data(
            self.thisId, self.match_detail, "teamDamagePercentage")
        self.thisDamageTakenRatioListe = dict_data(
            self.thisId, self.match_detail, "damageTakenOnTeamPercentage")
        
        # stats mobalytics
        
        self.data_mobalytics, self.data_mobalytics_complete = await get_mobalytics(self.summonerName, self.session, int(self.last_match[5:]))
             
        self.avgtier_ally = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.n_moba]['avgTier']['tier']
        self.avgrank_ally = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.n_moba]['avgTier']['division']
        
        self.avgtier_enemy = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.team]['avgTier']['tier']
        self.avgrank_enemy = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.team]['avgTier']['division']
        
        if self.thisId >= 5:
            dict_id = {5 : 0, 6 : 1, 7: 2, 8: 3, 9 : 4 }
            
            id_mobalytics = dict_id[self.thisId]
        else:
            id_mobalytics = self.thisId
        
        self.mvp = int(self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == self.thisPseudoListe[id_mobalytics]]['mvpScore'].values[0])
        
        self.badges = self.data_mobalytics_complete['data']['lol']['player']['match']['subject']['badges']

        # on doit identifier les stats soloq (et non flex...)
        try:
            if str(self.thisStats[0]['queueType']) == "RANKED_SOLO_5x5":
                self.i = 0
            else:
                self.i = 1

            self.thisWinrate = int(self.thisStats[self.i]['wins']) / (
                int(self.thisStats[self.i]['wins']) + int(self.thisStats[self.i]['losses']))
            self.thisWinrateStat = str(int(self.thisWinrate * 100))
            self.thisRank = str(self.thisStats[self.i]['rank'])
            self.thisTier = str(self.thisStats[self.i]['tier'])
            self.thisLP = str(self.thisStats[self.i]['leaguePoints'])
            self.thisVictory = str(self.thisStats[self.i]['wins'])
            self.thisLoose = str(self.thisStats[self.i]['losses'])
            self.thisWinStreak = str(self.thisStats[self.i]['hotStreak'])
        except IndexError:  # on va avoir une index error si le joueur est en placement, car Riot ne fournit pas dans son api les données de placement
            self.thisWinrate = '0'
            self.thisWinrateStat = '0'
            self.thisRank = 'En placement'
            self.thisTier = " "
            self.thisLP = '0'
            self.thisVictory = '0'
            self.thisLoose = '0'
            self.thisWinStreak = '0'


    async def save_data(self):
        """Sauvegarde l'ensemble des données dans la base de données"""

        requete_perso_bdd(f'''INSERT INTO public.matchs(
        match_id, joueur, role, champion, kills, assists, deaths, double, triple, quadra, penta,
        victoire, team_kills, team_deaths, "time", dmg, dmg_ad, dmg_ap, dmg_true, vision_score, cs, cs_jungle, vision_pink, vision_wards, vision_wards_killed,
        gold, cs_min, vision_min, gold_min, dmg_min, solokills, dmg_reduit, heal_total, heal_allies, serie_kills, cs_dix_min, jgl_dix_min,
        baron, drake, team, herald, cs_max_avantage, level_max_avantage, afk, vision_avantage, early_drake, temps_dead,
        item1, item2, item3, item4, item5, item6, kp, kda, mode, season, date, damageratio, tankratio, rank, tier, lp, id_participant, dmg_tank, shield,
        early_baron, allie_feeder, snowball, temps_vivant, dmg_tower, gold_share, mvp)
        VALUES (:match_id, :joueur, :role, :champion, :kills, :assists, :deaths, :double, :triple, :quadra, :penta,
        :result, :team_kills, :team_deaths, :time, :dmg, :dmg_ad, :dmg_ap, :dmg_true, :vision_score, :cs, :cs_jungle, :vision_pink, :vision_wards, :vision_wards_killed,
        :gold, :cs_min, :vision_min, :gold_min, :dmg_min, :solokills, :dmg_reduit, :heal_total, :heal_allies, :serie_kills, :cs_dix_min, :jgl_dix_min,
        :baron, :drake, :team, :herald, :cs_max_avantage, :level_max_avantage, :afk, :vision_avantage, :early_drake, :temps_dead,
        :item1, :item2, :item3, :item4, :item5, :item6, :kp, :kda, :mode, :season, :date, :damageratio, :tankratio, :rank, :tier, :lp, :id_participant, :dmg_tank, :shield,
        :early_baron, :allie_feeder, :snowball, :temps_vivant, :dmg_tower, :gold_share, :mvp);''',
                          {'match_id': self.last_match,
                           'joueur': self.summonerName.lower(),
                           'role': self.thisPosition,
                           'champion': self.thisChampName,
                           'kills': self.thisKills,
                           'assists': self.thisAssists,
                           'deaths': self.thisDeaths,
                           'double': self.thisDouble,
                           'triple': self.thisTriple,
                           'quadra': self.thisQuadra,
                           'penta': self.thisPenta,
                           'result': self.thisWinBool,
                           'team_kills': self.thisTeamKills,
                           'team_deaths': self.thisTeamKillsOp,
                           'time': self.thisTime,
                           'dmg': self.thisDamageNoFormat,
                           'dmg_ad': self.thisDamageADNoFormat,
                           'dmg_ap': self.thisDamageAPNoFormat,
                           'dmg_true': self.thisDamageTrueNoFormat,
                           'vision_score': self.thisVision,
                           'cs': self.thisMinion,
                           'cs_jungle': self.thisJungleMonsterKilled,
                           'vision_pink': self.thisPink,
                           'vision_wards': self.thisWards,
                           'vision_wards_killed': self.thisWardsKilled,
                           'gold': self.thisGoldNoFormat,
                           'cs_min': self.thisMinionPerMin,
                           'vision_min': self.thisVisionPerMin,
                           'gold_min': self.thisGoldPerMinute,
                           'dmg_min': self.thisDamagePerMinute,
                           'solokills': self.thisSoloKills,
                           'dmg_reduit': self.thisDamageSelfMitigated,
                           'heal_total': self.thisTotalHealed,
                           'heal_allies': self.thisTotalOnTeammates,
                           'serie_kills': self.thisKillingSprees,
                           'cs_dix_min': self.thisCSafter10min,
                           'jgl_dix_min': self.thisJUNGLEafter10min,
                           'baron': self.thisBaronTeam,
                           'drake': self.thisDragonTeam,
                           'team': self.team,
                           'herald': self.thisHeraldTeam,
                           'cs_max_avantage': self.thisCSAdvantageOnLane,
                           'level_max_avantage': self.thisLevelAdvantage,
                           'afk': self.AFKTeamBool,
                           'vision_avantage': self.thisVisionAdvantage,
                           'early_drake': self.earliestDrake,
                           'temps_dead': self.thisTimeSpendDead,
                           'item1': self.thisItems[0],
                           'item2': self.thisItems[1],
                           'item3': self.thisItems[2],
                           'item4': self.thisItems[3],
                           'item5': self.thisItems[4],
                           'item6': self.thisItems[5],
                           'kp': self.thisKP,
                           'kda': self.thisKDA,
                           'mode': self.thisQ,
                           'season': self.season,
                           'date': int(self.timestamp),
                           'damageratio': self.thisDamageRatio,
                           'tankratio': self.thisDamageTakenRatio,
                           'rank': self.thisRank,
                           'tier': self.thisTier,
                           'lp': self.thisLP,
                           'id_participant': self.thisId,
                           'dmg_tank': self.thisDamageTakenNoFormat,
                           'shield': self.thisTotalShielded,
                           'early_baron': self.earliestBaron,
                           'allie_feeder': self.thisAllieFeeder,
                           'snowball': self.snowball,
                           'temps_vivant': self.thisTimeSpendAlive,
                           'dmg_tower': self.thisDamageTurrets,
                           'gold_share' : self.gold_share,
                           'mvp' : self.mvp
                           })

    async def add_couronnes(self, points):
        """Ajoute les couronnes dans la base de données"""

        requete_perso_bdd('''UPDATE matchs SET couronne = :points WHERE match_id = :match_id AND joueur = :joueur''', {'points': points,
                                                                                                                       'match_id': self.last_match,
                                                                                                                       'joueur': self.summonerName.lower()})
        
    async def calcul_badges(self):
        
        def insight_text(slug, values, type):
                  
            type_comment = {'Positive' : ':green_circle:', 'Negative' : ':red_circle:', '' : ':first_place:' }
            
            dict_insight = {'early_game_farmer' : f'\n{type_comment[type]} Farm en early avec **{values[0]}** cs à 10 minutes',
                        # 'never_slacking' : f'\n{type_comment[type]} **{values[0]}** cs en mid game',
                        'teamfight_god' : f'\n{type_comment[type]} Gagné **{values[0]}** sur **{values[1]}** teamfights',
                        'lane_tyrant' : f"\n{type_comment[type]} **{values[0]}** gold d'avance à 15 minutes",
                        'stomp' : f"\n{type_comment[type]} **{values[0]}** gold d'avance",
                        # 'how_could_you' : f"\n{type_comment[type]} **{values[0]}** wards placés", TODO A remettre quand rito aura corrigé
                        # 'not_fan_of_wards' : f"\n{type_comment[type]} Placé **{values[0]}** wards",
                        'servant_of_darkness' : f"\n{type_comment[type]} Détruit **{values[0]}** wards",
                        'good_guy' : f"\n{type_comment[type]} Acheté **{values[0]}** pink",
                        'no_dragons_taken' : f"\n{type_comment[type]} Aucun dragon",
                        'no_rift_heralds_taken' : f"\n{type_comment[type]} Aucun herald",
                        'no_objectives_taken' : f"\n{type_comment[type]} Aucun objectif",
                        'ready_to_rumble' : f"\n{type_comment[type]} Proactif en early avec **{values[0]}** kills/assists avant 15 minutes",
                        'pick_up_artist' : f"\n{type_comment[type]} Sécurisé **{values[0]}** picks",
                        "wanderer" : f"\n{type_comment[type]} Roam énormément pour sécuriser kills et objectifs",
                        'survivor' : f"\n{type_comment[type]} Seulement  **{values[0]}** morts",
                        'elite_skirmisher' : f"\n{type_comment[type]} Gagné **{values[0]}** escarmouches sur **{values[1]}**",
                        'on_fire' : f"\n{type_comment[type]} **{round(values[0],2)}** KDA",
                        "wrecking_ball" : f"\n{type_comment[type]} **{values[0]}** Dégats aux structures",
                        "ouch_you_hurt" : f"\n{type_comment[type]} **{values[0]}** Dommages infligés",
                        "goblin_hoarder" : f"\n{type_comment[type]} **{int(values[0])}** Gold par minute",
                        "bringer_of_carnage" : f"\n{type_comment[type]} **{values[0]}** Kills",
                        "anti_kda_player" : f"\n{type_comment[type]} **{round(values[0],2)}** KDA",
                        "what_powerspike" : f"\n{type_comment[type]} Pas atteint le niveau 11",
                        "not_fan_of_farming" : f"\n {type_comment[type]} **{int(values[0])}** farm par minute",
                        "immortal" : f"\n {type_comment[type]} Immortel",
                        # "visionary" : f"\n {type_comment[type]} **{values[0]}** wards placés", # TODO à remettre quand rito aura corrigé
                        "no_control" : f"\n{type_comment[type]} Aucune pink",
                        "blood_thirsty" : f"\n{type_comment[type]} Tu as réussi **{values[0]}** ganks dans les 10 premières minutes.",
                        "superior_jungler" : f"\n{type_comment[type]} Tu as réussi plus de ganks que ton adversaire avec **{values[0]}**",
                        "comeback_king" : f"\n {type_comment[type]} Tu as réussi à comeback après un début difficile",
                        "safety_first" : f"\n{type_comment[type]} Tu as placé assez de vision pour préparer les objectifs neutres",
                        'no_damage_to_turrets' : f"\n{type_comment[type]} Tu n'as pas tapé les tours",
                        'mvp' : f"\n{type_comment[type]} Meilleur joueur"}
            
            return dict_insight.get(slug,'')

        self.observations = ''
        for insight in self.badges:
            self.observations += insight_text(insight['slug'], insight['values'], insight['type'])
            
        # Autres : 
        
        if self.thisDouble >= 3:
            self.observations += f"\n:green_circle: **{self.thisDouble}** doublé"
            
        if self.thisTriple >= 2:
            self.observations += f"\n:green_circle: **{self.thisTriple}** triplé"
        
        if self.thisQuadra >= 2:
            self.observations += f"\n:green_circle: **{self.thisQuadra}** quadra"
            
        if self.thisTotalHealed >= 5000:
            self.observations += f"\n:green_circle: **{self.thisTotalHealed}** HP soignés"
            
        if self.thisTotalShielded >= 3000:
            self.observations += f"\n:green_circle: **{self.thisTotalShielded} ** boucliers"
            
        if self.thisVisionAdvantage >= 60:
            self.observations += f"\n:green_circle: **{self.thisVisionAdvantage}**% AV vision"
        
        elif self.thisVisionAdvantage <= -50:
            self.observations += f"\n:red_circle: **{self.thisVisionAdvantage}**% AV vision"
            
        if self.thisSoloKills >= 1:
            self.observations += f"\n:green_circle: **{self.thisSoloKills}** solokills"
            
        if self.thisMinionPerMin >= 7:
            self.observations += f'\n:green_circle: **{self.thisMinionPerMin}** cs/min'
            
            


    async def resume_general(self,
                             name_img,
                             embed,
                             difLP):

        '''Resume global de la game

        Parameters
        -----------
        name_img : nom de l'image enregistré'''
        
        model = pickle.load(open('model/scoring_ridge.pkl', 'rb'))
        
        # def scoring(i):
        #     """Calcule la performance d'un joueur
        #     """
            
        #     score = model.predict(pd.DataFrame([[self.thisKillsListe[i],
        #                                          self.thisAssistsListe[i],
        #                                          self.thisDeathsListe[i],
        #                                          self.thisDoubleListe[i],
        #                                          self.thisTripleListe[i],
        #                                          self.thisQuadraListe[i],
        #                                          self.thisPentaListe[i],
        #                                          self.thisDamageListe[i],
        #                                          self.thisVisionListe[i],
        #                                          self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i],
        #                                          self.thisMinionPerMinListe[i],
        #                                          self.thisVisionPerMinListe[i],
        #                                          self.thisKPListe[i],
        #                                          self.thisKDAListe[i],
        #                                          self.thisDamageTakenListe[i]]]))

        #     return str(round(score[0],1))
            
        # Gestion de l'image 2
        lineX = 2600
        lineY = 100

        x_name = 350
        x_level = x_name - 350
        x_ecart = x_name - 200
        x_kills = 1000 + 120
        x_score = x_kills - 160
        x_deaths = x_kills + 100
        x_assists = x_deaths + 100

        x_kda = x_assists + 110

        x_kp = x_kda + 150

        x_cs = x_kp + 150

        x_vision = x_cs + 150

        x_dmg_percent = x_vision + 150

        x_dmg_taken = x_dmg_percent + 235

        x_kill_total = 1000
        x_objectif = 1700

        lineX = 2600
        lineY = 100

        x_name = 290
        y = 120
        y_name = y - 60
        x_rank = 1750

        x_metric = 120
        y_metric = 400

      

        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 50)  # Ubuntu 18.04
        except OSError:
            try:
                font = ImageFont.truetype("arial.ttf", 50)  # Windows
            except OSError:
                font = ImageFont.truetype(
                    "AppleSDGothicNeo.ttc", 50
                )  # MacOS

        try:
            font_little = ImageFont.truetype(
                "DejaVuSans.ttf", 40)  # Ubuntu 18.04
        except OSError:
            try:
                font_little = ImageFont.truetype("arial.ttf", 40)  # Windows
            except OSError:
                font_little = ImageFont.truetype(
                    "AppleSDGothicNeo.ttc", 40
                )  # MacOS

        im = Image.new("RGBA", (lineX, lineY * 13 + 190),
                       (255, 255, 255))  # Ligne blanche
        d = ImageDraw.Draw(im)
        
        line = Image.new("RGB", (lineX, 190), (230, 230, 230))  # Ligne grise
        im.paste(line, (0, 0))

        fill = (0, 0, 0)
        d.text((x_name, y_name), self.summonerName, font=font, fill=fill)

        im.paste(im=await get_image("avatar", self.avatar, self.session, 100, 100),
                 box=(x_name-240, y_name-20))

        im.paste(im=await get_image("champion", self.thisChampName, self.session, 100, 100),
                 box=(x_name-120, y_name-20))

        d.text((x_name+700, y_name-20),
               f"Niveau {self.level_summoner}", font=font_little, fill=fill)
        
        try: # Rank last season
            if self.thisQ != 'ARAM':
                data_last_season = get_data_bdd(f'''SELECT index, tier from suivi_s{self.season-1} where index = '{self.summonerName}' ''')
                self.tier_last_season = data_last_season.mappings().all()[0]['tier']
            else:
                data_last_season = get_data_bdd(f'''SELECT index, rank from ranked_aram_s{self.season-1} where index = '{self.summonerName}' ''')
                self.tier_last_season = data_last_season.mappings().all()[0]['rank']
            
            img_tier_last_season = await get_image("tier", self.tier_last_season, self.session, 100, 100)
            
            im.paste(img_tier_last_season,(x_name+950, y_name-50), img_tier_last_season.convert('RGBA'))
        except: # si pas d'info, on ne fait rien
            pass  

        if self.thisQ != "ARAM":  # si ce n'est pas le mode aram, on prend la soloq normal
            if self.thisTier != ' ':  # on vérifie que le joueur a des stats en soloq, sinon il n'y a rien à afficher
                img_rank = await get_image('tier', self.thisTier, self.session, 220, 220)

                im.paste(img_rank, (x_rank, y-140), img_rank.convert('RGBA'))

                d.text((x_rank+220, y-110),
                       f'{self.thisTier} {self.thisRank}', font=font, fill=fill)
                d.text((x_rank+220, y-45),
                       f'{self.thisLP} LP ({difLP})', font=font_little, fill=fill)

                # Gestion des bo
                if int(self.thisLP) == 100:
                    bo = self.thisStats[self.i]['miniSeries']
                    bo_wins = str(bo['wins'])
                    bo_losses = str(bo['losses'])
                    # bo_progress = str(bo['progress'])
                    d.text(
                        (x_rank+220, y+10), f'{self.thisVictory}W {self.thisLoose}L {self.thisWinrateStat}%  |  (BO3 : {bo_wins} / {bo_losses}) ', font=font_little, fill=fill)
                else:
                    d.text(
                        (x_rank+220, y+10), f'{self.thisVictory}W {self.thisLoose}L     {self.thisWinrateStat}% ', font=font_little, fill=fill)
            else:  # si pas de stats en soloq
                d.text((x_rank+220, y-45), 'En placement', font=font, fill=fill)

        else:  # si c'est l'aram, le traitement est différent

            data_aram = get_data_bdd(f'SELECT index,wins, losses, lp, games, k, d, a, activation, rank from ranked_aram_s{saison} WHERE index = :index', {
                                     'index': self.summonerName}).fetchall()

            wins_actual = data_aram[0]['wins']
            losses_actual = data_aram[0]['losses']
            lp_actual = data_aram[0]['lp']
            games_actual = data_aram[0]['games']
            k_actual = data_aram[0]['k']
            d_actual = data_aram[0]['d']
            a_actual = data_aram[0]['a']
            activation = data_aram[0]['activation']
            rank_actual = data_aram[0]['rank']

            if activation:

                games = games_actual + 1

                if str(self.thisWinId) == 'True':
                    wins = wins_actual + 1
                    losses = losses_actual

                else:
                    wins = wins_actual
                    losses = losses_actual + 1

                wr = round(wins / games, 2)*100

                # si afk et lose, pas de perte
                if self.AFKTeam >= 1 and str(self.thisWinId) != "True":
                    points = 0
                else:
                    # calcul des LP
                    if games <= 5:
                        if str(self.thisWinId) == 'True':
                            points = 50
                        else:
                            points = 0

                    elif wr >= 60:
                        if str(self.thisWinId) == 'True':
                            points = 30
                        else:
                            points = -10

                    elif wr <= 40:
                        if str(self.thisWinId) == "True":
                            points = 10
                        else:
                            points = -20
                    else:
                        if str(self.thisWinId) == "True":
                            points = dict_points[int(wr)][0]
                        else:
                            points = dict_points[int(wr)][1]

                lp = lp_actual + points

                # rank

                ranks = [
                    ('IRON', 100),
                    ('BRONZE', 200),
                    ('SILVER', 300),
                    ('GOLD', 500),
                    ('PLATINUM', 800),
                    ('DIAMOND', 1200),
                    ('MASTER', 1600),
                    ('GRANDMASTER', 2000),
                    ('CHALLENGER', float('inf'))
                ]

                for rank, lp_threshold in ranks:
                    if lp < lp_threshold:
                        break

                # SIMULATION CHANGEMENT ELO

                if games > 5 and self.AFKTeam == 0:  # si plus de 5 games et pas d'afk
                    lp = lp - elo_lp[rank]  # malus en fonction du elo

                # pas de lp negatif
                if lp < 0:
                    lp = 0

                if rank_actual != rank:
                    embed.add_field(
                        name="Changement d'elo", value=f" :star: Tu es passé de **{rank_actual}** à **{rank}**")

                k = k_actual + self.thisKills
                difLP = lp - lp_actual
                deaths = d_actual + self.thisDeaths
                a = a_actual + self.thisAssists

                img_rank = await get_image('tier', rank, self.session, 220, 220)

                im.paste(img_rank, (x_rank, y-140), img_rank.convert('RGBA'))
                d.text((x_rank+220, y-110), f'{rank}', font=font, fill=fill)
                d.text((x_rank+220, y-45),
                       f'{lp} LP ({difLP})', font=font_little, fill=fill)

                d.text((x_rank+220, y+10),
                       f'{wins}W {losses}L     {round(wr,1)}% ', font=font_little, fill=fill)

                # on met à jour
                requete_perso_bdd(f'''UPDATE ranked_aram_s{saison}
                                    SET wins = :wins,
                                    losses = :losses,
                                    lp = :lp,
                                    games = :games,
                                    k = :k,
                                    d = :d,
                                    a = :a,
                                    rank = :rank
                                  WHERE index = :index;
                                  UPDATE matchs
                                  SET tier = :rank,
                                  lp = :lp
                                  WHERE joueur = :index AND
                                  match_id = :match_id AND
                                  mode='ARAM';''',
                                  {'wins': wins,
                                   'losses': losses,
                                   'lp': lp,
                                   'games': games,
                                   'k': k,
                                   'd': deaths,
                                   'a': a,
                                   'rank': rank,
                                   'index': self.summonerName.lower(),
                                   'match_id': self.last_match})       
        
        line = Image.new("RGB", (lineX, lineY), (230, 230, 230))  # Ligne grise
        
        dict_position = {"TOP": 2, "JUNGLE": 3,
                         "MID": 4, "ADC": 5, "SUPPORT": 6}

        def draw_gray_line(i: int) -> None:
            im.paste(line, (0, (i * lineY) + 190))

        def draw_blue_line(i: int) -> None:
            im.paste(Image.new("RGB", (lineX, lineY),
                     (85, 85, 255)), (0, (i * lineY) + 190))

        def draw_red_line(i: int) -> None:
            im.paste(Image.new("RGB", (lineX, lineY),
                     (255, 70, 70)), (0, (i * lineY) + 190))

        def draw_light_blue_line(i: int) -> None:
            im.paste(Image.new("RGB", (lineX, lineY),
                     (173, 216, 230)), (0, (i*lineY) + 190))
            
        def draw_black_line() -> None:
            im.paste(Image.new("RGB", (lineX, 3),
                     (0, 0, 0)), (0, 180))

        for i in range(0, 13):
            if i % 2 == 0:
                draw_gray_line(i)
            elif i == 1:
                draw_blue_line(i)
            elif i == 7:
                draw_red_line(i)

            if self.thisQ != "ARAM":
                if i == dict_position[self.thisPosition]:
                    draw_light_blue_line(i)
                    
        draw_black_line()

        # match
        d.text((10, 20 + 190), self.thisQ, font=font, fill=(0, 0, 0))

        money = await get_image('gold', 'dragon', self.session, 60, 60)

        im.paste(money, (10, 120 + 190), money.convert('RGBA'))
        d.text((83, 120 + 190), f'{self.thisGold_team1}',
               font=font, fill=(255, 255, 255))
        im.paste(money, (10, 720 + 190), money.convert('RGBA'))
        d.text((83, 720 + 190), f'{self.thisGold_team2}', font=font, fill=(0, 0, 0))
        
        self.img_ally_avg = await get_image('tier', self.avgtier_ally.upper(), self.session, 100, 100)
        
        im.paste(self.img_ally_avg, (x_name+200, 120-20 + 190), self.img_ally_avg.convert('RGBA'))
        
        d.text((x_name+300, 120 + 190), str(
                    self.avgrank_ally), font=font, fill=(0, 0, 0))
        
        self.img_enemy_avg = await get_image('tier', self.avgtier_enemy.upper(), self.session, 100, 100)
        
        im.paste(self.img_enemy_avg, (x_name+200, 720-20 + 190), self.img_enemy_avg.convert('RGBA'))
        
        d.text((x_name+300, 720 + 190), str(
                    self.avgrank_enemy), font=font, fill=(0, 0, 0))

        for y in range(123 + 190, 724 + 190, 600):
            if y == 123 + 190:
                fill = (255, 255, 255)
            else:
                fill = (0, 0, 0)
            d.text((x_name, y), 'Name', font=font, fill=fill)
            
            
            d.text((x_kills, y), 'K', font=font, fill=fill)
            d.text((x_deaths, y), 'D', font=font, fill=fill)
            d.text((x_assists, y), 'A', font=font, fill=fill)
            d.text((x_kda, y), 'KDA', font=font, fill=fill)
            d.text((x_kp+10, y), 'KP', font=font, fill=fill)
            d.text((x_cs, y), 'CS', font=font, fill=fill)
            d.text((x_dmg_percent+10, y), "DMG", font=font, fill=fill)
            d.text((x_dmg_taken+10, y), 'TANK(reduit)', font=font, fill=fill)
            d.text((x_score-20, y), 'MVP', font=font, fill=fill)

            if self.thisQ != "ARAM":
                d.text((x_vision, y), 'VS', font=font, fill=fill)
                

        # participants
        initial_y = 223 + 190
        
        # array_scoring = np.array([]) # qu'on va mettre du plus grand au plus petit
        # liste = []  # en ordre en fonction des joueurs
        # for i in range(0,10):
        #     liste.append(scoring(i))
        #     scoring = liste[i]
        #     array_scoring = np.append(array_scoring, scoring)
        # array_scoring = np.sort(array_scoring)


        for i in range(0, 10):
            im.paste(
                im=await get_image("champion", self.thisChampNameListe[i], self.session),
                box=(10, initial_y-13),
            )
           
            d.text((x_name, initial_y),
                   self.thisPseudoListe[i], font=font, fill=(0, 0, 0))
            
            # rank
            
            rank_joueur = self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == self.thisPseudoListe[i]]['rank'].values[0]['tier']
            tier_joueur = self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == self.thisPseudoListe[i]]['rank'].values[0]['division']
            
            if rank_joueur != '':
                img_rank_joueur = await get_image('tier', rank_joueur.upper(), self.session, 100, 100)

                im.paste(img_rank_joueur, (x_score-200, initial_y-20), img_rank_joueur.convert('RGBA'))
                
                d.text((x_score-100, initial_y), str(
                        tier_joueur), font=font, fill=(0, 0, 0))
            
            # Scoring
            
            # mvp_pts = np.where(array_scoring == liste[i])[0][0]
            # d.text((x_score, initial_y),
                #     mvp_pts), font=font, fill=(0,0,0))
                
            scoring = self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == self.thisPseudoListe[i]]['mvpScore'].values[0]
            
            color_scoring = {1 : (0,128,0), 2 : (89,148,207), 3 : (67,89,232), 10 : (220,20,60)}

                
            d.text((x_score+20, initial_y),
                    str(scoring),
                    font=font,
                    fill=color_scoring.get(scoring, (0,0,0)))

            if len(str(self.thisKillsListe[i])) == 1:
                d.text((x_kills, initial_y), str(
                    self.thisKillsListe[i]), font=font, fill=(0, 0, 0))
            else:
                d.text((x_kills - 20, initial_y),
                       str(self.thisKillsListe[i]), font=font, fill=(0, 0, 0))

            if len(str(self.thisDeathsListe[i])) == 1:
                d.text((x_deaths, initial_y), str(
                    self.thisDeathsListe[i]), font=font, fill=(0, 0, 0))
            else:
                d.text((x_deaths - 20, initial_y),
                       str(self.thisDeathsListe[i]), font=font, fill=(0, 0, 0))

            if len(str(self.thisAssistsListe[i])) == 1:
                d.text((x_assists, initial_y), str(
                    self.thisAssistsListe[i]), font=font, fill=(0, 0, 0))
            else:
                d.text((x_assists - 20, initial_y),
                       str(self.thisAssistsListe[i]), font=font, fill=(0, 0, 0))

            fill = range_value(i, self.thisKDAListe, True)

            # Recentrer le résultat quand chiffre rond
            if len(str(round(self.thisKDAListe[i], 2))) == 1:
                d.text((x_kda + 35, initial_y),
                       str(round(self.thisKDAListe[i], 2)), font=font, fill=fill)
            else:
                d.text((x_kda, initial_y), str(
                    round(self.thisKDAListe[i], 2)), font=font, fill=fill)

            fill = range_value(i, self.thisKPListe, True)

            d.text((x_kp, initial_y), str(
                self.thisKPListe[i]) + "%", font=font, fill=fill)

            fill = range_value(i, np.array(self.thisMinionListe) +
                               np.array(self.thisJungleMonsterKilledListe))

            if len(str(self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i])) != 2:
                d.text((x_cs, initial_y), str(
                    self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]), font=font, fill=fill)
            else:
                d.text((x_cs + 10, initial_y), str(
                    self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]), font=font, fill=fill)

            if self.thisQ != "ARAM":

                fill = range_value(i, self.thisVisionListe)

                d.text((x_vision, initial_y), str(
                    self.thisVisionListe[i]), font=font, fill=fill)

            fill = range_value(i, self.thisDamageListe)

            d.text((x_dmg_percent - 20, initial_y),
                   f'{int(self.thisDamageListe[i]/1000)}k ({int(self.thisDamageRatioListe[i]*100)}%)', font=font, fill=fill)

            fill = range_value(i, np.array(
                self.thisDamageTakenListe) + np.array(self.thisDamageSelfMitigatedListe))

            d.text((x_dmg_taken + 25, initial_y),
                   f'{int(self.thisDamageTakenListe[i]/1000)}k / {int(self.thisDamageSelfMitigatedListe[i]/1000)}k', font=font, fill=fill)

            if i == 4:
                initial_y += 200
            else:
                initial_y += 100

        if self.thisQ != "ARAM":
            y_ecart = 220 + 190
            for ecart in [self.ecart_top_gold_affiche, self.ecart_jgl_gold_affiche, self.ecart_mid_gold_affiche, self.ecart_adc_gold_affiche, self.ecart_supp_gold_affiche]:
                if ecart > 0:
                    d.text((x_ecart, y_ecart), str(round(ecart/1000, 1)
                                                   ) + "k", font=font, fill=(0, 128, 0))
                else:
                    d.text((x_ecart-10, y_ecart), str(round(ecart/1000, 1)
                                                      ) + "k", font=font, fill=(255, 0, 0))

                y_ecart = y_ecart + 100

        n = 0
        for image in self.thisItems:
            if image != 0:
                im.paste(await get_image("items", image, self.session),
                         box=(350 + n, 10 + 190))
                n += 100

        if self.thisQ != "ARAM":

            drk = await get_image('monsters', 'dragon', self.session)
            elder = await get_image('monsters', 'elder', self.session)
            herald = await get_image('monsters', 'herald', self.session)
            nashor = await get_image('monsters', 'nashor', self.session)

            im.paste(drk, (x_objectif, 10 + 190), drk.convert('RGBA'))
            d.text((x_objectif + 100, 25 + 190), str(self.thisDragonTeam),
                   font=font, fill=(0, 0, 0))

            im.paste(elder, (x_objectif + 200, 10 + 190), elder.convert('RGBA'))
            d.text((x_objectif + 200 + 100, 25 + 190),
                   str(self.thisElderPerso), font=font, fill=(0, 0, 0))

            im.paste(herald, (x_objectif + 400, 10 + 190), herald.convert('RGBA'))
            d.text((x_objectif + 400 + 100, 25 + 190),
                   str(self.thisHeraldTeam), font=font, fill=(0, 0, 0))

            im.paste(nashor, (x_objectif + 600, 10 + 190), nashor.convert('RGBA'))
            d.text((x_objectif + 600 + 100, 25 + 190),
                   str(self.thisBaronTeam), font=font, fill=(0, 0, 0))

        img_blue_epee = await get_image('epee', 'blue', self.session)
        img_red_epee = await get_image('epee', 'red', self.session)

        im.paste(img_blue_epee, (x_kill_total, 10 + 190),
                 img_blue_epee.convert('RGBA'))
        d.text((x_kill_total + 100, 23 + 190), str(self.thisTeamKills),
               font=font, fill=(0, 0, 0))

        im.paste(img_red_epee, (x_kill_total + 300, 10 + 190),
                 img_red_epee.convert('RGBA'))
        d.text((x_kill_total + 300 + 100, 23 + 190),
               str(self.thisTeamKillsOp), font=font, fill=(0, 0, 0))
        
        # Stat du jour
        if self.thisQ == 'ARAM':
            suivi_24h = lire_bdd('ranked_aram_24h', 'dict')
        else:
            suivi_24h = lire_bdd('suivi_24h', 'dict')

        if self.thisQ != 'ARAM':
            try:
                difwin = int(self.thisVictory) - \
                    int(suivi_24h[self.summonerName.lower()]["wins"])
                diflos = int(self.thisLoose) - \
                    int(suivi_24h[self.summonerName.lower()]["losses"])

                if (difwin + diflos) > 0:  # si pas de ranked aujourd'hui, inutile
                    d.text((x_metric + 650, y_name+50),
                           f'Victoires 24h : {difwin}', font=font_little, fill=(0, 0, 0))
                    d.text((x_metric + 1120, y_name+50),
                           f'Defaites 24h : {diflos}', font=font_little, fill=(0, 0, 0))

            except KeyError:
                pass

        elif self.thisQ == 'ARAM' and activation:
            try:
                difwin = wins - \
                    int(suivi_24h[self.summonerName.lower()]["wins"])
                diflos = losses - \
                    int(suivi_24h[self.summonerName.lower()]["losses"])

                if (difwin + diflos) > 0:  # si pas de ranked aujourd'hui, inutile
                    d.text((x_metric + 650, y_name+50),
                           f'Victoires 24h : {difwin}', font=font_little, fill=(0, 0, 0))
                    d.text((x_metric + 1120, y_name+50),
                           f'Defaites 24h : {diflos}', font=font_little, fill=(0, 0, 0))

            except KeyError:
                pass

        im.save(f'{name_img}.png')

        await self.session.close()
        
        return embed
