from discord.ext import commands, tasks

import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import plotly.graph_objects as go
from plotly.graph_objs import Layout
import plotly.express as px
import sys


import pandas as pd
import main
import datetime
import numpy as np
import warnings
from cogs.achievements_scoringlol import scoring

from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd, get_data_bdd, requete_perso_bdd, lire_bdd_perso
from fonctions.match import matchlol, getId, dict_rankid, lol_watcher, my_region
from discord_slash import cog_ext
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option
from fonctions.channels_discord import chan_discord

from time import sleep


warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'

import os

# Paramètres LoL
version = lol_watcher.data_dragon.versions_for_region(my_region)
champions_versions = version['n']['champion']

def get_image(type, name, resize_x=80, resize_y=80):
    if type == "champion":
        url = (f"https://raw.githubusercontent.com/Tomlora/MarinSlash/main/img/champions/{name}.png"
        )
        response = requests.get(url)
        if response.status_code != 200:
            img = Image.new("RGB", (resize_x, resize_y))
        else:
            img = Image.open(BytesIO(response.content))
            img = img.resize((resize_x, resize_y))
        return img

    elif type == "tier":
        img = Image.open(f"./img/{name}.png")
        img = img.resize((resize_x, resize_y))
        return img
    
    elif type == "avatar":
        url = (f"https://ddragon.leagueoflegends.com/cdn/12.6.1/img/profileicon/{name}.png")
        response = requests.get(url)
        if response.status_code != 200:
            img = Image.new("RGB", (resize_x, resize_y))
        else:
            img = Image.open(BytesIO(response.content))
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


def records_check(fichier, key_boucle, key: str, Score_check: float, thisChampName, summonerName, embed, url, saison:int, mode:str):
    mode = mode.lower()
    if str(key_boucle) == str(key):
        if str(key) in ['EARLY_DRAKE', 'EARLY_BARON'] and Score_check > 0: # ici on veut le plus faible et pas égale à 0
            if float(fichier[key]['Score']) > Score_check:
                ancien_score = fichier[key]['Score']
                detenteur_ancien_score = fichier[key]['Joueur']
                requete_perso_bdd('''UPDATE records
	            SET "Score"= :score, "Champion"= :champion, "Joueur"= :joueur, url= :url
	            WHERE index = :record and saison = :saison and mode = :mode;''', {'record' : key, 'score' : Score_check, 'champion' : thisChampName, 'joueur' : summonerName, 'url' : url, 'saison' : saison, 'mode' : mode })
                # Annonce que le record a été battu :
                embed = embed + f"\n ** :boom: Record {str(key).lower()} battu avec {Score_check} ** (Ancien : {ancien_score} par {detenteur_ancien_score})"

        else:
        # si le record est battu, on fait les modifs nécessaires:
            if float(fichier[key]['Score']) < Score_check:
                ancien_score = fichier[key]['Score']
                detenteur_ancien_score = fichier[key]['Joueur']
                requete_perso_bdd('''UPDATE records
	            SET "Score"= :score, "Champion"= :champion, "Joueur"= :joueur, url= :url
	            WHERE index= :record and saison = :saison and mode =:mode;''', {'record' : key, 'score' : Score_check, 'champion' : thisChampName, 'joueur' : summonerName, 'url' : url, 'saison' : saison, 'mode' : mode })

                embed = embed + f"\n ** :boom: Record {str(key).lower()} battu avec {Score_check} ** (Ancien : {ancien_score} par {detenteur_ancien_score})"


    return embed

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

def score_personnel(embed, key:str, summonerName:str, stats:str, old_value:float, new_value:float, url):
    if key == stats:
        if old_value < new_value:
            requete_perso_bdd(f'''UPDATE records_personnel
	SET "{key}" = :key_value, "{key + '_url'}" = :key_url_value 
	WHERE index = :joueur''', {'key_value' : new_value, 'key_url_value' : url, 'joueur' : summonerName.lower() })
            embed = embed + f"\n ** :military_medal: Tu as battu ton record personnel en {stats.lower()} avec {new_value} {stats.lower()} ** (Anciennement : {old_value})"
    return embed

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
                

class LeagueofLegends(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.my_task.start()
        self.lolsuivi.start()
        
 
    def printInfo(self, summonerName, idgames: int, succes):



        match_info = matchlol(summonerName, idgames) #class
        
        
        if match_info.thisQId == 900: #urf 
            return {}, 'URF'
        
        if match_info.thisQId == 840:
            return {}, 'Bot' # bot game
        
        
        url_game = f'https://www.leagueofgraphs.com/fr/match/euw/{str(match_info.last_match)[5:]}#participant{int(match_info.thisId)+1}'

        
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

        if (match_info.thisQ == "RANKED" and match_info.thisTime > 20) or (match_info.thisQ == "ARAM" and match_info.thisTime > 10):
            

            records = lire_bdd_perso('SELECT index, "Score", "Champion", "Joueur", url from records where saison= %(saison)s and mode=%(mode)s', params={'saison' : match_info.season,
                                                                                                                                             'mode' : match_info.thisQ.lower()})
            records = records.to_dict()
            
            for key, value in records.items():
                if int(match_info.thisDeaths) >= 1:

                    exploits = records_check(records, key, 'KDA',
                                            float(match_info.thisKDA),
                                            match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                else:
                    exploits = records_check(records, key, 'KDA',
                                            float(
                                                round((int(match_info.thisKills) + int(match_info.thisAssists)) / (int(match_info.thisDeaths) + 1), 2)),
                                            match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                exploits = records_check(records, key, 'KP', match_info.thisKP,
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'CS', match_info.thisMinion,
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'CS/MIN', match_info.thisMinionPerMin,
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'KILLS', match_info.thisKills,
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DEATHS', match_info.thisDeaths,
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'ASSISTS', match_info.thisAssists,
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                
                if match_info.thisQ == "RANKED" :
                    exploits = records_check(records, key, 'WARDS_SCORE', match_info.thisVision,
                                            match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'WARDS_POSEES', match_info.thisWards,
                                            match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'WARDS_DETRUITES', match_info.thisWardsKilled,
                                            match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'WARDS_PINKS', match_info.thisPink,
                                            match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'BUFFS_VOLEES', match_info.thisbuffsVolees,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'TOWER_PLATES', match_info.thisTurretPlatesTaken,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'ECART_LEVEL', match_info.thisLevelAdvantage,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'EARLY_DRAKE', match_info.earliestDrake,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'EARLY_BARON', match_info.earliestBaron,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'CS_AVANTAGES', match_info.thisCSAdvantageOnLane,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'CS_APRES_10_MIN', match_info.thisCSafter10min,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    
                    if match_info.thisPosition == "SUPPORT":
                        exploits = records_check(records, key, 'AVANTAGE_VISION_SUPPORT', float(match_info.thisVisionAdvantage),
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    
                    else:
                        exploits = records_check(records, key, 'AVANTAGE_VISION', float(match_info.thisVisionAdvantage),
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                        
                exploits = records_check(records, key, 'DEGATS_INFLIGES',
                                        match_info.match_detail_participants['totalDamageDealtToChampions'],
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, '% DMG', match_info.thisDamageRatio,
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DOUBLE', match_info.thisDouble,
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'TRIPLE', match_info.thisTriple,
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'QUADRA', match_info.thisQuadra,
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'PENTA', match_info.thisPenta,
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DUREE_GAME', match_info.thisTime,
                                        match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'ALLIE_FEEDER', match_info.thisAllieFeeder,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                

                    
                if match_info.thisChampName != "Zeri": # on supprime Zeri de ce record qui est impossible à égaler avec d'autres champions
                    exploits = records_check(records, key, 'SPELLS_USED',
                                                 match_info.thisSpellUsed,
                                                 match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                exploits = records_check(records, key, 'SPELLS_EVITES', match_info.thisSpellsDodged,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                exploits = records_check(records, key, 'SOLOKILLS', match_info.thisSoloKills,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                exploits = records_check(records, key, 'NB_SERIES_DE_KILLS', match_info.thisKillingSprees,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DOMMAGES_TANK',
                                             int(match_info.match_detail_participants['totalDamageTaken']),
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DOMMAGES_TANK%', match_info.thisDamageTakenRatio,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DOMMAGES_REDUITS', match_info.thisDamageSelfMitigated,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DOMMAGES_TOWER', match_info.thisDamageTurrets,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'GOLDS_GAGNES', match_info.thisGoldEarned,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'SERIES_DE_KILLS', match_info.thisKillsSeries,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'TOTAL_HEALS',
                                             match_info.thisTotalHealed,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'HEALS_SUR_ALLIES', match_info.thisTotalOnTeammates,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                
                if match_info.thisChampName != "Zeri": # champion désactivé pour ce record
                    exploits = records_check(records, key, 'SKILLSHOTS_HIT', match_info.thisSkillshot_hit,
                                                match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    
                exploits = records_check(records, key, 'SKILLSHOTS_DODGES', match_info.thisSkillshot_dodged,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                exploits = records_check(records, key, 'SHIELD', match_info.thisTotalShielded,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                       
                   
        # on le fait après sinon ça flingue les records
        match_info.thisDamageTurrets = "{:,}".format(match_info.thisDamageTurrets).replace(',', ' ').replace('.', ',')

        # couleur de l'embed en fonction du pseudo

        pseudo = str(summonerName).lower()

        try:
            data = get_data_bdd(f'SELECT "R", "G", "B" from tracker WHERE index= :index', {'index' : pseudo} ).fetchall()
            color = discord.Color.from_rgb(data[0][0], data[0][1], data[0][2])
            
        except:
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

        if match_info.thisQ == 'ARAM':
            
            settings = lire_bdd_perso(f'SELECT index, score_aram as score from achievements_settings')
        else:
            settings = lire_bdd_perso(f'SELECT index, score as score from achievements_settings')   
             
    
        settings = settings.to_dict()

        records_cumul = lire_bdd('records3', 'dict')
        records_personnel = lire_bdd('records_personnel', 'dict')
        
        if match_info.thisQ == 'RANKED':
            if int(match_info.thisLevelAdvantage) >= settings['Ecart_Level']['score']:
                exploits = exploits + f"\n ** :crown: :wave: Tu as au moins {match_info.thisLevelAdvantage} niveaux d'avance sur ton adversaire durant la game**"
                points = points + 1
            
            if (float(match_info.thisVisionAdvantage) >= settings['Avantage_vision(support)']['score'] and str(match_info.thisPosition) == "SUPPORT") or (float(match_info.thisVisionAdvantage) >= settings['Avantage_vision(autres)']['score'] and str(match_info.thisPosition) != "SUPPORT"):
                exploits = exploits + f"\n ** :crown: :eye: Ce joueur a un gros avantage de vision sur son adversaire avec {match_info.thisVisionAdvantage}% **"
                points = points + 1
                
            if (float(match_info.thisDragonTeam) >= settings['Dragon']['score']):
                exploits = exploits + f"\n ** :crown: :dragon: Tu as obtenu l'âme du dragon **"
                points = points + 1
                
            if (int(match_info.thisDanceHerald) >= 1):
                exploits = exploits + f"\n ** :crown: :dancer: A dansé avec l'Herald **"
                points = points + 1
                
            if (int(match_info.thisPerfectGame) >= 1):
                exploits = exploits + f"\n :crown: :crown: :sunny: Perfect Game"
                points = points + 2

            if int(match_info.thisDeaths) == int(settings['Ne_pas_mourir']['score']):
                exploits = exploits + "\n ** :crown: :heart: Ce joueur n'est pas mort de la game ** \n ** :crown: :star: Ce joueur a un PERFECT KDA **"
                points = points + 2
                
            if float(match_info.thisVisionPerMin) >= settings['Vision/min(support)']['score'] and str(match_info.thisPosition) == "SUPPORT":
                exploits = exploits + f"\n ** :crown: :eye: Ce joueur a un gros score de vision avec {match_info.thisVisionPerMin} / min **"
                points = points + 1

            if int(match_info.thisVisionPerMin) >= settings['Vision/min(autres)']['score'] and str(match_info.thisPosition) != "SUPPORT":
                exploits = exploits + f"\n ** :crown: :eye: Ce joueur a un gros score de vision avec {match_info.thisVisionPerMin} / min **"
                points = points + 1
                
            if int(match_info.thisSoloKills) >= settings['Solokills']['score']:
                exploits = exploits + f"\n ** :crown: :muscle: Ce joueur a réalisé {match_info.thisSoloKills} solokills **"
                points = points + 1
                
            if int(match_info.thisCSAdvantageOnLane) >= settings['CSAvantage']['score']:
                exploits = exploits + f"\n ** :crown: :ghost: Tu as plus de {match_info.thisCSAdvantageOnLane} CS d'avance sur ton adversaire durant la game**"
                points = points + 1
                
                
        if float(match_info.thisKDA) >= settings['KDA']['score']:
                exploits = exploits + f"\n ** :crown: :star: Ce joueur a un bon KDA avec un KDA de {match_info.thisKDA} **"
                points = points + 1
                
        if int(match_info.thisKP) >= settings['KP']['score']:
            exploits = exploits + f"\n ** :crown: :dagger: Ce joueur a participé à énormément de kills dans son équipe avec {match_info.thisKP} % **"
            points = points + 1

        if int(match_info.thisPenta) >= settings['Pentakill']['score']:
                exploits = exploits + f"\n ** :crown: :five: Ce joueur a pentakill ** {match_info.thisPenta} fois"
                points = points + (1 * int(match_info.thisPenta))

        if int(match_info.thisQuadra) >= settings['Quadrakill']['score']:
                exploits = exploits + f"\n ** :crown: :four: Ce joueur a quadrakill ** {match_info.thisQuadra} fois"
                points = points + (1 * int(match_info.thisQuadra))

        if int(match_info.thisMinionPerMin) >= settings['CS/min']['score']:
            exploits = exploits + f"\n ** :crown: :ghost: Ce joueur a bien farm avec {match_info.thisMinionPerMin} CS / min **"
            points = points + 1

        if int(match_info.thisDamageRatio) >= settings['%_dmg_équipe']['score']:
            exploits = exploits + f"\n ** :crown: :dart: Ce joueur a infligé beaucoup de dmg avec {match_info.thisDamageRatio}%  pour son équipe **"
            points = points + 1

        if int(match_info.thisDamageTakenRatio) >= settings['%_dmg_tank']['score']:
            exploits = exploits + f"\n ** :crown: :shield: Ce joueur a bien tank pour son équipe avec {match_info.thisDamageTakenRatio}% **"
            points = points + 1

        if int(match_info.thisTotalOnTeammates) >= settings['Total_Heals_sur_alliés']['score']:
            exploits = exploits + f"\n ** :crown: :heart: Ce joueur a heal plus de {match_info.thisTotalOnTeammatesFormat} sur ses alliés **"
            points = points + 1
            
        if (int(match_info.thisTotalShielded) >= settings['Shield']['score']):
            exploits = exploits + f"\n ** :crown: :shield: Tu as shield {match_info.thisTotalShielded} **"
            
            
        # Présence d'afk    
        if match_info.AFKTeam >= 1:
            exploits = exploits + "\n ** :tired_face: Tu as eu un afk dans ton équipe :'( **"
            
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
        
        if match_info.thisQ == 'ARAM':
            dict_cumul = {"SOLOKILLS_ARAM": [match_info.thisSoloKills, np.arange(100, 1000, 100, int).tolist()], 
                        "NBGAMES_ARAM": [1, np.arange(50, 1000, 50, int).tolist()], 
                        "DUREE_GAME_ARAM": [match_info.thisTime / 60, np.arange(500, 10000, 500, int).tolist()],
                        "KILLS_ARAM": [match_info.thisKills, np.arange(500, 10000, 500, int).tolist()],
                        "DEATHS_ARAM": [match_info.thisDeaths, np.arange(500, 10000, 500, int).tolist()],
                        "ASSISTS_ARAM": [match_info.thisAssists, np.arange(500, 10000, 500, int).tolist()],
                        "CS_ARAM" : [match_info.thisMinion, np.arange(10000, 100000, 10000, int).tolist()],
                        "DOUBLE_ARAM" : [match_info.thisDouble, np.arange(5, 100, 5, int).tolist()],
                        "TRIPLE_ARAM" : [match_info.thisTriple, np.arange(5, 100, 5, int).tolist()],
                        "QUADRA_ARAM" : [match_info.thisQuadra, np.arange(5, 100, 5, int).tolist()],
                        "PENTA_ARAM" : [match_info.thisPenta, np.arange(5, 100, 5, int).tolist()]}
            
        else:
            dict_cumul = {"SOLOKILLS": [match_info.thisSoloKills, np.arange(100, 1000, 100, int).tolist()], 
                        "NBGAMES": [1, np.arange(50, 1000, 50, int).tolist()], 
                        "DUREE_GAME": [match_info.thisTime / 60, np.arange(500, 10000, 500, int).tolist()],
                        "KILLS": [match_info.thisKills, np.arange(500, 10000, 500, int).tolist()],
                        "DEATHS": [match_info.thisDeaths, np.arange(500, 10000, 500, int).tolist()],
                        "ASSISTS": [match_info.thisAssists, np.arange(500, 10000, 500, int).tolist()],
                        "WARDS_SCORE": [match_info.thisVision, np.arange(500,10000,500, int).tolist()],
                        "WARDS_POSEES": [match_info.thisWards, np.arange(500, 10000, 500, int).tolist()],
                        "WARDS_DETRUITES": [match_info.thisWardsKilled, np.arange(500, 10000, 500, int).tolist()],
                        "WARDS_PINKS": [match_info.thisPink, np.arange(500,10000, 500, int).tolist()],
                        "CS" : [match_info.thisMinion, np.arange(10000, 100000, 10000, int).tolist()],
                        "QUADRA" : [match_info.thisQuadra, np.arange(5, 100, 5, int).tolist()],
                        "PENTA" : [match_info.thisPenta, np.arange(5, 100, 5, int).tolist()]}
        
        if match_info.thisQ == 'ARAM':
            metrics_personnel = {"SOLOKILLS_ARAM": match_info.thisSoloKills, "DUREE_GAME_ARAM": match_info.thisTime, "KILLS_ARAM": match_info.thisKills,
                        "DEATHS_ARAM": match_info.thisDeaths, "ASSISTS_ARAM": match_info.thisAssists, 
                        "CS_ARAM" : match_info.thisMinion, "QUADRA_ARAM" : match_info.thisQuadra, "PENTA_ARAM" : match_info.thisPenta, "DAMAGE_RATIO_ARAM" : match_info.thisDamageRatio,
                        "DAMAGE_RATIO_ENCAISSE_ARAM" : match_info.thisDamageTakenRatio, "CS/MIN_ARAM": match_info.thisMinionPerMin, 
                        "KP_ARAM" : match_info.thisKP,  
                        "DMG_TOTAL_ARAM" : match_info.match_detail_participants['totalDamageDealtToChampions'],
                        "DOUBLE_ARAM" : match_info.thisDouble, "TRIPLE_ARAM" : match_info.thisTriple, "NB_COURONNE_1_GAME_ARAM" : points, "SHIELD_ARAM" : match_info.thisTotalShielded,
                        "ALLIE_FEEDER_ARAM" : match_info.thisAllieFeeder}
        else:
            metrics_personnel = {"SOLOKILLS": match_info.thisSoloKills, "DUREE_GAME": match_info.thisTime, "KILLS": match_info.thisKills,
                        "DEATHS": match_info.thisDeaths, "ASSISTS": match_info.thisAssists, "WARDS_SCORE": match_info.thisVision,
                        "WARDS_POSEES": match_info.thisWards, "WARDS_DETRUITES": match_info.thisWardsKilled, "WARDS_PINKS": match_info.thisPink,
                        "CS" : match_info.thisMinion, "QUADRA" : match_info.thisQuadra, "PENTA" : match_info.thisPenta, "DAMAGE_RATIO" : match_info.thisDamageRatio,
                        "DAMAGE_RATIO_ENCAISSE" : match_info.thisDamageTakenRatio, "CS/MIN": match_info.thisMinionPerMin, "AVANTAGE_VISION": match_info.thisVisionAdvantage,
                        "KP" : match_info.thisKP, "CS_AVANTAGE": match_info.thisCSAdvantageOnLane, "CS_APRES_10_MIN" : match_info.thisCSafter10min, 
                        "DMG_TOTAL" : match_info.match_detail_participants['totalDamageDealtToChampions'],
                        "ECART_LEVEL" : match_info.thisLevelAdvantage, "VISION/MIN" : match_info.thisVisionPerMin, 
                        "DOUBLE" : match_info.thisDouble, "TRIPLE" : match_info.thisTriple, "SERIE_VICTOIRE" : serie_victoire, "NB_COURONNE_1_GAME" : points, "SHIELD" : match_info.thisTotalShielded,
                        "ALLIE_FEEDER" : match_info.thisAllieFeeder}


        for key, value in dict_cumul.items():

            old_value = int(records_cumul[key][summonerName.lower().replace(" ", "")])
            records_cumul[key][summonerName.lower().replace(" ", "")] = records_cumul[key][
                                                                                summonerName.lower().replace(" ",
                                                                                                             "")] + value[0]
            new_value = int(records_cumul[key][summonerName.lower().replace(" ", "")])
                
            # les paliers
            if (succes is True and match_info.thisQ == "RANKED" and match_info.thisTime > 20) or (match_info.thisQ == "ARAM" and match_info.thisTime > 10):
                for key2 in dict_cumul.keys():
                    exploits = palier(exploits, key, key2, old_value, new_value, value[1])


                
        if (succes is True and match_info.thisQ == "RANKED" and match_info.thisTime > 20) or (match_info.thisQ == "ARAM" and match_info.thisTime > 10):
            sauvegarde_bdd(records_cumul, 'records3')

                
            # records personnels
        for key,value in metrics_personnel.items():
        

            if (succes is True and match_info.thisQ == "RANKED" and match_info.thisTime > 20) or (match_info.thisQ == 'ARAM' and match_info.thisTime > 10):
                old_value = float(records_personnel[summonerName.lower().replace(" ", "")][key])
                    
                for stats in metrics_personnel.keys():
                    if len(exploits2) < 900: # on ne peut pas dépasser 1024 caractères par embed
                                exploits2 = score_personnel(exploits2, key, summonerName, stats, float(old_value), float(value), url_game)
                    elif len(exploits3) < 900:
                                exploits3 = score_personnel(exploits3, key, summonerName, stats, float(old_value), float(value), url_game)
                    elif len(exploits4) < 900:
                                exploits4 = score_personnel(exploits4, key, summonerName, stats, float(old_value), float(value), url_game)
                            

             
        # Achievements
        if match_info.thisQ == "RANKED" and match_info.thisTime > 20 and succes is True:
            suivi[summonerName.lower().replace(" ", "")]['Achievements'] = \
                suivi[summonerName.lower().replace(" ", "")][
                        'Achievements'] + points

            suivi[summonerName.lower().replace(" ", "")]['games'] = suivi[summonerName.lower().replace(" ", "")][
                                                                            'games'] + 1
  
            

        if match_info.thisQ == "ARAM" and match_info.thisTime > 10:
            suivi[summonerName.lower().replace(" ", "")]['Achievements_aram'] = \
                suivi[summonerName.lower().replace(" ", "")][
                        'Achievements_aram'] + points

            suivi[summonerName.lower().replace(" ", "")]['games_aram'] = suivi[summonerName.lower().replace(" ", "")][
                                                                            'games_aram'] + 1


        sauvegarde_bdd(suivi, 'suivi') #achievements + suivi


                
        # observations
        
        embed.add_field(name="Game", value=f"[LeagueofGraph]({url_game})") # ici, ça va de 1 à 10.. contrairement à Rito qui va de 1 à 9
        embed.add_field(name="OPGG", value=f"[Profil](https://euw.op.gg/summoners/euw/{summonerName})")
        embed.add_field(name="Stats", value=f"[{match_info.thisChampName}](https://lolalytics.com/lol/{match_info.thisChampName.lower()}/build/)")

        if len(exploits) <= 1024:
            if match_info.thisPosition in ['SUPPORT', 'ADC', 'MID', 'JUNGLE'] and match_info.thisQ in ["RANKED", "FLEX"]:
                embed.add_field(
                    name="Durée : " + str(int(match_info.thisTime)) + " minutes | Score " + str(result),
                    value=exploits, inline=False)
            else:
                embed.add_field(name="Durée de la game : " + str(int(match_info.thisTime)) + " minutes",
                                value=exploits, inline=False)
                
        else:
            if match_info.thisPosition in ['SUPPORT', 'ADC', 'MID', 'JUNGLE'] and match_info.thisQ in ["RANKED", "FLEX"]:
                embed.add_field(
                    name="Durée : " + str(int(match_info.thisTime)) + " minutes | Score " + str(result),
                    value=exploits[:1023], inline=False)
                embed.add_field(
                    name="Records 2",
                    value=exploits[1023:2047], inline=False)
                if len(exploits) >= 2047:
                    embed.add_field(
                        name="Records 3",
                        value=exploits[2047:3071], inline=False)
                if len(exploits) >= 3071:
                    embed.add_field(
                        name="Records 4",
                        value=exploits[3071:4095], inline=False)
                if len(exploits) >= 4095:
                    embed.add_field(
                        name="Records 5",
                        value=exploits[4095:])
            else:
                embed.add_field(name="Durée de la game : " + str(int(match_info.thisTime)) + " minutes",
                                value=exploits[:1024], inline=False)
                embed.add_field(
                    name="Records 2",
                    value=exploits[1023:2047], inline=False)
                if len(exploits) >= 2047:
                    embed.add_field(
                        name="Records 3",
                        value=exploits[2047:3071], inline=False)
                if len(exploits) >= 3071:
                    embed.add_field(
                        name="Records 4",
                        value=exploits[3071:4095], inline=False)
                if len(exploits) >= 4095:
                    embed.add_field(
                        name="Records 5",
                        value=exploits[4095:])
                    
            
            

        if len(exploits2) > 5: # si plus de 15 lettres, alors il y a un exploit personnel
            embed.add_field(name="Statistiques personnelles : ", value=exploits2, inline=False)
        
        if len(exploits3) > 5: # si plus de 15 lettres, alors il y a un exploit personnel
            embed.add_field(name="Statistiques personnelles Part2: ", value=exploits3, inline=False)
        
        if len(exploits4) > 5: # si plus de 15 lettres, alors il y a un exploit personnel
            embed.add_field(name="Statistiques personnelles Part3: ", value=exploits4, inline=False)
            
    
        # # Objectifs
        if match_info.thisQ != "ARAM":
            embed.add_field(name="Team :", value=f"\nEcart top - Vision : **{match_info.ecart_top_vision}** | CS : **{match_info.ecart_top_cs}** \n"
                            + f"Ecart jgl - Vision: **{match_info.ecart_jgl_vision}** | CS : **{match_info.ecart_jgl_cs}** \n"
                            + f"Ecart mid - Vision : **{match_info.ecart_mid_vision}** | CS : **{match_info.ecart_mid_cs}** \n"
                            + f"Ecart adc - Vision : **{match_info.ecart_adc_vision}** | CS : **{match_info.ecart_adc_cs}** \n"
                            + f"Ecart supp - Vision : **{match_info.ecart_supp_vision}** | CS : **{match_info.ecart_supp_cs}**", inline=False)
        
       # Gestion de l'image 1
       
        embed = match_info.resume_personnel('resume_perso', embed, difLP)
       
        # Gestion de l'image 2
        
        match_info.resume_general('resume')
        
        # on charge les img
        
        resume = discord.File('resume_perso.png')
        embed.set_image(url='attachment://resume_perso.png')
        
        embed2 = discord.Embed(color=color)
        resume2 = discord.File('resume.png')
        embed2.set_image(url='attachment://resume.png')

        embed.set_footer(text=f'Version {main.Var_version} by Tomlora - Match {str(match_info.last_match)}')

        return embed, match_info.thisQ, resume, embed2, resume2

    @tasks.loop(minutes=1, count=None)
    async def my_task(self):
        await self.update()


    async def updaterank(self, key, discord_server_id):
        
        suivirank = lire_bdd('suivi', 'dict')
        me = lol_watcher.summoner.by_name(my_region, key)
        stats = lol_watcher.league.by_summoner(my_region, me['id'])

        if len(stats) > 0:
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
                    channel_tracklol = self.bot.get_channel(discord_server_id.tracklol)   
                    if dict_rankid[rank_old] > dict_rankid[level]:  # 19 > 18
                        await channel_tracklol.send(f' Le joueur **{key}** a démote du rank **{rank_old}** à **{level}**')
                        await channel_tracklol.send(file=discord.File('./img/notstonks.jpg'))
                    elif dict_rankid[rank_old] < dict_rankid[level]:
                        await channel_tracklol.send(f' Le joueur **{key}** a été promu du rank **{rank_old}** à **{level}**')
                        await channel_tracklol.send(file=discord.File('./img/stonks.jpg'))
                                    
                    suivirank[key]['tier'] = tier
                    suivirank[key]['rank'] = rank
                except:
                    print('Channel impossible')
                    print(sys.exc_info())     

            sauvegarde_bdd(suivirank, 'suivi')


    @cog_ext.cog_slash(name="game",
                       description="Voir les statistiques d'une games",
                       options=[create_option(name="summonername", description= "Nom du joueur", option_type=3, required=True),
                                create_option(name="numerogame", description="Numero de la game, de 0 à 100", option_type=4, required=True),
                                create_option(name="succes", description="Faut-il la compter dans les records/achievements ? True = Oui / False = Non", option_type=5, required=True),
                                create_option(name="chrono", description="Reserve au proprietaire", option_type=5, required=False)])
    async def game(self, ctx, summonername:str, numerogame:int, succes: bool):
        
        await ctx.defer(hidden=False)
        
        summonername = summonername.lower()

        embed, mode_de_jeu, resume, embed2, resume2 = self.printInfo(summonerName=summonername.lower(), idgames=int(numerogame), succes=succes)

        if embed != {}:
            await ctx.send(embed=embed, file=resume)
            await ctx.send(embed=embed2, file=resume2)
            os.remove('resume.png')
            os.remove('resume_perso.png')
            
            
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

            embed, mode_de_jeu, resume, embed2, resume2 = self.printInfo(summonerName=summonername.lower(), idgames=int(i), succes=succes)

            if embed != {}:
                await ctx.send(embed=embed, file=resume)
                await ctx.send(embed=embed2, file=resume2)
            else:
                await ctx.send(f"La game {str(i)} n'a pas été comptabilisée")
                
            sleep(5)
               

    async def printLive(self, summonername, discord_server_id):
        
        summonername = summonername.lower()
        
        embed, mode_de_jeu, resume, embed2, resume2 = self.printInfo(summonerName=summonername, idgames=0, succes=True)
        
       
        if mode_de_jeu in ['RANKED', 'FLEX']:
            channel_tracklol = self.bot.get_channel(discord_server_id.tracklol)
        else:
            channel_tracklol = self.bot.get_channel(discord_server_id.lol_others)   
        
        if embed != {}:
            await channel_tracklol.send(embed=embed, file=resume)
            await channel_tracklol.send(embed=embed2, file=resume2)
            os.remove('resume.png')
            os.remove('resume_perso.png')


    async def update(self):
        

        data = get_data_bdd(f'SELECT index, id from tracker where activation = true').fetchall()
        
 
        for key, value in data: 
            
            id_last_game = getId(key)

            if str(value) != id_last_game:  # value -> ID de dernière game enregistrée dans id_data != ID de la dernière game via l'API Rito / #key = pseudo // value = numéro de la game
                try:
                    # identification du channel
                    data = lire_bdd_perso(f'SELECT server_id, index from tracker where index= %(joueur)s', params={'joueur' : key})
                    server_id_joueur = int(data[key][0])
                    discord_server_id = chan_discord(server_id_joueur)
                    
                    # résumé de game
                    
                    await self.printLive(key, discord_server_id)
                    
                    # update rank
                    await self.updaterank(key, discord_server_id)
                    
                    
                except: 
                    print(f"erreur {key}") # joueur qui a posé pb
                    print(sys.exc_info()) # erreur
                       
                # update la bdd
                requete_perso_bdd(f'UPDATE tracker SET id = :id WHERE index = :index', {'id' : id_last_game, 'index' : key})



    @cog_ext.cog_slash(name="loladd",description="Ajoute le joueur au suivi",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    async def loladd(self, ctx, *, summonername):
        try:
            requete_perso_bdd(f'''INSERT INTO tracker(index, id, discord, server_id) VALUES (:summonername, :id, :discord, :guilde);
                              
                            INSERT INTO suivi(
	                        index, wins, losses, "LP", tier, rank, "Achievements", games, serie)
	                        VALUES (:summonername, 0, 0, 0, 'Non-classe', 0, 0, 0, 0);
                         
                            INSERT INTO suivi_24h(
	                        index, wins, losses, "LP", tier, rank, "Achievements", games, serie)
	                        VALUES (:summonername, 0, 0, 0, 'Non-classe', 0, 0, 0, 0);
                         
                            INSERT INTO ranked_aram(
	                        index, wins, losses, lp, games, k, d, a, activation, rank)
	                        VALUES (:summonername, 0, 0, 0, 0, 0, 0, 0, True, 'IRON');
                         
                            INSERT INTO ranked_aram_24h(
	                        index, wins, losses, lp, games, k, d, a, activation, rank)
	                        VALUES (:summonername, 0, 0, 0, 0, 0, 0, 0, True, 'IRON');
                         
                            INSERT INTO records_personnel(index)
                            VALUES (:summonername);
                            
                            ALTER TABLE records3
                            ADD COLUMN {summonername.lower} DOUBLE PRECISION;
                            
                            UPDATE records3 SET "{summonername.lower}" = 0;''',
                         {'summonername' : summonername.lower(), 'id' : getId(summonername), 'discord' : ctx.author.id, 'guilde' : ctx.guild.id})

            

            await ctx.send(summonername + " was successfully added to live-feed!")
        except:
            await ctx.send("Oops! There is no summoner with that name!")

    @cog_ext.cog_slash(name='lolremove', description='Activation/Désactivation du tracker',
                       options=[create_option(name='summonername', description="nom ingame", option_type=3, required=True),
                                create_option(name="activation", description="True : Activé / False : Désactivé", option_type=5, required=True)])
    
    async def lolremove(self, ctx, summonername:str, activation:bool):
        
        summonername = summonername.lower()
        
        try:
            requete_perso_bdd('UPDATE tracker SET activation = :activation WHERE index = :index', {'activation' : activation, 'index' : summonername})
            if activation:
                await ctx.send('Tracker activé !')
            else:
                await ctx.send('Tracker désactivé !')
        except KeyError:
            await ctx.send('Joueur introuvable')


    @cog_ext.cog_slash(name='lollist', description='Affiche la liste des joueurs suivis')
    async def lollist(self, ctx):

        data = get_data_bdd('SELECT index from tracker').fetchall()
        response = ""

        for key in data:
            response += key[0].upper() + ", "

        response = response[:-2]
        embed = discord.Embed(title="Live feed list", description=response, colour=discord.Colour.blurple())

        await ctx.send(embed=embed)

    
    @tasks.loop(hours=1, count=None)
    async def lolsuivi(self):


        currentHour = str(datetime.datetime.now().hour)

        if currentHour == str(2):
            
            for guild in self.bot.guilds:
                
                chan_discord_id = chan_discord(guild.id)
            
            # le suivi est déjà maj par game/update... Pas besoin de le refaire ici..

                suivi = lire_bdd('suivi', 'dict')
                suivi_24h = lire_bdd('suivi_24h', 'dict')
                
                
                # df = lire_bdd_perso("""SELECT * from suivi WHERE tier != 'Non-classe'""").transpose().reset_index()
                df = pd.DataFrame.from_dict(suivi)
                df = df.transpose().reset_index()
                
                # df_24h = lire_bdd_perso("""SELECT * from suivi_24h WHERE tier != 'Non-classe'""").transpose().reset_index()
                df_24h = pd.DataFrame.from_dict(suivi_24h)
                df_24h = df_24h.transpose().reset_index()

                
                df = df[df['tier'] != 'Non-classe'] # on supprime les non-classés
                
                df_24h = df_24h[df_24h['tier'] != 'Non-classe'] # on supprime les non-classés
                

                # Pour l'ordre de passage
                df['tier_pts'] = 0
                df['tier_pts'] = np.where(df.tier == 'IRON', 1, df.tier_pts)
                df['tier_pts'] = np.where(df.tier == 'BRONZE', 1, df.tier_pts)
                df['tier_pts'] = np.where(df.tier == 'SILVER', 2, df.tier_pts)
                df['tier_pts'] = np.where(df.tier == 'GOLD', 3, df.tier_pts)
                df['tier_pts'] = np.where(df.tier == 'PLATINUM', 4, df.tier_pts)
                df['tier_pts'] = np.where(df.tier == 'DIAMOND', 5, df.tier_pts)
                df['tier_pts'] = np.where(df.tier == 'MASTER', 6, df.tier_pts)


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
                        
                        if classement_new != "Non-classe 0":

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
                                            

                    else:
                        suivi[key]["tier"] = "Non-classe"

                sauvegarde_bdd(suivi, 'suivi_24h')

                channel_tracklol = self.bot.get_channel(chan_discord_id.tracklol) 
                
                embed.set_footer(text=f'Version {main.Var_version} by Tomlora')  

                await channel_tracklol.send(embed=embed)
                await channel_tracklol.send(f'Sur {totalgames} games -> {totalwin} victoires et {totaldef} défaites')
                

     
    @cog_ext.cog_slash(name="color_recap",
                       description="Couleur du recap",
                       options=[create_option(name="summonername", description= "Nom du joueur", option_type=3, required=True),
                                create_option(name="rouge", description="R", option_type=4, required=True),
                                create_option(name="vert", description="G", option_type=4, required=True),
                                create_option(name="bleu", description="B", option_type=4, required=True)])        
    async def color_recap(self, ctx, summonername:str, rouge:int, vert:int, bleu: int):
        
        await ctx.defer(hidden=False)
        
        params = {'rouge' : rouge, 'vert' : vert, 'bleu' : bleu, 'index' : summonername.lower()}
        requete_perso_bdd(f'UPDATE tracker SET "R" = :rouge, "G" = :vert, "B" = :bleu WHERE index = :index', params)
        
        await ctx.send(f' La couleur du joueur {summonername} a été modifiée.')  
        

    # @cog_ext.cog_slash(name="spectator", description="Spectator",
    #                    options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    # @main.isOwner2_slash()
    # async def spectator(self, ctx, summonerName):
    #     try:
    #         match = match_spectator(summonerName)
    #         print(match['participants'])
    #         await ctx.send('Fait !')
    #     except:
    #         await ctx.send("Tu n'es pas en match.")     
        
    @cog_ext.cog_slash(name="abbedagge", description="Meilleur joueur de LoL")
    async def abbedagge(self, ctx):
        await ctx.send('https://clips.twitch.tv/ShakingCovertAuberginePanicVis-YDRK3JFk7Glm6nbB')
        
    @cog_ext.cog_slash(name="closer", description="Meilleur joueur de LoL")
    async def closer(self, ctx):
        await ctx.send('https://clips.twitch.tv/EmpathicClumsyYogurtKippa-lmcFoGXm1U5Jx2bv')
        
    @cog_ext.cog_slash(name="upset", description="Meilleur joueur de LoL")
    async def upset(self, ctx):
        await ctx.send('https://clips.twitch.tv/CuriousBenevolentMageHotPokket-8M0TX_zTaGW7P2g7')
        
       
    @cog_ext.cog_slash(name='lol_discord', description='Link discord et lol')
    async def link(self, ctx, summonername, member:discord.Member):
        
        summonername = summonername.lower()
        
        requete_perso_bdd('UPDATE tracker SET discord = :discord, server_id = :guild WHERE index = :summonername', {'discord' : member.id, 'server_id' : ctx.guild.id, 'summonername' : summonername})
        
        await ctx.send(f'Le compte LoL {summonername} a été link avec <@{member.id}>')


def setup(bot):
    bot.add_cog(LeagueofLegends(bot))
