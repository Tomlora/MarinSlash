from json import detect_encoding
from discord.ext import commands, tasks

from matplotlib import pyplot as plt

from riotwatcher import LolWatcher
import pandas as pd
import main
import datetime
import numpy as np
import warnings
from discord_slash.utils.manage_components import *
from cogs.achievements_scoringlol import scoring
from fonctions.gestion_fichier import loadData, writeData
from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd

from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice
import time



warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'

import os

api_key_lol = os.environ.get('API_LOL')  # https://www.youtube.com/watch?v=IolxqkL7cD8

lol_watcher = LolWatcher(api_key_lol)
my_region = 'euw1'
region = "EUROPE"

# Paramètres LoL
version = lol_watcher.data_dragon.versions_for_region(my_region)
champions_versions = version['n']['champion']


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
               "DIAMOND I" : 20}



def records_check(fichier, key_boucle, key: str, Score_check: float, thisChampName, summonerName, embed):
    if str(key_boucle) == str(key):
        # si le record est battu, on fait les modifs nécessaires:
        if float(fichier[key]['Score']) < Score_check:
            ancien_score = fichier[key]['Score']
            detenteur_ancien_score = fichier[key]['Joueur']
            fichier[key]['Score'] = Score_check
            fichier[key]['Champion'] = str(thisChampName)
            fichier[key]['Joueur'] = summonerName
            # Annonce que le record a été battu :
            embed = embed + "\n ** :boom: Record " + str(key).lower() + " battu avec " + str(Score_check) + " ** (Ancien : " + str(ancien_score) + " par " + str(detenteur_ancien_score) + ")"


    return fichier, embed

def match_by_puuid(summonerName, idgames: int):
    me = lol_watcher.summoner.by_name(my_region, summonerName)
    my_matches = lol_watcher.match.matchlist_by_puuid(region, me['puuid'], count=100)
    last_match = my_matches[idgames]
    match_detail_stats = lol_watcher.match.by_id(region, last_match)
    return last_match, match_detail_stats, me


def match_spectator(summonerName):
    me = lol_watcher.summoner.by_name(my_region, summonerName)
    try:
        my_match = lol_watcher.spectator.by_summoner(my_region, me['id'])
    except:
        my_match = False
    return my_match


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


def getId(summonerName):
    try:
        last_match, match_detail, me = match_by_puuid(summonerName, 0)

        return str(match_detail['info']['gameId'])
    except:
        print(f'getId Erreur avec {summonerName}')
        data = loadData('id_data')
        return str(data[summonerName])


def palier(embed, key:str, stats:str, old_value:int, new_value:int, palier:list):
    if key == stats:
        for value in palier:
            if old_value < value and new_value > value:
                stats = stats.replace('_', ' ')
                embed = embed + "\n ** :tada: Stats cumulées : A dépassé les " + str(value) +  " " + stats.lower() + " avec " + str(new_value) + " " + stats.lower() + "**"
    return embed 
                

class LeagueofLegends(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.my_task.start()
        self.lolsuivi.start()      
 
    def printInfo(self, summonerName, idgames: int, succes):

        last_match, match_detail_stats, me = match_by_puuid(summonerName, idgames)

        current_champ_list = lol_watcher.data_dragon.champions(champions_versions, False, 'fr_FR')

        channel = self.bot.get_channel(int(main.chan_tracklol))


        champ_dict = {}
        for key in current_champ_list['data']:
            row = current_champ_list['data'][key]
            champ_dict[row['key']] = row['id']

        # Detail de chaque champion...

        match_detail = pd.DataFrame(match_detail_stats)

        dic = {
            (match_detail['info']['participants'][0]['summonerName']).lower().replace(" ", ""): 0,
            (match_detail['info']['participants'][1]['summonerName']).lower().replace(" ", ""): 1,
            (match_detail['info']['participants'][2]['summonerName']).lower().replace(" ", ""): 2,
            (match_detail['info']['participants'][3]['summonerName']).lower().replace(" ", ""): 3,
            (match_detail['info']['participants'][4]['summonerName']).lower().replace(" ", ""): 4,
            (match_detail['info']['participants'][5]['summonerName']).lower().replace(" ", ""): 5,
            (match_detail['info']['participants'][6]['summonerName']).lower().replace(" ", ""): 6,
            (match_detail['info']['participants'][7]['summonerName']).lower().replace(" ", ""): 7,
            (match_detail['info']['participants'][8]['summonerName']).lower().replace(" ", ""): 8,
            (match_detail['info']['participants'][9]['summonerName']).lower().replace(" ", ""): 9
        }

        # stats
        thisId = dic[
            summonerName.lower().replace(" ", "")]  # cherche le pseudo dans le dico et renvoie le nombre entre 0 et 9
        # print(thisId)
        thisQId = match_detail['info']['queueId']
        thisPosition = match_detail['info']['participants'][thisId]['teamPosition']
        
        if thisQId == 900: #urf (géré différemment)
            return {}
        
        if thisQId == 840:
            return {} # bot game
        ##
        if (str(thisPosition) == "MIDDLE"):
            thisPosition = "MID"
        elif (str(thisPosition) == "BOTTOM"):
            thisPosition = "ADC"
        elif (str(thisPosition) == "UTILITY"):
            thisPosition = "SUPPORT"

        thisQ = ' '
        thisChamp = match_detail['info']['participants'][thisId]['championId']
        thisDouble = match_detail['info']['participants'][thisId]['doubleKills']
        thisTriple = match_detail['info']['participants'][thisId]['tripleKills']
        thisQuadra = match_detail['info']['participants'][thisId]['quadraKills']
        thisPenta = match_detail['info']['participants'][thisId]['pentaKills']
        thisChamp = match_detail['info']['participants'][thisId]['championId']
        thisChampName = champ_dict[str(thisChamp)]
        thisKills = match_detail['info']['participants'][thisId]['kills']
        thisDeaths = match_detail['info']['participants'][thisId]['deaths']
        thisAssists = match_detail['info']['participants'][thisId]['assists']
        thisWinId = match_detail['info']['participants'][thisId]['win']
        thisTimeLiving = round((int(match_detail['info']['participants'][thisId]['longestTimeSpentLiving']) / 60), 2)
        thisWin = ' '
        thisTime = round((int(match_detail['info']['gameDuration']) / 60), 2)
        thisMultiKill = match_detail['info']['participants'][thisId]['largestMultiKill']
        thisDamage = match_detail['info']['participants'][thisId]['totalDamageDealtToChampions']
        thisDamageTaken = int(match_detail['info']['participants'][thisId]['totalDamageTaken'])
        thisVision = match_detail['info']['participants'][thisId]['visionScore']
        thisJungleMonsterKilled = match_detail['info']['participants'][thisId]['neutralMinionsKilled']
        thisMinion = match_detail['info']['participants'][thisId]['totalMinionsKilled'] + thisJungleMonsterKilled
        thisPink = match_detail['info']['participants'][thisId]['visionWardsBoughtInGame']
        thisWards = match_detail['info']['participants'][thisId]['wardsPlaced']
        thisWardsKilled = match_detail['info']['participants'][thisId]['wardsKilled']
        thisGold = int(match_detail['info']['participants'][thisId]['goldEarned'])
        thisMinionPerMin = round((thisMinion / thisTime), 2)
        thisVisionPerMin = round((thisVision / thisTime), 2)
        thisGoldPerMinute = round((thisGold / thisTime), 2)
        thisDamagePerMinute = round(
            int(match_detail['info']['participants'][thisId]['totalDamageDealtToChampions']) / thisTime, 0)
        thisDamageTakenPerMinute = round(
            int(match_detail['info']['participants'][thisId]['totalDamageTaken']) / thisTime, 0)
        thisStats = lol_watcher.league.by_summoner(my_region, me['id'])
        thisWinrateStat = ' '
        thisWinrate = ' '
        thisRank = ' '
        thisLP = ' '
        if int(thisDeaths) >= 1:
            thisKDA = round((int(thisKills) + int(thisAssists)) / int(thisDeaths), 2)
        else:
            thisKDA = 0

        # Page record 2

        thisSpellUsed = match_detail['info']['participants'][thisId]['challenges']['abilityUses']
        thisbuffsVolees = match_detail['info']['participants'][thisId]['challenges']['buffsStolen']
        thisSpellsDodged = match_detail['info']['participants'][thisId]['challenges']['dodgeSkillShotsSmallWindow']
        thisMultiKillOneSpell = match_detail['info']['participants'][thisId]['challenges']['multiKillOneSpell']
        thisSoloKills = match_detail['info']['participants'][thisId]['challenges']['soloKills']
        thisJUNGLEafter10min = match_detail['info']['participants'][thisId]['challenges']['jungleCsBefore10Minutes']
        thisCSafter10min = match_detail['info']['participants'][thisId]['challenges']['laneMinionsFirst10Minutes'] + thisJUNGLEafter10min
        thisKillingSprees = match_detail['info']['participants'][thisId]['killingSprees']
        thisDamageSelfMitigated = match_detail['info']['participants'][thisId]['damageSelfMitigated']
        thisDamageTurrets = match_detail['info']['participants'][thisId]['damageDealtToTurrets']
        thisGoldEarned = match_detail['info']['participants'][thisId]['goldEarned']
        thisKillsSeries = match_detail['info']['participants'][thisId]['largestKillingSpree']
        thisTotalHealed = match_detail['info']['participants'][thisId]['totalHeal']
        thisTotalOnTeammates = match_detail['info']['participants'][thisId]['totalHealsOnTeammates']
        thisAcesBefore15min = match_detail['info']['participants'][thisId]['challenges']['acesBefore15Minutes']


        thisGold = "{:,}".format(thisGold).replace(',', ' ').replace('.', ',')
        thisDamage = "{:,}".format(thisDamage).replace(',', ' ').replace('.', ',')
        thisDamageTaken = "{:,}".format(thisDamageTaken).replace(',', ' ').replace('.', ',')
        thisDamageSelfMitigatedFormat = "{:,}".format(thisDamageSelfMitigated).replace(',', ' ').replace('.', ',')
        thisTimeLiving = str(thisTimeLiving).replace(".", "m")
        thisTotalOnTeammatesFormat = "{:,}".format(thisTotalOnTeammates).replace(',', ' ').replace('.', ',')

        if thisQId == 420:
            thisQ = "RANKED"
        elif thisQId == 400:
            thisQ = "NORMAL"
        elif thisQId == 440:
            thisQ = "FLEX"
        elif thisQId == 450:
            thisQ = "ARAM"
        else:
            thisQ = "OTHER"
            
   

            # thisQ = 0 (partie entrainement) / thisQ = 2000 (didactiel)

        if str(thisWinId) == 'True':
            thisWin = "GAGNER"
        else:
            thisWin = "PERDRE"

        thisDamageListe = dict_data(thisId, match_detail, 'totalDamageDealtToChampions')

        # thisTeamDamage = thisDamageListe[0] + thisDamageListe[1] + thisDamageListe[2] + thisDamageListe[3] + \
        #                  thisDamageListe[4]

        # pseudo

        thisPseudoListe = dict_data(thisId, match_detail, 'summonerName')

        # champ id

        thisChampListe = dict_data(thisId, match_detail, 'championId')

        # champ

        thisChampName1 = champ_dict[str(thisChampListe[0])]
        thisChampName2 = champ_dict[str(thisChampListe[1])]
        thisChampName3 = champ_dict[str(thisChampListe[2])]
        thisChampName4 = champ_dict[str(thisChampListe[3])]
        thisChampName5 = champ_dict[str(thisChampListe[4])]
        thisChampName6 = champ_dict[str(thisChampListe[5])]
        thisChampName7 = champ_dict[str(thisChampListe[6])]
        thisChampName8 = champ_dict[str(thisChampListe[7])]
        thisChampName9 = champ_dict[str(thisChampListe[8])]
        thisChampName10 = champ_dict[str(thisChampListe[9])]

        # total kills

        thisKillsListe = dict_data(thisId, match_detail, 'kills')
        
        thisTeamKills = thisKillsListe[0] + thisKillsListe[1] + thisKillsListe[2] + thisKillsListe[3] + thisKillsListe[4]

        # deaths

        thisDeathsListe = dict_data(thisId, match_detail, 'deaths')

        # assists

        thisAssistsListe = dict_data(thisId, match_detail, 'assists')

        # gold

        thisGoldListe = dict_data(thisId, match_detail, 'goldEarned')


        
        thisGold_team1 = thisGoldListe[0] + thisGoldListe[1] + thisGoldListe[2] + thisGoldListe[3] + thisGoldListe[4]
        thisGold_team2 = thisGoldListe[5] + thisGoldListe[6] + thisGoldListe[7] + thisGoldListe[8] + thisGoldListe[9]
        
        thisGold_team1 = "{:,}".format(thisGold_team1).replace(',', ' ').replace('.', ',')
        thisGold_team2 = "{:,}".format(thisGold_team2).replace(',', ' ').replace('.', ',')
        
        

        try:
            thisKP = int(round((thisKills + thisAssists) / (thisTeamKills), 2) * 100)
        except:
            thisKP = 0

        # thisDamageRatio = round((float(thisDamage) / float(thisTeamDamage)) * 100, 2)
        thisDamageRatio = round(
            (match_detail['info']['participants'][thisId]['challenges']['teamDamagePercentage']) * 100, 2)
        thisDamageTakenRatio = round(
            (match_detail['info']['participants'][thisId]['challenges']['damageTakenOnTeamPercentage']) * 100, 2)

        # on doit identifier les stats soloq (et non flex...)
        try:
            if str(thisStats[0]['queueType']) == "RANKED_SOLO_5x5":
                i = 0
            else:
                i = 1

            thisWinrate = int(thisStats[i]['wins']) / (int(thisStats[i]['wins']) + int(thisStats[i]['losses']))
            thisWinrateStat = str(int(thisWinrate * 100))
            thisRank = str(thisStats[i]['rank'])
            thisTier = str(thisStats[i]['tier'])
            thisLP = str(thisStats[i]['leaguePoints'])
            thisVictory = str(thisStats[i]['wins'])
            thisLoose = str(thisStats[i]['losses'])
        except IndexError:
            rank = "no rank in ranked"

        # name3 = 'suivi'
        
        exploits = "Observations :"

        if thisQ == "RANKED" and thisTime > 20:

            records = loadData('records')


            suivi = loadData('suivi')

            for key, value in records.items():
                if int(thisDeaths) >= 1:

                    records, exploits = records_check(records, key, 'KDA',
                                            float(thisKDA),
                                            thisChampName, summonerName, exploits)
                else:
                    records, exploits = records_check(records, key, 'KDA',
                                            float(
                                                round((int(thisKills) + int(thisAssists)) / (int(thisDeaths) + 1), 2)),
                                            thisChampName, summonerName, exploits)

                records, exploits = records_check(records, key, 'KP', thisKP,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'CS', thisMinion,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'CS/MIN', thisMinionPerMin,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'KILLS', thisKills,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'DEATHS', thisDeaths,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'ASSISTS', thisAssists,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'WARDS_SCORE', thisVision,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'WARDS_POSEES', thisWards,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'WARDS_DETRUITES', thisWardsKilled,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'WARDS_PINKS', thisPink,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'DEGATS_INFLIGES',
                                        match_detail['info']['participants'][thisId]['totalDamageDealtToChampions'],
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, '% DMG', thisDamageRatio,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'DOUBLE', thisDouble,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'TRIPLE', thisTriple,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'QUADRA', thisQuadra,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'PENTA', thisPenta,
                                        thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'DUREE_GAME', thisTime,
                                        thisChampName, summonerName, exploits)

                records2 = loadData('records2')


                for key, value in records2.items():
                    if thisChampName != "Zeri": # on supprime Zeri de ce record qui est impossible à égaler avec d'autres champions
                        records2, exploits = records_check(records2, key, 'SPELLS_USED',
                                                 thisSpellUsed,
                                                 thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'BUFFS_VOLEES', thisbuffsVolees,
                                             thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'SPELLS_EVITES', thisSpellsDodged,
                                             thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'MULTIKILL_1_SPELL', thisMultiKillOneSpell,
                                             thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'SOLOKILLS', thisSoloKills,
                                             thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'CS_APRES_10_MIN', thisCSafter10min,
                                             thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'NB_SERIES_DE_KILLS', thisKillingSprees,
                                             thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'DOMMAGES_TANK',
                                             int(match_detail['info']['participants'][thisId]['totalDamageTaken']),
                                             thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'DOMMAGES_TANK%', thisDamageTakenRatio,
                                             thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'DOMMAGES_REDUITS', thisDamageSelfMitigated,
                                             thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'DOMMAGES_TOWER', thisDamageTurrets,
                                             thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'GOLDS_GAGNES', thisGoldEarned,
                                             thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'SERIES_DE_KILLS', thisKillsSeries,
                                             thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'TOTAL_HEALS',
                                             thisTotalHealed,
                                             thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'HEALS_SUR_ALLIES', thisTotalOnTeammates,
                                             thisChampName, summonerName, exploits)

                    writeData(records, 'records')
                    writeData(records2, 'records2')
                    # sauvegarde_bdd(records, 'records')
                    # sauvegarde_bdd(records2, 'records2')

        # couleur de l'embed en fonction du pseudo

        pseudo = str(summonerName).upper()

        global color

        if (pseudo == 'NAMIYEON') or (pseudo == 'ZYRADELEVINGNE') or (pseudo == 'CHATOBOGAN'):
            color = discord.Color.gold()
        elif pseudo == 'DJINGO':
            color = discord.Color.orange()
        elif pseudo == 'TOMLORA':
            color = discord.Color.dark_green()
        elif pseudo == 'YLARABKA':
            color = discord.Colour.from_rgb(253, 119, 90)
        elif (pseudo == 'LINÒ') or (pseudo == 'LORDOFCOUBI') or (pseudo == 'NUKETHESTARS'):
            color = discord.Colour.from_rgb(187, 112, 255)
        elif (pseudo == 'EXORBLUE'):
            color = discord.Colour.from_rgb(223, 55, 93)
        elif (pseudo == 'KULBUTOKÉ'):
            color = discord.Colour.from_rgb(42, 188, 248)
        elif (pseudo == 'KAZSC'):
            color = discord.Colour.from_rgb(245, 68, 160)
        else:
            color = discord.Color.blue()

        # constructing the message

        if thisQ == "OTHER":
            embed = discord.Embed(
                title="**" + str(summonerName).upper() + "** vient de **" + thisWin + "** une game sur " + str(
                    thisChampName), color=color)
        elif thisQ == "ARAM":
            embed = discord.Embed(
                title="**" + str(summonerName).upper() + "** vient de **" + thisWin + "** une ARAM sur " + str(
                    thisChampName), color=color)
        else:
            embed = discord.Embed(
                title="**" + str(summonerName).upper() + "** vient de **" + thisWin + "** une " + str(
                    thisQ) + " game sur " + str(thisChampName) + " (" + str(thisPosition) + ")", color=color)

            if thisPosition in ['SUPPORT', 'ADC', 'MID', 'JUNGLE']:
                result = scoring(thisPosition, summonerName, thisKills, thisDeaths, thisAssists, (thisKP / 100),
                                 thisWards, thisWardsKilled, thisPink, thisMinion, thisMinionPerMin)

        # annonce
        points = 0
        

        settings = loadData("achievements_settings")
        records_cumul = loadData('records3')

        if int(thisPenta) >= settings['Pentakill']:
            exploits = exploits + "\n ** :crown: :five: Ce joueur a pentakill ** " + str(thisPenta) + " fois"
            points = points + (1 * int(thisPenta))

        if int(thisQuadra) >= settings['Quadrakill']:
            exploits = exploits + "\n ** :crown: :four: Ce joueur a quadrakill ** " + str(thisQuadra) + " fois"
            points = points + (1 * int(thisQuadra))

        if float(thisKDA) >= settings['KDA']:
            exploits = exploits + "\n ** :crown: :star: Ce joueur a un bon KDA avec un KDA de " + str(
                thisKDA) + " **"
            points = points + 1

        if str(thisDeaths) == str(settings['Ne_pas_mourir']):
            exploits = exploits + "\n ** :crown: :heart: Ce joueur n'est pas mort de la game ** \n ** :crown: :star: Ce joueur a un PERFECT KDA **"
            points = points + 2

        if int(thisKP) >= settings['KP']:
            exploits = exploits + "\n ** :crown: :dagger: Ce joueur a participé à énormément de kills dans son équipe avec " + str(
                thisKP) + "% **"
            points = points + 1

        if float(thisVisionPerMin) >= settings['Vision/min(support)'] and str(thisPosition) == "SUPPORT":
            exploits = exploits + "\n ** :crown: :eye: Ce joueur a un gros score de vision avec " + str(
                thisVisionPerMin) + " / min **"
            points = points + 1

        if int(thisVisionPerMin) >= settings['Vision/min(autres)'] and str(thisPosition) != "SUPPORT":
            exploits = exploits + "\n ** :crown: :eye: Ce joueur a un gros score de vision avec " + str(
                thisVisionPerMin) + " / min **"
            points = points + 1

        if int(thisMinionPerMin) >= settings['CS/min']:
            exploits = exploits + "\n ** :crown: :ghost: Ce joueur a bien farm avec " + str(
                thisMinionPerMin) + " CS / min **"
            points = points + 1

        if int(thisDamageRatio) >= settings['%_dmg_équipe']:
            exploits = exploits + "\n ** :crown: :dart: Ce joueur a infligé beaucoup de dmg avec " + str(
                thisDamageRatio) + "%  pour son équipe **"
            points = points + 1

        if int(thisDamageTakenRatio) >= settings['%_dmg_tank']:
            exploits = exploits + "\n ** :crown: :shield: Ce joueur a bien tank pour son équipe avec " + str(
                thisDamageTakenRatio) + "% **"
            points = points + 1

        if int(thisSoloKills) >= settings['Solokills']:
            exploits = exploits + "\n ** :crown: :muscle: Ce joueur a réalisé " + str(thisSoloKills) + " solokills **"
            points = points + 1

        if int(thisTotalOnTeammates) >= settings['Total_Heals_sur_alliés']:
            exploits = exploits + "\n ** :crown: :heart: Ce joueur a heal plus de " + str(
                thisTotalOnTeammatesFormat) + " sur ses alliés **"
            points = points + 1

        dict_cumul = {"SOLOKILLS": thisSoloKills, "NBGAMES": 1, "DUREE_GAME": thisTime / 60, "KILLS": thisKills,
                      "DEATHS": thisDeaths, "ASSISTS": thisAssists, "WARDS_SCORE": thisVision,
                      "WARDS_POSEES": thisWards, "WARDS_DETRUITES": thisWardsKilled, "WARDS_PINKS": thisPink,
                      "CS" : thisMinion, "QUADRA" : thisQuadra, "PENTA" : thisPenta}

        for key, value in dict_cumul.items():
            try:
                old_value = int(records_cumul[key][summonerName.lower().replace(" ", "")])
                records_cumul[key][summonerName.lower().replace(" ", "")] = records_cumul[key][
                                                                                summonerName.lower().replace(" ",
                                                                                                             "")] + value
                new_value = int(records_cumul[key][summonerName.lower().replace(" ", "")])
                
                # les paliers
                if succes is True and thisQ == "RANKED" and thisTime > 20:
                    exploits = palier(exploits, key, "WARDS_POSEES", old_value, new_value, np.arange(500, 10000, 500, int).tolist())
                    exploits = palier(exploits, key, "SOLOKILLS", old_value, new_value, np.arange(100, 1000, 100, int).tolist())
                    exploits = palier(exploits, key, "NBGAMES", old_value, new_value, np.arange(50, 1000, 50, int).tolist())
                    exploits = palier(exploits, key, "KILLS", old_value, new_value, np.arange(500, 10000, 500, int).tolist())
                    exploits = palier(exploits, key, "DEATHS", old_value, new_value, np.arange(500, 10000, 500, int).tolist())
                    exploits = palier(exploits, key, "ASSISTS", old_value, new_value, np.arange(500, 10000, 500, int).tolist())
                    exploits = palier(exploits, key, "CS", old_value, new_value, np.arange(10000, 100000, 10000, int).tolist())
                    exploits = palier(exploits, key, "QUADRA", old_value, new_value, np.arange(5, 100, 5, int).tolist())
                    exploits = palier(exploits, key, "PENTA", old_value, new_value, np.arange(5, 100, 5, int).tolist())
                    
                        
                            
            except:
                records_cumul[key][summonerName.lower().replace(" ", "")] = value

        # Achievements
        if thisQ == "RANKED" and thisTime > 20:
            try:
                suivi[summonerName.lower().replace(" ", "")]['Achievements'] = \
                    suivi[summonerName.lower().replace(" ", "")][
                        'Achievements'] + points
            except:
                suivi[summonerName.lower().replace(" ", "")]['Achievements'] = points

            try:
                suivi[summonerName.lower().replace(" ", "")]['games'] = suivi[summonerName.lower().replace(" ", "")][
                                                                            'games'] + 1
            except:
                suivi[summonerName.lower().replace(" ", "")]['games'] = 0

            if succes is True:
                writeData(suivi, 'suivi') #achievements

                writeData(records_cumul, 'records3')  # records3
                # sauvegarde_bdd(records_cumul, 'records3')
                
        # observations

        if thisPosition in ['SUPPORT', 'ADC', 'MID', 'JUNGLE'] and thisQ == "RANKED":
            embed.add_field(
                name="Durée de la game : " + str(int(thisTime)) + " minutes | Score (EXPERIMENTAL) : " + str(result),
                value=exploits)
        else:
            embed.add_field(name="Durée de la game : " + str(int(thisTime)) + " minutes",
                            value=exploits)

        try:
            if int(thisDeaths) >= 1:  # KDA
                embed.add_field(name="KDA : " + str(thisKDA),
                                value=str(thisKills) + " | " + str(thisDeaths) + " | " + str(
                                    thisAssists) + "\n KP : " + str(thisKP) + "%",
                                inline=False)
            else:
                embed.add_field(name="KDA : Perfect KDA",
                                value=str(thisKills) + " | " + str(thisDeaths) + " | " + str(
                                    thisAssists) + "\n KP : " + str(thisKP) + "%",
                                inline=False)
        except Exception:
            embed.add_field(name="KDA : ", value=str(thisKills) + " | " + str(thisDeaths) + " | " + str(thisAssists),
                            inline=False)

        # CS
        embed.add_field(name="CS : " + str(thisMinion), value="minions par minute: " + str(
            thisMinionPerMin),
                        inline=False)
        # Score de vision
        if thisQ != "ARAM":
            embed.add_field(
                name="Score de vision : " + str(thisVision) + " (Vision par minute : " + str(thisVisionPerMin) + " )",
                value="wards posées : " + str(thisWards) + "\n wards détruites : " + str(thisWardsKilled) +
                      "\n pinks achetées: " + str(thisPink), inline=False)
        # Golds
        embed.add_field(name="Golds gagnés : " + str(thisGold), value="golds par minute: " + str(thisGoldPerMinute),
                        inline=False)
        # Dmg
        embed.add_field(name="Dégats infligés : " + str(thisDamage) + " (" + str(thisDamageRatio) + "%)",
                        value="Dégats par minutes : " + str(
                            round(thisDamagePerMinute, 0)) + "\n Double : " + str(thisDouble) + " | Triple : " + str(
                            thisTriple) + " | Quadra : " + str(thisQuadra) + " | Penta : " + str(
                            thisPenta) + "\n SoloKills : " + str(thisSoloKills),
                        inline=False)
        embed.add_field(name="Dégats reçus : " + str(thisDamageTaken) + " (" + str(thisDamageTakenRatio) + "%)",
                        value="Dégats réduits : " + str(
                            thisDamageSelfMitigatedFormat), inline=False)

        # Stats soloq :
        if thisQ == "RANKED" or thisQ == "FLEX":
            if thisWinrate == ' ':
                embed.add_field(name="Current rank", value=rank, inline=False)
            else:
                embed.add_field(name="Current rank : " + thisTier + " " + thisRank + " - " + thisLP + "LP",
                                value="Winrate: " + thisWinrateStat + "%" + "\n Victoires : " + thisVictory +
                                      " | Defaites : " + thisLoose,
                                inline=False)
        embed.add_field(name=f"Team 1 ({thisGold_team1} Golds)",
                        value=str(thisPseudoListe[0]) + " (" + str(thisChampName1) + ") - " + str(
                            thisKillsListe[0]) + "/" + str(
                            thisDeathsListe[0]) + "/" + str(thisAssistsListe[0]) + "\n" +
                              str(thisPseudoListe[1]) + " (" + str(thisChampName2) + ") - " + str(
                            thisKillsListe[1]) + "/" + str(
                            thisDeathsListe[1]) + "/" + str(thisAssistsListe[1]) + "\n" +
                              str(thisPseudoListe[2]) + " (" + str(thisChampName3) + ") - " + str(
                            thisKillsListe[2]) + "/" + str(
                            thisDeathsListe[2]) + "/" + str(thisAssistsListe[2]) + "\n" +
                              str(thisPseudoListe[3]) + " (" + str(thisChampName4) + ") - " + str(
                            thisKillsListe[3]) + "/" + str(
                            thisDeathsListe[3]) + "/" + str(thisAssistsListe[3]) + "\n" +
                              str(thisPseudoListe[4]) + " (" + str(thisChampName5) + ") - " + str(
                            thisKillsListe[4]) + "/" + str(
                            thisDeathsListe[4]) + "/" + str(thisAssistsListe[4]), inline=True)
        embed.add_field(name=f"Team 2 ({thisGold_team2} Golds)",
                        value=str(thisPseudoListe[5]) + " (" + str(thisChampName6) + ") - " + str(
                            thisKillsListe[5]) + "/" + str(
                            thisDeathsListe[5]) + "/" + str(
                            thisAssistsListe[5]) + "\n" +
                              str(thisPseudoListe[6]) + " (" + str(thisChampName7) + ") - " + str(
                            thisKillsListe[6]) + "/" + str(
                            thisDeathsListe[6]) + "/" + str(
                            thisAssistsListe[6]) + "\n" +
                              str(thisPseudoListe[7]) + " (" + str(thisChampName8) + ") - " + str(
                            thisKillsListe[7]) + "/" + str(
                            thisDeathsListe[7]) + "/" + str(
                            thisAssistsListe[7]) + "\n" +
                              str(thisPseudoListe[8]) + " (" + str(thisChampName9) + ") - " + str(
                            thisKillsListe[8]) + "/" + str(
                            thisDeathsListe[8]) + "/" + str(
                            thisAssistsListe[8]) + "\n" +
                              str(thisPseudoListe[9]) + " (" + str(thisChampName10) + ") - " + str(
                            thisKillsListe[9]) + "/" + str(
                            thisDeathsListe[9]) + "/" + str(thisAssistsListe[9]),
                        inline=True)

        embed.set_footer(text=f'Version {main.Var_version} by Tomlora')



        return embed

    @commands.command(brief="Version du jeu")
    async def lolversion(self, ctx):
        await ctx.send(version)

    @commands.command()
    async def datadragon(self, ctx, type, key):
        if type == "champion":
            current_champ_list = lol_watcher.data_dragon.champions(champions_versions, True, 'fr_FR')['data'][key]
            del current_champ_list['lore']
            del current_champ_list['blurb']

            df = pd.DataFrame(current_champ_list).transpose()

            print(df)

        elif type == "item":

            current_items_list = lol_watcher.data_dragon.items(champions_versions, 'fr_FR')['data']
            df = pd.DataFrame(current_items_list).transpose()
            print(df)
        # current_runes_list = lol_watcher.data_dragon.runes(champions_versions, 'fr_FR')['data']
        # print(current_items_list)
        # print(current_runes_list)

        await ctx.send("Fait !")

        # await ctx.send(current_champ_list)

    # ----------------------------- test

    @tasks.loop(minutes=1, count=None)
    async def my_task(self):
        await self.update()
        await self.updaterank()

    @commands.command(brief='Réservé au bot')
    async def updaterank(self):

        id_data = loadData("id_data")
        suivirank = loadData("suivi")

        id_data_keys = id_data.keys()

        for key in id_data_keys:
            me = lol_watcher.summoner.by_name(my_region, key)
            stats = lol_watcher.league.by_summoner(my_region, me['id'])
            try:
                if str(stats[0]['queueType']) == 'RANKED_SOLO_5x5':
                    i = 0
                else:
                    i = 1

                tier = str(stats[i]['tier'])
                rank = str(stats[i]['rank'])
                level = tier + " " + rank

                if str(suivirank[key]['tier']) + " " + str(suivirank[key]['rank']) != level:
                    rank_old = str(suivirank[key]['tier']) + " " + str(suivirank[key]['rank'])
                    suivirank[key]['tier'] = tier
                    suivirank[key]['rank'] = rank
                    try:
                        channel = self.bot.get_channel(int(main.chan_tracklol))
                        if dict_rankid[rank_old] > dict_rankid[level]:  # 19 > 18
                            await channel.send(f' Le joueur {key} a démote du rank {rank_old} à {level}')
                            await channel.send(file=discord.File('./img/notstonks.jpg'))
                        elif dict_rankid[rank_old] < dict_rankid[level]:
                            await channel.send(f' Le joueur {key} a été promu du rank {rank_old} à {level}')
                            await channel.send(file=discord.File('./img/stonks.jpg'))
                        
                        suivirank[key]['tier'] = tier
                        suivirank[key]['rank'] = rank
                    except:
                        print('Channel impossible')
            except:
                suivirank[key] = {
                    'wins': 0,
                    'losses': 0,
                    'LP': 0,
                    'tier': "Non-classe",
                    'rank': '0',
                    'Achievements': 0,
                    'games': 0}
                

        writeData(suivirank, "suivi")

    @cog_ext.cog_slash(name="game",
                       description="Voir les statistiques d'une games",
                       options=[create_option(name="summonername", description= "Nom du joueur", option_type=3, required=True),
                                create_option(name="numerogame", description="Numero de la game, de 0 à 10", option_type=4, required=True),
                                create_option(name="succes", description="Faut-il la compter dans les records/achievements ?", option_type=5, required=True)])
    async def game(self, ctx, summonername:str, numerogame:int, succes: bool):

        embed = self.printInfo(summonerName=summonername, idgames=int(numerogame), succes=succes)

        if embed != {}:
            await ctx.send(embed=embed)
               

    async def printLive(self, summonerName):
        channel = self.bot.get_channel(int(main.chan_tracklol))

        embed = self.printInfo(summonerName=summonerName, idgames=0, succes=True)
        
        if embed != {}:
            await channel.send(embed=embed)


    async def update(self):
        data = loadData('id_data')
        # print('Verification LoL en cours...')
        for key, value in data.items():
            if str(value) != getId(
                    key):  # value -> ID de dernière game enregistrée dans id_data != ID de la dernière game via l'API Rito / #key = pseudo // value = numéro de la game
                try:
                    await self.printLive(key)
                except:
                    print(f"Message non envoyé car le joueur {key} a fait une partie avec moins de 10 joueurs ou un mode désactivé")
                data[key] = getId(key)

        writeData(data, 'id_data')

    @cog_ext.cog_slash(name="loladd",description="Ajoute le joueur au suivi",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    async def loladd(self, ctx, *, summonername):
        try:
            data = loadData('id_data')
            data[summonername.lower().replace(" ", "")] = getId(
                summonername)  # ajout du pseudo (clé) et de l'id de la dernière game(getId)
            writeData(data, 'id_data')

            await ctx.send(summonername + " was successfully added to live-feed!")
        except:
            await ctx.send("Oops! There is no summoner with that name!")

    @cog_ext.cog_slash(name="lolremove", description="Supprime le joueur du suivi",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    async def lolremove(self, ctx, *, summonername):
        data = loadData('id_data')
        if summonername.lower().replace(" ", "") in data: del data[summonername.lower().replace(" ",
                                                                                                "")]  # si le pseudo est présent dans la data, on supprime la data de ce pseudo
        writeData(data, 'id_data')

        await ctx.send(summonername + " was successfully removed from live-feed!")

    @cog_ext.cog_slash(name='lollist', description='Affiche la liste des joueurs suivis')
    async def lollist(self, ctx):

        response = ""

        for key, value in loadData('id_data').items():
            response += key.upper() + ", "

        response = response[:-2]
        embed = discord.Embed(title="Live feed list", description=response, colour=discord.Colour.blurple())

        await ctx.send(embed=embed)

    @cog_ext.cog_slash(name="debug_getId",description="Réservé au propriétaire du bot",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    @main.isOwner2_slash()
    async def debug_getId(self, ctx, *, summonerName):
        me = lol_watcher.summoner.by_name(my_region, summonerName)
        my_matches = lol_watcher.match.matchlist_by_puuid(region, me['puuid'])
        last_match = my_matches[0]
        match_detail = lol_watcher.match.by_id(region, last_match)
        await ctx.send(last_match)
        # await ctx.send(match_detail['info']['gameId'])

        


    @tasks.loop(hours=1, count=None)
    async def lolsuivi(self):

        currentHour = str(datetime.datetime.now().hour)

        if currentHour == str(0):

            suivi2 = loadData('suivi')
            suivi_24h = loadData('suivi_24h')

            df = pd.DataFrame.from_dict(suivi2)
            df = df.transpose().reset_index()
            
            df_24h = pd.DataFrame.from_dict(suivi_24h)
            df_24h = df_24h.transpose().reset_index()

            channel = self.bot.get_channel(int(main.chan_lol))
            
            df = df[df['tier'] != 'Non-classe'] # on supprime les non-classés
            df_24h = df_24h[df_24h['tier'] != 'Non-classe'] # on supprime les non-classés

            df['tier_pts'] = 0
            df['tier_pts'] = np.where(df.tier == 'BRONZE', 1, df.tier_pts)
            df['tier_pts'] = np.where(df.tier == 'SILVER', 2, df.tier_pts)
            df['tier_pts'] = np.where(df.tier == 'GOLD', 3, df.tier_pts)
            df['tier_pts'] = np.where(df.tier == 'PLATINUM', 4, df.tier_pts)
            df['tier_pts'] = np.where(df.tier == 'DIAMOND', 5, df.tier_pts)

            df['rank_pts'] = 0
            df['rank_pts'] = np.where(df['rank'] == 'IV', 1, df.rank_pts)
            df['rank_pts'] = np.where(df['rank'] == 'III', 2, df.rank_pts)
            df['rank_pts'] = np.where(df['rank'] == 'II', 3, df.rank_pts)
            df['rank_pts'] = np.where(df['rank'] == 'I', 4, df.rank_pts)
            
            df_24h['tier_pts'] = 0
            df_24h['tier_pts'] = np.where(df_24h.tier == 'BRONZE', 1, df_24h.tier_pts)
            df_24h['tier_pts'] = np.where(df_24h.tier == 'SILVER', 2, df_24h.tier_pts)
            df_24h['tier_pts'] = np.where(df_24h.tier == 'GOLD', 3, df_24h.tier_pts)
            df_24h['tier_pts'] = np.where(df_24h.tier == 'PLATINUM', 4, df_24h.tier_pts)
            df_24h['tier_pts'] = np.where(df_24h.tier == 'DIAMOND', 5, df_24h.tier_pts)

            df_24h['rank_pts'] = 0
            df_24h['rank_pts'] = np.where(df_24h['rank'] == 'IV', 1, df_24h.rank_pts)
            df_24h['rank_pts'] = np.where(df_24h['rank'] == 'III', 2, df_24h.rank_pts)
            df_24h['rank_pts'] = np.where(df_24h['rank'] == 'II', 3, df_24h.rank_pts)
            df_24h['rank_pts'] = np.where(df_24h['rank'] == 'I', 4, df_24h.rank_pts)

            df.sort_values(by=['tier_pts', 'rank_pts', 'LP'], ascending=[False, False, False], inplace=True)

            joueur = df['index'].to_dict()
            joueur_24h = df_24h['index'].to_dict()

            embed = discord.Embed(title="Suivi LOL", description='Periode : 24h', colour=discord.Colour.blurple())
            totalwin = 0
            totaldef = 0
            totalgames = 0

            for id, key in joueur.items():
                pseudo = lol_watcher.summoner.by_name(my_region, key)
                stats = lol_watcher.league.by_summoner(my_region, pseudo['id'])

                suivi = loadData('suivi')
                suivi_24h = loadData('suivi_24h')

                if len(stats) > 0:
                    try:
                        # suivi est mis à jour par updaterank. On va donc prendre l'autre qui n'est affecté que par lolsuivi
                        wins = int(suivi[key]['wins'])
                        losses = int(suivi[key]['losses'])
                        nbgames = wins + losses
                        LP = int(suivi[key]['LP'])
                        tier_old = str(suivi_24h[key]['tier'])
                        rank_old = str(suivi_24h[key]['rank'])
                        classement_old = tier_old + " " + rank_old
                    except:
                        wins = 0
                        losses = 0
                        nbgames = 0
                        LP = 0

                    # on veut les stats soloq

                    if str(stats[0]['queueType']) == "RANKED_SOLO_5x5":
                        i = 0
                    else:
                        i = 1

                    tier = str(stats[i]['tier'])
                    rank = str(stats[i]['rank'])
                    classement_new = tier + " " + rank

                    suivi[key]['wins'] = int(stats[i]['wins'])
                    suivi[key]['losses'] = int(stats[i]['losses'])
                    suivi[key]['LP'] = int(stats[i]['leaguePoints'])
                    suivi[key]['tier'] = str(stats[i]['tier'])
                    suivi[key]['rank'] = str(stats[i]['rank'])

                    difwins = suivi[key]['wins'] - wins
                    diflosses = suivi[key]['losses'] - losses
                    difLP = suivi[key]['LP'] - LP
                    totalwin = totalwin + difwins
                    totaldef = totaldef + diflosses
                    totalgames = totalwin + totaldef
                    
                
                    # evolution

                    if dict_rankid[classement_old] > dict_rankid[classement_new]: # 19-18
                        difLP = 100 + LP - suivi[key]['LP']
                        difLP = "Démote / -" + str(difLP)
                        emote = ":arrow_down:"

                    elif dict_rankid[classement_old] < dict_rankid[classement_new]:
                        difLP = 100 - LP + suivi[key]['LP']
                        difLP = "Promotion / +" + str(difLP)
                        emote = ":arrow_up:"
                        
                    elif dict_rankid[classement_old] == dict_rankid[classement_new]:
                        if difLP > 0:
                            emote = ":arrow_up:"
                        elif difLP < 0:
                            emote = ":arrow_down:"
                        elif difLP == 0:
                            emote = ":arrow_right:"

                    embed.add_field(name=str(key) + " ( " + tier + " " + rank + " )",
                                    value="V : " + str(suivi[key]['wins']) + "(" + str(difwins) + ") | D : "
                                          + str(suivi[key]['losses']) + "(" + str(diflosses) + ") | LP :  "
                                          + str(suivi[key]['LP']) + "(" + str(difLP) + ")    " + emote, inline=False)
                    embed.set_footer(text=f'Version {main.Var_version} by Tomlora')

                    writeData(suivi, 'suivi')
                    writeData(suivi, 'suivi_24h')

                else:
                    suivi[key]["tier"] = "Non-classé"

                    writeData(suivi, 'suivi')
                    writeData(suivi, 'suivi_24h')

            # print(data)
            await channel.send(embed=embed)
            await channel.send(f'Sur {totalgames} games -> {totalwin} victoires et {totaldef} défaites')
            
                      
    # @commands.command()
    # @main.isOwner2()
    # async def reset_solokills(self, ctx):
    #     records3 = loadData('records3')
        
    #     for key in records3['QUADRA'].keys():
    #         records3['QUADRA'][key] = 0
    #         records3['PENTA'][key] = 0
        
    #     writeData(records3, 'records3')
        
    #     await ctx.send('Reset')        



    # @commands.command()
    # @main.isOwner2()
    # async def add_solokills(self, ctx):
    #     records_cumul = loadData('records3')
    #     for summonerName in records_cumul['NBGAMES'].keys():
    #         if summonerName in ['Kazsc', 'Personne', 'ylarabka', 'kulbutoké', 'tomlora', 'chatobogan', 'exorblue']:
    #         #if summonerName in ['Kazsc', 'Personne']:
    #             pass
    #         else:
    #             games = records_cumul['NBGAMES'][summonerName.lower().replace(" ", "")]
    #             games = int(games)
    #             i = 0
                
    #             while i != games:
    #                 last_match, match_detail_stats, me = match_by_puuid(summonerName, i)
                    
    #                 match_detail = pd.DataFrame(match_detail_stats)

    #                 dic = {
    #                     (match_detail['info']['participants'][0]['summonerName']).lower().replace(" ", ""): 0,
    #                     (match_detail['info']['participants'][1]['summonerName']).lower().replace(" ", ""): 1,
    #                     (match_detail['info']['participants'][2]['summonerName']).lower().replace(" ", ""): 2,
    #                     (match_detail['info']['participants'][3]['summonerName']).lower().replace(" ", ""): 3,
    #                     (match_detail['info']['participants'][4]['summonerName']).lower().replace(" ", ""): 4,
    #                     (match_detail['info']['participants'][5]['summonerName']).lower().replace(" ", ""): 5,
    #                     (match_detail['info']['participants'][6]['summonerName']).lower().replace(" ", ""): 6,
    #                     (match_detail['info']['participants'][7]['summonerName']).lower().replace(" ", ""): 7,
    #                     (match_detail['info']['participants'][8]['summonerName']).lower().replace(" ", ""): 8,
    #                     (match_detail['info']['participants'][9]['summonerName']).lower().replace(" ", ""): 9
    #                 }
                    

    #                 # stats
    #                 thisId = dic[
    #                     summonerName.lower().replace(" ", "")]  # cherche le pseudo dans le dico et renvoie le nombre entre 0 et 9
                    
    #                 thisTime = round((int(match_detail['info']['gameDuration']) / 60), 2)
    #                 thisQId = match_detail['info']['queueId']
    #                 ThisQ = ' '
                    
    #                 if thisQId == 420:
    #                     thisQ = "RANKED"
    #                 elif thisQId == 400:
    #                     thisQ = "NORMAL"
    #                 elif thisQId == 440:
    #                     thisQ = "FLEX"
    #                 elif thisQId == 450:
    #                     thisQ = "ARAM"
    #                 else:
    #                     thisQ = "OTHER"
                        
                    
    #                 thisSoloKills = match_detail['info']['participants'][thisId]['challenges']['soloKills']
    #                 thisQuadra = match_detail['info']['participants'][thisId]['quadraKills']
    #                 thisPenta = match_detail['info']['participants'][thisId]['pentaKills']
                    

                    
                        
    #                 i = i + 1
    #                 if thisQ == "RANKED" and thisTime > 20:
    #                     try:
    #                         records_cumul['PENTA'][summonerName.lower().replace(" ", "")] = records_cumul['PENTA'][
    #                                                                                                 summonerName.lower().replace(" ",
    #                                                                                                                             "")] + int(thisPenta)
    #                     except:
    #                         records_cumul['PENTA'][summonerName.lower().replace(" ", "")] = int(thisPenta)                       
                            
                        
    #                     cumul = records_cumul['PENTA'][summonerName.lower().replace(" ", "")]
    #                     writeData(records_cumul, 'records3')
    #                     await ctx.send(f'{summonerName} : \n {i} / {games} games \n {str(thisPenta)} ajoutés. \n {cumul} au total')
    #                 else:
    #                     games = games + 1
    #                     await ctx.send(f'{summonerName} : \n {i} / {games} \n Non ajouté. Ne remplit pas les conditions. \n On ajoute une game au process')
                        
    #                 time.sleep(3)
        
        

    @commands.command()
    @main.isOwner2()
    async def spectator(self, ctx, *, summonerName):
        match = match_spectator(summonerName)
        print(match['participants'])
        await ctx.send('Fait !')     
        
    @cog_ext.cog_slash(name="abbedagge", description="Meilleur joueur de LoL")
    async def abbedagge(self, ctx):
        await ctx.send('https://clips.twitch.tv/ShakingCovertAuberginePanicVis-YDRK3JFk7Glm6nbB')
        
    @commands.command()
    async def askrank(self, ctx, *, rank:str):
        idrank = dict_rankid[rank]
        await ctx.send(idrank)
        rank_split = rank.split()
        tier = rank_split[0]
        await ctx.send(file=discord.File(f'./img/{tier}.png'))


def setup(bot):
    bot.add_cog(LeagueofLegends(bot))
