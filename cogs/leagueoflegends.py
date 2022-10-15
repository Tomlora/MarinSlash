
from pkgutil import get_data
from discord.ext import commands, tasks

import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import plotly.graph_objects as go
from plotly.graph_objs import Layout
import plotly.express as px
import sys



from riotwatcher import LolWatcher
import pandas as pd
import main
import datetime
import numpy as np
import warnings
from cogs.achievements_scoringlol import scoring

from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd, get_data_bdd, requete_perso_bdd, lire_bdd_perso



from fonctions.match import matchlol, getId, dict_rankid 
from fonctions.date import calcul_time


from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice

from time import sleep, time




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
    
    elif type == "items":
        img = Image.open(f'./img/items/{name}.png')
        img = img.resize((resize_x,resize_y))
        return img
    
    elif type == "monsters":
        img = Image.open(f'./img/monsters/{name}.png')
                 
        img = img.resize((resize_x,resize_y))
        
        return img
        
    elif type == "epee":
        img = Image.open(f'./img/epee/{name}.png')
        img = img.resize((resize_x, resize_y))
        
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

def score_personnel(embed, dict, key:str, summonerName:str, stats:str, old_value:float, new_value:float, url):
    if key == stats:
        if old_value < new_value:
            requete_perso_bdd('''UPDATE records_personnel
	SET :key = :key_value, :key_url = :key_url_value 
	WHERE index = :joueur''', {'key' : key, 'key_value' : new_value, 'key_url' : key + "_url", 'key_url_value' : url, 'joueur' : summonerName.lower() })
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
        
        
        if match_info.thisQId == 900: #urf (géré différemment)
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
            data = get_data_bdd(f'SELECT "R", "G", "B" from tracker WHERE index= :index', {'index' : pseudo} )
            data = data.fetchall()
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
                
            if (float(match_info.participation_tower) >= settings['Participation_tower']['score']):
                exploits = exploits + f"\n ** :crown: :tokyo_tower: Ce joueur a contribué à la destruction de {match_info.participation_tower}% des tours **"
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

            if int(match_info.thisPenta) >= settings['Pentakill']['score']:
                exploits = exploits + f"\n ** :crown: :five: Ce joueur a pentakill ** {match_info.thisPenta} fois"
                points = points + (1 * int(match_info.thisPenta))

            if int(match_info.thisQuadra) >= settings['Quadrakill']['score']:
                exploits = exploits + f"\n ** :crown: :four: Ce joueur a quadrakill ** {match_info.thisQuadra} fois"
                points = points + (1 * int(match_info.thisQuadra))

            if float(match_info.thisKDA) >= settings['KDA']['score']:
                exploits = exploits + f"\n ** :crown: :star: Ce joueur a un bon KDA avec un KDA de {match_info.thisKDA} **"
                points = points + 1

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

        if int(match_info.thisKP) >= settings['KP']['score']:
            exploits = exploits + f"\n ** :crown: :dagger: Ce joueur a participé à énormément de kills dans son équipe avec {match_info.thisKP} % **"
            points = points + 1


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
            
        if (int(match_info.thisTotalShielded) >= settings['Shield']['Score']):
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
        for key,value in metrics_personnel.items():
        
            try:
                if succes is True and match_info.thisQ == "RANKED" and match_info.thisTime > 20:
                    old_value = float(records_personnel[summonerName.lower().replace(" ", "")][key])
                    
                    for stats in metrics_personnel.keys():
                        if len(exploits2) < 900: # on ne peut pas dépasser 1024 caractères par embed
                            exploits2 = score_personnel(exploits2, records_personnel, key, summonerName, stats, float(old_value), float(value), url_game)
                        elif len(exploits3) < 900:
                            exploits3 = score_personnel(exploits3, records_personnel, key, summonerName, stats, float(old_value), float(value), url_game)
                        elif len(exploits4) < 900:
                            exploits4 = score_personnel(exploits4, records_personnel, key, summonerName, stats, float(old_value), float(value), url_game)
                            
                        

                    
            except: # cela va retourner une erreur si c'est un nouveau joueur dans la bdd.
                records_personnel[summonerName.lower().replace(" ", "")][key] = value
             
        # Achievements
        if match_info.thisQ == "RANKED" and match_info.thisTime > 20 and succes is True:
            suivi[summonerName.lower().replace(" ", "")]['Achievements'] = \
                suivi[summonerName.lower().replace(" ", "")][
                        'Achievements'] + points

            suivi[summonerName.lower().replace(" ", "")]['games'] = suivi[summonerName.lower().replace(" ", "")][
                                                                            'games'] + 1
  
            sauvegarde_bdd(records_cumul, 'records3')

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
       
       ## Graphique KP
        values = [match_info.thisKP/100, 1-match_info.thisKP/100]

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
            annotations=[dict(text=f'{match_info.thisKP}%',font_size=40, showarrow=False)])
        fig.update_traces(textinfo='none')



        fig.write_image('kp.png')
        
        ## Graphique stats
        
        stats_name = ['DMG', 'TANK', 'TANK_REDUC', 'Healing', 'Shield']
        stats_value = [match_info.thisDamageNoFormat, match_info.thisDamageTakenNoFormat, match_info.thisDamageSelfMitigated,
                    match_info.thisTotalHealed, match_info.thisTotalShielded]
        
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
        d.text((x_name, y_name), match_info.summonerName, font=font, fill=fill)
        
        im.paste(im=get_image("avatar", match_info.avatar, 100, 100),
            box=(x_name-240, y_name-20))
        
        im.paste(im=get_image("champion", match_info.thisChampName, 100, 100),
                box=(x_name-120, y_name-20))
        
        d.text((x_name+700, y_name-20), f"Niveau {match_info.level_summoner}", font=font_little, fill=fill)
        
        if match_info.thisQ != "ARAM":

            img_rank = get_image('tier', match_info.thisTier, 220, 220)
            
                        
            im.paste(img_rank,(x_rank, y-140), img_rank.convert('RGBA'))
            
            
            d.text((x_rank+220, y-110), f'{match_info.thisTier} {match_info.thisRank}', font=font, fill=fill)
            d.text((x_rank+220, y-45), f'{match_info.thisLP} LP ({difLP})', font=font_little, fill=fill)
            
            # Gestion des bo    
            if int(match_info.thisLP) == 100:
                bo = match_info.thisStats[match_info.i]['miniSeries']
                bo_wins = str(bo['wins'])
                bo_losses = str(bo['losses'])
                # bo_progress = str(bo['progress'])
                d.text((x_rank+220, y+10), f'{match_info.thisVictory}W {match_info.thisLoose}L {match_info.thisWinrateStat}% (BO : {bo_wins} / {bo_losses}) ', font=font_little, fill=fill)
            else:
                d.text((x_rank+220, y+10), f'{match_info.thisVictory}W {match_info.thisLoose}L     {match_info.thisWinrateStat}% ', font=font_little, fill=fill)
        
        else:
            
            data_aram = get_data_bdd('SELECT * from ranked_aram WHERE index = :index', {'index' : match_info.summonerName})
            data_aram = data_aram.fetchall()

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
                               
                if str(match_info.thisWinId) == 'True':
                    wins = wins_actual + 1
                    losses = losses_actual
                        
                else:
                    wins = wins_actual
                    losses = losses_actual + 1
                   
                 
                   
                wr = round(wins / games,2)*100
                

                if match_info.AFKTeam >= 1: # si afk, pas de gain/perte
                    points = 0
                else:
                # calcul des LP 
                    if games <=5:
                        if str(match_info.thisWinId) == 'True':
                            points = 50
                        else:
                            points = 0
                    
                    elif wr >= 60:
                        if str(match_info.thisWinId) == 'True':
                            points = 30
                        else:
                            points = -10
                            
                    elif wr <= 40:
                        if str(match_info.thisWinId) == "True":
                            points = 10
                        else:
                            points = -20
                    else:
                        if str(match_info.thisWinId) == "True":
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

                
                if games >= 5 and match_info.AFKTeam == 0: #si plus de 5 games et pas d'afk
                    lp = lp - elo_lp[rank] # malus en fonction du elo
                    
                # pas de lp negatif
                if lp < 0:
                    lp = 0
                                        
                if rank_actual != rank:
                    embed.add_field(name = "Changement d'elo", value=f" :star: Tu es passé de **{rank_actual}** à **{rank}**")
                
                k = k_actual + match_info.thisKills
                difLP = lp - lp_actual 
                deaths = d_actual + match_info.thisDeaths
                a = a_actual + match_info.thisAssists

                img_rank = get_image('tier', rank, 220, 220)
            
                        
                im.paste(img_rank,(x_rank, y-140), img_rank.convert('RGBA'))
                d.text((x_rank+220, y-110), f'{rank}', font=font, fill=fill)
                d.text((x_rank+220, y-45), f'{lp} LP ({difLP})', font=font_little, fill=fill)
                

                d.text((x_rank+220, y+10), f'{wins}W {losses}L     {round(wr,1)}% ', font=font_little, fill=fill)
                
                requete_perso_bdd('UPDATE ranked_aram SET wins = :wins, losses = :losses, lp = :lp, games = :games, k = :k, d = :d, a = :a, rank = :rank WHERE index = :index',
                                  {'wins' : wins, 'losses' : losses, 'lp' : lp, 'games' : games, 'k' : k, 'd' : deaths, 'a' : a, 'rank' : rank, 'index' : match_info.summonerName.lower()})
            

        
        kp = get_image('autre', 'kp', 700, 500)
        
                    
        im.paste(kp,(x_metric-150, y_metric+20), kp.convert('RGBA'))
        d.text((x_metric + 170, y_metric+20), 'KP', font=font, fill=(0, 0, 0))
        
        # CS
    
        d.text((x_metric, y_metric+620),f'Avantage CS : {int(match_info.thisCSAdvantageOnLane)}', font=font, fill=(0, 0, 0))
        d.text((x_metric, y_metric+500),f'CS/min : {int(match_info.thisMinionPerMin)}', font=font, fill=(0, 0, 0))
               
        # Ward
        
        if match_info.thisQ != "ARAM":
        
            d.text((x_metric + 640, y_metric),f'Vision : {match_info.thisVision} (AV : {match_info.thisVisionAdvantage}%)', font=font, fill=(0, 0, 0))
            d.text((x_metric + 640, y_metric+90),f'{match_info.thisVisionPerMin}/min', font=font, fill=(0, 0, 0))
            
            im.paste(im=get_image("items", 3340, 100, 100),
                    box=(x_metric + 650, y_metric+200))
            
            d.text((x_metric + 800, y_metric+220),f'{match_info.thisWards}', font=font, fill=(0, 0, 0))
            
            im.paste(im=get_image("items", 3364, 100, 100),
                    box=(x_metric + 650, y_metric+400))
            
            d.text((x_metric + 800, y_metric+420),f'{match_info.thisWardsKilled}', font=font, fill=(0, 0, 0))
            
            im.paste(im=get_image("items", 2055, 100, 100),
                    box=(x_metric + 650, y_metric+600))
            
            d.text((x_metric + 800, y_metric+620),f'{match_info.thisPink}', font=font, fill=(0, 0, 0))
            
        # KDA
    
        kda_kills = 290
        kda_deaths = 890
        kda_assists = 1490
        kda_gold = 2090
        
        img_kda_kills = get_image('kda', 'rectangle bleu blanc', 300, 150)
        img_kda_deaths = get_image('kda', 'rectangle rouge blanc', 300, 150)
        img_kda_assists = get_image('kda', 'rectangle vert', 300, 150)
        img_kda_gold = get_image('kda', 'rectangle gold', 300, 150)
        
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
        if int(match_info.thisKills) >= 10:
            kda_kills = kda_kills - 30
        d.text((kda_kills+240, y_metric-180),f'{match_info.thisKills}', font=font, fill=(0, 0, 0))
        
        if int(match_info.thisDeaths) >=10:
            kda_deaths = kda_deaths - 30
        d.text((kda_deaths+240, y_metric-180),f'{match_info.thisDeaths}', font=font, fill=(0, 0, 0))
        
        if int(match_info.thisAssists) >=10:
            kda_assists = kda_assists - 30
        d.text((kda_assists+240, y_metric-180),f'{match_info.thisAssists}', font=font, fill=(0, 0, 0))
        
        d.text((kda_gold+150, y_metric-180),f'{round(match_info.thisGoldEarned/1000,1)}k', font=font, fill=(0, 0, 0))
            
            # Stat du jour
    
        suivi_24h = lire_bdd('suivi_24h', 'dict')
        
        
        try:
            difwin = int(match_info.thisVictory) - int(suivi_24h[match_info.summonerName.lower()]["wins"])
            diflos = int(match_info.thisLoose) - int(suivi_24h[match_info.summonerName.lower()]["losses"])
            
            
            if (difwin + diflos) > 0: # si pas de ranked aujourd'hui, inutile
                d.text((x_metric + 650, y_name+50),f'Victoires : {difwin}', font=font_little, fill=(0, 0, 0))
                d.text((x_metric + 1120, y_name+50),f'Defaites : {diflos}', font=font_little, fill=(0, 0, 0))
        
        except KeyError:
            pass
            
        im.paste(im=get_image("autre", 'stats', 1000, 800),
                    box=(x_metric + 900, y_metric+100))
        
        
        d.text((x_metric + 2000, y_metric+200),f'Solokills : {match_info.thisSoloKills}', font=font, fill=(0, 0, 0))
        d.text((x_metric + 2000, y_metric+300),f'Double : {match_info.thisDouble}', font=font, fill=(0, 0, 0))
        d.text((x_metric + 2000, y_metric+400),f'Triple : {match_info.thisTriple}', font=font, fill=(0, 0, 0))
        d.text((x_metric + 2000, y_metric+500),f'Quadra : {match_info.thisQuadra}', font=font, fill=(0, 0, 0))
        d.text((x_metric + 2000, y_metric+600),f'Penta : {match_info.thisPenta}', font=font, fill=(0, 0, 0))
        

    
        im.save('resume_perso.png')
       
        font_name = None
        
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

        if font_name is not None:
            font = ImageFont.truetype(font_name, 50)
        else:
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
                
            
            if match_info.thisQ != "ARAM":
                if i == dict_position[match_info.thisPosition]:
                    im.paste(Image.new("RGB", (lineX, lineY), (173,216,230)), (0, i*lineY))
                
            


        # match
        d.text((10, 15), match_info.thisQ, font=font, fill=(0, 0, 0))
        # d.text((10, 120), f'Gold : {match_info.thisGold_team1}', font=font, fill=(255, 255, 255))
        # d.text((10, 720), f'Gold : {match_info.thisGold_team2}', font=font, fill=(0, 0, 0))
        
        money = get_image('gold', 'dragon', 60, 60)
        
        
        im.paste(money,(10, 120), money.convert('RGBA'))
        d.text((80, 120), f'{match_info.thisGold_team1}', font=font, fill=(255, 255, 255))
        im.paste(money,(10, 720), money.convert('RGBA'))
        d.text((80, 720), f'{match_info.thisGold_team2}', font=font, fill=(0, 0, 0))
        
        
        
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
            
            if match_info.thisQ != "ARAM": 
                d.text((x_vision, y), 'VS', font=font, fill=fill)

        # participants
        initial_y = 220

        for i in range(0, 10):
            im.paste(
                im=get_image("champion", match_info.thisChampNameListe[i]),
                box=(10, initial_y-10),
            )
            
            d.text((x_level, initial_y), "Niv " + str(match_info.thisLevelListe[i]), font=font, fill=(0,0,0))

            d.text((x_name, initial_y), match_info.thisPseudoListe[i], font=font, fill=(0, 0, 0))
        
            
            if len(str(match_info.thisKillsListe[i])) == 1:
                d.text((x_kills, initial_y), str(match_info.thisKillsListe[i]), font=font, fill=(0,0,0))
            else:
                d.text((x_kills - 20, initial_y), str(match_info.thisKillsListe[i]), font=font, fill=(0,0,0))
                
                
            if len(str(match_info.thisDeathsListe[i])) == 1:
                d.text((x_deaths, initial_y), str(match_info.thisDeathsListe[i]), font=font, fill=(0,0,0))
            else:
                d.text((x_deaths - 20, initial_y), str(match_info.thisDeathsListe[i]), font=font, fill=(0,0,0))
            

            if len(str(match_info.thisAssistsListe[i])) == 1:            
                d.text((x_assists, initial_y), str(match_info.thisAssistsListe[i]), font=font, fill=(0,0,0))
            else:
                d.text((x_assists - 20, initial_y), str(match_info.thisAssistsListe[i]), font=font, fill=(0,0,0))
            
            
            if len(str(round(match_info.thisKDAListe[i],2)))==1: # Recentrer le résultat quand chiffre rond
                d.text((x_kda + 35, initial_y), str(round(match_info.thisKDAListe[i],2)), font=font, fill=(0,0,0))
            else:
                d.text((x_kda, initial_y), str(round(match_info.thisKDAListe[i],2)), font=font, fill=(0,0,0))
                
            d.text((x_kp, initial_y), str(match_info.thisKPListe[i]) + "%", font=font, fill=(0, 0, 0))
            
            if len(str(match_info.thisMinionListe[i] + match_info.thisJungleMonsterKilledListe[i])) != 2:
                d.text((x_cs, initial_y), str(match_info.thisMinionListe[i] + match_info.thisJungleMonsterKilledListe[i]), font=font, fill=(0, 0, 0))
            else:
                d.text((x_cs + 10, initial_y), str(match_info.thisMinionListe[i] + match_info.thisJungleMonsterKilledListe[i]), font=font, fill=(0, 0, 0))
                
            if match_info.thisQ != "ARAM": 
                
                d.text((x_vision, initial_y), str(match_info.thisVisionListe[i]), font=font, fill=(0, 0, 0))
                
                
            if len(str(round(match_info.thisDamageRatioListe[i]*100,1))) == 3:     
                d.text((x_dmg_percent + 15, initial_y), str(round(match_info.thisDamageRatioListe[i]*100,1)) + "%", font=font, fill=(0,0,0))
            else:
                d.text((x_dmg_percent, initial_y), str(round(match_info.thisDamageRatioListe[i]*100,1)) + "%", font=font, fill=(0,0,0))
                
                
            if len(str(round(match_info.thisDamageTakenRatioListe[i]*100,1))) == 3:
                d.text((x_dmg_taken + 15, initial_y), str(round(match_info.thisDamageTakenRatioListe[i]*100,1)) + "%", font=font, fill=(0,0,0))
            else:
                d.text((x_dmg_taken, initial_y), str(round(match_info.thisDamageTakenRatioListe[i]*100,1)) + "%", font=font, fill=(0,0,0))
                
            
            

            if i == 4:
                initial_y += 200
            else:
                initial_y += 100
                
        if match_info.thisQ != "ARAM":         
            y_ecart = 220
            for ecart in [match_info.ecart_top_gold_affiche, match_info.ecart_jgl_gold_affiche, match_info.ecart_mid_gold_affiche, match_info.ecart_adc_gold_affiche, match_info.ecart_supp_gold_affiche]:        
                if ecart > 0:
                    d.text((x_ecart, y_ecart), str(round(ecart/1000,1)) + "k", font=font, fill=(0,128,0))
                else:
                    d.text((x_ecart-10, y_ecart), str(round(ecart/1000,1)) + "k", font=font, fill=(255,0,0))   
                
                y_ecart = y_ecart + 100
                
            
        n = 0
        for image in match_info.thisItems:
            if image != 0:
                im.paste(get_image("items", image),
                box=(350 + n, 10))
                n += 100
                
        if match_info.thisQ != "ARAM":        
                
            drk = get_image('monsters', 'dragon')
            elder = get_image('monsters', 'elder')
            herald = get_image('monsters', 'herald')
            nashor = get_image('monsters', 'nashor')       
                    
            im.paste(drk,(x_objectif, 10), drk.convert('RGBA'))
            d.text((x_objectif + 100, 20), str(match_info.thisDragonTeam), font=font, fill=(0, 0, 0))
            
            im.paste(elder,(x_objectif + 200, 10), elder.convert('RGBA'))
            d.text((x_objectif + 200 + 100, 20), str(match_info.thisElderPerso), font=font, fill=(0, 0, 0))
                
            im.paste(herald,(x_objectif + 400, 10), herald.convert('RGBA'))
            d.text((x_objectif + 400 + 100, 20), str(match_info.thisHeraldTeam), font=font, fill=(0, 0, 0))
                    
            im.paste(nashor, (x_objectif + 600, 10), nashor.convert('RGBA'))
            d.text((x_objectif + 600 + 100, 20), str(match_info.thisBaronTeam), font=font, fill=(0, 0, 0))
            
        
        img_blue_epee = get_image('epee', 'blue')
        img_red_epee = get_image('epee', 'red')
        
        im.paste(img_blue_epee, (x_kill_total, 10), img_blue_epee.convert('RGBA'))
        d.text((x_kill_total + 100, 20), str(match_info.thisTeamKills), font=font, fill=(0, 0, 0))
        
        im.paste(img_red_epee, (x_kill_total + 300, 10), img_red_epee.convert('RGBA'))
        d.text((x_kill_total + 300 + 100, 20), str(match_info.thisTeamKillsOp), font=font, fill=(0, 0, 0))

        im.save('resume.png')
        
        resume = discord.File('resume_perso.png')
        embed.set_image(url='attachment://resume_perso.png')
        
        embed2 = discord.Embed(color=color)
        resume2 = discord.File('resume.png')
        embed2.set_image(url='attachment://resume.png')

        embed.set_footer(text=f'Version {main.Var_version} by Tomlora - Match {str(match_info.last_match)}')

        return embed, match_info.thisQ, resume, embed2, resume2

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

        id_data = get_data_bdd('SELECT index from tracker')
        suivirank = lire_bdd('suivi', 'dict')

        for key in id_data:
            me = lol_watcher.summoner.by_name(my_region, key[0])
            stats = lol_watcher.league.by_summoner(my_region, me['id'])

            if len(stats) > 0:
                if str(stats[0]['queueType']) == 'RANKED_SOLO_5x5':
                        i = 0
                else:
                        i = 1

                tier = str(stats[i]['tier'])
                rank = str(stats[i]['rank'])
                level = tier + " " + rank

                if str(suivirank[key[0]]['tier']) + " " + str(suivirank[key[0]]['rank']) != level:
                    rank_old = str(suivirank[key[0]]['tier']) + " " + str(suivirank[key[0]]['rank'])
                    suivirank[key[0]]['tier'] = tier
                    suivirank[key[0]]['rank'] = rank
                    try:
                        channel_tracklol = self.bot.get_channel(int(main.chan_tracklol))   
                        if dict_rankid[rank_old] > dict_rankid[level]:  # 19 > 18
                            await channel_tracklol.send(f' Le joueur **{key[0]}** a démote du rank **{rank_old}** à **{level}**')
                            await channel_tracklol.send(file=discord.File('./img/notstonks.jpg'))
                        elif dict_rankid[rank_old] < dict_rankid[level]:
                            await channel_tracklol.send(f' Le joueur **{key[0]}** a été promu du rank **{rank_old}** à **{level}**')
                            await channel_tracklol.send(file=discord.File('./img/stonks.jpg'))
                            
                        suivirank[key[0]]['tier'] = tier
                        suivirank[key[0]]['rank'] = rank
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
               

    async def printLive(self, summonername):
        
        summonername = summonername.lower()
        
        embed, mode_de_jeu, resume, embed2, resume2 = self.printInfo(summonerName=summonername, idgames=0, succes=True)
        
        if mode_de_jeu in ['RANKED', 'FLEX']:
            channel_tracklol = self.bot.get_channel(int(main.chan_tracklol))
        else:
            channel_tracklol = self.bot.get_channel(int(main.chan_lol_others))   
        
        if embed != {}:
            await channel_tracklol.send(embed=embed, file=resume)
            await channel_tracklol.send(embed=embed2, file=resume2)
            os.remove('resume.png')
            os.remove('resume_perso.png')


    async def update(self):
        
        data = get_data_bdd(f'SELECT index, id from tracker')
            
        for key, value in data: 
            if str(value) != getId(key):  # value -> ID de dernière game enregistrée dans id_data != ID de la dernière game via l'API Rito / #key = pseudo // value = numéro de la game
                try:
                    await self.printLive(key)
                except:
                    print(f"Message non envoyé car le joueur {key} a fait une partie avec moins de 10 joueurs ou un mode désactivé")
                    print(sys.exc_info())

                requete_perso_bdd(f'UPDATE tracker SET id = :id WHERE index = :index', {'id' : getId(key), 'index' : key})


    @cog_ext.cog_slash(name="loladd",description="Ajoute le joueur au suivi",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    async def loladd(self, ctx, *, summonername):
        try:
            requete_perso_bdd(f'''INSERT INTO tracker(index, id, discord) VALUES (:summonername, :id, 'na');
                              
                            INSERT INTO suivi(
	                        index, wins, losses, "LP", tier, rank, "Achievements", games, serie)
	                        VALUES (:summonername, 0, 0, 0, 'Non-classe', 0, 0, 0, 0);
                         
                            INSERT INTO ranked_aram(
	                        index, wins, losses, lp, games, k, d, a, activation, rank)
	                        VALUES (:summonername, 0, 0, 0, 0, 0, 0, 0, True, 'IRON');''',
                         {'summonername' : summonername.lower(), 'id' : getId(summonername)})

            

            await ctx.send(summonername + " was successfully added to live-feed!")
        except:
            await ctx.send("Oops! There is no summoner with that name!")

    @cog_ext.cog_slash(name="lolremove", description="Supprime le joueur du suivi",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    async def lolremove(self, ctx, *, summonername):
        
        # requete_perso_bdd('''DELETE FROM tracker WHERE index = :summonername;
        #                   DELETE FROM suivi WHERE index = :summonername;
        #                   DELETE FROM ranked_aram WHERE index = :summonername''',
        #                   {'summonername' : summonername.lower()})

        # await ctx.send(summonername + " was successfully removed from live-feed!")
        await ctx.send('Commande désactivée pour la fin de saison')

    @cog_ext.cog_slash(name='lollist', description='Affiche la liste des joueurs suivis')
    async def lollist(self, ctx):

        data = get_data_bdd('SELECT index from tracker')
        data = data.fetchall()
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
            df['tier_pts'] = np.where(df.tier == 'BRONZE', 1, df.tier_pts)
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

            channel_tracklol = self.bot.get_channel(int(main.chan_tracklol)) 
            
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
        
    @cog_ext.cog_slash(name="closer", description="Meilleur joueur de LoL")
    async def closer(self, ctx):
        await ctx.send('https://clips.twitch.tv/EmpathicClumsyYogurtKippa-lmcFoGXm1U5Jx2bv')
        
    @cog_ext.cog_slash(name="upset", description="Meilleur joueur de LoL")
    async def upset(self, ctx):
        await ctx.send('https://clips.twitch.tv/CuriousBenevolentMageHotPokket-8M0TX_zTaGW7P2g7')
        
       
    @cog_ext.cog_slash(name='lol_discord', description='Link discord et lol')
    async def link(self, ctx, summonername, member:discord.Member):
        
        summonername = summonername.lower()
        
        requete_perso_bdd('UPDATE tracker SET discord = :discord WHERE index = :summonername', {'discord' : member.id, 'summonername' : summonername})
        
        await ctx.send(f'Le compte LoL {summonername} a été link avec <@{member.id}>')
        
        # self.bot.fetch_user(id)


def setup(bot):
    bot.add_cog(LeagueofLegends(bot))
