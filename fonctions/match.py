import pandas as pd

from riotwatcher import LolWatcher
import pandas as pd
import warnings
from fonctions.gestion_bdd import lire_bdd
import json
import numpy as np


warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'

import os

dict_rankid = {"BRONZE IV" : 1,
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

def get_key(my_dict, val):
    for key, value in my_dict.items():
        if val == value:
            return key
        
    return "No key"



api_key_lol = os.environ.get('API_LOL')  # https://www.youtube.com/watch?v=IolxqkL7cD8

lol_watcher = LolWatcher(api_key_lol)
my_region = 'euw1'
region = "EUROPE"

# Paramètres LoL
version = lol_watcher.data_dragon.versions_for_region(my_region)
champions_versions = version['n']['champion']

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


def match_by_puuid(summonerName, idgames: int, index=0, queue=0):
    me = lol_watcher.summoner.by_name(my_region, summonerName) # informations sur le joueur
    if queue == 0:
        my_matches = lol_watcher.match.matchlist_by_puuid(region, me['puuid'], count=100, start=index)
    else:
        my_matches = lol_watcher.match.matchlist_by_puuid(region, me['puuid'], count=100, start=index, queue=queue) ## liste des id des matchs du joueur en fonction de son puuid
    last_match = my_matches[idgames] # match n° idgames
    match_detail_stats = lol_watcher.match.by_id(region, last_match) # detail du match sélectionné
    return last_match, match_detail_stats, me


def getId(summonerName):
    try:
        last_match, match_detail, me = match_by_puuid(summonerName, 0)

        return str(match_detail['info']['gameId'])
    except:
        data = lire_bdd('tracker', 'dict')
        return str(data[summonerName]['id'])
    
    
    
class matchlol():

    def __init__(self, summonerName, idgames:int, queue:int=0, index:int=0):
        self.summonerName = summonerName
        self.idgames = idgames
        self.queue = queue
        self.index = index
        self.last_match, self.match_detail_stats, self.me = match_by_puuid(self.summonerName, self.idgames, self.index, self.queue)    
        self.current_champ_list = lol_watcher.data_dragon.champions(champions_versions, False, 'fr_FR')
        
        self.champ_dict = {}
        for key in self.current_champ_list['data']:
            row = self.current_champ_list['data'][key]
            self.champ_dict[row['key']] = row['id']  
        
        
        # Detail de chaque champion...

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
        # print(thisId)
        self.thisQId = self.match_detail['info']['queueId']
        self.match_detail_participants = self.match_detail['info']['participants'][self.thisId]
        self.match_detail_challenges = self.match_detail_participants['challenges']
        self.thisPosition = self.match_detail_participants['teamPosition']
        
        if (str(self.thisPosition) == "MIDDLE"):
            self.thisPosition = "MID"
        elif (str(self.thisPosition) == "BOTTOM"):
            self.thisPosition = "ADC"
        elif (str(self.thisPosition) == "UTILITY"):
            self.thisPosition = "SUPPORT"
        
        
        self.thisQ = ' '
        self.thisChamp = self.match_detail_participants['championId']
        self.thisDouble = self.match_detail_participants['doubleKills']
        self.thisTriple = self.match_detail_participants['tripleKills']
        self.thisQuadra = self.match_detail_participants['quadraKills']
        self.thisPenta = self.match_detail_participants['pentaKills']
        self.thisChamp = self.match_detail_participants['championId']
        self.thisChampName = self.champ_dict[str(self.thisChamp)]
        self.thisKills = self.match_detail_participants['kills']
        self.thisDeaths = self.match_detail_participants['deaths']
        self.thisAssists = self.match_detail_participants['assists']
        self.thisWinId = self.match_detail_participants['win']
        self.thisTimeLiving = round((int(self.match_detail_participants['longestTimeSpentLiving']) / 60), 2)
        self.thisWin = ' '
        self.thisTime = round((int(self.match_detail['info']['gameDuration']) / 60), 2)
        self.thisDamage = self.match_detail_participants['totalDamageDealtToChampions']
        self.thisDamageAP = self.match_detail_participants['magicDamageDealtToChampions']
        self.thisDamageAD = self.match_detail_participants['physicalDamageDealtToChampions']
        self.thisDamageTrue = self.match_detail_participants['trueDamageDealtToChampions']
        
        self.thisTimeSpendDead = round(float(self.match_detail_participants['totalTimeSpentDead'])/60,2) 
        
        self.thisDamageTaken = int(self.match_detail_participants['totalDamageTaken'])
        self.thisDamageTakenAD = int(self.match_detail_participants['physicalDamageTaken'])
        self.thisDamageTakenAP = int(self.match_detail_participants['magicDamageTaken'])
        self.thisDamageTakenTrue = int(self.match_detail_participants['trueDamageTaken'])
        
        self.thisVision = self.match_detail_participants['visionScore']
        self.thisJungleMonsterKilled = self.match_detail_participants['neutralMinionsKilled']
        self.thisMinion = self.match_detail_participants['totalMinionsKilled'] + self.thisJungleMonsterKilled
        self.thisPink = self.match_detail_participants['visionWardsBoughtInGame']
        self.thisWards = self.match_detail_participants['wardsPlaced']
        self.thisWardsKilled = self.match_detail_participants['wardsKilled']
        self.thisGold = int(self.match_detail_participants['goldEarned'])
        
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
        self.thisStats = lol_watcher.league.by_summoner(my_region, self.me['id'])
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
        
        try:    
            self.AFKTeam = self.match_detail_challenges['hadAfkTeammate']
        except:
            self.AFKTeam = 0
        
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
        else:
            self.thisWin = "PERDRE"

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

        
    
        

