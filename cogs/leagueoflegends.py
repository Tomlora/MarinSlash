
from discord.ext import commands, tasks

from matplotlib import pyplot as plt
import sys
from riotwatcher import LolWatcher
import pandas as pd
import main
import datetime
import numpy as np
import warnings
from cogs.achievements_scoringlol import scoring
from fonctions.gestion_fichier import loadData, writeData
from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd
from tqdm import tqdm
import json

from fonctions.match import matchlol, match_by_puuid, getId, dict_rankid 


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


# dict_rankid = {"BRONZE IV" : 1,
#                "BRONZE III" : 2,
#                "BRONZE II" : 3,
#                "BRONZE I" : 4,
#                "SILVER IV" : 5,
#                "SILVER III" : 6,
#                "SILVER II": 7,
#                "SILVER I" : 8,
#                "GOLD IV" : 9,
#                "GOLD III" : 10,
#                "GOLD II" : 11,
#                "GOLD I" : 12,
#                "PLATINUM IV" : 13,
#                "PLATINUM III" : 14,
#                "PLATINUM II" : 15,
#                "PLATINUM I" : 16,
#                "DIAMOND IV" : 17,
#                "DIAMOND III" : 18,
#                "DIAMOND II" : 19,
#                "DIAMOND I" : 20,
#                'MASTER I' : 21,
#                'GRANDMASTER I': 22,
#                'CHALLENGER I' : 23}



def records_check(fichier, key_boucle, key: str, Score_check: float, thisChampName, summonerName, embed):
    if str(key_boucle) == str(key):
        if str(key) in ['EARLY_DRAKE', 'EARLY_BARON'] and Score_check > 0: # ici on veut le plus faible et pas égale à 0
            if float(fichier[key]['Score']) > Score_check:
                ancien_score = fichier[key]['Score']
                detenteur_ancien_score = fichier[key]['Joueur']
                fichier[key]['Score'] = Score_check
                fichier[key]['Champion'] = str(thisChampName)
                fichier[key]['Joueur'] = summonerName
                # Annonce que le record a été battu :
                embed = embed + f"\n ** :boom: Record {str(key).lower()} battu avec {Score_check} ** (Ancien : {ancien_score} par {detenteur_ancien_score})"

        else:
        # si le record est battu, on fait les modifs nécessaires:
            if float(fichier[key]['Score']) < Score_check:
                ancien_score = fichier[key]['Score']
                detenteur_ancien_score = fichier[key]['Joueur']
                fichier[key]['Score'] = Score_check
                fichier[key]['Champion'] = str(thisChampName)
                fichier[key]['Joueur'] = summonerName
                # Annonce que le record a été battu :
                embed = embed + f"\n ** :boom: Record {str(key).lower()} battu avec {Score_check} ** (Ancien : {ancien_score} par {detenteur_ancien_score})"


    return fichier, embed




def match_spectator(summonerName):
    me = lol_watcher.summoner.by_name(my_region, summonerName)
    try:
        my_match = lol_watcher.spectator.by_summoner(my_region, me['id'])
    except:
        my_match = False
    return my_match

def palier(embed, key:str, stats:str, old_value:int, new_value:int, palier:list):
    if key == stats:
        for value in palier:
            if old_value < value and new_value > value:
                stats = stats.replace('_', ' ')
                embed = embed + f"\n ** :tada: Stats cumulées : A dépassé les {value} {stats.lower()} avec {new_value} {stats.lower()} **"
    return embed 

def score_personnel(embed, dict, key:str, summonerName:str, stats:str, old_value:float, new_value:float):
    if key == stats:
        if old_value < new_value:
            dict[key][summonerName.lower().replace(" ", "")] = new_value
            stats = stats.replace('_', ' ')
            embed = embed + f"\n ** :military_medal: Tu as battu ton record personnel en {stats.lower()} avec {new_value} {stats.lower()} ** (Anciennement : {old_value})"
    return embed, dict
                

class LeagueofLegends(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.my_task.start()
        self.lolsuivi.start()
        
 
    def printInfo(self, summonerName, idgames: int, succes):


        match_info = matchlol(summonerName, idgames) #class
        
        
        if match_info.thisQId == 900: #urf (géré différemment)
            return {}, 'URF'
        
        if match_info.thisQId == 840:
            return {}, 'Bot' # bot game

        
        exploits = "Observations :"
        exploits2 = " "
        exploits3 = " "
        exploits4 = " "
        
        # Suivi
        
        suivi = lire_bdd('suivi', 'dict')
        try:
            if suivi[summonerName.lower().replace(" ", "")]['tier'] == match_info.thisTier and suivi[summonerName.lower().replace(" ", "")]['rank'] == match_info.thisRank:
                difLP = int(match_info.thisLP) - int(suivi[summonerName.lower().replace(" ", "")]['LP'])
            else:
                difLP = 0
        except:
            difLP = 0
        
        if difLP > 0:
            difLP = '+' + str(difLP)
        else:
            difLP = str(difLP)
            
        if match_info.thisQ == "RANKED": # si pas ranked, inutile car ça bougera pas
        
            suivi[summonerName.lower().replace(" ", "")]['wins'] = match_info.thisVictory
            suivi[summonerName.lower().replace(" ", "")]['losses'] = match_info.thisLoose
            suivi[summonerName.lower().replace(" ", "")]['LP'] = match_info.thisLP

        if match_info.thisQ == "RANKED" and match_info.thisTime > 20:

            records = lire_bdd('records', 'dict')
            records2 = lire_bdd('records2', 'dict')          

            for key, value in records.items():
                if int(match_info.thisDeaths) >= 1:

                    records, exploits = records_check(records, key, 'KDA',
                                            float(match_info.thisKDA),
                                            match_info.thisChampName, summonerName, exploits)
                else:
                    records, exploits = records_check(records, key, 'KDA',
                                            float(
                                                round((int(match_info.thisKills) + int(match_info.thisAssists)) / (int(match_info.thisDeaths) + 1), 2)),
                                            match_info.thisChampName, summonerName, exploits)

                records, exploits = records_check(records, key, 'KP', match_info.thisKP,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'CS', match_info.thisMinion,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'CS/MIN', match_info.thisMinionPerMin,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'KILLS', match_info.thisKills,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'DEATHS', match_info.thisDeaths,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'ASSISTS', match_info.thisAssists,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'WARDS_SCORE', match_info.thisVision,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'WARDS_POSEES', match_info.thisWards,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'WARDS_DETRUITES', match_info.thisWardsKilled,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'WARDS_PINKS', match_info.thisPink,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'DEGATS_INFLIGES',
                                        match_info.match_detail_participants['totalDamageDealtToChampions'],
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, '% DMG', match_info.thisDamageRatio,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'DOUBLE', match_info.thisDouble,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'TRIPLE', match_info.thisTriple,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'QUADRA', match_info.thisQuadra,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'PENTA', match_info.thisPenta,
                                        match_info.thisChampName, summonerName, exploits)
                records, exploits = records_check(records, key, 'DUREE_GAME', match_info.thisTime,
                                        match_info.thisChampName, summonerName, exploits)
                
                if match_info.thisPosition == "SUPPORT":
                    records, exploits = records_check(records, key, 'AVANTAGE_VISION_SUPPORT', float(match_info.thisVisionAdvantage),
                                        match_info.thisChampName, summonerName, exploits)
                    
                else:
                    records, exploits = records_check(records, key, 'AVANTAGE_VISION', float(match_info.thisVisionAdvantage),
                                        match_info.thisChampName, summonerName, exploits)
                    
                


                for key, value in records2.items():
                    if match_info.thisChampName != "Zeri": # on supprime Zeri de ce record qui est impossible à égaler avec d'autres champions
                        records2, exploits = records_check(records2, key, 'SPELLS_USED',
                                                 match_info.thisSpellUsed,
                                                 match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'BUFFS_VOLEES', match_info.thisbuffsVolees,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'SPELLS_EVITES', match_info.thisSpellsDodged,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'CS_AVANTAGES', match_info.thisCSAdvantageOnLane,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'SOLOKILLS', match_info.thisSoloKills,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'CS_APRES_10_MIN', match_info.thisCSafter10min,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'NB_SERIES_DE_KILLS', match_info.thisKillingSprees,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'DOMMAGES_TANK',
                                             int(match_info.match_detail_participants['totalDamageTaken']),
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'DOMMAGES_TANK%', match_info.thisDamageTakenRatio,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'DOMMAGES_REDUITS', match_info.thisDamageSelfMitigated,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'DOMMAGES_TOWER', match_info.thisDamageTurrets,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'GOLDS_GAGNES', match_info.thisGoldEarned,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'SERIES_DE_KILLS', match_info.thisKillsSeries,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'TOTAL_HEALS',
                                             match_info.thisTotalHealed,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'HEALS_SUR_ALLIES', match_info.thisTotalOnTeammates,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'EARLY_DRAKE', match_info.earliestDrake,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'EARLY_BARON', match_info.earliestBaron,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'SKILLSHOTS_HIT', match_info.thisSkillshot_hit,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'SKILLSHOTS_DODGES', match_info.thisSkillshot_dodged,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'TOWER_PLATES', match_info.thisTurretPlatesTaken,
                                             match_info.thisChampName, summonerName, exploits)
                    records2, exploits = records_check(records2, key, 'ECART_LEVEL', match_info.thisLevelAdvantage,
                                             match_info.thisChampName, summonerName, exploits)
                    
                    sauvegarde_bdd(records, 'records')
                    sauvegarde_bdd(records2, 'records2')
                    
        # on le fait après sinon ça flingue les records
        match_info.thisDamageTurrets = "{:,}".format(match_info.thisDamageTurrets).replace(',', ' ').replace('.', ',')

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
        elif (pseudo == 'CHGUIZOU'):
            color = discord.Colour.from_rgb(127, 0, 255)
        else:
            color = discord.Color.blue()

        # constructing the message

        if match_info.thisQ == "OTHER":
            embed = discord.Embed(
                title=f"** {summonerName.upper()} ** vient de ** {match_info.thisWin} ** une game ", color=color)
        elif match_info.thisQ == "ARAM":
            embed = discord.Embed(
                title=f"** {summonerName.upper()} ** vient de ** {match_info.thisWin} ** une ARAM ", color=color)
        else:
            embed = discord.Embed(
                title=f"** {summonerName.upper()} ** vient de ** {match_info.thisWin} ** une {match_info.thisQ} game ({match_info.thisPosition})", color=color)

            if match_info.thisPosition in ['SUPPORT', 'ADC', 'MID', 'JUNGLE']:
                result = scoring(match_info.thisPosition, summonerName, match_info.thisKills, match_info.thisDeaths, match_info.thisAssists, (match_info.thisKP / 100),
                                 match_info.thisWards, match_info.thisWardsKilled, match_info.thisPink, match_info.thisMinion, match_info.thisMinionPerMin)

        # annonce
        points = 0
        

        settings = lire_bdd('achievements_settings', 'dict')

        records_cumul = lire_bdd('records3', 'dict')
        records_personnel = lire_bdd('records_personnel', 'dict')
        


        if int(match_info.thisPenta) >= settings['Pentakill']['Score']:
            exploits = exploits + f"\n ** :crown: :five: Ce joueur a pentakill ** {match_info.thisPenta} fois"
            points = points + (1 * int(match_info.thisPenta))

        if int(match_info.thisQuadra) >= settings['Quadrakill']['Score']:
            exploits = exploits + f"\n ** :crown: :four: Ce joueur a quadrakill ** {match_info.thisQuadra} fois"
            points = points + (1 * int(match_info.thisQuadra))

        if float(match_info.thisKDA) >= settings['KDA']['Score']:
            exploits = exploits + f"\n ** :crown: :star: Ce joueur a un bon KDA avec un KDA de {match_info.thisKDA} **"
            points = points + 1

        if int(match_info.thisDeaths) == int(settings['Ne_pas_mourir']['Score']):
            exploits = exploits + "\n ** :crown: :heart: Ce joueur n'est pas mort de la game ** \n ** :crown: :star: Ce joueur a un PERFECT KDA **"
            points = points + 2

        if int(match_info.thisKP) >= settings['KP']['Score']:
            exploits = exploits + f"\n ** :crown: :dagger: Ce joueur a participé à énormément de kills dans son équipe avec {match_info.thisKP} % **"
            points = points + 1

        if float(match_info.thisVisionPerMin) >= settings['Vision/min(support)']['Score'] and str(match_info.thisPosition) == "SUPPORT":
            exploits = exploits + f"\n ** :crown: :eye: Ce joueur a un gros score de vision avec {match_info.thisVisionPerMin} / min **"
            points = points + 1

        if int(match_info.thisVisionPerMin) >= settings['Vision/min(autres)']['Score'] and str(match_info.thisPosition) != "SUPPORT":
            exploits = exploits + f"\n ** :crown: :eye: Ce joueur a un gros score de vision avec {match_info.thisVisionPerMin} / min **"
            points = points + 1

        if int(match_info.thisMinionPerMin) >= settings['CS/min']['Score']:
            exploits = exploits + f"\n ** :crown: :ghost: Ce joueur a bien farm avec {match_info.thisMinionPerMin} CS / min **"
            points = points + 1

        if int(match_info.thisDamageRatio) >= settings['%_dmg_équipe']['Score']:
            exploits = exploits + f"\n ** :crown: :dart: Ce joueur a infligé beaucoup de dmg avec {match_info.thisDamageRatio}%  pour son équipe **"
            points = points + 1

        if int(match_info.thisDamageTakenRatio) >= settings['%_dmg_tank']['Score']:
            exploits = exploits + f"\n ** :crown: :shield: Ce joueur a bien tank pour son équipe avec {match_info.thisDamageTakenRatio}% **"
            points = points + 1

        if int(match_info.thisSoloKills) >= settings['Solokills']['Score']:
            exploits = exploits + f"\n ** :crown: :muscle: Ce joueur a réalisé {match_info.thisSoloKills} solokills **"
            points = points + 1

        if int(match_info.thisTotalOnTeammates) >= settings['Total_Heals_sur_alliés']['Score']:
            exploits = exploits + f"\n ** :crown: :heart: Ce joueur a heal plus de {match_info.thisTotalOnTeammatesFormat} sur ses alliés **"
            points = points + 1
        
        if int(match_info.thisCSAdvantageOnLane) >= settings['CSAvantage']['Score']:
            exploits = exploits + f"\n ** :crown: :ghost: Tu as plus de {match_info.thisCSAdvantageOnLane} CS d'avance sur ton adversaire durant la game**"
            points = points + 1
            
        if int(match_info.thisLevelAdvantage) >= settings['Ecart_Level']['Score']:
            exploits = exploits + f"\n ** :crown: :wave: Tu as au moins {match_info.thisLevelAdvantage} niveaux d'avance sur ton adversaire durant la game**"
            points = points + 1
            
        if (float(match_info.thisVisionAdvantage) >= settings['Avantage_vision(support)']['Score'] and str(match_info.thisPosition) == "SUPPORT") or (float(match_info.thisVisionAdvantage) >= settings['Avantage_vision(autres)']['Score'] and str(match_info.thisPosition) != "SUPPORT"):
            exploits = exploits + f"\n ** :crown: :eye: Ce joueur a un gros avantage de vision sur son adversaire avec {match_info.thisVisionAdvantage}% **"
            points = points + 1
            
        if (float(match_info.participation_tower) >= settings['Participation_tower']['Score']):
            exploits = exploits + f"\n ** :crown: :tokyo_tower: Ce joueur a contribué à la destruction de {match_info.participation_tower}% des tours **"
            points = points + 1
            
        if (float(match_info.thisDragonTeam) >= settings['Dragon']['Score']):
            exploits = exploits + f"\n ** :crown: :dragon: Tu as obtenu l'âme du dragon **"
            points = points + 1

            
        # Présence d'afk    
        if match_info.AFKTeam >= 1:
            exploits = exploits + "\n ** Tu as eu un afk dans ton équipe :'( **"
            
        # Série de victoire    
        if match_info.thisWinStreak == "True" and match_info.thisQ == "RANKED" and succes is True and match_info.thisTime > 20:
            if suivi[summonerName.lower().replace(" ", "")]["serie"] == 0: # si égal à 0, le joueur commence une série avec 3 wins
                suivi[summonerName.lower().replace(" ", "")]["serie"] = 3
            else: # si pas égal à 0, la série a déjà commencé
                suivi[summonerName.lower().replace(" ", "")]["serie"] = suivi[summonerName.lower().replace(" ", "")]["serie"] + 1
            
            serie_victoire = round(suivi[summonerName.lower().replace(" ", "")]["serie"],0)
                
            exploits = exploits + f"\n ** :fire: Ce joueur est en série de victoire avec {serie_victoire} victoires**"
                       
        elif match_info.thisWinStreak == "False" and match_info.thisQ == "RANKED": # si pas de série en soloq
            suivi[summonerName.lower().replace(" ", "")]["serie"] = 0
            serie_victoire = 0
        else:
            serie_victoire = 0
            
            
        # Structure : Stat / Nombre / Palier sous forme de liste numérique
        dict_cumul = {"SOLOKILLS": [match_info.thisSoloKills, np.arange(100, 1000, 100, int).tolist()], 
                      "NBGAMES": [1, np.arange(50, 1000, 50, int).tolist()], 
                      "DUREE_GAME": [match_info.thisTime / 60, 0],
                      "KILLS": [match_info.thisKills, np.arange(500, 10000, 500, int).tolist()],
                      "DEATHS": [match_info.thisDeaths, np.arange(500, 10000, 500, int).tolist()],
                      "ASSISTS": [match_info.thisAssists, np.arange(500, 10000, 500, int).tolist()],
                      "WARDS_SCORE": [match_info.thisVision, 0],
                      "WARDS_POSEES": [match_info.thisWards, np.arange(500, 10000, 500, int).tolist()],
                      "WARDS_DETRUITES": [match_info.thisWardsKilled, np.arange(500, 10000, 500, int).tolist()],
                      "WARDS_PINKS": [match_info.thisPink, 0],
                      "CS" : [match_info.thisMinion, np.arange(10000, 100000, 10000, int).tolist()],
                      "QUADRA" : [match_info.thisQuadra, np.arange(5, 100, 5, int).tolist()],
                      "PENTA" : [match_info.thisPenta, np.arange(5, 100, 5, int).tolist()]}
        
        personnel_cumul = {"SOLOKILLS": match_info.thisSoloKills, "DUREE_GAME": match_info.thisTime, "KILLS": match_info.thisKills,
                      "DEATHS": match_info.thisDeaths, "ASSISTS": match_info.thisAssists, "WARDS_SCORE": match_info.thisVision,
                      "WARDS_POSEES": match_info.thisWards, "WARDS_DETRUITES": match_info.thisWardsKilled, "WARDS_PINKS": match_info.thisPink,
                      "CS" : match_info.thisMinion, "QUADRA" : match_info.thisQuadra, "PENTA" : match_info.thisPenta, "DAMAGE_RATIO" : match_info.thisDamageRatio,
                      "DAMAGE_RATIO_ENCAISSE" : match_info.thisDamageTakenRatio, "CS/MIN": match_info.thisMinionPerMin, "AVANTAGE_VISION": match_info.thisVisionAdvantage,
                      "KP" : match_info.thisKP, "CS_AVANTAGE": match_info.thisCSAdvantageOnLane, "CS_APRES_10_MIN" : match_info.thisCSafter10min, 
                      "DMG_TOTAL" : match_info.match_detail_participants['totalDamageDealtToChampions'],
                      "ECART_LEVEL" : match_info.thisLevelAdvantage, "VISION/MIN" : match_info.thisVisionPerMin, 
                      "DOUBLE" : match_info.thisDouble, "TRIPLE" : match_info.thisTriple, "SERIE_VICTOIRE" : serie_victoire, "NB_COURONNE_1_GAME" : points }

        for key, value in dict_cumul.items():
            # records cumul
            try:
                old_value = int(records_cumul[key][summonerName.lower().replace(" ", "")])
                records_cumul[key][summonerName.lower().replace(" ", "")] = records_cumul[key][
                                                                                summonerName.lower().replace(" ",
                                                                                                             "")] + value[0]
                new_value = int(records_cumul[key][summonerName.lower().replace(" ", "")])
                
                # les paliers
                if succes is True and match_info.thisQ == "RANKED" and match_info.thisTime > 20:
                    for key2 in dict_cumul.keys():
                        exploits = palier(exploits, key, key2, old_value, new_value, value[1])

                                                
            except: # cela va retourner une erreur si c'est un nouveau joueur dans la bdd.
                records_cumul[key][summonerName.lower().replace(" ", "")] = value[0]
                
            # records personnels
        for key,value in personnel_cumul.items():
        
            try:
                if succes is True and match_info.thisQ == "RANKED" and match_info.thisTime > 20:
                    old_value = float(records_personnel[key][summonerName.lower().replace(" ", "")])
                    
                    for stats in personnel_cumul.keys():
                        if len(exploits2) < 900: # on ne peut pas dépasser 1024 caractères par embed
                            exploits2, records_personnel = score_personnel(exploits2, records_personnel, key, summonerName, stats, float(old_value), float(value))
                        elif len(exploits3) < 900:
                            exploits3, records_personnel = score_personnel(exploits3, records_personnel, key, summonerName, stats, float(old_value), float(value))
                        elif len(exploits4) < 900:
                            exploits4, records_personnel = score_personnel(exploits4, records_personnel, key, summonerName, stats, float(old_value), float(value))
                            
                        

                    
            except: # cela va retourner une erreur si c'est un nouveau joueur dans la bdd.
                records_personnel[key][summonerName.lower().replace(" ", "")] = value                 
                

        

        # Achievements
        if match_info.thisQ == "RANKED" and match_info.thisTime > 20 and succes is True:
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
                
            sauvegarde_bdd(records_cumul, 'records3')
            sauvegarde_bdd(records_personnel, 'records_personnel')


        sauvegarde_bdd(suivi, 'suivi') #achievements + suivi


                
        # observations
        
        embed.add_field(name="Game", value=f"[LeagueofGraph](https://www.leagueofgraphs.com/fr/match/euw/{str(match_info.last_match)[5:]}#participant{int(match_info.thisId)+1})") # ici, ça va de 1 à 10.. contrairement à Rito qui va de 1 à 9
        embed.add_field(name="OPGG", value=f"[Profil](https://euw.op.gg/summoners/euw/{summonerName})")
        embed.add_field(name="Stats", value=f"[{match_info.thisChampName}](https://lolalytics.com/lol/{match_info.thisChampName.lower()}/build/)")

        if match_info.thisPosition in ['SUPPORT', 'ADC', 'MID', 'JUNGLE'] and match_info.thisQ == "RANKED":
            embed.add_field(
                name="Durée de la game : " + str(int(match_info.thisTime)) + " minutes | Score (EXPERIMENTAL) : " + str(result),
                value=exploits, inline=False)
        else:
            embed.add_field(name="Durée de la game : " + str(int(match_info.thisTime)) + " minutes",
                            value=exploits, inline=False)
            

        if len(exploits2) > 5: # si plus de 15 lettres, alors il y a un exploit personnel
            embed.add_field(name="Statistiques personnelles : ", value=exploits2, inline=False)
        
        if len(exploits3) > 5: # si plus de 15 lettres, alors il y a un exploit personnel
            embed.add_field(name="Statistiques personnelles Part2: ", value=exploits3, inline=False)
        
        if len(exploits4) > 5: # si plus de 15 lettres, alors il y a un exploit personnel
            embed.add_field(name="Statistiques personnelles Part3: ", value=exploits4, inline=False)
            
        # Items :
        
        embed.add_field(name="Items :", value=match_info.data_item, inline=False)

        try:
            if int(match_info.thisDeaths) >= 1:  # KDA
                embed.add_field(name="KDA : " + str(match_info.thisKDA),
                                value=str(match_info.thisKills) + " | " + str(match_info.thisDeaths) + " | " + str(
                                    match_info.thisAssists) + "\n KP : " + str(match_info.thisKP) + "%",
                                inline=False)
            else:
                embed.add_field(name="KDA : Perfect KDA",
                                value=str(match_info.thisKills) + " | " + str(match_info.thisDeaths) + " | " + str(
                                    match_info.thisAssists) + "\n KP : " + str(match_info.thisKP) + "%",
                                inline=False)
        except Exception:
            embed.add_field(name="KDA : ", value=str(match_info.thisKills) + " | " + str(match_info.thisDeaths) + " | " + str(match_info.thisAssists),
                            inline=False)

        # CS
        if match_info.thisQ != "ARAM":
            embed.add_field(name="CS : " + str(match_info.thisMinion), value="minions par minute: " + str(
                match_info.thisMinionPerMin) + "\n Avantage maximal CS :" + str(match_info.thisCSAdvantageOnLane),
                            inline=False)
        else:
            embed.add_field(name="CS : " + str(match_info.thisMinion), value="minions par minute: " + str(match_info.thisMinionPerMin) ,inline=False)
        # Score de vision
        if match_info.thisQ != "ARAM":
            embed.add_field(
                name="Score de vision : " + str(match_info.thisVision) + " | Avantage : " + str(match_info.thisVisionAdvantage) + "%",
                value="Vision par minute : " + str(match_info.thisVisionPerMin) + "\nwards posées : " + str(match_info.thisWards) + "\n wards détruites : " + str(match_info.thisWardsKilled) +
                      "\n pinks achetées: " + str(match_info.thisPink), inline=False)
        # Golds
            embed.add_field(name="Golds gagnés : " + str(match_info.thisGold), value="golds par minute: " + str(match_info.thisGoldPerMinute),
                        inline=False)
        # Dmg
        embed.add_field(name="DMG deal : " + str(match_info.thisDamage) + " (" + str(match_info.thisDamageRatio) + "%) | AD : " + str(match_info.thisDamageAD) + " | AP : " + str(match_info.thisDamageAP) + " | True : " + str(match_info.thisDamageTrue),
                        value="Dégats par minutes : " + str(
                            round(match_info.thisDamagePerMinute, 0)) + "\n Double : " + str(match_info.thisDouble) + " | Triple : " + str(
                            match_info.thisTriple) + " | Quadra : " + str(match_info.thisQuadra) + " | Penta : " + str(
                            match_info.thisPenta) + "\n SoloKills : " + str(match_info.thisSoloKills),
                        inline=False)
        embed.add_field(name="DMG reçus : " + str(match_info.thisDamageTaken) + " (" + str(match_info.thisDamageTakenRatio) + "%) | AD : " + str(match_info.thisDamageTakenAD) + " | AP : " + str(match_info.thisDamageTakenAP) + " | True : " + str(match_info.thisDamageTakenTrue),
                        value="Dégats réduits : " + str(match_info.thisDamageSelfMitigatedFormat), inline=False)
        

        # Objectifs
        if match_info.thisQ != "ARAM":
            embed.add_field(name="Objectifs :", value=f"Herald : {match_info.thisHeraldTeam} | Dragon :  {match_info.thisDragonTeam}\nBaron : {match_info.thisBaronTeam} (Participation : {match_info.thisBaronPerso})| Elder : {match_info.thisElderPerso}\n Towers : {match_info.thisTurretsKillsTeam} détruites (Participation : {match_info.thisTurretsKillsPerso}) | {match_info.thisTurretsLost} perdues \nDmg tower : {match_info.thisDamageTurrets} | Dmg objectifs : {match_info.thisDamageObjectives} ", inline=False  )
        

        # Stats soloq :
        if match_info.thisQ == "RANKED" or match_info.thisQ == "FLEX":
            if match_info.thisRank == 'En placement':
                embed.add_field(name="Current rank", value=match_info.thisRank, inline=False)
            else:
                embed.add_field(name="Current rank : " + match_info.thisTier + " " + match_info.thisRank + " - " + match_info.thisLP + "LP" + " (" + difLP + ")",
                                value="Winrate: " + match_info.thisWinrateStat + "%" + "\n Victoires : " + match_info.thisVictory +
                                      " | Defaites : " + match_info.thisLoose,
                                inline=False)
        
        # Gestion des bo    
            if int(match_info.thisLP) == 100:
                bo = match_info.thisStats[match_info.i]['miniSeries']
                bo_wins = str(bo['wins'])
                bo_losses = str(bo['losses'])
                bo_progress = str(bo['progress'])
                embed.add_field(name=f'Bo5', value=f'Victoires : {bo_wins} | Defaites : {bo_losses} \nProgress : {bo_progress}', inline=False) 
                
        embed.add_field(name=f"Blue Side ({match_info.thisGold_team1} Golds)",
                        value=str(match_info.thisPseudoListe[0]) + " (" + str(match_info.thisChampName1) + ") - " + str(
                            match_info.thisKillsListe[0]) + "/" + str(
                            match_info.thisDeathsListe[0]) + "/" + str(match_info.thisAssistsListe[0]) + "\n" +
                              str(match_info.thisPseudoListe[1]) + " (" + str(match_info.thisChampName2) + ") - " + str(
                            match_info.thisKillsListe[1]) + "/" + str(
                            match_info.thisDeathsListe[1]) + "/" + str(match_info.thisAssistsListe[1]) + "\n" +
                              str(match_info.thisPseudoListe[2]) + " (" + str(match_info.thisChampName3) + ") - " + str(
                            match_info.thisKillsListe[2]) + "/" + str(
                            match_info.thisDeathsListe[2]) + "/" + str(match_info.thisAssistsListe[2]) + "\n" +
                              str(match_info.thisPseudoListe[3]) + " (" + str(match_info.thisChampName4) + ") - " + str(
                            match_info.thisKillsListe[3]) + "/" + str(
                            match_info.thisDeathsListe[3]) + "/" + str(match_info.thisAssistsListe[3]) + "\n" +
                              str(match_info.thisPseudoListe[4]) + " (" + str(match_info.thisChampName5) + ") - " + str(
                            match_info.thisKillsListe[4]) + "/" + str(
                            match_info.thisDeathsListe[4]) + "/" + str(match_info.thisAssistsListe[4]), inline=True)
        embed.add_field(name=f"Red Side ({match_info.thisGold_team2} Golds)",
                        value=str(match_info.thisPseudoListe[5]) + " (" + str(match_info.thisChampName6) + ") - " + str(
                            match_info.thisKillsListe[5]) + "/" + str(
                            match_info.thisDeathsListe[5]) + "/" + str(
                            match_info.thisAssistsListe[5]) + "\n" +
                              str(match_info.thisPseudoListe[6]) + " (" + str(match_info.thisChampName7) + ") - " + str(
                            match_info.thisKillsListe[6]) + "/" + str(
                            match_info.thisDeathsListe[6]) + "/" + str(
                            match_info.thisAssistsListe[6]) + "\n" +
                              str(match_info.thisPseudoListe[7]) + " (" + str(match_info.thisChampName8) + ") - " + str(
                            match_info.thisKillsListe[7]) + "/" + str(
                            match_info.thisDeathsListe[7]) + "/" + str(
                            match_info.thisAssistsListe[7]) + "\n" +
                              str(match_info.thisPseudoListe[8]) + " (" + str(match_info.thisChampName9) + ") - " + str(
                            match_info.thisKillsListe[8]) + "/" + str(
                            match_info.thisDeathsListe[8]) + "/" + str(
                            match_info.thisAssistsListe[8]) + "\n" +
                              str(match_info.thisPseudoListe[9]) + " (" + str(match_info.thisChampName10) + ") - " + str(
                            match_info.thisKillsListe[9]) + "/" + str(
                            match_info.thisDeathsListe[9]) + "/" + str(match_info.thisAssistsListe[9]),
                        inline=True)
        
        
        url_champion = f'https://raw.githubusercontent.com/Tomlora/MarinSlash/main/img/champions/{match_info.thisChampName}.png'
        embed.set_thumbnail(url=url_champion)

        embed.set_footer(text=f'Version {main.Var_version} by Tomlora - Match {str(match_info.last_match)}')



        return embed, match_info.thisQ

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

        id_data = lire_bdd('tracker', 'dict')
        suivirank = lire_bdd('suivi', 'dict')

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
                        channel_tracklol = self.bot.get_channel(int(main.chan_tracklol))   
                        if dict_rankid[rank_old] > dict_rankid[level]:  # 19 > 18
                            await channel_tracklol.send(f' Le joueur {key} a démote du rank {rank_old} à {level}')
                            await channel_tracklol.send(file=discord.File('./img/notstonks.jpg'))
                        elif dict_rankid[rank_old] < dict_rankid[level]:
                            await channel_tracklol.send(f' Le joueur {key} a été promu du rank {rank_old} à {level}')
                            await channel_tracklol.send(file=discord.File('./img/stonks.jpg'))
                        
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
                

        sauvegarde_bdd(suivirank, 'suivi')

    @cog_ext.cog_slash(name="game",
                       description="Voir les statistiques d'une games",
                       options=[create_option(name="summonername", description= "Nom du joueur", option_type=3, required=True),
                                create_option(name="numerogame", description="Numero de la game, de 0 à 100", option_type=4, required=True),
                                create_option(name="succes", description="Faut-il la compter dans les records/achievements ? True = Oui / False = Non", option_type=5, required=True)])
    async def game(self, ctx, summonername:str, numerogame:int, succes: bool):
        
        await ctx.defer(hidden=False)
        
        summonername = summonername.lower()

        embed, mode_de_jeu = self.printInfo(summonerName=summonername.lower(), idgames=int(numerogame), succes=succes)

        if embed != {}:
            await ctx.send(embed=embed)
            
            
    @cog_ext.cog_slash(name="game_multi",
                       description="Voir les statistiques d'une games",
                       options=[create_option(name="summonername", description= "Nom du joueur", option_type=3, required=True),
                                create_option(name="debut", description="Numero de la game, de 0 à 100", option_type=4, required=True),
                                create_option(name="fin", description="Numero de la game, de 0 à 100", option_type=4, required=True),
                                create_option(name="succes", description="Faut-il la compter dans les records/achievements ? True = Oui / False = Non", option_type=5, required=True)])        
    async def game_multi(self, ctx, summonername:str, debut:int, fin:int, succes: bool):
        
        await ctx.defer(hidden=False)
        
        for i in range(fin, debut, -1):
            
            summonername = summonername.lower()

            embed, mode_de_jeu = self.printInfo(summonerName=summonername.lower(), idgames=int(i), succes=succes)

            if embed != {}:
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"La game {str(i)} n'a pas été comptabilisée")
                
            time.sleep(5)
               

    async def printLive(self, summonername):
        
        summonername = summonername.lower()
        
        embed, mode_de_jeu = self.printInfo(summonerName=summonername, idgames=0, succes=True)
        
        if mode_de_jeu in ['RANKED', 'FLEX']:
            channel_tracklol = self.bot.get_channel(int(main.chan_tracklol))
        else:
            channel_tracklol = self.bot.get_channel(int(main.chan_lol_others))   
        
        if embed != {}:
            await channel_tracklol.send(embed=embed)


    async def update(self):
        data = lire_bdd('tracker', 'dict')
        for key, value in data.items():
            if str(value['id']) != getId(key):  # value -> ID de dernière game enregistrée dans id_data != ID de la dernière game via l'API Rito / #key = pseudo // value = numéro de la game
                try:
                    await self.printLive(key)
                except:
                    print(f"Message non envoyé car le joueur {key} a fait une partie avec moins de 10 joueurs ou un mode désactivé")
                    # print(sys.exc_info())
                    # raise
                data[key]['id'] = getId(key)
        data = pd.DataFrame.from_dict(data, orient="index", columns=['id'])
        sauvegarde_bdd(data, 'tracker')

    @cog_ext.cog_slash(name="loladd",description="Ajoute le joueur au suivi",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    async def loladd(self, ctx, *, summonername):
        # try:
            data = lire_bdd('tracker', 'dict')
            data[summonername.lower().replace(" ", "")] = {'id' : getId(
                summonername)}  # ajout du pseudo (clé) et de l'id de la dernière game(getId)
            data = pd.DataFrame.from_dict(data, orient="index", columns=['id'])
            sauvegarde_bdd(data, 'tracker')

            await ctx.send(summonername + " was successfully added to live-feed!")
        # except:
            # await ctx.send("Oops! There is no summoner with that name!")

    @cog_ext.cog_slash(name="lolremove", description="Supprime le joueur du suivi",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    async def lolremove(self, ctx, *, summonername):
        data = lire_bdd('tracker', 'dict')
        if summonername.lower().replace(" ", "") in data: del data[summonername.lower().replace(" ",
                                                                                                "")]  # si le pseudo est présent dans la data, on supprime la data de ce pseudo
        data = pd.DataFrame.from_dict(data, orient="index", columns=['id'])
        sauvegarde_bdd(data, 'tracker')

        await ctx.send(summonername + " was successfully removed from live-feed!")

    @cog_ext.cog_slash(name='lollist', description='Affiche la liste des joueurs suivis')
    async def lollist(self, ctx):

        data = lire_bdd('tracker', 'dict')
        response = ""

        for key in data.keys():
            response += key.upper() + ", "

        response = response[:-2]
        embed = discord.Embed(title="Live feed list", description=response, colour=discord.Colour.blurple())

        await ctx.send(embed=embed)

    @cog_ext.cog_slash(name="get_matchId",description="Réservé au propriétaire du bot",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    @main.isOwner2_slash()
    async def get_matchId(self, ctx, summonername):
        me = lol_watcher.summoner.by_name(my_region, summonername)
        my_matches = lol_watcher.match.matchlist_by_puuid(region, me['puuid'])
        last_match = my_matches[0]
        match_detail = lol_watcher.match.by_id(region, last_match)
        await ctx.send(last_match)
        # await ctx.send(match_detail['info']['gameId'])

        



    @tasks.loop(hours=1, count=None)
    async def lolsuivi(self):

        currentHour = str(datetime.datetime.now().hour)

        if currentHour == str(0):
            
            # le suivi est déjà maj par game/update... Pas besoin de le refaire ici..

            suivi = lire_bdd('suivi', 'dict')
            suivi_24h = lire_bdd('suivi_24h', 'dict')

            df = pd.DataFrame.from_dict(suivi)
            df = df.transpose().reset_index()
            

            df_24h = pd.DataFrame.from_dict(suivi_24h)
            df_24h = df_24h.transpose().reset_index()

            
            df = df[df['tier'] != 'Non-classe'] # on supprime les non-classés
            
            df_24h = df_24h[df_24h['tier'] != 'Non-classe'] # on supprime les non-classés
            

            # Pour l'ordre de passage
            df['tier_pts'] = 0
            df['tier_pts'] = np.where(df.tier == 'BRONZE', 1, df.tier_pts)
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
            


            for key in joueur.values():
                
                if suivi[key]['rank'] != "Non-classe":

                    try:
                        # suivi est mis à jour par update et updaterank. On va donc prendre le comparer à suivi24h
                        wins = int(suivi_24h[key]['wins'])
                        losses = int(suivi_24h[key]['losses'])
                        nbgames = wins + losses
                        LP = int(suivi_24h[key]['LP'])
                        tier_old = str(suivi_24h[key]['tier'])
                        rank_old = str(suivi_24h[key]['rank'])
                        classement_old = tier_old + " " + rank_old
                    except:
                        wins = 0
                        losses = 0
                        nbgames = 0
                        LP = 0

                    # on veut les stats soloq

                    tier = str(suivi[key]['tier'])
                    rank = str(suivi[key]['rank'])
                    classement_new = tier + " " + rank

                    difwins = int(suivi[key]['wins']) - wins
                    diflosses = int(suivi[key]['losses']) - losses
                    difLP = int(suivi[key]['LP']) - LP
                    totalwin = totalwin + difwins
                    totaldef = totaldef + diflosses
                    totalgames = totalwin + totaldef
                    
                    # evolution

                    if dict_rankid[classement_old] > dict_rankid[classement_new]: # 19-18
                        difLP = 100 + LP - int(suivi[key]['LP'])
                        difLP = "Démote / -" + str(difLP)
                        emote = ":arrow_down:"

                    elif dict_rankid[classement_old] < dict_rankid[classement_new]:
                        difLP = 100 - LP + int(suivi[key]['LP'])
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

                else:
                    suivi[key]["tier"] = "Non-classe"

                sauvegarde_bdd(suivi, 'suivi_24h')

            channel_tracklol = self.bot.get_channel(int(main.chan_tracklol))   

            await channel_tracklol.send(embed=embed)
            await channel_tracklol.send(f'Sur {totalgames} games -> {totalwin} victoires et {totaldef} défaites')
      
        

    @commands.command()
    @main.isOwner2()
    async def spectator(self, ctx, *, summonerName):
        try:
            match = match_spectator(summonerName)
            print(match['participants'])
            await ctx.send('Fait !')
        except:
            await ctx.send("Tu n'es pas en match.")     
        
    @cog_ext.cog_slash(name="abbedagge", description="Meilleur joueur de LoL")
    async def abbedagge(self, ctx):
        await ctx.send('https://clips.twitch.tv/ShakingCovertAuberginePanicVis-YDRK3JFk7Glm6nbB')
        



def setup(bot):
    bot.add_cog(LeagueofLegends(bot))
