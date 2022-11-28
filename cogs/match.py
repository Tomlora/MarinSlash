import pandas as pd

from riotwatcher import LolWatcher
import pandas as pd
import warnings
from fonctions.gestion_bdd import lire_bdd, get_data_bdd, requete_perso_bdd
import json
import numpy as np
import sys
import requests
from PIL import Image, ImageDraw, ImageFont
import plotly.graph_objects as go
from plotly.graph_objs import Layout
import plotly.express as px
from io import BytesIO
import aiohttp
import asyncio

warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'

import os

dict_rankid =  {"Non-classe 0" : 0,
               "BRONZE IV" : 1,
               "BRONZE III" : 2,
               "BRONZE II" : 3,
               "BRONZE I" : 4,
               "SILVER IV" : 5,
               "SILVER III" : 6,
               "SILVER II": 7,
               "SILVER I" : 8,
               "GOLD IV" : 9,
               "GOLD III" : 10,
               "GOLD II" : 11,
               "GOLD I" : 12,
               "PLATINUM IV" : 13,
               "PLATINUM III" : 14,
               "PLATINUM II" : 15,
               "PLATINUM I" : 16,
               "DIAMOND IV" : 17,
               "DIAMOND III" : 18,
               "DIAMOND II" : 19,
               "DIAMOND I" : 20,
               'MASTER I' : 21,
               'GRANDMASTER I': 22,
               'CHALLENGER I' : 23}

elo_lp = {'IRON' : 0,
        'BRONZE' : 1,
        'SILVER' : 2,
        'GOLD' : 3,
        'PLATINUM' : 4,
        'DIAMOND' : 5,
        'MASTER' : 6,
        'GRANDMASTER' : 7,
        'CHALLENGER' : 8,
        'FIRST_GAME' : 0}

dict_points = {41 : [11, -19],
                               42 : [12, -18],
                               43 : [13, -17],
                               44 : [14, -16],
                               45 : [15, -15],
                               46 : [16, -15],
                               47 : [17, -15],
                               48 : [18, -15],
                               49 : [19, -15],
                               50 : [20, -15],
                               51 : [21, -15],
                               52 : [22, -15],
                               53 : [23, -15],
                               54 : [24, -15],
                               55 : [25, -15],
                               56 : [26, -14],
                               57 : [27, -13],
                               58 : [28, -12],
                               59 : [29, -11]} 

def get_key(my_dict, val):
    for key, value in my_dict.items():
        if val == value:
            return key
        
    return "No key"


async def get_image(type, name, session : aiohttp.ClientSession, resize_x=80, resize_y=80):
    if type == "champion":
        url = (f"https://raw.githubusercontent.com/Tomlora/MarinSlash/main/img/champions/{name}.png")
        async with session.get(url) as response:
            # response = request.get(url)
            if response.status != 200:
                img = Image.new("RGB", (resize_x, resize_y))
            else:
                img_raw = await response.read()
                img = Image.open(BytesIO(img_raw))
                img = img.resize((resize_x, resize_y))
        return img

    elif type == "tier":
        img = Image.open(f"./img/{name}.png")
        img = img.resize((resize_x, resize_y))
        return img
    
    elif type == "avatar":
        url = (f"https://ddragon.leagueoflegends.com/cdn/12.6.1/img/profileicon/{name}.png")
        async with session.get(url) as response:
            # response = request.get(url)
            if response.status != 200:
                img = Image.new("RGB", (resize_x, resize_y))
            else:
                img_raw = await response.read()
                img = Image.open(BytesIO(img_raw))
                img = img.resize((resize_x, resize_y))
        return img
    
    elif type in ["items", "monsters", "epee"]:
        img = Image.open(f'./img/{type}/{name}.png')
        img = img.resize((resize_x,resize_y))
        return img
        
    elif type == "gold":
        img = Image.open(f'./img/money.png')
        img = img.resize((resize_x, resize_y))
        
        return img
    
    elif type == "autre":
        img = Image.open(f'{name}.png')
        img = img.resize((resize_x, resize_y))
        
        return img
    
    elif type == "kda":
        img = Image.open(f'./img/rectangle/{name}.png')
        img = img.resize((resize_x, resize_y))
        
        return img


api_key_lol = os.environ.get('API_LOL')  # https://www.youtube.com/watch?v=IolxqkL7cD8

lol_watcher = LolWatcher(api_key_lol, timeout=7)
my_region = 'euw1'
region = "EUROPE"

async def get_version(session : aiohttp.ClientSession):
    async with session.get(f"https://ddragon.leagueoflegends.com/realms/euw.json") as session_version:
        version = await session_version.json()
    return version

async def get_champ_list(session : aiohttp.ClientSession, version):
    champions_versions = version['n']['champion']
        
    async with session.get(f"https://ddragon.leagueoflegends.com/cdn/{champions_versions}/data/fr_FR/champion.json") as session_champlist:
        current_champ_list = await session_champlist.json() 
    return current_champ_list

async def get_summoner_by_name(session : aiohttp.ClientSession, key):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{key}', params={'api_key' : api_key_lol}) as session_summoner:
        me = await session_summoner.json() # informations sur le joueur
    return me
    
async def get_league_by_summoner(session : aiohttp.ClientSession, me):
    async with session.get(f"https://{my_region}.api.riotgames.com/lol/league/v4/entries/by-summoner/{me['id']}",
                                    params={'api_key' : api_key_lol}) as session_league:
        stats = await session_league.json()
    return stats    

async def get_list_matchs(session : aiohttp.ClientSession, me, params): 
    async with session.get(f'https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{me["puuid"]}/ids?', params=params) as session_match:
        my_matches = await session_match.json()
    return my_matches

async def get_match_detail(session : aiohttp.ClientSession, match_id, params):
    async with session.get(f'https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}', params=params) as session_match_detail:
        match_detail_stats = await session_match_detail.json() # detail du match sélectionné
    return match_detail_stats

async def get_match_timeline(session : aiohttp.ClientSession, match_id):
    async with session.get(f'https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline', params={'api_key' : api_key_lol}) as session_timeline:
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
            infos1 = match_detail['info']['participants'][5][info]
            infos2 = match_detail['info']['participants'][6][info]
            infos3 = match_detail['info']['participants'][7][info]
            infos4 = match_detail['info']['participants'][8][info]
            infos5 = match_detail['info']['participants'][9][info]
            infos6 = match_detail['info']['participants'][0][info]
            infos7 = match_detail['info']['participants'][1][info]
            infos8 = match_detail['info']['participants'][2][info]
            infos9 = match_detail['info']['participants'][3][info]
            infos10 = match_detail['info']['participants'][4][info]
        else:
            infos1 = match_detail['info']['participants'][0][info]
            infos2 = match_detail['info']['participants'][1][info]
            infos3 = match_detail['info']['participants'][2][info]
            infos4 = match_detail['info']['participants'][3][info]
            infos5 = match_detail['info']['participants'][4][info]
            infos6 = match_detail['info']['participants'][5][info]
            infos7 = match_detail['info']['participants'][6][info]
            infos8 = match_detail['info']['participants'][7][info]
            infos9 = match_detail['info']['participants'][8][info]
            infos10 = match_detail['info']['participants'][9][info]
    except:
        if thisId > 4:
            infos1 = match_detail['info']['participants'][5]['challenges'][info]
            infos2 = match_detail['info']['participants'][6]['challenges'][info]
            infos3 = match_detail['info']['participants'][7]['challenges'][info]
            infos4 = match_detail['info']['participants'][8]['challenges'][info]
            infos5 = match_detail['info']['participants'][9]['challenges'][info]
            infos6 = match_detail['info']['participants'][0]['challenges'][info]
            infos7 = match_detail['info']['participants'][1]['challenges'][info]
            infos8 = match_detail['info']['participants'][2]['challenges'][info]
            infos9 = match_detail['info']['participants'][3]['challenges'][info]
            infos10 = match_detail['info']['participants'][4]['challenges'][info]
        else:
            infos1 = match_detail['info']['participants'][0]['challenges'][info]
            infos2 = match_detail['info']['participants'][1]['challenges'][info]
            infos3 = match_detail['info']['participants'][2]['challenges'][info]
            infos4 = match_detail['info']['participants'][3]['challenges'][info]
            infos5 = match_detail['info']['participants'][4]['challenges'][info]
            infos6 = match_detail['info']['participants'][5]['challenges'][info]
            infos7 = match_detail['info']['participants'][6]['challenges'][info]
            infos8 = match_detail['info']['participants'][7]['challenges'][info]
            infos9 = match_detail['info']['participants'][8]['challenges'][info]
            infos10 = match_detail['info']['participants'][9]['challenges'][info]

    liste = [infos1, infos2, infos3, infos4, infos5, infos6, infos7, infos8, infos9, infos10]

    return liste


async def match_by_puuid(summonerName, idgames: int, session, index=0, queue=0, count=20):
    params_me= {'api_key' : api_key_lol}
    if queue == 0:
        params_my_match= {'start' : index, 'count' : count, 'api_key' : api_key_lol}
    else:
        params_my_match= {'queue' : queue, 'start' : index, 'count' : count, 'api_key' : api_key_lol}
        
    me = await get_summoner_by_name(session, summonerName)    
    my_matches = await get_list_matchs(session, me, params_my_match)
    last_match = my_matches[idgames] # match n° idgames    
    match_detail_stats = await get_match_detail(session, last_match, params_me) # detail du match sélectionné

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

    def __init__(self, summonerName, idgames:int, queue:int=0, index:int=0, count:int=20, sauvegarder:bool=False):
        self.summonerName = summonerName
        self.idgames = idgames
        self.queue = queue
        self.index = index
        self.count = count    
        self.sauvegarder = sauvegarder
        self.params_me= {'api_key' : api_key_lol}

        
    
    async def get_data_riot(self):

        self.session = aiohttp.ClientSession()
        if self.queue == 0:
            self.params_my_match= {'start' : self.index, 'count' : self.count, 'api_key' : api_key_lol}
        else:
            self.params_my_match= {'queue' : self.queue, 'start' : self.index, 'count' : self.count, 'api_key' : api_key_lol}
        
        self.me = await get_summoner_by_name(self.session, self.summonerName)
    
        self.my_matches = await get_list_matchs(self.session, self.me, self.params_my_match)
        self.last_match = self.my_matches[self.idgames] # match n° idgames    
        self.match_detail_stats = await get_match_detail(self.session, self.last_match, self.params_me) # detail du match sélectionné
        
        self.avatar = self.me['profileIconId']
        self.level_summoner = self.me['summonerLevel']
        
        self.version = await get_version(self.session)
        self.current_champ_list = await get_champ_list(self.session, self.version)
        
        
    async def prepare_data(self):
        
        # Detail de chaque champion...
        
        self.champ_dict = {}
        for key in self.current_champ_list['data']:
            row = self.current_champ_list['data'][key]
            self.champ_dict[row['key']] = row['id']  

        self.match_detail = pd.DataFrame(self.match_detail_stats)
        
        self.dic = {
            (self.match_detail['info']['participants'][0]['summonerName']).lower().replace(" ", ""): 0,
            (self.match_detail['info']['participants'][1]['summonerName']).lower().replace(" ", ""): 1,
            (self.match_detail['info']['participants'][2]['summonerName']).lower().replace(" ", ""): 2,
            (self.match_detail['info']['participants'][3]['summonerName']).lower().replace(" ", ""): 3,
            (self.match_detail['info']['participants'][4]['summonerName']).lower().replace(" ", ""): 4,
            (self.match_detail['info']['participants'][5]['summonerName']).lower().replace(" ", ""): 5,
            (self.match_detail['info']['participants'][6]['summonerName']).lower().replace(" ", ""): 6,
            (self.match_detail['info']['participants'][7]['summonerName']).lower().replace(" ", ""): 7,
            (self.match_detail['info']['participants'][8]['summonerName']).lower().replace(" ", ""): 8,
            (self.match_detail['info']['participants'][9]['summonerName']).lower().replace(" ", ""): 9
        }
        
        # stats
        self.thisId = self.dic[
            self.summonerName.lower().replace(" ", "")]  # cherche le pseudo dans le dico et renvoie le nombre entre 0 et 9

        self.thisQId = self.match_detail['info']['queueId']
        self.match_detail_participants = self.match_detail['info']['participants'][self.thisId]
        self.match_detail_challenges = self.match_detail_participants['challenges']
        self.thisPosition = self.match_detail_participants['teamPosition']
        # self.season = int(self.match_detail['info']['gameVersion'][0:2])
        self.season = 12 # TODO a modifier quand s13
        
        if (str(self.thisPosition) == "MIDDLE"):
            self.thisPosition = "MID"
        elif (str(self.thisPosition) == "BOTTOM"):
            self.thisPosition = "ADC"
        elif (str(self.thisPosition) == "UTILITY"):
            self.thisPosition = "SUPPORT"
        
        self.timestamp = str(self.match_detail['info']['gameCreation'])[:-3] # traduire avec datetime.date.fromtimestamp()
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
        self.thisTimeLiving = round((int(self.match_detail_participants['longestTimeSpentLiving']) / 60), 2)
        self.thisWin = ' '
        self.thisTime = round((int(self.match_detail['info']['gameDuration']) / 60), 2)
        self.thisDamage = self.match_detail_participants['totalDamageDealtToChampions']
        self.thisDamageNoFormat = self.match_detail_participants['totalDamageDealtToChampions']
        self.thisDamageAP = self.match_detail_participants['magicDamageDealtToChampions']
        self.thisDamageAPNoFormat = self.match_detail_participants['magicDamageDealtToChampions']
        self.thisDamageAD = self.match_detail_participants['physicalDamageDealtToChampions']
        self.thisDamageADNoFormat = self.match_detail_participants['physicalDamageDealtToChampions']
        self.thisDamageTrue = self.match_detail_participants['trueDamageDealtToChampions']
        self.thisDamageTrueNoFormat = self.match_detail_participants['trueDamageDealtToChampions']
        
        self.thisTimeSpendDead = round(float(self.match_detail_participants['totalTimeSpentDead'])/60,2) 
        
        self.thisDamageTaken = int(self.match_detail_participants['totalDamageTaken'])
        self.thisDamageTakenNoFormat = int(self.match_detail_participants['totalDamageTaken'])
        self.thisDamageTakenAD = int(self.match_detail_participants['physicalDamageTaken'])
        self.thisDamageTakenADNoFormat = int(self.match_detail_participants['physicalDamageTaken'])
        self.thisDamageTakenAP = int(self.match_detail_participants['magicDamageTaken'])
        self.thisDamageTakenAPNoFormat = int(self.match_detail_participants['magicDamageTaken'])
        self.thisDamageTakenTrue = int(self.match_detail_participants['trueDamageTaken'])
        self.thisDamageTakenTrueNoFormat = int(self.match_detail_participants['trueDamageTaken'])
        
        self.thisVision = self.match_detail_participants['visionScore']
        self.thisJungleMonsterKilled = self.match_detail_participants['neutralMinionsKilled']
        self.thisMinion = self.match_detail_participants['totalMinionsKilled'] + self.thisJungleMonsterKilled
        self.thisPink = self.match_detail_participants['visionWardsBoughtInGame']
        self.thisWards = self.match_detail_participants['wardsPlaced']
        self.thisWardsKilled = self.match_detail_participants['wardsKilled']
        self.thisGold = int(self.match_detail_participants['goldEarned'])
        self.thisGoldNoFormat = int(self.match_detail_participants['goldEarned'])
        
        self.spell1 = self.match_detail_participants['summoner1Id']
        self.spell2 = self.match_detail_participants['summoner2Id']
        
        try:
            self.thisPing = self.match_detail_participants['basicPings']
        except:
            self.thisPing = 0
                
        self.item = self.match_detail_participants
        self.thisItems = [self.item['item0'], self.item['item1'], self.item['item2'], self.item['item3'], self.item['item4'], self.item['item5']]
        
        
                # item6 = ward. Pas utile 
        
        
        # on transpose les items
        
        with open('./obj/item.json', encoding='utf-8') as mon_fichier:
            self.data = json.load(mon_fichier)
        
        self.data_item = list()
        
        for item in self.thisItems:
            if item != 0: # si = 0, il n'y a pas d'items
                self.data_item.append(self.data['data'][str(item)]['name'])
        
        
        self.data_item = (' | '.join(self.data_item))
        
        self.thisMinionPerMin = round((self.thisMinion / self.thisTime), 2)
        self.thisVisionPerMin = round((self.thisVision / self.thisTime), 2)
        self.thisGoldPerMinute = round((self.thisGold / self.thisTime), 2)
        self.thisDamagePerMinute = round(
            int(self.match_detail_participants['totalDamageDealtToChampions']) / self.thisTime, 0)
        
        async with self.session.get(f"https://{my_region}.api.riotgames.com/lol/league/v4/entries/by-summoner/{self.me['id']}",
                                    params=self.params_me) as session4:
            self.thisStats = await session4.json() # detail du match sélectionné
        # self.thisStats = lol_watcher.league.by_summoner(my_region, self.me['id'])
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
        self.thisJUNGLEafter10min = self.match_detail_challenges['jungleCsBefore10Minutes']
        self.thisCSafter10min = self.match_detail_challenges['laneMinionsFirst10Minutes'] + self.thisJUNGLEafter10min
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
        else:
            self.team = 1
            
            
        self.team_stats = self.match_detail['info']['teams'][self.team]['objectives']
        
        self.thisBaronTeam = self.team_stats['baron']['kills']
        self.thisDragonTeam = self.team_stats['dragon']['kills']
        self.thisHeraldTeam = self.team_stats['riftHerald']['kills']
        self.thisTurretsKillsTeam = self.team_stats['tower']['kills']
        
        
                # A voir...
        
        try: # pas dispo en aram ?
            self.thisCSAdvantageOnLane = round(self.match_detail_challenges['maxCsAdvantageOnLaneOpponent'],0)
        except:
            self.thisCSAdvantageOnLane = 0
        
        try:
            self.thisLevelAdvantage = self.match_detail_challenges['maxLevelLeadLaneOpponent']
        except:
            self.thisLevelAdvantage = 0
        
        try: # si pas d'afk, la variable n'est pas présente
            self.AFKTeam = self.match_detail_challenges['hadAfkTeammate']
            self.AFKTeamBool = True
        except:
            self.AFKTeam = 0
            self.AFKTeamBool = False
            
        
        self.thisSkillshot_dodged = self.match_detail_challenges['skillshotsDodged']
        self.thisSkillshot_hit = self.match_detail_challenges['skillshotsHit']
        
        try:
            self.thisTurretPlatesTaken =  self.match_detail_challenges['turretPlatesTaken'] 
        except:
            self.thisTurretPlatesTaken = 0   
        
        try: # si tu n'en poses pas, tu n'as pas la stat
            self.ControlWardInRiver = round(self.match_detail_challenges['controlWardTimeCoverageInRiverOrEnemyHalf'],2)
        except:
            self.ControlWardInRiver = 0 
            
        try:
            self.thisVisionAdvantage = round(self.match_detail_challenges['visionScoreAdvantageLaneOpponent']*100 , 2)
        except:
            self.thisVisionAdvantage = 0
        
        try: # si pas d'info, la team n'a pas fait de drake
            self.earliestDrake = round(self.match_detail_challenges['earliestDragonTakedown'] / 60,2) 
        except:
            self.earliestDrake = 0
            
        try:
            self.earliestBaron = round(self.match_detail_challenges['earliestBaron'] / 60,2)
        except:
            self.earliestBaron = 0
            
        try:
            self.participation_tower = round((self.thisTurretsKillsPerso / self.thisTurretsKillsTeam)*100 , 2)
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

         
        self.thisDamageListe = dict_data(self.thisId, self.match_detail, 'totalDamageDealtToChampions')

        # pseudo

        self.thisPseudoListe = dict_data(self.thisId, self.match_detail, 'summonerName')

        # champ id

        self.thisChampListe = dict_data(self.thisId, self.match_detail, 'championId')

        # champ

        self.thisChampName1 = self.champ_dict[str(self.thisChampListe[0])]
        self.thisChampName2 = self.champ_dict[str(self.thisChampListe[1])]
        self.thisChampName3 = self.champ_dict[str(self.thisChampListe[2])]
        self.thisChampName4 = self.champ_dict[str(self.thisChampListe[3])]
        self.thisChampName5 = self.champ_dict[str(self.thisChampListe[4])]
        self.thisChampName6 = self.champ_dict[str(self.thisChampListe[5])]
        self.thisChampName7 = self.champ_dict[str(self.thisChampListe[6])]
        self.thisChampName8 = self.champ_dict[str(self.thisChampListe[7])]
        self.thisChampName9 = self.champ_dict[str(self.thisChampListe[8])]
        self.thisChampName10 = self.champ_dict[str(self.thisChampListe[9])]
        
        self.thisChampNameListe = [self.thisChampName1, self.thisChampName2, self.thisChampName3, self.thisChampName4, self.thisChampName5, self.thisChampName6, self.thisChampName7, self.thisChampName8, self.thisChampName9, self.thisChampName10]
        
        
                # total kills

        self.thisKillsListe = dict_data(self.thisId, self.match_detail, 'kills')
        
        self.thisTeamKills = self.thisKillsListe[0] + self.thisKillsListe[1] + self.thisKillsListe[2] + self.thisKillsListe[3] + self.thisKillsListe[4]
        self.thisTeamKillsOp = self.thisKillsListe[5] + self.thisKillsListe[6] + self.thisKillsListe[7] + self.thisKillsListe[8] + self.thisKillsListe[9]

        # deaths

        self.thisDeathsListe = dict_data(self.thisId, self.match_detail, 'deaths')
        
        # Alliés feeder
        self.thisAllieFeeder = np.array(self.thisDeathsListe)
        self.thisAllieFeeder = float(self.thisAllieFeeder[0:5].max())

        # assists

        self.thisAssistsListe = dict_data(self.thisId, self.match_detail, 'assists')

        # gold

        self.thisGoldListe = dict_data(self.thisId, self.match_detail, 'goldEarned')


        self.thisChampTeam1 = [self.thisChampName1, self.thisChampName2, self.thisChampName3, self.thisChampName4, self.thisChampName5]
        self.thisChampTeam2 = [self.thisChampName6, self.thisChampName7, self.thisChampName8, self.thisChampName9, self.thisChampName10]
        self.thisGold_team1 = self.thisGoldListe[0] + self.thisGoldListe[1] + self.thisGoldListe[2] + self.thisGoldListe[3] + self.thisGoldListe[4]
        self.thisGold_team2 = self.thisGoldListe[5] + self.thisGoldListe[6] + self.thisGoldListe[7] + self.thisGoldListe[8] + self.thisGoldListe[9]
        
        self.thisVisionListe = dict_data(self.thisId, self.match_detail, 'visionScore')
        
        self.thisJungleMonsterKilledListe = dict_data(self.thisId, self.match_detail, 'neutralMinionsKilled')
        self.thisMinionListe = dict_data(self.thisId, self.match_detail, 'totalMinionsKilled')
        
        self.thisKDAListe = dict_data(self.thisId, self.match_detail, "kda")
        
        self.thisLevelListe = dict_data(self.thisId, self.match_detail, "champLevel")
        
        
        
        if self.team == 0 :
            self.ecart_top_gold = self.thisGoldListe[0] - self.thisGoldListe[5]
            self.ecart_jgl_gold = self.thisGoldListe[1] - self.thisGoldListe[6]
            self.ecart_mid_gold = self.thisGoldListe[2] - self.thisGoldListe[7]
            self.ecart_adc_gold = self.thisGoldListe[3] - self.thisGoldListe[8]
            self.ecart_supp_gold = self.thisGoldListe[4] - self.thisGoldListe[9]
            
            self.ecart_top_gold_affiche = self.thisGoldListe[0] - self.thisGoldListe[5]
            self.ecart_jgl_gold_affiche = self.thisGoldListe[1] - self.thisGoldListe[6]
            self.ecart_mid_gold_affiche = self.thisGoldListe[2] - self.thisGoldListe[7]
            self.ecart_adc_gold_affiche = self.thisGoldListe[3] - self.thisGoldListe[8]
            self.ecart_supp_gold_affiche = self.thisGoldListe[4] - self.thisGoldListe[9]
            
            self.ecart_top_vision = self.thisVisionListe[0] - self.thisVisionListe[5]
            self.ecart_jgl_vision = self.thisVisionListe[1] - self.thisVisionListe[6]
            self.ecart_mid_vision = self.thisVisionListe[2] - self.thisVisionListe[7]
            self.ecart_adc_vision = self.thisVisionListe[3] - self.thisVisionListe[8]
            self.ecart_supp_vision = self.thisVisionListe[4] - self.thisVisionListe[9]
            
            self.ecart_top_cs = (self.thisMinionListe[0] + self.thisJungleMonsterKilledListe[0]) - (self.thisMinionListe[5] + self.thisJungleMonsterKilledListe[5])
            self.ecart_jgl_cs = (self.thisMinionListe[1] + self.thisJungleMonsterKilledListe[1]) - (self.thisMinionListe[6] + self.thisJungleMonsterKilledListe[6])
            self.ecart_mid_cs = (self.thisMinionListe[2] + self.thisJungleMonsterKilledListe[2]) - (self.thisMinionListe[7] + self.thisJungleMonsterKilledListe[7])
            self.ecart_adc_cs = (self.thisMinionListe[3] + self.thisJungleMonsterKilledListe[3]) - (self.thisMinionListe[8] + self.thisJungleMonsterKilledListe[8])
            self.ecart_supp_cs = (self.thisMinionListe[4] + self.thisJungleMonsterKilledListe[4]) - (self.thisMinionListe[9] + self.thisJungleMonsterKilledListe[9])
            
            self.thisKPListe = [int(round((self.thisKillsListe[0] + self.thisAssistsListe[0]) / (self.thisTeamKills), 2) * 100),
                                int(round((self.thisKillsListe[1] + self.thisAssistsListe[1]) / (self.thisTeamKills), 2) * 100),
                                int(round((self.thisKillsListe[2] + self.thisAssistsListe[2]) / (self.thisTeamKills), 2) * 100),
                                int(round((self.thisKillsListe[3] + self.thisAssistsListe[3]) / (self.thisTeamKills), 2) * 100),
                                int(round((self.thisKillsListe[4] + self.thisAssistsListe[4]) / (self.thisTeamKills), 2) * 100),
                                int(round((self.thisKillsListe[5] + self.thisAssistsListe[5]) / (self.thisTeamKillsOp), 2) * 100),
                                int(round((self.thisKillsListe[6] + self.thisAssistsListe[6]) / (self.thisTeamKillsOp), 2) * 100),
                                int(round((self.thisKillsListe[7] + self.thisAssistsListe[7]) / (self.thisTeamKillsOp), 2) * 100),
                                int(round((self.thisKillsListe[8] + self.thisAssistsListe[8]) / (self.thisTeamKillsOp), 2) * 100),
                                int(round((self.thisKillsListe[9] + self.thisAssistsListe[9]) / (self.thisTeamKillsOp), 2) * 100),
            ]
            
        elif self.team == 1:
            
            self.ecart_top_gold = self.thisGoldListe[0] - self.thisGoldListe[5]
            self.ecart_jgl_gold = self.thisGoldListe[1] - self.thisGoldListe[6]
            self.ecart_mid_gold = self.thisGoldListe[2] - self.thisGoldListe[7]
            self.ecart_adc_gold = self.thisGoldListe[3] - self.thisGoldListe[8]
            self.ecart_supp_gold = self.thisGoldListe[4] - self.thisGoldListe[9]
            
            self.ecart_top_gold_affiche = self.thisGoldListe[0] - self.thisGoldListe[5]
            self.ecart_jgl_gold_affiche = self.thisGoldListe[1] - self.thisGoldListe[6]
            self.ecart_mid_gold_affiche = self.thisGoldListe[2] - self.thisGoldListe[7]
            self.ecart_adc_gold_affiche = self.thisGoldListe[3] - self.thisGoldListe[8]
            self.ecart_supp_gold_affiche = self.thisGoldListe[4] - self.thisGoldListe[9]
            
            self.ecart_top_vision = self.thisVisionListe[0] - self.thisVisionListe[5]
            self.ecart_jgl_vision = self.thisVisionListe[1] - self.thisVisionListe[6]
            self.ecart_mid_vision = self.thisVisionListe[2] - self.thisVisionListe[7]
            self.ecart_adc_vision = self.thisVisionListe[3] - self.thisVisionListe[8]
            self.ecart_supp_vision = self.thisVisionListe[4] - self.thisVisionListe[9]
            
            self.ecart_top_cs = (self.thisMinionListe[0] + self.thisJungleMonsterKilledListe[0]) - (self.thisMinionListe[5] + self.thisJungleMonsterKilledListe[5])
            self.ecart_jgl_cs = (self.thisMinionListe[1] + self.thisJungleMonsterKilledListe[1]) - (self.thisMinionListe[6] + self.thisJungleMonsterKilledListe[6])
            self.ecart_mid_cs = (self.thisMinionListe[2] + self.thisJungleMonsterKilledListe[2]) - (self.thisMinionListe[7] + self.thisJungleMonsterKilledListe[7])
            self.ecart_adc_cs = (self.thisMinionListe[3] + self.thisJungleMonsterKilledListe[3]) - (self.thisMinionListe[8] + self.thisJungleMonsterKilledListe[8])
            self.ecart_supp_cs = (self.thisMinionListe[4] + self.thisJungleMonsterKilledListe[4]) - (self.thisMinionListe[9] + self.thisJungleMonsterKilledListe[9])
            
            self.thisKPListe = [int(round((self.thisKillsListe[0] + self.thisAssistsListe[0]) / (self.thisTeamKills), 2) * 100),
                                int(round((self.thisKillsListe[1] + self.thisAssistsListe[1]) / (self.thisTeamKills), 2) * 100),
                                int(round((self.thisKillsListe[2] + self.thisAssistsListe[2]) / (self.thisTeamKills), 2) * 100),
                                int(round((self.thisKillsListe[3] + self.thisAssistsListe[3]) / (self.thisTeamKills), 2) * 100),
                                int(round((self.thisKillsListe[4] + self.thisAssistsListe[4]) / (self.thisTeamKills), 2) * 100),
                                int(round((self.thisKillsListe[5] + self.thisAssistsListe[5]) / (self.thisTeamKillsOp), 2) * 100),
                                int(round((self.thisKillsListe[6] + self.thisAssistsListe[6]) / (self.thisTeamKillsOp), 2) * 100),
                                int(round((self.thisKillsListe[7] + self.thisAssistsListe[7]) / (self.thisTeamKillsOp), 2) * 100),
                                int(round((self.thisKillsListe[8] + self.thisAssistsListe[8]) / (self.thisTeamKillsOp), 2) * 100),
                                int(round((self.thisKillsListe[9] + self.thisAssistsListe[9]) / (self.thisTeamKillsOp), 2) * 100),
            ]
            
        self.adversaire_direct = {"TOP" : self.ecart_top_gold, "JUNGLE" : self.ecart_jgl_gold, "MID" : self.ecart_mid_gold, "ADC" : self.ecart_adc_gold, "SUPPORT" : self.ecart_supp_gold}
         
        try:    
            self.ecart_gold = self.adversaire_direct[self.thisPosition]
        except KeyError:
            self.ecart_gold = "Indisponible"
        
        # mise en forme
        self.thisGold_team1 = "{:,}".format(self.thisGold_team1).replace(',', ' ').replace('.', ',')
        self.thisGold_team2 = "{:,}".format(self.thisGold_team2).replace(',', ' ').replace('.', ',')
        
        self.ecart_top_gold = "{:,}".format(self.ecart_top_gold).replace(',', ' ').replace('.', ',')
        self.ecart_jgl_gold = "{:,}".format(self.ecart_jgl_gold).replace(',', ' ').replace('.', ',')
        self.ecart_mid_gold = "{:,}".format(self.ecart_mid_gold).replace(',', ' ').replace('.', ',')
        self.ecart_adc_gold = "{:,}".format(self.ecart_adc_gold).replace(',', ' ').replace('.', ',')
        self.ecart_supp_gold = "{:,}".format(self.ecart_supp_gold).replace(',', ' ').replace('.', ',')
        
        self.thisGold = "{:,}".format(self.thisGold).replace(',', ' ').replace('.', ',')
        if self.ecart_gold != "Indisponible" : # si nombre
            self.ecart_gold = "{:,}".format(self.ecart_gold).replace(',', ' ').replace('.', ',')
        self.thisDamage = "{:,}".format(self.thisDamage).replace(',', ' ').replace('.', ',')
        self.thisDamageAD = "{:,}".format(self.thisDamageAD).replace(',', ' ').replace('.', ',')
        self.thisDamageAP = "{:,}".format(self.thisDamageAP).replace(',', ' ').replace('.', ',')
        self.thisDamageTrue = "{:,}".format(self.thisDamageTrue).replace(',', ' ').replace('.', ',')
        self.thisDamageTaken = "{:,}".format(self.thisDamageTaken).replace(',', ' ').replace('.', ',')
        self.thisDamageSelfMitigatedFormat = "{:,}".format(self.thisDamageSelfMitigated).replace(',', ' ').replace('.', ',')
        self.thisTimeLiving = str(self.thisTimeLiving).replace(".", "m")
        self.thisTotalOnTeammatesFormat = "{:,}".format(self.thisTotalOnTeammates).replace(',', ' ').replace('.', ',')
        
        self.thisDamageTakenAD = "{:,}".format(self.thisDamageTakenAD).replace(',', ' ').replace('.', ',')
        self.thisDamageTakenAP = "{:,}".format(self.thisDamageTakenAP).replace(',', ' ').replace('.', ',')
        self.thisDamageTakenTrue = "{:,}".format(self.thisDamageTakenTrue).replace(',', ' ').replace('.', ',')
        

        self.thisDamageObjectives = "{:,}".format(self.thisDamageObjectives).replace(',', ' ').replace('.', ',')        
        

        

        try:
            self.thisKP = int(round((self.thisKills + self.thisAssists) / (self.thisTeamKills), 2) * 100)
        except:
            self.thisKP = 0

        # thisDamageRatio = round((float(thisDamage) / float(thisTeamDamage)) * 100, 2)
        self.thisDamageRatio = round(
            (self.match_detail_challenges['teamDamagePercentage']) * 100, 2)
        self.thisDamageTakenRatio = round(
            (self.match_detail_challenges['damageTakenOnTeamPercentage']) * 100, 2)
        
        
        self.thisDamageRatioListe = dict_data(self.thisId, self.match_detail, "teamDamagePercentage")
        self.thisDamageTakenRatioListe = dict_data(self.thisId, self.match_detail, "damageTakenOnTeamPercentage")

        # on doit identifier les stats soloq (et non flex...)
        try:
            if str(self.thisStats[0]['queueType']) == "RANKED_SOLO_5x5":
                self.i = 0
            else:
                self.i = 1
                

            self.thisWinrate = int(self.thisStats[self.i]['wins']) / (int(self.thisStats[self.i]['wins']) + int(self.thisStats[self.i]['losses']))
            self.thisWinrateStat = str(int(self.thisWinrate * 100))
            self.thisRank = str(self.thisStats[self.i]['rank'])
            self.thisTier = str(self.thisStats[self.i]['tier'])
            self.thisLP = str(self.thisStats[self.i]['leaguePoints'])
            self.thisVictory = str(self.thisStats[self.i]['wins'])
            self.thisLoose = str(self.thisStats[self.i]['losses'])
            self.thisWinStreak = str(self.thisStats[self.i]['hotStreak'])
        except IndexError: # on va avoir une index error si le joueur est en placement, car Riot ne fournit pas dans son api les données de placement
            self.thisWinrate = '0'
            self.thisWinrateStat = '0'
            self.thisRank = 'En placement'
            self.thisTier = " "
            self.thisLP = '0'
            self.thisVictory = '0'
            self.thisLoose = '0'
            self.thisWinStreak = '0'  
            
        # TODO save la game 
        if self.sauvegarder:
            requete_perso_bdd(f'''INSERT INTO public.matchs(
        match_id, joueur, role, champion, kills, assists, deaths, double, triple, quadra, penta,
        victoire, team_kills, team_deaths, "time", dmg, dmg_ad, dmg_ap, dmg_true, vision_score, cs, cs_jungle, vision_pink, vision_wards, vision_wards_killed,
        gold, spell1, spell2, cs_min, vision_min, gold_min, dmg_min, solokills, dmg_reduit, heal_total, heal_allies, serie_kills, cs_dix_min, jgl_dix_min,
        baron, drake, team, herald, cs_max_avantage, level_max_avantage, afk, vision_avantage, early_drake, temps_dead,
        item1, item2, item3, item4, item5, item6, kp, kda, mode, season, date, damageratio, tankratio, rank, tier)
        VALUES (:match_id, :joueur, :role, :champion, :kills, :assists, :deaths, :double, :triple, :quadra, :penta,
        :result, :team_kills, :team_deaths, :time, :dmg, :dmg_ad, :dmg_ap, :dmg_true, :vision_score, :cs, :cs_jungle, :vision_pink, :vision_wards, :vision_wards_killed,
        :gold, :spell1, :spell2, :cs_min, :vision_min, :gold_min, :dmg_min, :solokills, :dmg_reduit, :heal_total, :heal_allies, :serie_kills, :cs_dix_min, :jgl_dix_min,
        :baron, :drake, :team, :herald, :cs_max_avantage, :level_max_avantage, :afk, :vision_avantage, :early_drake, :temps_dead,
        :item1, :item2, :item3, :item4, :item5, :item6, :kp, :kda, :mode, :season, :date, :damageratio, :tankratio, :rank, :tier);''',
        {'match_id' : self.last_match,
        'joueur' : self.summonerName.lower(),
        'role' : self.thisPosition,
        'champion' : self.thisChampName,
        'kills' : self.thisKills,
        'assists' : self.thisAssists,
        'deaths' : self.thisDeaths,
        'double' : self.thisDouble,
        'triple' : self.thisTriple,
        'quadra' : self.thisQuadra,
        'penta' : self.thisPenta,
        'result' : self.thisWinBool,
        'team_kills' : self.thisTeamKills,
        'team_deaths' : self.thisTeamKillsOp,
        'time' : self.thisTime,
        'dmg' : self.thisDamageNoFormat,
        'dmg_ad' : self.thisDamageADNoFormat,
        'dmg_ap' : self.thisDamageAPNoFormat,
        'dmg_true' : self.thisDamageTrueNoFormat,
        'vision_score' : self.thisVision,
        'cs' : self.thisMinion,
        'cs_jungle' : self.thisJungleMonsterKilled,
        'vision_pink' : self.thisPink,
        'vision_wards' : self.thisWards,
        'vision_wards_killed' : self.thisWardsKilled,
        'gold' : self.thisGoldNoFormat,
        'spell1' : self.spell1,
        'spell2' : self.spell2,
        'cs_min' : self.thisMinionPerMin,
        'vision_min' : self.thisVisionPerMin,
        'gold_min' : self.thisGoldPerMinute,
        'dmg_min' : self.thisDamagePerMinute,
        'solokills' : self.thisSoloKills,
        'dmg_reduit' : self.thisDamageSelfMitigated,
        'heal_total' : self.thisTotalHealed,
        'heal_allies' : self.thisTotalOnTeammates,
        'serie_kills' : self.thisKillingSprees,
        'cs_dix_min' : self.thisCSafter10min,
        'jgl_dix_min' : self.thisJUNGLEafter10min,
        'baron' : self.thisBaronTeam,
        'drake' : self.thisDragonTeam,
        'team' : self.team,
        'herald' : self.thisHeraldTeam,
        'cs_max_avantage' : self.thisCSAdvantageOnLane,
        'level_max_avantage' : self.thisLevelAdvantage,
        'afk' : self.AFKTeamBool,
        'vision_avantage' : self.thisVisionAdvantage,
        'early_drake' : self.earliestDrake,
        'temps_dead' : self.thisTimeSpendDead,
        'item1' : self.thisItems[0],
        'item2' : self.thisItems[1],
        'item3' : self.thisItems[2],
        'item4' : self.thisItems[3],
        'item5' : self.thisItems[4],
        'item6' : self.thisItems[5],
        'kp' : self.thisKP,
        'kda' : self.thisKDA,
        'mode' : self.thisQ,
        'season' : self.season,
        'date' : int(self.timestamp),
        'damageratio' : self.thisDamageRatio,
        'tankratio' : self.thisDamageTakenRatio,
        'rank' : self.thisRank,
        'tier' : self.thisTier
        })

   
            
    async def resume_personnel(self, name_img, embed, difLP):
        
        """Resume personnel de sa game
        Parameters
        -----------
        name_img : nom de l'image enregistré
        embed : embed discord
        diflp : calcul
        
        return
        -----------
        embed discord"""
        # Gestion de l'image 1

       ## Graphique KP
        values = [self.thisKP/100, 1-self.thisKP/100]

        layout = Layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )

        fig = go.Figure(data=[go.Pie(labels=['a', 'b'],
                                    values=values,
                                    hole=.3,
                                    marker_colors=['rgb(68,138,236)', 'rgb(243,243,243)'])], layout=layout)
        fig.update_layout(showlegend=False,
            # Add annotations in the center of the donut pies.
            annotations=[dict(text=f'{self.thisKP}%',font_size=40, showarrow=False)])
        fig.update_traces(textinfo='none')



        fig.write_image('kp.png')
        
        ## Graphique stats
        
        stats_name = ['DMG', 'TANK', 'TANK_REDUC', 'Healing', 'Shield']
        stats_value = [self.thisDamageNoFormat, self.thisDamageTakenNoFormat, self.thisDamageSelfMitigated,
                    self.thisTotalHealed, self.thisTotalShielded]
        
        df_stats = pd.DataFrame([stats_name, stats_value]).transpose()
        df_stats.columns = ['stats', 'value']
        
        fig = px.histogram(df_stats, 'stats', 'value', color='stats', text_auto=".i")
        fig.update_traces(textfont_size=20)
        fig.update_layout(showlegend=False, font=dict(size=20))
        fig.update_yaxes(visible=False)
        fig.write_image('stats.png')
        
        # Image 1
        
        lineX = 2600
        lineY = 100
        
        x_name = 290
        y = 120
        y_name= y - 60
        x_rank = 1750
        
        x_metric = 120
        y_metric = 400
        
        line = Image.new("RGB", (lineX, 190), (230, 230, 230)) # Ligne grise

        
        

        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 50) # Ubuntu 18.04
        except OSError:
            try:
                font = ImageFont.truetype("arial.ttf", 50)  # Windows
            except OSError:
                font = ImageFont.truetype(
                        "AppleSDGothicNeo.ttc", 50
                    )  # MacOS
        

        try:
            font_little = ImageFont.truetype("DejaVuSans.ttf", 40) # Ubuntu 18.04
        except OSError:
            try:
                font_little = ImageFont.truetype("arial.ttf", 40)  # Windows
            except OSError:
                font_little = ImageFont.truetype(
                    "AppleSDGothicNeo.ttc", 40
                )  # MacOS
                    

        im = Image.new("RGBA", (lineX, 1400), (255, 255, 255)) # Ligne blanche
        d = ImageDraw.Draw(im)
        
        im.paste(line, (0, 0))
        
        fill=(0,0,0)
        d.text((x_name, y_name), self.summonerName, font=font, fill=fill)
    
        im.paste(im= await get_image("avatar", self.avatar, self.session, 100, 100),
            box=(x_name-240, y_name-20))
        
        im.paste(im=await get_image("champion", self.thisChampName, self.session, 100, 100),
                box=(x_name-120, y_name-20))
        
        d.text((x_name+700, y_name-20), f"Niveau {self.level_summoner}", font=font_little, fill=fill)
        
        if self.thisQ != "ARAM": # si ce n'est pas le mode aram, on prend la soloq normal
            if self.thisTier != ' ': # on vérifie que le joueur a des stats en soloq, sinon il n'y a rien à afficher
                img_rank = await get_image('tier', self.thisTier, self.session, 220, 220)
                
                            
                im.paste(img_rank,(x_rank, y-140), img_rank.convert('RGBA'))
                
                
                d.text((x_rank+220, y-110), f'{self.thisTier} {self.thisRank}', font=font, fill=fill)
                d.text((x_rank+220, y-45), f'{self.thisLP} LP ({difLP})', font=font_little, fill=fill)
                
                # Gestion des bo    
                if int(self.thisLP) == 100:
                    bo = self.thisStats[self.i]['miniSeries']
                    bo_wins = str(bo['wins'])
                    bo_losses = str(bo['losses'])
                    # bo_progress = str(bo['progress'])
                    d.text((x_rank+220, y+10), f'{self.thisVictory}W {self.thisLoose}L {self.thisWinrateStat}% (BO : {bo_wins} / {bo_losses}) ', font=font_little, fill=fill)
                else:
                    d.text((x_rank+220, y+10), f'{self.thisVictory}W {self.thisLoose}L     {self.thisWinrateStat}% ', font=font_little, fill=fill)
            else: # si pas de stats en soloq
                d.text((x_rank+220, y-45), 'En placement', font=font, fill=fill)
        else:
            
            data_aram = get_data_bdd(f'SELECT index,wins, losses, lp, games, k, d, a, activation, rank from ranked_aram WHERE index = :index', {'index' : self.summonerName}).fetchall()

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
                   
                 
                   
                wr = round(wins / games,2)*100
                

                if self.AFKTeam >= 1 and str(self.thisWinId) != "True": # si afk et lose, pas de perte
                    points = 0
                else:
                # calcul des LP 
                    if games <=5:
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
                
                if lp < 100:
                    rank = 'IRON'
                elif lp < 200:
                    rank = 'BRONZE'
                elif lp < 300:
                    rank = 'SILVER'
                elif lp < 500:
                    rank = 'GOLD'
                elif lp < 800:
                    rank = 'PLATINUM'
                elif lp < 1200:
                    rank = 'DIAMOND'
                elif lp < 1600:
                    rank = 'MASTER'
                elif lp < 2000: 
                    rank = 'GRANDMASTER'
                elif lp > 2000:
                    rank = 'CHALLENGER'
                
                # SIMULATION CHANGEMENT ELO    

                
                if games >= 5 and self.AFKTeam == 0: #si plus de 5 games et pas d'afk
                    lp = lp - elo_lp[rank] # malus en fonction du elo
                    
                # pas de lp negatif
                if lp < 0:
                    lp = 0
                                        
                if rank_actual != rank:
                    embed.add_field(name = "Changement d'elo", value=f" :star: Tu es passé de **{rank_actual}** à **{rank}**")
                
                k = k_actual + self.thisKills
                difLP = lp - lp_actual 
                deaths = d_actual + self.thisDeaths
                a = a_actual + self.thisAssists

                img_rank = await get_image('tier', rank, self.session, 220, 220)
            
                        
                im.paste(img_rank,(x_rank, y-140), img_rank.convert('RGBA'))
                d.text((x_rank+220, y-110), f'{rank}', font=font, fill=fill)
                d.text((x_rank+220, y-45), f'{lp} LP ({difLP})', font=font_little, fill=fill)
                

                d.text((x_rank+220, y+10), f'{wins}W {losses}L     {round(wr,1)}% ', font=font_little, fill=fill)
                
                requete_perso_bdd(f'''UPDATE ranked_aram
                                    SET wins = :wins,
                                    losses = :losses,
                                    lp = :lp,
                                    games = :games,
                                    k = :k,
                                    d = :d,
                                    a = :a,
                                    rank = :rank
                                  WHERE index = :index''',
                                    {'wins' : wins,
                                    'losses' : losses,
                                    'lp' : lp,
                                    'games' : games,
                                    'k' : k,
                                    'd' : deaths,
                                    'a' : a,
                                    'rank' : rank,
                                    'index' : self.summonerName.lower()})
           

        
        kp = await get_image('autre', 'kp', self.session, 700, 500)
        
                    
        im.paste(kp,(x_metric-150, y_metric+20), kp.convert('RGBA'))
        d.text((x_metric + 170, y_metric+20), 'KP', font=font, fill=(0, 0, 0))
        
        # CS
    
        d.text((x_metric, y_metric+620),f'Avantage CS : {int(self.thisCSAdvantageOnLane)}', font=font, fill=(0, 0, 0))
        d.text((x_metric, y_metric+500),f'CS/min : {int(self.thisMinionPerMin)}', font=font, fill=(0, 0, 0))
               
        # Ward
        
        if self.thisQ != "ARAM":
        
            d.text((x_metric + 640, y_metric),f'Vision : {self.thisVision} (AV : {self.thisVisionAdvantage}%)', font=font, fill=(0, 0, 0))
            d.text((x_metric + 640, y_metric+90),f'{self.thisVisionPerMin}/min', font=font, fill=(0, 0, 0))
            
            im.paste(im= await get_image("items", 3340, self.session, 100, 100),
                    box=(x_metric + 650, y_metric+200))
            
            d.text((x_metric + 800, y_metric+220),f'{self.thisWards}', font=font, fill=(0, 0, 0))
            
            im.paste(im=await get_image("items", 3364, self.session, 100, 100),
                    box=(x_metric + 650, y_metric+400))
            
            d.text((x_metric + 800, y_metric+420),f'{self.thisWardsKilled}', font=font, fill=(0, 0, 0))
            
            im.paste(im=await get_image("items", 2055, self.session, 100, 100),
                    box=(x_metric + 650, y_metric+600))
            
            d.text((x_metric + 800, y_metric+620),f'{self.thisPink}', font=font, fill=(0, 0, 0))
            
        # KDA
    
        kda_kills = 290
        kda_deaths = 890
        kda_assists = 1490
        kda_gold = 2090
        
        img_kda_kills = await get_image('kda', 'rectangle bleu blanc', self.session, 300, 150)
        img_kda_deaths = await get_image('kda', 'rectangle rouge blanc', self.session, 300, 150)
        img_kda_assists = await get_image('kda', 'rectangle vert', self.session, 300, 150)
        img_kda_gold = await get_image('kda', 'rectangle gold', self.session, 300, 150)
        
        im.paste(img_kda_kills,
                (kda_kills, y_metric-190), img_kda_kills.convert('RGBA'))
        
        im.paste(img_kda_deaths,
                (kda_deaths, y_metric-190), img_kda_deaths.convert('RGBA'))
        
        im.paste(img_kda_assists,
                (kda_assists, y_metric-190), img_kda_assists.convert('RGBA'))
        
        im.paste(img_kda_gold,
                (kda_gold, y_metric-190), img_kda_gold.convert('RGBA'))
        
        d.text((kda_kills+20, y_metric-100),f'Kills', font=font, fill=(255, 255, 255))
        d.text((kda_deaths+20, y_metric-100),f'Morts', font=font, fill=(255, 255, 255))
        d.text((kda_assists+20, y_metric-100),f'Assists', font=font, fill=(255, 255, 255))
        d.text((kda_gold+20, y_metric-100),f'Gold', font=font, fill=(0, 0, 0))
        
        # si le score est à deux chiffres, il faut décaler dans l'img
        if int(self.thisKills) >= 10:
            kda_kills = kda_kills - 30
        d.text((kda_kills+240, y_metric-180),f'{self.thisKills}', font=font, fill=(0, 0, 0))
        
        if int(self.thisDeaths) >=10:
            kda_deaths = kda_deaths - 30
        d.text((kda_deaths+240, y_metric-180),f'{self.thisDeaths}', font=font, fill=(0, 0, 0))
        
        if int(self.thisAssists) >=10:
            kda_assists = kda_assists - 30
        d.text((kda_assists+240, y_metric-180),f'{self.thisAssists}', font=font, fill=(0, 0, 0))
        
        d.text((kda_gold+150, y_metric-180),f'{round(self.thisGoldEarned/1000,1)}k', font=font, fill=(0, 0, 0))
            
            # Stat du jour
        if self.thisQ == 'ARAM':
            suivi_24h = lire_bdd('ranked_aram_24h', 'dict')
        else:
            suivi_24h = lire_bdd('suivi_24h', 'dict')
        
        
        if self.thisQ != 'ARAM':
            try:
                difwin = int(self.thisVictory) - int(suivi_24h[self.summonerName.lower()]["wins"])
                diflos = int(self.thisLoose) - int(suivi_24h[self.summonerName.lower()]["losses"])
                
                
                if (difwin + diflos) > 0: # si pas de ranked aujourd'hui, inutile
                    d.text((x_metric + 650, y_name+50),f'Victoires 24h : {difwin}', font=font_little, fill=(0, 0, 0))
                    d.text((x_metric + 1120, y_name+50),f'Defaites 24h : {diflos}', font=font_little, fill=(0, 0, 0))
            
            except KeyError:
                pass
        
        elif self.thisQ == 'ARAM' and activation:
            try:
                difwin = wins - int(suivi_24h[self.summonerName.lower()]["wins"])
                diflos = losses - int(suivi_24h[self.summonerName.lower()]["losses"])
                
                
                if (difwin + diflos) > 0: # si pas de ranked aujourd'hui, inutile
                    d.text((x_metric + 650, y_name+50),f'Victoires 24h : {difwin}', font=font_little, fill=(0, 0, 0))
                    d.text((x_metric + 1120, y_name+50),f'Defaites 24h : {diflos}', font=font_little, fill=(0, 0, 0))
            
            except KeyError:
                pass
            
            
        im.paste(im=await get_image("autre", 'stats', self.session, 1000, 800),
                    box=(x_metric + 900, y_metric+100))
        
        
        d.text((x_metric + 2000, y_metric+200),f'Solokills : {self.thisSoloKills}', font=font, fill=(0, 0, 0))
        d.text((x_metric + 2000, y_metric+300),f'Double : {self.thisDouble}', font=font, fill=(0, 0, 0))
        d.text((x_metric + 2000, y_metric+400),f'Triple : {self.thisTriple}', font=font, fill=(0, 0, 0))
        d.text((x_metric + 2000, y_metric+500),f'Quadra : {self.thisQuadra}', font=font, fill=(0, 0, 0))
        d.text((x_metric + 2000, y_metric+600),f'Penta : {self.thisPenta}', font=font, fill=(0, 0, 0))
        

    
        im.save(f'{name_img}.png')
        
        return embed
        
        
    async def resume_general(self, name_img):

        '''Resume global de la game
        
        Parameters
        -----------
        name_img : nom de l'image enregistré'''
        # Gestion de l'image 2
        lineX = 2600
        lineY = 100
        
        x_name = 500
        x_level = x_name - 400
        x_ecart = x_name - 150
        x_kills = 1000
        x_deaths = x_kills + 100
        x_assists = x_deaths + 100
        
        x_kda = x_assists + 200
        
        x_kp = x_kda + 200
        
        x_cs = x_kp + 200 
        
        x_vision = x_cs + 150
        
        x_dmg_percent = x_vision + 150
        
        x_dmg_taken = x_dmg_percent + 250
        
        x_kill_total = 1000
        x_objectif = 1700

        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 50) # Ubuntu 18.04
        except OSError:
            try:
                font = ImageFont.truetype("arial.ttf", 50)  # Windows
            except OSError:
                font = ImageFont.truetype(
                        "AppleSDGothicNeo.ttc", 50
                    )  # MacOS
        

        im = Image.new("RGBA", (lineX, lineY * 13), (255, 255, 255)) # Ligne blanche
        d = ImageDraw.Draw(im)
        line = Image.new("RGB", (lineX, lineY), (230, 230, 230)) # Ligne grise

        dict_position = {"TOP" : 2, "JUNGLE": 3, "MID" : 4, "ADC" : 5, "SUPPORT" : 6}

        for i in range(0, 13):
            if i % 2 == 0:
                im.paste(line, (0, i * lineY))
            elif i == 1:
                im.paste(Image.new("RGB", (lineX, lineY), (85, 85, 255)), (0, i * lineY)) # Ligne bleu
            elif i == 7:
                im.paste(Image.new("RGB", (lineX, lineY), (255, 70, 70)), (0, i * lineY)) # Ligne rouge
                
            
            if self.thisQ != "ARAM":
                if i == dict_position[self.thisPosition]:
                    im.paste(Image.new("RGB", (lineX, lineY), (173,216,230)), (0, i*lineY))
                
            


        # match
        d.text((10, 15), self.thisQ, font=font, fill=(0, 0, 0))
        # d.text((10, 120), f'Gold : {self.thisGold_team1}', font=font, fill=(255, 255, 255))
        # d.text((10, 720), f'Gold : {self.thisGold_team2}', font=font, fill=(0, 0, 0))
        
        money = await get_image('gold', 'dragon', self.session, 60, 60)
        
        
        im.paste(money,(10, 120), money.convert('RGBA'))
        d.text((80, 120), f'{self.thisGold_team1}', font=font, fill=(255, 255, 255))
        im.paste(money,(10, 720), money.convert('RGBA'))
        d.text((80, 720), f'{self.thisGold_team2}', font=font, fill=(0, 0, 0))
        
        
        
        for y in range(120, 721, 600):
            if y == 120:
                fill = (255,255,255)
            else:
                fill = (0,0,0)
            d.text((x_name, y), 'Name', font=font, fill=fill)
            d.text((x_kills, y), 'K', font=font, fill=fill)
            d.text((x_deaths, y), 'D', font=font, fill=fill)
            d.text((x_assists, y), 'A', font=font, fill=fill)
            d.text((x_kda, y), 'KDA', font=font, fill=fill)
            d.text((x_kp, y), 'KP', font=font, fill=fill)
            d.text((x_cs, y), 'CS', font=font, fill=fill)
            d.text((x_dmg_percent+10, y), "DMG%", font=font, fill=fill)
            d.text((x_dmg_taken+15, y), 'TANK%', font=font, fill=fill)
            
            if self.thisQ != "ARAM": 
                d.text((x_vision, y), 'VS', font=font, fill=fill)

        # participants
        initial_y = 220

        for i in range(0, 10):
            im.paste(
                im=await get_image("champion", self.thisChampNameListe[i], self.session),
                box=(10, initial_y-10),
            )
            
            d.text((x_level, initial_y), "Niv " + str(self.thisLevelListe[i]), font=font, fill=(0,0,0))

            d.text((x_name, initial_y), self.thisPseudoListe[i], font=font, fill=(0, 0, 0))
        
            
            if len(str(self.thisKillsListe[i])) == 1:
                d.text((x_kills, initial_y), str(self.thisKillsListe[i]), font=font, fill=(0,0,0))
            else:
                d.text((x_kills - 20, initial_y), str(self.thisKillsListe[i]), font=font, fill=(0,0,0))
                
                
            if len(str(self.thisDeathsListe[i])) == 1:
                d.text((x_deaths, initial_y), str(self.thisDeathsListe[i]), font=font, fill=(0,0,0))
            else:
                d.text((x_deaths - 20, initial_y), str(self.thisDeathsListe[i]), font=font, fill=(0,0,0))
            

            if len(str(self.thisAssistsListe[i])) == 1:            
                d.text((x_assists, initial_y), str(self.thisAssistsListe[i]), font=font, fill=(0,0,0))
            else:
                d.text((x_assists - 20, initial_y), str(self.thisAssistsListe[i]), font=font, fill=(0,0,0))
            
            
            if len(str(round(self.thisKDAListe[i],2)))==1: # Recentrer le résultat quand chiffre rond
                d.text((x_kda + 35, initial_y), str(round(self.thisKDAListe[i],2)), font=font, fill=(0,0,0))
            else:
                d.text((x_kda, initial_y), str(round(self.thisKDAListe[i],2)), font=font, fill=(0,0,0))
                
            d.text((x_kp, initial_y), str(self.thisKPListe[i]) + "%", font=font, fill=(0, 0, 0))
            
            if len(str(self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i])) != 2:
                d.text((x_cs, initial_y), str(self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]), font=font, fill=(0, 0, 0))
            else:
                d.text((x_cs + 10, initial_y), str(self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]), font=font, fill=(0, 0, 0))
                
            if self.thisQ != "ARAM": 
                
                d.text((x_vision, initial_y), str(self.thisVisionListe[i]), font=font, fill=(0, 0, 0))
                
                
            if len(str(round(self.thisDamageRatioListe[i]*100,1))) == 3:     
                d.text((x_dmg_percent + 15, initial_y), str(round(self.thisDamageRatioListe[i]*100,1)) + "%", font=font, fill=(0,0,0))
            else:
                d.text((x_dmg_percent, initial_y), str(round(self.thisDamageRatioListe[i]*100,1)) + "%", font=font, fill=(0,0,0))
                
                
            if len(str(round(self.thisDamageTakenRatioListe[i]*100,1))) == 3:
                d.text((x_dmg_taken + 15, initial_y), str(round(self.thisDamageTakenRatioListe[i]*100,1)) + "%", font=font, fill=(0,0,0))
            else:
                d.text((x_dmg_taken, initial_y), str(round(self.thisDamageTakenRatioListe[i]*100,1)) + "%", font=font, fill=(0,0,0))
                
            
            

            if i == 4:
                initial_y += 200
            else:
                initial_y += 100
                
        if self.thisQ != "ARAM":         
            y_ecart = 220
            for ecart in [self.ecart_top_gold_affiche, self.ecart_jgl_gold_affiche, self.ecart_mid_gold_affiche, self.ecart_adc_gold_affiche, self.ecart_supp_gold_affiche]:        
                if ecart > 0:
                    d.text((x_ecart, y_ecart), str(round(ecart/1000,1)) + "k", font=font, fill=(0,128,0))
                else:
                    d.text((x_ecart-10, y_ecart), str(round(ecart/1000,1)) + "k", font=font, fill=(255,0,0))   
                
                y_ecart = y_ecart + 100
                
            
        n = 0
        for image in self.thisItems:
            if image != 0:
                im.paste(await get_image("items", image, self.session),
                box=(350 + n, 10))
                n += 100
                
        if self.thisQ != "ARAM":        
                
            drk = await get_image('monsters', 'dragon', self.session)
            elder = await get_image('monsters', 'elder', self.session)
            herald = await get_image('monsters', 'herald', self.session)
            nashor = await get_image('monsters', 'nashor', self.session)       
                    
            im.paste(drk,(x_objectif, 10), drk.convert('RGBA'))
            d.text((x_objectif + 100, 20), str(self.thisDragonTeam), font=font, fill=(0, 0, 0))
            
            im.paste(elder,(x_objectif + 200, 10), elder.convert('RGBA'))
            d.text((x_objectif + 200 + 100, 20), str(self.thisElderPerso), font=font, fill=(0, 0, 0))
                
            im.paste(herald,(x_objectif + 400, 10), herald.convert('RGBA'))
            d.text((x_objectif + 400 + 100, 20), str(self.thisHeraldTeam), font=font, fill=(0, 0, 0))
                    
            im.paste(nashor, (x_objectif + 600, 10), nashor.convert('RGBA'))
            d.text((x_objectif + 600 + 100, 20), str(self.thisBaronTeam), font=font, fill=(0, 0, 0))
            
        
        img_blue_epee = await get_image('epee', 'blue', self.session)
        img_red_epee = await get_image('epee', 'red', self.session)
        
        im.paste(img_blue_epee, (x_kill_total, 10), img_blue_epee.convert('RGBA'))
        d.text((x_kill_total + 100, 20), str(self.thisTeamKills), font=font, fill=(0, 0, 0))
        
        im.paste(img_red_epee, (x_kill_total + 300, 10), img_red_epee.convert('RGBA'))
        d.text((x_kill_total + 300 + 100, 20), str(self.thisTeamKillsOp), font=font, fill=(0, 0, 0))

        im.save(f'{name_img}.png')

        await self.session.close()