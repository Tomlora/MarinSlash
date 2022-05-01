from discord.ext import commands, tasks
import discord
from matplotlib import pyplot as plt

from riotwatcher import LolWatcher
import pandas as pd
import pickle
import main
import datetime
import calendar
import asyncio
import numpy as np
from sklearn import linear_model
from sklearn.model_selection import train_test_split

import os
import plotly.express as px

api_key_lol = os.environ.get('API_LOL')  # https://www.youtube.com/watch?v=IolxqkL7cD8

lol_watcher = LolWatcher(api_key_lol)
my_region = 'euw1'
region = "EUROPE"

# Paramètres LoL
version = lol_watcher.data_dragon.versions_for_region(my_region)
champions_versions = version['n']['champion']


# print(lol_watcher.summoner.by_name(my_region, 'Tomlora'))


# print(version)
# print(champions_versions)


def records_check(fichier, key_boucle, key: str, Score_check: float, thisChampName, summonerName, channel):
    if str(key_boucle) == str(key):
        # print(key)
        # print(float(fichier[key]['Score']))
        # print(Score_check)
        # print(float(fichier[key]['Score']) < Score_check)
        if float(fichier[key]['Score']) < Score_check:
            fichier[key]['Score'] = Score_check
            fichier[key]['Champion'] = str(thisChampName)
            fichier[key]['Joueur'] = summonerName

    return fichier


def reset_records_help(key: str, fichier: int):
    if fichier == 1:
        name = 'records'
    elif fichier == 2:
        name = 'records2'

    with open('obj/' + name + '.pkl', 'rb') as f:
        fichier = pickle.load(f)
        fichier[key] = {
            "Score": 0,
            "Champion": "Ezreal",
            "Joueur": "Tomlora"
        }

    with open('obj/' + name + '.pkl', 'wb+') as f:
        pickle.dump(fichier, f, protocol=0)


def loadData(name):
    try:
        with open('obj/' + name + '.pkl', 'rb') as f:
            fichier = pickle.load(f)
        return fichier
    except Exception:
        return {}


def writeData(data, name):
    with open('obj/' + name + '.pkl', 'wb+') as f:
        pickle.dump(data, f, protocol=0)


def unifier_joueur(df, colonne):


    df[colonne] = df[colonne].replace('nukethestars', 'state')
    df[colonne] = df[colonne].replace('linò', 'state')

    return df

def match_by_puuid(summonerName, idgames:int):
    me = lol_watcher.summoner.by_name(my_region, summonerName)
    my_matches = lol_watcher.match.matchlist_by_puuid(region, me['puuid'])
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

def dict_data(thisId:int, match_detail, info):
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

    return

# def ajouter_game(df, pseudo, kills, deaths, assists, kp, wardsplaced, wardskilled, pink, cs, csm, score:0):
#     df=df.append({'Pseudo' : pseudo , 'Kills' : kills, 'Deaths' : deaths
#                  , 'Assists' : assists, 'KP': kp,  'WardsPlaced' : wardsplaced, 'WardsKilled' : wardskilled
#                  , 'Pink' : pink, 'cs' : cs, 'csm' : csm, 'Score' : score} , ignore_index=True)
#     return df
#
#
# def scoring(pseudo, kills, deaths, assists, kp, wardsplaced, wardskilled, pink, cs, csm):
#
#     dict = loadData('scoring_support')
#     df = pd.DataFrame.from_dict(dict)
#     df[['Kills', 'Deaths', 'Assists', 'WardsPlaced', 'WardsKilled', 'Pink', 'cs']] = df[
#         ['Kills', 'Deaths', 'Assists', 'WardsPlaced', 'WardsKilled', 'Pink', 'cs']].astype(int)
#     df[['KP', 'csm', 'Score']] = df[['KP', 'csm', 'Score']].astype(float)
#
#     variables = ['Kills', 'Deaths', 'Assists', 'KP', 'WardsPlaced', 'WardsKilled', 'Pink', 'cs', 'csm']
#
#     x_data = df[variables]
#     y = df['Score']
#
#     x_train, x_test, y_train, y_test = train_test_split(x_data.values, y, test_size=0.33, random_state=42)
#
#     reg = linear_model.LinearRegression()
#     reg.fit(x_train, y_train)
#
#     df_predict = pd.DataFrame(
#         columns=['Pseudo', 'Kills', 'Deaths', 'Assists', 'KP', 'WardsPlaced', 'WardsKilled', 'Pink', 'cs', 'csm',
#                  'Score'])
#     df_predict = ajouter_game(df_predict, pseudo, kills, deaths, assists, kp, wardsplaced, wardskilled, pink, cs, csm, 0)
#
#     predict = round(reg.predict(df_predict[variables].values)[0], 2)
#
#     print(predict)
#
#     return predict





class LeagueofLegends(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.my_task.start()
        self.reminder.start()

    @commands.command(brief="Version du jeu")
    async def lolversion(self, ctx):
        await ctx.send(version)


    @commands.command()
    async def datadragon(self,ctx, type, key):
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
                        await channel.send(f' Le joueur {key} est passé du rank {rank_old} à {level}')
                        suivirank[key]['tier'] = tier
                        suivirank[key]['rank'] = rank
                    except:
                        print('Channel impossible')
            except:
                del suivirank[key]
                suivirank[key] = {
                    'wins': 0,
                    'losses': 0,
                    'LP': 0,
                    'tier': "Non-classe",
                    'rank': '0',
                    'Achievements': 0,
                    'games': 0}

        writeData(suivirank, "suivi")


    @commands.command(brief="Permet d'avoir ses stats sur la dernière game")
    async def game(self, ctx, summonerName, numerogame, succes: bool):

        embed, chart = self.printInfo(summonerName=summonerName, idgames=int(numerogame), succes=succes)
        chart.write_image('screenshot.png')

        await ctx.send(embed=embed)
        # await ctx.send(file=discord.File('screenshot.png'))

        os.remove('screenshot.png')

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
        thisMinion = match_detail['info']['participants'][thisId]['totalMinionsKilled']
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
        thisCSafter10min = match_detail['info']['participants'][thisId]['challenges']['laneMinionsFirst10Minutes']
        thisKillingSprees = match_detail['info']['participants'][thisId]['killingSprees']
        thisDamageSelfMitigated = match_detail['info']['participants'][thisId]['damageSelfMitigated']
        thisDamageTurrets = match_detail['info']['participants'][thisId]['damageDealtToTurrets']
        thisGoldEarned = match_detail['info']['participants'][thisId]['goldEarned']
        thisKillsSeries = match_detail['info']['participants'][thisId]['largestKillingSpree']
        thisTotalHealed = match_detail['info']['participants'][thisId]['totalHeal']
        thisTotalOnTeammates = match_detail['info']['participants'][thisId]['totalHealsOnTeammates']
        thisAcesBefore15min = match_detail['info']['participants'][thisId]['challenges']['acesBefore15Minutes']

        # format
        # src : https://www.w3schools.com/python/ref_string_format.asp

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


        thisDamageListe = dict_data(thisId, match_detail,'totalDamageDealtToChampions')

        thisTeamDamage = thisDamageListe[0] + thisDamageListe[1] + thisDamageListe[2] + thisDamageListe[3] + thisDamageListe[4]

        # pseudo

        thisPseudoListe = dict_data(thisId, match_detail, 'summonerName')


        #champ id

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

        # deaths

        thisDeathsListe = dict_data(thisId, match_detail, 'deaths')

        # assists

        thisAssistsListe = dict_data(thisId, match_detail, 'assists')

        # gold

        thisGoldListe = dict_data(thisId, match_detail, 'goldEarned')


        thisTeamKills = thisKillsListe[0] + thisKillsListe[1] + thisKillsListe[2] + thisKillsListe[3] + thisKillsListe[4]


        try:
            thisKP = int(round((thisKills + thisAssists) / (thisTeamKills), 2) * 100)
        except:
            thisKP = 0

        # thisDamageRatio = round((float(thisDamage) / float(thisTeamDamage)) * 100, 2)
        thisDamageRatio = round(
            (match_detail['info']['participants'][thisId]['challenges']['teamDamagePercentage']) * 100, 2)
        thisDamageTakenRatio = round(
            (match_detail['info']['participants'][thisId]['challenges']['damageTakenOnTeamPercentage']) * 100, 2)



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
        except IndexError:
            print("no ranked stats available for " + str(summonerName))

        # name3 = 'suivi'

        if thisQ == "RANKED" and thisTime > 20:

            records = loadData('records')

            suivi = loadData('suivi')

            for key, value in records.items():
                if int(thisDeaths) >= 1:

                    records = records_check(records, key, 'KDA',
                                            float(thisKDA),
                                            thisChampName, summonerName, channel)
                else:
                    records = records_check(records, key, 'KDA',
                                            float(
                                                round((int(thisKills) + int(thisAssists)) / (int(thisDeaths) + 1), 2)),
                                            thisChampName, summonerName, channel)

                records = records_check(records, key, 'KP', thisKP,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'CS', thisMinion,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'CS/MIN', thisMinionPerMin,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'KILLS', thisKills,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'DEATHS', thisDeaths,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'ASSISTS', thisAssists,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'WARDS_SCORE', thisVision,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'WARDS_POSEES', thisWards,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'WARDS_DETRUITES', thisWardsKilled,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'WARDS_PINKS', thisPink,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'DEGATS_INFLIGES',
                                        match_detail['info']['participants'][thisId]['totalDamageDealtToChampions'],
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, '% DMG', thisDamageRatio,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'DOUBLE', thisDouble,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'TRIPLE', thisTriple,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'QUADRA', thisQuadra,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'PENTA', thisPenta,
                                        thisChampName, summonerName, channel)
                records = records_check(records, key, 'DUREE_GAME', thisTime,
                                        thisChampName, summonerName, channel)

                records2 = loadData('records2')

                for key, value in records2.items():
                    if thisChampName != "Zeri":
                        records2 = records_check(records2, key, 'SPELLS_USED',
                                                 thisSpellUsed,
                                                 thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'BUFFS_VOLEES', thisbuffsVolees,
                                             thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'SPELLS_EVITES', thisSpellsDodged,
                                             thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'MULTIKILL_1_SPELL', thisMultiKillOneSpell,
                                             thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'SOLOKILLS', thisSoloKills,
                                             thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'CS_APRES_10_MIN', thisCSafter10min,
                                             thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'NB_SERIES_DE_KILLS', thisKillingSprees,
                                             thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'DOMMAGES_TANK',
                                             int(match_detail['info']['participants'][thisId]['totalDamageTaken']),
                                             thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'DOMMAGES_TANK%', thisDamageTakenRatio,
                                             thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'DOMMAGES_REDUITS', thisDamageSelfMitigated,
                                             thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'DOMMAGES_TOWER', thisDamageTurrets,
                                             thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'GOLDS_GAGNES', thisGoldEarned,
                                             thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'SERIES_DE_KILLS', thisKillsSeries,
                                             thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'TOTAL_HEALS',
                                             thisTotalHealed,
                                             thisChampName, summonerName, channel)
                    records2 = records_check(records2, key, 'HEALS_SUR_ALLIES', thisTotalOnTeammates,
                                             thisChampName, summonerName, channel)

                    # await channel.send(f'Le joueur {summonerName} détient désormais le record de {key} avec un score de {float(round((int(thisKills) + int(thisAssists)) / int(thisDeaths), 2))} sur {thisChamp}')

                    writeData(records, 'records')
                    writeData(records2, 'records2')

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

            # if thisPosition == "SUPPORT":
            #     score = scoring(summonerName, thisKills, thisDeaths, thisAssists, thisKP, thisWards, thisWardsKilled, thisPink, thisMinion, thisMinionPerMin)
            # else:
            #     score = 0

        # print(score)

        # annonce
        points = 0
        exploits = "Observations :"

        settings = loadData("achievements_settings")


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
            exploits = exploits + "\n ** :crown: :heart: Ce joueur n'est pas mort de la game **"
            points = points + 1

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
            exploits = exploits + "\n ** :crown: :heart: Ce joueur a heal plus de " + str(thisTotalOnTeammatesFormat) + " sur ses alliés **"
            points = points + 1

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
                writeData(suivi, 'suivi')

        # if thisPosition == "SUPPORT":
        #     embed.add_field(name="Durée de la game : " + str(int(thisTime)) + " minutes | Score (EXPERIMENTAL) : " + str(score),
        #                     value=exploits)
        # else:
        #     embed.add_field(name="Durée de la game : " + str(int(thisTime)) + " minutes",
        #                     value=exploits)
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
                            thisTriple) + " | Quadra : " + str(thisQuadra) + " | Penta : " + str(thisPenta) + "\n SoloKills : " + str(thisSoloKills),
                        inline=False)
        embed.add_field(name="Dégats reçus : " + str(thisDamageTaken) + " (" + str(thisDamageTakenRatio) + "%)", value="Dégats réduits : " + str(
            thisDamageSelfMitigatedFormat), inline=False)

        # Stats soloq :
        if thisQ == "RANKED" or thisQ == "FLEX":
            if thisWinrate == ' ':
                embed.add_field(name="Current rank", value="no ranked data available", inline=False)
            else:
                embed.add_field(name="Current rank : " + thisTier + " " + thisRank + " - " + thisLP + "LP",
                                value="Winrate: " + thisWinrateStat + "%" + "\n Victoires : " + str(
                                    int(thisStats[0]['wins'])) +
                                      " | Defaites : " + str(int(thisStats[0]['losses'])),
                                inline=False)
        embed.add_field(name="Team 1",
                        value=str(thisPseudoListe[0]) + " (" + str(thisChampName1) + ") - " + str(thisKillsListe[0]) + "/" + str(
                            thisDeathsListe[0]) + "/" + str(thisAssistsListe[0]) + "\n" +
                              str(thisPseudoListe[1]) + " (" + str(thisChampName2) + ") - " + str(thisKillsListe[1]) + "/" + str(
                            thisDeathsListe[1]) + "/" + str(thisAssistsListe[1]) + "\n" +
                              str(thisPseudoListe[2]) + " (" + str(thisChampName3) + ") - " + str(thisKillsListe[2]) + "/" + str(
                            thisDeathsListe[2]) + "/" + str(thisAssistsListe[2]) + "\n" +
                              str(thisPseudoListe[3]) + " (" + str(thisChampName4) + ") - " + str(thisKillsListe[3]) + "/" + str(
                            thisDeathsListe[3]) + "/" + str(thisAssistsListe[3]) + "\n" +
                              str(thisPseudoListe[4]) + " (" + str(thisChampName5) + ") - " + str(thisKillsListe[4]) + "/" + str(
                            thisDeathsListe[4]) + "/" + str(thisAssistsListe[4]), inline=True)
        embed.add_field(name="Team 2",
                        value=str(thisPseudoListe[5]) + " (" + str(thisChampName6) + ") - " + str(thisKillsListe[5]) + "/" + str(
                            thisDeathsListe[5]) + "/" + str(
                            thisAssistsListe[5]) + "\n" +
                              str(thisPseudoListe[6]) + " (" + str(thisChampName7) + ") - " + str(thisKillsListe[6]) + "/" + str(
                            thisDeathsListe[6]) + "/" + str(
                            thisAssistsListe[6]) + "\n" +
                              str(thisPseudoListe[7]) + " (" + str(thisChampName8) + ") - " + str(thisKillsListe[7]) + "/" + str(
                            thisDeathsListe[7]) + "/" + str(
                            thisAssistsListe[7]) + "\n" +
                              str(thisPseudoListe[8]) + " (" + str(thisChampName9) + ") - " + str(thisKillsListe[8]) + "/" + str(
                            thisDeathsListe[8]) + "/" + str(
                            thisAssistsListe[8]) + "\n" +
                              str(thisPseudoListe[9]) + " (" + str(thisChampName10) + ") - " + str(thisKillsListe[9]) + "/" + str(
                            thisDeathsListe[9]) + "/" + str(thisAssistsListe[9]),
                        inline=True)

        embed.set_footer(text=f'Version {main.Var_version} by Tomlora')

        # embed gold


        df = pd.DataFrame({'pseudo': thisPseudoListe, 'gold': thisGoldListe})

        chart = px.bar(df, x='pseudo', y='gold', color='pseudo', title='Gold', text_auto='.2s').update_xaxes(
            categoryorder='total ascending')

        chart.update_layout(coloraxis_showscale=False, showlegend=False)

        return embed, chart

    # info.gameId
    def getId(self, summonerName):
        try:
            last_match, match_detail, me = match_by_puuid(summonerName, 0)

            return str(match_detail['info']['gameId'])
        except:
            print(f'getId Erreur avec {summonerName}')
            data = loadData('id_data')
            return str(data[summonerName])

    async def printLive(self, summonerName):
        channel = self.bot.get_channel(int(main.chan_tracklol))

        embed, chart = self.printInfo(summonerName=summonerName, idgames=0, succes=True)
        chart.write_image('screenshot.png')

        await channel.send(embed=embed)
        # await channel.send(file=discord.File('screenshot.png'))

        os.remove('screenshot.png')

    async def update(self):
        data = loadData('id_data')
        # print('Verification LoL en cours...')
        for key, value in data.items():
            if str(value) != self.getId(
                    key):  # value -> ID de dernière game enregistrée dans id_data != ID de la dernière game via l'API Rito / #key = pseudo // value = numéro de la game
                try:
                    await self.printLive(key)
                except:
                    print(f"Message non envoyé car le joueur {key} a fait une partie avec moins de 10 joueurs")
                data[key] = self.getId(key)

        writeData(data, 'id_data')

    @game.error
    async def game_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                'Un argument est manquant pour valider la commande \n [joueur] [numeroGame] [succes=True/False] ')

    @commands.command(brief="Permet d'être ajouté au suivi")
    async def loladd(self, ctx, *, summonerName):
        try:
            data = loadData('id_data')
            data[summonerName.lower().replace(" ", "")] = self.getId(
                summonerName)  # ajout du pseudo (clé) et de l'id de la dernière game(getId)
            writeData(data, 'id_data')

            await ctx.send(summonerName + " was successfully added to live-feed!")
        except:
            await ctx.send("Oops! There is no summoner with that name!")

    @commands.command(brief="Permet de se retirer du suivi")
    async def lolremove(self, ctx, *, summonerName):
        data = loadData('id_data')
        if summonerName.lower().replace(" ", "") in data: del data[summonerName.lower().replace(" ",
                                                                                                "")]  # si le pseudo est présent dans la data, on supprime la data de ce pseudo
        writeData(data, 'id_data')

        await ctx.send(summonerName + " was successfully removed from live-feed!")

    @commands.command(brief="Affiche la liste des joueurs suivis")
    async def lollist(self, ctx):

        response = ""

        for key, value in loadData('id_data').items():
            response += key.upper() + ", "

        response = response[:-2]
        embed = discord.Embed(title="Live feed list", description=response, colour=discord.Colour.blurple())

        await ctx.send(embed=embed)

    @commands.command(brief="Réservé au propriétaire du bot")
    @main.isOwner2()
    async def debug_getId(self, ctx, *, summonerName):
        me = lol_watcher.summoner.by_name(my_region, summonerName)
        my_matches = lol_watcher.match.matchlist_by_puuid(region, me['puuid'])
        last_match = my_matches[0]
        match_detail = lol_watcher.match.by_id(region, last_match)
        await ctx.send(last_match)
        # await ctx.send(match_detail['info']['gameId'])

        # ------------------------------------------------- Alarm

    roleLEC = "<@&956612773868077106>"
    roleLFL = "<@&956613314731991100>"
    roleLCS = "<@&956613191956324384>"
    messageLFL = "La LFL va commencer sur OTP ! " + roleLFL + "\n https://www.twitch.tv/otplol_"
    messageEUM = "Les EUM vont commencer sur OTP ! " + roleLFL + "\n https://www.twitch.tv/otplol_"
    messageLCS = "Les LCS vont commencer sur LCS ! " + roleLCS + "\n https://www.twitch.tv/lcs"
    messageLEC = "La LEC va commencer sur OTP/LEC ! " + roleLEC + "\n https://www.twitch.tv/lec  \n https://www.twitch.tv/otplol_"

    def findDay(self, date):
        born = datetime.datetime.strptime(date, '%d %m %Y').weekday()
        return calendar.day_name[born]

    def alarm(self, h, m, message):
        currentHour = str(datetime.datetime.now().hour)
        currentMinute = str(datetime.datetime.now().minute)
        if currentHour == str(h) and currentMinute == str(m):
            channel = self.bot.get_channel(main.chan_lol)
            return channel.send(message)
        else:
            return False

    @tasks.loop(minutes=1, count=None)
    async def reminder(self):

        currentHour = str(datetime.datetime.now().hour)
        currentMonth = str(datetime.datetime.now().month)
        currentYear = str(datetime.datetime.now().year)
        currentDay = str(datetime.datetime.now().day)
        currentJour = str(self.findDay(str(currentDay + ' ' + currentMonth + " " + currentYear)))

        if self.bot.get_channel(main.chan_lol):
            if currentJour == 'Saturday' and currentHour == str(22):
                try:
                    await self.alarm(22, 25, self.messageLCS)
                except:
                    return False
            elif currentJour == 'Sunday' and currentHour == str(16):
                try:
                    await self.alarm(16, 55, self.messageLEC)
                except:
                    return False
            elif currentJour == 'Sunday' and currentHour == str(21):
                try:
                    await self.alarm(21, 25, self.messageLCS)
                except:
                    return False

    @commands.command(brief="Permet d'être ping pour les alarmes",
                      description='Rang disponible : LEC/Main Kayn/LCS/LFL')
    async def alarm_lol(self, ctx, *, competition: str):

        liste = ['LEC', 'Main Kayn', 'LCS', 'LFL']
        user = ctx.message.author
        role = discord.utils.get(ctx.message.guild.roles, name=competition)
        if competition in liste:
            if role in user.roles:
                await user.remove_roles(role)
                await ctx.send(f' Le rang {role} a été retiré !')
            else:
                await user.add_roles(role)
                await ctx.send(f'Le rang {role} a été ajouté !')
        else:
            await ctx.send(f"Le rôle {competition} n'existe pas ou tu n'as pas les droits nécessaires")

    @alarm_lol.error
    async def info_error_alarm(self, ctx, error):
        if isinstance(error, commands.CommandError):
            await ctx.send(f"La competition n'a pas ete precisée : Tu as le choix entre LEC / LFL / LCS / Main Kayn")

    @commands.command(brief='Réservé au propriétaire du bot',
                      description='Compare entre deux commandes le nombre de victoires/défaites/LP')
    @main.isOwner2()
    async def lolsuivi(self, ctx):

        suivi2 = loadData('suivi')

        df = pd.DataFrame.from_dict(suivi2)
        df = df.transpose().reset_index()

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

        df.sort_values(by=['tier_pts', 'rank_pts', 'LP'], ascending=[False, False, False], inplace=True)

        joueur = df['index'].to_dict()

        embed = discord.Embed(title="Suivi LOL", description='Periode : 24h', colour=discord.Colour.blurple())
        totalwin = 0
        totaldef = 0
        totalgames = 0

        for id, key in joueur.items():
            pseudo = lol_watcher.summoner.by_name(my_region, key)
            stats = lol_watcher.league.by_summoner(my_region, pseudo['id'])

            suivi = loadData('suivi')

            if len(stats) > 0:
                try:
                    wins = int(suivi[key]['wins'])
                    losses = int(suivi[key]['losses'])
                    nbgames = wins + losses
                    LP = int(suivi[key]['LP'])
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
                if difLP > 0:
                    if difwins < diflosses and difLP > 10:
                        difLP = 100 + LP - suivi[key]['LP']
                        difLP = "-" + str(difLP)
                        emote = ":arrow_down:"
                    else:
                        emote = ":arrow_up:"
                        difLP = "+" + str(difLP)
                elif difLP < 0:
                    if difwins > diflosses and difLP < -10:
                        difLP = 100 - LP + suivi[key]['LP']
                        difLP = "+" + str(difLP)
                        emote = ":arrow_up:"
                    else:
                        emote = ":arrow_down:"
                elif difLP == 0:
                    emote = ":arrow_right:"

                embed.add_field(name=str(key) + " ( " + tier + " " + rank + " )",
                                value="V : " + str(suivi[key]['wins']) + "(" + str(difwins) + ") | D : "
                                      + str(suivi[key]['losses']) + "(" + str(diflosses) + ") | LP :  "
                                      + str(suivi[key]['LP']) + "(" + str(difLP) + ")    " + emote, inline=False)
                embed.set_footer(text=f'Version {main.Var_version} by Tomlora')

                writeData(suivi, 'suivi')

            else:
                suivi[key]["tier"] = "Non-classé"

                writeData(suivi, 'suivi')

        # print(data)
        await ctx.send(embed=embed)
        await ctx.send(f'Sur {totalgames} games -> {totalwin} victoires et {totaldef} défaites')

    @commands.command(brief="Réservé au propriétaire du bot", description='Remet à zéro les records')
    @main.isOwner2()
    async def records_reset(self, ctx, fichier: int):
        if fichier == 1:
            reset_records_help('KDA', 1)
            reset_records_help('KP', 1)
            reset_records_help('CS', 1)
            reset_records_help('CS/MIN', 1)
            reset_records_help('KILLS', 1)
            reset_records_help('DEATHS', 1)
            reset_records_help('ASSISTS', 1)
            reset_records_help('WARDS_SCORE', 1)
            reset_records_help('WARDS_POSEES', 1)
            reset_records_help('WARDS_DETRUITES', 1)
            reset_records_help('WARDS_PINKS', 1)
            reset_records_help('DEGATS_INFLIGES', 1)
            reset_records_help('% DMG', 1)
            reset_records_help('DOUBLE', 1)
            reset_records_help('TRIPLE', 1)
            reset_records_help('QUADRA', 1)
            reset_records_help('PENTA', 1)
            reset_records_help('DUREE_GAME', 1)
        elif fichier == 2:
            reset_records_help('SPELLS_USED', 2)
            reset_records_help('BUFFS_VOLEES', 2)
            reset_records_help('SPELLS_EVITES', 2)
            reset_records_help('MUlTIKILL_1_SPELL', 2)
            reset_records_help('SOLOKILLS', 2)
            reset_records_help('CS_APRES_10_MIN', 2)
            reset_records_help('SERIES_DE_KILLS', 2)
            reset_records_help('NB_SERIES_DE_KILLS', 2)
            reset_records_help('DOMMAGES_TANK', 2)
            reset_records_help('DOMMAGES_TANK%', 2)
            reset_records_help('DOMMAGES_REDUITS', 2)
            reset_records_help('DOMMAGES_TOWER', 2)
            reset_records_help('GOLDS_GAGNES', 2)
            reset_records_help('TOTAL_HEALS', 2)
            reset_records_help('HEALS_SUR_ALLIES', 2)

        await ctx.send(f'Records Page {str(fichier)} réinitialisé !')

    @commands.command(brief='Affiche les records')
    # @main.isOwner2()
    async def records_list(self, ctx):

        current = 0

        fichier = loadData('records')

        emote = {
            "KDA": ":star:",
            "KP": ":trophy:",
            "CS": ":ghost:",
            "CS/MIN": ":ghost:",
            "KILLS": ":dagger:",
            "DEATHS": ":skull:",
            "ASSISTS": ":crossed_swords:",
            'WARDS_SCORE': ":eye:",
            'WARDS_POSEES': ":eyes:",
            'WARDS_DETRUITES': ":mag:",
            'WARDS_PINKS': ":red_circle:",
            'DEGATS_INFLIGES': ":dart:",
            "% DMG": ":magic_wand:",
            'DOUBLE': ":two:",
            'TRIPLE': ":three:",
            'QUADRA': ":four:",
            'PENTA': ":five:",
            'DUREE_GAME': ":timer:",
            'SPELLS_USED': ":gun:",
            'BUFFS_VOLEES': "<:PandaWow:732316840495415398>",
            'SPELLS_EVITES': ":white_check_mark:",
            'MUlTIKILL_1_SPELL': ":goal:",
            'SOLOKILLS': ":karate_uniform:",
            'CS_APRES_10_MIN': ":ghost:",
            'SERIES_DE_KILLS': ":crossed_swords:",
            'NB_SERIES_DE_KILLS': ":crossed_swords:",
            'DOMMAGES_TANK': ":shield:",
            'DOMMAGES_TANK%': ":shield:",
            'DOMMAGES_REDUITS': ":shield:",
            'DOMMAGES_TOWER': ":hook:",
            'GOLDS_GAGNES': ":euro:",
            'TOTAL_HEALS': ":sparkling_heart:",
            'HEALS_SUR_ALLIES': ":two_hearts:",
        }

        response = ""

        embed1 = discord.Embed(title="Records (Page 1) :bar_chart:", colour=discord.Colour.blurple())

        for key, value in fichier.items():
            valeur = ""
            if key == "DEGATS_INFLIGES":
                valeur = "{:,}".format(value['Score']).replace(',', ' ').replace('.', ',')
            elif key == "DUREE_GAME":
                valeur = str(int(round(value['Score'], 0))).replace(".", "m")
            elif key == "KP" or key == "% DMG":
                valeur = str(value['Score']) + "%"
            else:
                valeur = str(value['Score'])
            embed1.add_field(name=str(emote[key]) + "" + key,
                             value="Records : __ " + valeur + " __ \n ** " + str(
                                 value['Joueur']) + " ** (" + str(value['Champion']) + ")")

        embed1.set_footer(text=f'Version {main.Var_version} by Tomlora')

        fichier2 = loadData('records2')

        embed2 = discord.Embed(title="Records (Page 2) :bar_chart:", colour=discord.Colour.blurple())

        for key, value in fichier2.items():
            valeur2 = ""
            if key == "GOLDS_GAGNES" or key == "DOMMAGES_TANK" or key == 'DOMMAGES_REDUITS' or key == "DOMMAGES_TOWER" or key == "TOTAL_HEALS" or key == "HEALS_SUR_ALLIES":
                valeur2 = "{:,}".format(value['Score']).replace(',', ' ').replace('.', ',')
            elif key == "DOMMAGES_TANK%":
                valeur2 = str(value['Score']) + "%"
            else:
                valeur2 = str(value['Score'])
            embed2.add_field(name=str(emote[key]) + "" + key,
                             value="Records : __ " + valeur2 + " __ \n ** " + str(
                                 value['Joueur']) + " ** (" + str(value['Champion']) + ")")

        embed2.set_footer(text=f'Version {main.Var_version} by Tomlora')

        self.bot.pages = [embed1, embed2]
        buttons = [u"\u2B05", u"\u27A1"]  # skip to start, left, right, skip to end

        msg = await ctx.send(embed=self.bot.pages[current])

        for button in buttons:
            await msg.add_reaction(button)

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", check=lambda reaction,
                                                                                      user: user == ctx.author and reaction.emoji in buttons,
                                                         timeout=30.0)
            except asyncio.TimeoutError:
                return print("Records_list terminés")
            else:
                previous_page = current

                if reaction.emoji == u"\u2B05":
                    if current > 0:
                        current -= 1

                elif reaction.emoji == u"\u27A1":
                    if current < len(self.bot.pages) - 1:
                        current += 1

                for button in buttons:
                    await msg.remove_reaction(button, ctx.author)

                if current != previous_page:
                    await msg.edit(embed=self.bot.pages[current])

    @commands.command(brief="DB Rito")
    async def loldb(self, ctx):
        await ctx.send('https://docs.google.com/spreadsheets/d/1Y7k5kQ2AegbuyiGwEPsa62e883FYVtHqr6UVut9RC4o/pubhtml#')

    @commands.command()
    async def achievements(self, ctx, records:str = 'no'):

        # Succes
        suivi = loadData('suivi')
        records1 = loadData('records')
        records2 = loadData('records2')
        settings = loadData('achievements_settings')

        df = pd.DataFrame(suivi)
        df = df.transpose().reset_index()

        # Records
        if records == "records":
            df2 = pd.DataFrame(records1).transpose()
            df3 = pd.DataFrame(records2).transpose()

            plt.figure(figsize=(15,8))

            df2 = pd.concat([df2, df3])

            df2 = unifier_joueur(df2, 'Joueur')

            df2_count = df2.groupby(by=['Joueur']).count().reset_index()

            df2_count = df2_count.sort_values(by='Score', ascending=False)

            df2_count = df2_count[df2_count['Joueur'] != "Tomlora"] #Records non-pris

            fig = px.bar(df2_count, y='Score', x='Joueur', title="Records", color='Joueur')
            fig.update_layout(showlegend=False)
            fig.write_image('plot.png')



        df = df[df['games'] >= settings['Nb_games']]
        df['Achievements_par_game'] = df['Achievements'] / df['games']

        df.sort_values(by=['Achievements_par_game'], ascending=[False], inplace=True)


        joueur = df['index'].to_dict()

        await ctx.send(f"Couronnes (SoloQ only et {settings['Nb_games']} games minimum) : ")
        for id, key in joueur.items():
            try:
                if suivi[key]['Achievements'] > 0:
                    achievements = suivi[key]['Achievements']
                    games = suivi[key]['games']
                    achievements_par_game = round(achievements / games, 2)

                    await ctx.send(
                        " ** " + key + " ** : " + str(achievements) + " :crown: en " + str(games) + " games (" + str(
                            achievements_par_game) + " :crown: / games)")
            except:
                suivi[key]['Achievements'] = 0
                suivi[key]['games'] = 0

                writeData(suivi, 'suivi')

        if records == "records":
            # await ctx.send(file=discord.File('filename.png'))
            # os.remove('filename.png')

            await ctx.send(file=discord.File('plot.png'))
            os.remove('plot.png')

    @commands.command()
    @main.isOwner2()
    async def achievements_reset(self, ctx):

        suivi = loadData('suivi')

        for key in suivi:
            suivi[key]['Achievements'] = 0
            suivi[key]['games'] = 0

        writeData(suivi, 'suivi')

        await ctx.send('Achievements remis à zéro.')


    @commands.command()
    async def achievements_regles(self, ctx):

        settings = loadData("achievements_settings")

        partie0 = f":gear: Nombre de games minimum : {settings['Nb_games']} \n"
        partie1 = f":crown: Pentakill : {settings['Pentakill']} \n :crown: Quadrakill : {settings['Quadrakill']} \n :crown: KDA >= {settings['KDA']} \n :crown: Ne pas mourir \n :crown: KP >= {settings['KP']}% \n"
        partie2 = f":crown: Vision/min >= {settings['Vision/min(support)']} (support) | {settings['Vision/min(autres)']} (autres) \n :crown: CS/min >= {settings['CS/min']} \n"
        partie3 = f":crown: % DMG équipe > {settings['%_dmg_équipe']}% \n :crown: % dmg tank >= {settings['%_dmg_tank']}% \n"
        partie4 = f":crown: Solokills >= {settings['Solokills']} \n :crown: Total Heals sur alliés >= {settings['Total_Heals_sur_alliés']}"

        embed = discord.Embed(title="** Règles : **" , color=discord.Colour.gold())
        embed.add_field(name="Parametres", value=partie0,inline=False)
        embed.add_field(name="Couronnes disponibles", value=partie1 + partie2 + partie3 + partie4, inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    @main.isOwner2()
    async def achievements_maj(self, ctx, param, condition:int = 0):

        data = loadData("achievements_settings")

        if param == "key":
            await ctx.send(data.keys())
        else:
            data[param] = condition

            writeData(data, "achievements_settings")

            await ctx.send(":trophy: Achievements mis à jour !")


    @commands.command()
    @main.isOwner2()
    async def spectator(self, ctx, *, summonerName):
        match = match_spectator(summonerName)
        print(match['participants'])
        await ctx.send('Fait !')


    @commands.command()
    @main.isOwner2()
    async def dataframe(self, ctx):
        import warnings
        warnings.simplefilter(action='ignore', category=FutureWarning)
        def ajouter_game(df, pseudo, kills, deaths, assists, kp, wardsplaced, wardskilled, pink, cs, csm, score):
            df = df.append({'Pseudo': pseudo, 'Kills': kills, 'Deaths': deaths
                               , 'Assists': assists, 'KP': kp, 'WardsPlaced': wardsplaced, 'WardsKilled': wardskilled
                               , 'Pink': pink, 'cs': cs, 'csm': csm, 'Score': score}, ignore_index=True)
            return df

        df = pd.DataFrame(
            columns=['Pseudo', 'Kills', 'Deaths', 'Assists', 'KP', 'WardsPlaced', 'WardsKilled', 'Pink', 'cs', 'csm',
                     'Score'])
        df = ajouter_game(df, 'Nami Yeon', 0, 3, 31, 0.79, 67, 12, 17, 20, 0.5, 7.8)
        df = ajouter_game(df, 'Nami Yeon', 1, 1, 10, 0.79, 30, 3, 8, 10, 0.3, 7.12)
        df = ajouter_game(df, 'Nami Yeon', 4, 4, 18, 0.4, 45, 7, 11, 20, 0.6, 7.84)
        df = ajouter_game(df, 'Nami Yeon', 5, 0, 21, 0.59, 42, 8, 12, 22, 0.7, 9.34)
        df = ajouter_game(df, 'Nami Yeon', 1, 4, 16, 0.35, 49, 12, 8, 18, 0.6, 5.81)
        df = ajouter_game(df, 'Nami Yeon', 3, 4, 14, 0.65, 53, 12, 12, 26, 0.8, 6.7)
        df = ajouter_game(df, 'Nami Yeon', 2, 8, 20, 0.42, 63, 15, 15, 25, 0.7, 6.57)
        df = ajouter_game(df, 'Nami Yeon', 4, 2, 21, 0.69, 49, 8, 11, 11, 0.3, 7.72)
        df = ajouter_game(df, 'Nami Yeon', 5, 5, 19, 0.65, 36, 6, 8, 14, 0.5, 6.39)
        df = ajouter_game(df, 'Nami Yeon', 1, 2, 21, 0.59, 65, 19, 14, 27, 0.8, 8.59)
        df = ajouter_game(df, 'Nami Yeon', 5, 4, 27, 0.74, 42, 7, 9, 22, 0.7, 9.18)
        df = ajouter_game(df, 'Nami Yeon', 4, 0, 14, 0.82, 26, 6, 6, 10, 0.4, 7.94)
        df = ajouter_game(df, 'Nami Yeon', 0, 4, 19, 0.42, 33, 4, 9, 8, 0.2, 6.9)
        df = ajouter_game(df, 'Nami Yeon', 4, 5, 24, 0.68, 64, 19, 14, 39, 1.1, 7.71)
        df = ajouter_game(df, 'Nami Yeon', 1, 5, 18, 0.58, 33, 13, 9, 17, 0.7, 7.25)
        df = ajouter_game(df, 'Nami Yeon', 5, 2, 25, 0.59, 74, 13, 17, 20, 0.5, 8.09)
        df = ajouter_game(df, 'Nami Yeon', 7, 8, 21, 0.53, 57, 13, 14, 26, 0.7, 7.41)
        df = ajouter_game(df, 'Nami Yeon', 3, 2, 15, 0.62, 37, 8, 11, 14, 0.6, 8.47)
        df = ajouter_game(df, 'Nami Yeon', 5, 5, 23, 0.68, 47, 3, 15, 24, 0.6, 7.31)
        df = ajouter_game(df, 'Nami Yeon', 6, 6, 32, 0.70, 75, 17, 16, 35, 0.9, 8.34)
        df = ajouter_game(df, 'Millanah', 6, 9, 13, 0.54, 31, 11, 0, 76, 1.9, 6.20)
        df = ajouter_game(df, 'Vinine Rain', 4, 2, 13, 0.52, 25, 11, 5, 35, 1.1, 7.88)
        df = ajouter_game(df, 'Kyugure', 1, 10, 12, 0.43, 31, 11, 3, 24, 0.7, 5.17)
        df = ajouter_game(df, 'Fiddlestick irl', 0, 9, 1, 0.07, 25, 3, 2, 15, 0.5, 3.65)
        df = ajouter_game(df, 'Shobo Kok', 3, 6, 6, 0.3, 27, 19, 1, 55, 1.7, 6.44)
        df = ajouter_game(df, 'Andrea Pucci', 0, 8, 19, 0.61, 34, 15, 10, 49, 1.5, 6.18)
        df = ajouter_game(df, 'guzz', 22, 9, 5, 0.60, 48, 15, 1, 79, 2.1, 7.55)
        df = ajouter_game(df, 'Dadapon', 1, 7, 12, 0.59, 14, 7, 4, 57, 1.8, 5.55)
        df = ajouter_game(df, 'SFS NoobT', 14, 9, 7, 0.48, 13, 5, 1, 62, 2.1, 7.05)
        df = ajouter_game(df, 'This is Soo', 2, 9, 16, 0.64, 27, 16, 4, 45, 1.3, 5.50)
        df = ajouter_game(df, 'Thresh Sol', 1, 7, 17, 0.55, 16, 3, 1, 14, 0.5, 4.76)
        df = ajouter_game(df, 'Bduyendaria', 2, 5, 7, 0.43, 30, 7, 5, 28, 1.1, 5.74)
        df = ajouter_game(df, 'R3V ANG3L', 1, 8, 7, 0.32, 15, 7, 3, 61, 1.9, 5.35)
        df = ajouter_game(df, 'Endé', 2, 7, 14, 0.3, 57, 27, 13, 65, 0.3, 6.77)
        df = ajouter_game(df, 'loulou0701', 6, 4, 13, 0.5, 30, 17, 5, 29, 0.9, 7.57)
        df = ajouter_game(df, 'Ezekiel', 2, 5, 17, 0.73, 27, 9, 6, 14, 0.4, 6.39)
        df = ajouter_game(df, 'Pilgrim', 5, 3, 12, 0.52, 33, 14, 8, 44, 1.5, 8.72)
        df = ajouter_game(df, 'kazAbunga', 0, 6, 9, 0.53, 41, 4, 10, 9, 0.3, 5.21)
        df = ajouter_game(df, 'Angry Land', 0, 6, 8, 0.50, 24, 6, 4, 19, 0.7, 4.80)
        df = ajouter_game(df, 'Kiroulpé', 4, 2, 14, 0.67, 18, 7, 3, 12, 0.4, 8.06)
        df = ajouter_game(df, 'Pueblo x C', 4, 2, 13, 0.5, 23, 1, 6, 41, 1.5, 8.02)
        df = ajouter_game(df, 'Princess Ja', 1, 5, 11, 0.67, 11, 2, 2, 2, 0.1, 4.22)
        df = ajouter_game(df, 'Tobiseus', 3, 5, 3, 0.86, 7, 2, 1, 19, 0.2, 5.57)
        df = ajouter_game(df, 'maari', 3, 3, 8, 0.42, 11, 1, 3, 10, 0.7, 6.14)
        df = ajouter_game(df, '5all elite', 1, 5, 21, 0.54, 55, 8, 14, 45, 101, 6.18)
        df = ajouter_game(df, 'SGirbi', 2, 6, 8, 0.40, 38, 39, 1, 161, 3.8, 6.75)
        df = ajouter_game(df, 'Janna supp', 5, 4, 31, 0.86, 24, 3, 4, 6, 0.2, 7.03)
        df = ajouter_game(df, '3hd', 4, 8, 12, 0.53, 27, 9, 3, 72, 2.2, 6.01)
        df = ajouter_game(df, 'TrippinJ', 0, 5, 2, 0.18, 22, 2, 5, 30, 1.0, 5.12)
        df = ajouter_game(df, 'hewfplit', 2, 2, 18, 0.65, 23, 4, 7, 4, 0.1, 7.41)
        df = ajouter_game(df, 'kk2kwz', 10, 5, 9, 0.43, 30, 9, 9, 39, 1.2, 7.70)
        df = ajouter_game(df, 'With a smile', 5, 11, 2, 0.23, 32, 9, 7, 26, 0.8, 6.14)
        df = ajouter_game(df, 'typefaller', 1, 3, 9, 0.38, 20, 5, 4, 27, 1.2, 6.51)
        df = ajouter_game(df, 'Agua de merda', 1, 7, 6, 0.33, 15, 7, 4, 25, 1.1, 5.41)
        df = ajouter_game(df, 'Brukseles', 0, 5, 21, 0.47, 24, 5, 5, 28, 0.9, 6.42)
        df = ajouter_game(df, 'Yobany shef', 4, 9, 15, 0.61, 35, 5, 5, 19, 0.6, 6.24)
        df = ajouter_game(df, 'Abaka', 0, 3, 14, 0.52, 16, 5, 3, 13, 0.5, 6.7)
        df = ajouter_game(df, 'Trakun', 4, 6, 2, 0.46, 21, 6, 3, 32, 1.3, 6.5)
        df = ajouter_game(df, 'NormanLOL', 1, 5, 16, 0.55, 27, 7, 3, 38, 1.5, 6.59)
        df = ajouter_game(df, 'Imperus', 1, 4, 7, 0.57, 11, 15, 4, 46, 1.8, 6.80)
        df = ajouter_game(df, 'idsf', 0, 3, 15, 0.56, 23, 4, 2, 32, 1.3, 5.89)
        df = ajouter_game(df, 'Bragaintl', 2, 2, 6, 0.57, 19, 8, 3, 43, 1.7, 7.21)
        df = ajouter_game(df, 'Kind of god', 3, 13, 11, 0.5, 37, 6, 5, 30, 0.9, 5.71)
        df = ajouter_game(df, 'Des7r0', 0, 7, 27, 0.52, 24, 7, 1, 34, 1.0, 6.15)
        df = ajouter_game(df, 'MabzZ', 7, 8, 15, 0.58, 34, 7, 7, 30, 0.8, 7.2)
        df = ajouter_game(df, 'Karzow', 2, 5, 25, 0.77, 26, 8, 6, 31, 0.9, 6.46)
        df = ajouter_game(df, 'burn in fires', 3, 8, 17, 0.49, 21, 4, 0, 36, 1.1, 6.66)
        df = ajouter_game(df, 'CD9', 0, 8, 16, 0.5, 27, 7, 9, 12, 0.4, 5.38)
        df = ajouter_game(df, 'DarkHeaven', 3, 9, 12, 0.45, 59, 13, 13, 46, 1.2, 6.85)
        df = ajouter_game(df, 'TrollKarl', 1, 6, 11, 0.32, 39, 10, 8, 23, 0.6, 5.9)
        df = ajouter_game(df, 'Arrancabrita', 3, 2, 14, 0.45, 26, 6, 2, 45, 1.5, 8.99)
        df = ajouter_game(df, 'sofmega', 0, 9, 7, 0.35, 22, 6, 3, 8, 0.3, 3.53)
        df = ajouter_game(df, 'Feedmeme', 2, 3, 18, 0.50, 33, 9, 5, 33, 0.9, 7.56)
        df = ajouter_game(df, 'TKS Karda', 2, 8, 13, 0.52, 35, 8, 5, 40, 1.1, 4.90)
        df = ajouter_game(df, 'Satan Hell', 4, 4, 18, 0.56, 16, 2, 2, 11, 0.4, 6.64)
        df = ajouter_game(df, 'Mushroom', 9, 10, 3, 0.48, 24, 8, 1, 35, 1.2, 6.05)
        df = ajouter_game(df, 'Renata D', 5, 11, 12, 0.4, 28, 6, 9, 49, 1.4, 6.78)
        df = ajouter_game(df, 'OSRS is b', 1, 5, 19, 0.65, 23, 10, 0, 18, 0.5, 5.66)
        df = ajouter_game(df, 'Knuspriger', 11, 2, 9, 0.48, 31, 6, 4, 40, 1.6, 8.98)
        df = ajouter_game(df, 'Brezeilito', 4, 11, 2, 0.33, 12, 10, 4, 27, 1.1, 4.47)
        df = ajouter_game(df, 'Nysderoy', 1, 3, 12, 0.48, 26, 6, 6, 16, 0.6, 6.91)
        df = ajouter_game(df, 'El Fotos', 3, 5, 2, 0.5, 29, 5, 3, 42, 1.6, 6.08)
        df = ajouter_game(df, 'Festivalbar96', 1, 8, 9, 0.40, 44, 11, 3, 58, 1.9, 6.30)
        df = ajouter_game(df, 'Exalted Orb', 1, 7, 16, 0.89, 23, 12, 7, 40, 1.3, 6.15)
        df = ajouter_game(df, 'Sc S4ntos', 4, 9, 22, 0.54, 45, 18, 9, 54, 1.4, 6.64)
        df = ajouter_game(df, 'mp3gear', 1, 3, 31, 0.63, 49, 15, 1, 19, 0.5, 5.98)
        df = ajouter_game(df, 'Tomlora', 0, 5, 2, 0.22, 12, 0, 2, 14, 0.7, 3.55)
        df = ajouter_game(df, 'Tomlora', 3, 8, 18, 0.58, 20, 5, 3, 48, 1.4, 6.07)
        df = ajouter_game(df, 'WeeeZy', 7, 6, 26, 0.62, 21, 3, 4, 41, 1.2, 7.1)
        df = ajouter_game(df, 'Tomlora', 11, 1, 13, 0.59, 13, 1, 3, 42, 1.7, 8.87)

        dict = df.to_dict()

        writeData(dict, 'scoring_support')

        await ctx.send('BDD crée')





def setup(bot):
    bot.add_cog(LeagueofLegends(bot))
