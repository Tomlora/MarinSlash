import os
import pandas as pd
import warnings
from fonctions.gestion_bdd import lire_bdd, get_data_bdd, requete_perso_bdd, lire_bdd_perso, sauvegarde_bdd
from fonctions.channels_discord import mention
import numpy as np
import sys
import traceback
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import aiohttp
import asyncio
import pickle
import sqlalchemy.exc
from fonctions.api_calls import getPlayerStats, getRanks, update_ugg, get_role, get_player_match_history
from fonctions.api_moba import update_moba, get_mobalytics, get_player_match_history_moba, get_role_stats, get_wr_ranked, detect_win_streak, get_stat_champion_by_player_mobalytics, get_rank_moba
import math
from utils.lol import elo_lp, dict_points, dict_id_q
from utils.emoji import emote_champ_discord, emote_rank_discord
from utils.params import api_key_lol, region, my_region

# TODO : rajouter temps en vie

warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'

from collections import Counter

def mode(lst):
    
    cleaned_lst = [value for value in lst if value != '']
    
    if not cleaned_lst:
        return ''
    # Compter les occurrences de chaque élément dans la liste
    counts = Counter(cleaned_lst)
    # Trouver l'élément avec le plus grand nombre d'occurrences
    mode_value = max(counts.values())
    # Filtrer les éléments qui ont le même nombre maximal d'occurrences
    modes = [key for key, value in counts.items() if value == mode_value]
    return modes

def fix_temps(duree):
    '''Convertit le temps en secondes en minutes et secondes'''
    minutes = int(duree)
    secondes = int((duree - minutes) * 60)/100
    
    return minutes + secondes


def get_id_account_bdd(riot_id, riot_tag):
    id_acc = lire_bdd_perso(f'''SELECT * from tracker where riot_id = '{riot_id.replace(' ', '')}' and riot_tagline = '{riot_tag}' ''').loc['id_compte'].values[0]
    return id_acc









def trouver_records(df, category, methode='max', identifiant='riot_id'):
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

        if identifiant == 'riot_id':
            joueur = lig['riot_id']
        elif identifiant == 'discord':
            joueur = mention(lig['discord'], 'membre')

        champion = lig['champion']
        record = lig[category]
        url_game = f'https://www.leagueofgraphs.com/fr/match/euw/{str(lig["match_id"])[5:]}#participant{int(lig["id_participant"])+1}'

    except Exception:
        return 'inconnu', 'inconnu', 0, '#'

    return joueur, champion, record, url_game

def trouver_records_multiples(df, category, methode='max', identifiant = 'riot_id', rank:bool=False):
    """
        Trouve les lignes avec le record associé

        Parameters
        ----------
        df : `dataframe`
            df avec les records
        category : `str`
            colonne où chercher le record
        methode : `str`, optional
            min ou max ?, by default 'max'

        Returns
        -------
        joueur, champion, record, url
    """

    try:
        df[category] = pd.to_numeric(df[category])

        # Trouvez la valeur minimale de la colonne
        if methode == 'max':
            df = df[df[category] != 0]
            df = df[df[category] != 0.0]

            col = df[category]
            record = col.max(skipna=True)

        elif methode == 'min':
            # pas de 0. Ca veut dire qu'il n'ont pas fait l'objectif par exemple
            df = df[df[category] != 0]
            df = df[df[category] != 0.0]

            col = df[category]
            record = col.min(skipna=True)
            
        # Sélectionnez toutes les lignes avec la même valeur minimale
        max_min_rows : pd.DataFrame = df.loc[df[category] == record]

        
        if rank:
            rank_value = max_min_rows[f'{category}_rank_{methode}'].values[0]

        # si le df est vide, pas de record
        if max_min_rows.empty and not rank:
            return ['inconnu'], ['inconnu'], 0, ['#'], [0]
        
        elif max_min_rows.empty and rank:
            return ['inconnu'], ['inconnu'], 0, ['#'], 0, [0]

        joueur = []
        champion = []
        url_game = []
        season = []

        # on regarde chaque ligne où il y a le record
        for lig, data in max_min_rows.iterrows():


            if data['riot_id'] not in joueur and mention(data['discord'], 'membre') not in joueur: # on affiche qu'une game du joueur. Pas besoin de toutes...

                if identifiant == 'riot_id':
                    joueur.append(data['riot_id'])
                elif identifiant == 'discord':
                    joueur.append(mention(data['discord'], 'membre'))

                champion.append(data['champion'])

                season.append(data['season'])

                url_game.append(f'https://www.leagueofgraphs.com/fr/match/euw/{str(data["match_id"])[5:]}#participant{int(data["id_participant"])+1}')
                
                

    except Exception:
        # exc_type, exc_value, exc_traceback = sys.exc_info()
        # traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
        # traceback_msg = ''.join(traceback_details)
        # print(traceback_msg)
        if rank:
            return ['inconnu'], ['inconnu'], 0, ['#'], 0, [0]
        else:
            return ['inconnu'], ['inconnu'], 0, ['#'], [0]

    if rank:
        return joueur, champion, record, url_game, rank_value, season
    else:
        return joueur, champion, record, url_game, season
    

def top_records(df, category, methode='max', identifiant='riot_id', top_n=10):
    ### A tester
    try:
        df[category] = pd.to_numeric(df[category], errors='coerce')
        df = df[df[category].notna()]
        df = df[df[category] != 0]
        df = df[df[category] != 999]

        df_sorted = df.sort_values(by=category, ascending=(methode != 'max')).head(top_n)

        records = []
        for _, lig in df_sorted.iterrows():
            if identifiant == 'riot_id':
                joueur = lig.get('riot_id', 'inconnu')
            elif identifiant == 'discord':
                joueur = mention(lig.get('discord', ''), 'membre')
            else:
                joueur = 'inconnu'

            champion = lig.get('champion', 'inconnu')
            record = lig[category]
            url_game = f'https://www.leagueofgraphs.com/fr/match/euw/{str(lig.get("match_id", ""))[5:]}#participant{int(lig.get("id_participant", 0)) + 1}'

            records.append((joueur, champion, record, url_game))

        return records

    except Exception:
        return []



def range_value(i, liste, min: bool = False, return_top: bool = False):
    if i == np.argmax(liste[:5]) or i-5 == np.argmax(liste[5:]):
        fill = (0, 128, 0)
        top = 'max'
    elif min and (i == np.argmin(liste[:5]) or i - 5 == np.argmin(liste[5:])):
        fill = (220, 20, 60)
        top = 'min'
    else:
        fill = (0, 0, 0)
        top = None

    return (fill, top) if return_top else fill

def range_value_arena(i, liste, min: bool = False, return_top: bool = False):
    if i == np.argmax(liste):
        fill = (0, 128, 0)
        top = 'max'
    elif min and i == np.argmin(liste):
        fill = (220, 20, 60)
        top = 'min'
    else:
        fill = (0, 0, 0)
        top = None

    return (fill, top) if return_top else fill

# https://ddragon.leagueoflegends.com/cdn/14.8.1/data/fr_FR/champion.json

async def get_image(type, name, session: aiohttp.ClientSession, resize_x=80, resize_y=80, profil_version='13.6.1'):
    url_mapping = {
        "champion": f"https://ddragon.leagueoflegends.com/cdn/{profil_version}/img/champion/{name}.png",
        "tier": f"./img/{name}.png",
        "avatar": f"https://ddragon.leagueoflegends.com/cdn/{profil_version}/img/profileicon/{name}.png",
        "items": f'https://ddragon.leagueoflegends.com/cdn/{profil_version}/img/item/{name}.png',
        "monsters": f'./img/monsters/{name}.png',
        "epee": f'./img/epee/{name}.png',
        "timer" : f'./img/timer/{name}.png',
        "gold": './img/money.png',
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



def get_stat_null_rules():
    query = "SELECT stat_name, champion FROM records_exclusion"
    df = lire_bdd_perso(query, index_col=None).T

    stat_null_rules = {}
    for stat_name, group in df.groupby("stat_name"):
        stat_null_rules[stat_name] = group["champion"].tolist()
    return stat_null_rules


async def get_masteries_old(summonerName: str, championIds, session : aiohttp.ClientSession) -> dict:
    
    championIds = {v: k for k, v in championIds.items()} # on inverse clé et value
    summonerName_url = summonerName.replace(' ', '+')
    summonerNameTag = summonerName
    
    
    def trouver_indice_hashtag(chaine):
        for indice, caractere in enumerate(chaine):
            if caractere == '#':
                return indice
        return -1
    indice = trouver_indice_hashtag(summonerName_url)
    
    if indice != -1:
        summonerName_url = summonerName_url[:indice]
        riot_id = summonerNameTag[:indice].lower().replace(' ', '+')
        riot_tag = summonerNameTag[indice+1:].lower()
        
    try: # si le tag est EUW, championmastery fonctionne bien. En revanche, si ce n'est pas le cas, il peut se tromper de joueur.
        

        url = f'https://championmastery.gg/player?riotId={riot_id}%23{riot_tag}&region=EUW&lang=en_US'

        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()
                df = pd.read_html(text, header=0)[0].head(-1)
        
        mastery_list = []
        try:               
                def correction_name(mot : str):
                    mot = mot.replace("'", "").replace(" ", "").replace(".", "")
                    if mot == 'KaiSa':
                        return "Kaisa"
                    elif mot == 'LeBlanc':
                        return "Leblanc"
                    elif mot == 'KhaZix':
                        return "Khazix"
                    elif mot == 'VelKoz':
                        return "Velkoz"  
                    elif mot == 'Wukong':
                        return "MonkeyKing"  
                    elif mot == 'ChoGath':
                        return "Chogath"
                    elif mot == "Nunu&Willump":
                        return "Nunu"
                    elif mot == "RenataGlasc":
                        return "Renata"
                    elif mot == "BelVeth":
                        return "Belveth"
                    return mot
                
                df['Champion name'] = df['Champion name'].apply(correction_name)
                
               
                for index, data in df.iterrows():
                    championId = int(championIds[data['Champion name']])
                    mastery = int(data['Points'])
                    level = int(data['Level'])
                    mastery_list.append({"mastery": mastery, 'level' : level, "championId": championId})
            
        except AttributeError:
            try:
                me = await get_summoner_by_riot_id(session, riot_id, riot_tag)
                puuid = me['puuid']
                
                data_masteries : dict = await get_champion_masteries(session, puuid)
                
                for value in data_masteries:
                    mastery = value['championPoints']
                    level = value['championLevel']
                    championId = value['championId']
                
                    mastery_list.append({"mastery": mastery, 'level' : level, "championId": championId})
                    
                
            except Exception:
                print(summonerName)
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
                traceback_msg = ''.join(traceback_details)
                print(traceback_msg)
    
    except:
        try:
            print(f"Erreur Masteries {summonerName_url} {riot_tag} : Retour à l'API")
            mastery_list = []
            me = await get_summoner_by_riot_id(session, riot_id, riot_tag)
            puuid = me['puuid']
                    
            data_masteries : dict = await get_champion_masteries(session, puuid)
                    
            for value in data_masteries:
                mastery = value['championPoints']
                level = value['championLevel']
                championId = value['championId']
                    
                mastery_list.append({"mastery": mastery, 'level' : level, "championId": championId})           

        except:
            print(f"Erreur avec l'API pour {summonerName_url} {riot_tag}")
            mastery_list.append({"mastery" : 1, 'level' : 0, 'championId' : 1})

        

    mastery_dict = {
        "summonerName": summonerName,
        "region": "EUW",
        "mastery": mastery_list,
    }

    return pd.DataFrame(mastery_dict['mastery'])



async def get_version(session: aiohttp.ClientSession):

    async with session.get("https://ddragon.leagueoflegends.com/realms/euw.json") as session_version:
        version = await session_version.json()

    return version

async def get_champ_list(session: aiohttp.ClientSession, version):
    champions_versions = version['n']['champion']

    async with session.get(f"https://ddragon.leagueoflegends.com/cdn/{champions_versions}/data/fr_FR/champion.json") as session_champlist:
        current_champ_list = await session_champlist.json()
    
    return current_champ_list


async def get_summoner_by_riot_id(session : aiohttp.ClientSession, riot_id, riot_tag):
    async with session.get(f'https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{riot_id}/{riot_tag}', params={'api_key': api_key_lol}) as session_summoner:
        me = await session_summoner.json()  # informations sur le joueur
    return me

async def get_summoner_by_puuid(puuid, session):
    async with session.get(f'https://europe.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}', params={'api_key': api_key_lol}) as session_summoner:
        me = await session_summoner.json()  # informations sur le joueur
    return me    


async def get_summoner_by_name(session: aiohttp.ClientSession, key):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{key}', params={'api_key': api_key_lol}) as session_summoner:
        me = await session_summoner.json()  # informations sur le joueur
    return me

async def get_summonerinfo_by_puuid(puuid, session):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}', params={'api_key': api_key_lol}) as session_summoner:
        me = await session_summoner.json()

        if session_summoner.status != 200:
            print(session_summoner.reason)
    return me


async def get_league_by_puuid(session: aiohttp.ClientSession, me):
    '''me = puuid'''
    async with session.get(f"https://{my_region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{me}",
                                params={'api_key': api_key_lol}) as session_league:
        stats = await session_league.json()

    return stats


async def get_list_matchs_with_me(session: aiohttp.ClientSession, me, params):
    attemps = 0

    while attemps < 5:
        try:
            async with session.get(f'https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{me["puuid"]}/ids?', params=params) as session_match:

                if session_match.status != 200:
                    print(session_match.status)
                    print(session_match.reason)

                my_matches = await session_match.json()
                
                break
        except:
            attemps += 1
            await asyncio.sleep(5)

            if attemps >= 5:
                my_matches = ''

    return my_matches


async def get_list_matchs_with_puuid(session: aiohttp.ClientSession, puuid, params=None):

    if params is None:
        params = {'start': 0, 'count': 20, 'api_key': api_key_lol}
        
    attemps = 0

    while attemps < 5:
        try:
            async with session.get(f'https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?', params=params) as session_match:

                if session_match.status != 200:
                    print(session_match.status)
                    print(session_match.reason)

                my_matches = await session_match.json()
                break
        except:
            attemps += 1
            await asyncio.sleep(5)

            if attemps >= 5:
                my_matches = ''
    
    return my_matches



async def get_match_detail(session: aiohttp.ClientSession, match_id, params):

    attemps = 0

    while attemps < 5:
        try:
            async with session.get(f'https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}', params=params) as session_match_detail:
                
                if session_match_detail.status != 200:
                    print(session_match_detail.status)
                    print(session_match_detail.reason)

                match_detail_stats = await session_match_detail.json()  # detail du match sélectionné
                break

        except:
            attemps += 1
            await asyncio.sleep(5)

            if attemps >= 5:
                match_detail_stats = ''

    return match_detail_stats


async def get_match_timeline(session: aiohttp.ClientSession, match_id):
    async with session.get(f'https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline', params={'api_key': api_key_lol}) as session_timeline:
        match_detail_timeline = await session_timeline.json()
    return match_detail_timeline


async def get_challenges_config(session):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/challenges/v1/challenges/config?api_key={api_key_lol}') as challenge_config:
        return await challenge_config.json()
    
async def get_spectator(session, puuid):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}?api_key={api_key_lol}') as session_spectator:
        if session_spectator.status == 404:
            return None
        return await session_spectator.json()


async def get_champion_masteries(session, puuid):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}', params={'api_key': api_key_lol}) as data_masteries:    
        return await data_masteries.json()
    

async def get_data_champ_tags(session, version):
    async with session.get(f'https://ddragon.leagueoflegends.com/cdn/{version}/data/fr_FR/champion.json') as session_summoner:
        me = await session_summoner.json()  # informations sur le joueur
        df = pd.DataFrame(me['data']).T
        df = df[['key', 'name', 'tags']]
    return df  

async def get_data_rank(session, puuid):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}?api_key={api_key_lol}') as session_rank:
        if session_rank.status == 404:
            return ''    
        
        return await session_rank.json()



def dict_data(thisId: int, match_detail, info):
    try:
        if thisId > 4:
            liste = [match_detail['info']['participants'][i][info] for i in range(5, 10)] + \
                    [match_detail['info']['participants'][i][info]
                        for i in range(5)]
        else:
            liste = [match_detail['info']['participants'][i][info]
                     for i in range(10)]
    except Exception:
        if thisId > 4:
            liste = [match_detail['info']['participants'][i]['challenges'][info] for i in range(5, 10)] + \
                    [match_detail['info']['participants'][i]['challenges'][info]
                        for i in range(5)]

        else:
            liste = [match_detail['info']['participants'][i]
                     ['challenges'][info] for i in range(10)]

    return liste

def dict_data_swarm(thisId: int, match_detail, info, nb_joueur):
    try:
        liste = [match_detail['info']['participants'][i][info]
                     for i in range(nb_joueur)]
    except Exception:
        if thisId > 4:
            liste = [match_detail['info']['participants'][i]['challenges'][info] for i in range(0, 3)] + \
                    [match_detail['info']['participants'][i]['challenges'][info]
                        for i in range(nb_joueur)]

        else:
            liste = [match_detail['info']['participants'][i]
                     ['challenges'][info] for i in range(nb_joueur)]

    return liste


async def match_by_puuid_with_summonername(summonerName,
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
    my_matches = await get_list_matchs_with_me(session, me, params_my_match)
    last_match = my_matches[idgames]  # match n° idgames
    # detail du match sélectionné
    match_detail_stats = await get_match_detail(session, last_match, params_me)

    return last_match, match_detail_stats, me


   


async def match_by_puuid_with_puuid(puuid,
                         idgames: int,
                         session,
                         index=0,
                         queue=0,
                         count=20,
                         id_game = None):
    params_me = {'api_key': api_key_lol}
    if queue == 0:
        params_my_match = {'start': index,
                           'count': count, 'api_key': api_key_lol}
    else:
        params_my_match = {'queue': queue, 'start': index,
                           'count': count, 'api_key': api_key_lol}

    if id_game == None:
        my_matches = await get_list_matchs_with_puuid(session, puuid, params_my_match)
        last_match = my_matches[idgames]  # match n° idgames
    # detail du match sélectionné
    else:
        last_match = str(id_game)
        if 'EUW' not in last_match:
            last_match = f'EUW1_{last_match}' 
    match_detail_stats = await get_match_detail(session, last_match, params_me)

    return last_match, match_detail_stats


async def getId_with_summonername(summonerName : str, session : aiohttp.ClientSession):
    try:
        last_match, match_detail_stats, me = await match_by_puuid_with_summonername(summonerName, 0, session)
        return str(match_detail_stats['info']['gameId'])
    except KeyError:
        data = lire_bdd('tracker', 'dict')
        return str(data[summonerName]['id'])
    except asyncio.exceptions.TimeoutError:
        data = lire_bdd('tracker', 'dict')
        return str(data[summonerName]['id'])
    except Exception:
        print('erreur getId')
        data = lire_bdd('tracker', 'dict')
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
        traceback_msg = ''.join(traceback_details)
        print(traceback_msg)
        return str(data[summonerName]['id'])

async def getId_with_puuid(puuid : str, session : aiohttp.ClientSession):
    try:
        last_match, match_detail_stats = await match_by_puuid_with_puuid(puuid, 0, session)
        return str(match_detail_stats['info']['gameId'])
    except asyncio.exceptions.TimeoutError:
        print('error TimeOut')
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
        traceback_msg = ''.join(traceback_details)
        print(traceback_msg)
        data = lire_bdd('tracker').transpose()
        return str(data.loc[data['puuid'] == puuid]['id'].values[0])
    except Exception:
        print('error Autres')
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
        traceback_msg = ''.join(traceback_details)
        print(traceback_msg)
        data = lire_bdd('tracker').transpose()
        return str(data.loc[data['puuid'] == puuid]['id'].values[0])
    
    
async def get_spectator_data(puuid, session):
    data = await get_spectator(session, puuid)

    if data is None:
        return None, None, None, None, None

    thisQ = dict_id_q.get(data['gameQueueConfigId'], 'OTHER')

    summonerName = summonerName.lower()

    id_game = data['gameId']

    df = pd.DataFrame(data['participants'])
    df = df.sort_values('teamId')

    df['summonerName'] = df['summonerName'].str.lower()

    version = await get_version(session)
    # get champion list
    current_champ_list = await get_champ_list(session, version)

    champ_dict = {}
    for key in current_champ_list['data']:
                row = current_champ_list['data'][key]
                champ_dict[row['key']] = row['id']

    df['champion'] = df['championId'].astype('str').map(champ_dict)

    champ_joueur = df.loc[df['summonerName'] == summonerName, 'champion'].values[0]
    id_icon = df.loc[df['summonerName'] == summonerName, 'profileIconId'].values[0]
    icon = f'https://ddragon.leagueoflegends.com/cdn/{version["n"]["profileicon"]}/img/profileicon/{id_icon}.png'

    df['summonerName'] = df['summonerName'].str.replace(' ', '%20') # pour l'url opgg, chaque espace = %20

    liste_joueurs = ''.join(joueur + ',' for joueur in df['summonerName'].tolist())
    url = f'https://www.op.gg/multisearch/euw?summoners={liste_joueurs}'

    return url, thisQ, id_game, champ_joueur, icon  


def charger_font(size):

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", size)  # Ubuntu 18.04
    except OSError:
        try:
            font = ImageFont.truetype("arial.ttf", size)  # Windows
        except OSError:
            font = ImageFont.truetype(
                            "AppleSDGothicNeo.ttc", size
                        )  # MacOS

    return font




    
    
def load_timeline(timeline):
    df_timeline = pd.DataFrame(
        timeline['info']['frames'][1]['participantFrames'])
    df_timeline = df_timeline.transpose()
    df_timeline['timestamp'] = 0

    minute = len(timeline['info']['frames']) - 1

    for i in range(1, minute):
        df_timeline2 = pd.DataFrame(
            timeline['info']['frames'][i]['participantFrames'])
        df_timeline2 = df_timeline2.transpose()
        df_timeline2['timestamp'] = i
        df_timeline = df_timeline.append(df_timeline2)

    df_timeline['riot_id'] = df_timeline['participantId']
            
    return df_timeline, minute


async def get_stat_champion_by_player(session, champ_dict, riot_id, riot_tag, season=23):
    """
    Retrieves the statistics of a player's performance with each champion.
    
    Parameters:
        session (object): The session object for making HTTP requests.
        champ_dict (dict): A dictionary mapping champion IDs to their names.
        riot_id (str): The Riot ID of the player.
        riot_tag (str): The Riot tag of the player.
        season (int, optional): The season number. Defaults to 22.
    
    Returns:
        pandas.DataFrame: A DataFrame containing the statistics of the player's performance with each champion.
    """

    if isinstance(season, int):
        data_stat = await getPlayerStats(session, riot_id, riot_tag, season=season)

        if data_stat == '':
            return ''
        
        try:
            df_data_stat = pd.DataFrame(data_stat['data']['fetchPlayerStatistics'][0]['basicChampionPerformances'])
        except TypeError:
            return ''
        
        if not 'championId' in df_data_stat.columns: # pas de data
            return ''
            

        df_data_stat['championId'] = df_data_stat['championId'].astype(str)

        df_data_stat.replace({'championId': champ_dict}, inplace=True)

    if isinstance(season, list):
        list_df = []
        for s in season:
            data_stat = await getPlayerStats(session, riot_id, riot_tag, season=s)

            if data_stat == '':
                continue
            
            try:
                df_data_stat = pd.DataFrame(data_stat['data']['fetchPlayerStatistics'][0]['basicChampionPerformances'])
            except TypeError:
                continue
            
            if not 'championId' in df_data_stat.columns: # pas de data
                continue
                

            df_data_stat['championId'] = df_data_stat['championId'].astype(str)

            df_data_stat.replace({'championId': champ_dict}, inplace=True)

            list_df.append(df_data_stat)
    
        if len(list_df) == 0:
            return ''
        
        df_data_stat = pd.concat(list_df)

        if df_data_stat.empty:
            return ''

        df_data_stat = df_data_stat.groupby('championId', as_index=False).sum()

    df_data_stat['winrate'] = df_data_stat['wins'] / df_data_stat['totalMatches'] * 100

    df_data_stat['winrate'] = df_data_stat['winrate'].astype(int)
    
    return df_data_stat



async def detect_duos(session, riot_id, riot_tag, count=10):
    summoner_data = await get_summoner_by_riot_id(session, riot_id, riot_tag)
    match_ids = await get_list_matchs_with_puuid(session, summoner_data['puuid'], {'start': 0,
                                                                                  'count': count, 'api_key': api_key_lol})

    duo_tracker = {}

    for match_id in match_ids:
        match_details = await get_match_detail(session, match_id, {'api_key': api_key_lol})
        participants = match_details['info']['participants']
        
        team = {p['summonerName']: p['teamId'] for p in participants}

        # Parcourir tous les joueurs
        for player1 in team:
            for player2 in team:
                if player1 != player2 and team[player1] == team[player2]:
                    duo_key = tuple(sorted([player1, player2]))
                    if duo_key not in duo_tracker:
                        duo_tracker[duo_key] = 0
                    duo_tracker[duo_key] += 1

    return {duo: count for duo, count in duo_tracker.items() if count > 5}



class matchlol():

    def __init__(self,
                 id_compte,
                 riot_id,
                 riot_tag,
                 idgames: int,
                 queue: int = 0,
                 index: int = 0,
                 count: int = 50,
                 identifiant_game=None,
                 me=None):
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
        self.id_compte = id_compte
        self.riot_id = riot_id
        self.riot_tag = riot_tag
        self.idgames = idgames
        self.queue = queue
        self.index = index
        self.count = count
        self.params_me = {'api_key': api_key_lol}
        self.model = ''


        if identifiant_game is None:
            self.identifiant_game = identifiant_game
        else:
            self.identifiant_game = str(identifiant_game)
            if 'EUW' not in self.identifiant_game:
                self.identifiant_game = f'EUW1_{self.identifiant_game}'
        self.me = me

        params = lire_bdd_perso('select * from settings', format='dict', index_col='parametres')

        self.ugg = params['update_ugg']['value']
        self.season = int(params['saison']['value'])
        self.last_season = params['last_season']['value']
        self.split = int(params['split']['value'])
        self.season_ugg = int(params['season_ugg']['value'])
        self.season_ugg_min = int(params['season_ugg_min']['value'])
        self.activate_mobalytics = params['data_mobalytics']['value']

        self.list_season_ugg = list(range(self.season_ugg_min, self.season_ugg + 1))
        

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

        if self.me is None:
            self.me = await get_summoner_by_riot_id(self.session, self.riot_id, self.riot_tag)
            
            
        self.puuid = self.me['puuid']    
        self.info_account = await get_summonerinfo_by_puuid(self.puuid, self.session)
        # on recherche l'id de la game.
        if self.identifiant_game is None:
            self.my_matches = await get_list_matchs_with_me(self.session, self.me, self.params_my_match)
            self.last_match = self.my_matches[self.idgames]  # match n° idgames
        else:  # si identifiant_game est renseigné, on l'a déjà en entrée.
            self.last_match = self.identifiant_game

        # detail du match sélectionné
        self.match_detail_stats = await get_match_detail(self.session, self.last_match, self.params_me)




        self.avatar = self.info_account['profileIconId']
        self.level_summoner = self.info_account['summonerLevel']

        # on a besoin de la version du jeu pour obtenir les champions
        self.version = await get_version(self.session)
        # get champion list
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

        # Event du match selectionné
        if self.thisQ in ['RANKED', 'FLEX', 'SWIFTPLAY']:
            self.data_timeline = await get_match_timeline(self.session, self.last_match)
            self.index_timeline = self.data_timeline['metadata']['participants'].index(self.puuid) + 1
        else:
            self.data_timeline = ''  
            self.index_timeline = 0

        self.liste_puuid = self.match_detail['metadata']['participants']
        self.liste_account_id = [self.match_detail['info']['participants'][i]['summonerId'] for i in range(self.nb_joueur)]


    async def prepare_data(self):
        """Récupère les données de la game"""

        self.champ_dict = {}
        for key in self.current_champ_list['data']:
            row = self.current_champ_list['data'][key]
            self.champ_dict[row['key']] = row['id']

        # Detail de chaque champion...

        try:

            self.dic = {(self.match_detail['info']['participants'][i]['riotIdGameName']).lower(
            ).replace(" ", "") + "#" + (self.match_detail['info']['participants'][i]['riotIdTagline'].upper()): i for i in range(self.nb_joueur)}
        except KeyError: # game ancienne, où le riotid n'existait pas

            self.dic = {(self.match_detail['info']['participants'][i]['summonerName']).lower(
            ).replace(" ", ""): i for i in range(self.nb_joueur)}
            
        # stats
        try:

            self.thisId = self.dic[
                self.riot_id.lower().replace(" ", "") + "#" + self.riot_tag.upper()]  # cherche le pseudo dans le dico et renvoie le nombre entre 0 et 9
        except KeyError: # changement de pseudo ? On va faire avec le puuid

            self.dic = {(self.match_detail['metadata']['participants'][i]) : i for i in range(self.nb_joueur)}
            self.thisId = self.dic[self.puuid]


        self.match_detail_participants = self.match_detail['info']['participants'][self.thisId]
        self.match_detail_challenges = self.match_detail_participants['challenges']
        self.thisPosition = self.match_detail_participants['teamPosition']


        if (str(self.thisPosition) == "MIDDLE"):
            self.thisPosition = "MID"
        elif (str(self.thisPosition) == "BOTTOM"):
            self.thisPosition = "ADC"
        elif (str(self.thisPosition) == "UTILITY"):
            self.thisPosition = "SUPPORT"

        try:
            self.summonerName = self.match_detail_participants['summonerName'].lower().replace(' ', '')
        except KeyError:
            self.summonerName = self.match_detail_participants['riotIdGameName'].lower().replace(' ', '')
        self.timestamp = str(self.match_detail['info']['gameCreation'])[:-3]  # traduire avec datetime.date.fromtimestamp()
        # self.thisQ = ' '
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
        self.thisTimeLiving = fix_temps(round(
            (int(self.match_detail_participants['longestTimeSpentLiving']) / 60), 2))
        self.thisWin = ' '
        self.thisTime = fix_temps(round(
            (int(self.match_detail['info']['gameDuration']) / 60), 2))
        self.time_CC = self.match_detail_participants['timeCCingOthers']
        self.largest_crit = self.match_detail_participants['largestCriticalStrike']

        self.teamId = self.match_detail_participants['teamId']
                
        # si le joueur n'est pas mort, le temps est à 0
        if self.thisTimeLiving == 0:
            self.thisTimeLiving = self.thisTime
            
            
        self.thisDamage = self.match_detail_participants['totalDamageDealtToChampions']
        self.thisDamageNoFormat = self.match_detail_participants['totalDamageDealtToChampions']
        self.thisDamageAP = self.match_detail_participants['magicDamageDealtToChampions']
        self.thisDamageAPNoFormat = self.match_detail_participants['magicDamageDealtToChampions']
        self.thisDamageAD = self.match_detail_participants['physicalDamageDealtToChampions']
        self.thisDamageADNoFormat = self.match_detail_participants['physicalDamageDealtToChampions']
        self.thisDamageTrue = self.match_detail_participants['trueDamageDealtToChampions']
        self.thisDamageTrueNoFormat = self.match_detail_participants['trueDamageDealtToChampions']

        self.thisDamageTrueAllNoFormat = self.match_detail_participants['trueDamageDealt']

        self.thisDamageADAllNoFormat = self.match_detail_participants['physicalDamageDealt']
        self.thisDamageAPAllNoFormat = self.match_detail_participants['magicDamageDealt']

        self.thisDamageAllNoFormat = self.match_detail_participants['totalDamageDealt']

        self.thisDoubleListe = dict_data(
            self.thisId, self.match_detail, 'doubleKills')
        self.thisTripleListe = dict_data(
            self.thisId, self.match_detail, 'tripleKills')
        self.thisQuadraListe = dict_data(
            self.thisId, self.match_detail, 'quadraKills')
        self.thisPentaListe = dict_data(
            self.thisId, self.match_detail, 'pentaKills')

        self.thisTimeSpendDead = fix_temps(round(
            float(self.match_detail_participants['totalTimeSpentDead'])/60, 2))

        self.thisTimeSpendAlive = fix_temps(round(
            self.thisTime - self.thisTimeSpendDead, 2))
        
        try:
            self.first_tower_time = self.match_detail_challenges['firstTurretKilledTime']    
            self.first_tower_time = fix_temps(round(
                (self.first_tower_time / 60), 2)) 
        except KeyError:
            self.first_tower_time = 999

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
        except Exception:
            self.thisPing = 0

        self.item = self.match_detail_participants

        self.thisItems = [self.item[f'item{i}'] for i in range(6)]

        # item6 = ward. Pas utile

        # on transpose les items

        async with self.session.get(f"https://ddragon.leagueoflegends.com/cdn/{self.version['n']['item']}/data/fr_FR/item.json") as itemlist:
            self.data = await itemlist.json()

        self.data_item = []

        try:
            for item in self.thisItems:
                if item != 0:  # si = 0, il n'y a pas d'items
                    self.data_item.append(self.data['data'][str(item)]['name'])
        except KeyError:

            async with self.session.get(f"https://ddragon.leagueoflegends.com/cdn/14.6.1/data/fr_FR/item.json") as itemlist:
                self.data = await itemlist.json()      
                for item in self.thisItems:
                    if item != 0:  # si = 0, il n'y a pas d'items
                        self.data_item.append(self.data['data'][str(item)]['name'])      

        self.data_item = (' | '.join(self.data_item))

        self.thisMinionPerMin = round((self.thisMinion / self.thisTime), 2)
        self.thisVisionPerMin = round((self.thisVision / self.thisTime), 2)
        self.thisGoldPerMinute = round((self.thisGold / self.thisTime), 2)
        self.thisDamagePerMinute = round(
            int(self.match_detail_participants['totalDamageDealtToChampions']) / self.thisTime, 0)

        self.thisDamageTrueAllPerMinute = round(int(self.match_detail_participants['trueDamageDealt']) / self.thisTime, 0)
        

        self.thisDamageADAllPerMinute = round(int(self.match_detail_participants['physicalDamageDealt']) / self.thisTime, 0)
        
        self.thisDamageAPAllPerMinute = round(int(self.match_detail_participants['magicDamageDealt']) / self.thisTime, 0)
        

        self.thisDamageAllPerMinute = round(int(self.match_detail_participants['totalDamageDealt']) / self.thisTime, 0)

        self.damage_per_kills = round(
            (self.thisDamage / self.thisKills), 0) if self.thisKills != 0 else 0
        



        self.thisStats = await get_data_rank(self.session, self.puuid)

        
        self.thisWinrateStat = ' '
        self.thisWinrate = ' '
        self.thisRank = ' '
        self.thisLP = ' '

        if int(self.thisDeaths) >= 1:
            self.thisKDA = float(round(self.match_detail_challenges['kda'], 2))
        else:
            self.thisKDA = 0
            
        self.kills_min = np.round(self.thisKills / self.thisTime, 2)
        self.deaths_min = np.round(self.thisDeaths / self.thisTime, 2)
        self.assists_min = np.round(self.thisAssists / self.thisTime, 2)

        # Page record 2

        self.thisSpellUsed = self.match_detail_challenges['abilityUses']
        self.thisbuffsVolees = self.match_detail_challenges['buffsStolen']
        self.thisSpellsDodged = self.match_detail_challenges['dodgeSkillShotsSmallWindow']
        self.thisSoloKills = self.match_detail_challenges['soloKills']
        self.thisDanceHerald = self.match_detail_challenges['dancedWithRiftHerald']
        self.thisPerfectGame = self.match_detail_challenges['perfectGame']
        self.thisJUNGLEafter10min = int(self.match_detail_challenges['jungleCsBefore10Minutes'])
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
        
        
        # pings
        
        self.pings_allin = self.match_detail_participants['allInPings']
        self.pings_assistsme = self.match_detail_participants['assistMePings']
        self.pings_basics = self.match_detail_participants['basicPings']
        self.pings_command = self.match_detail_participants['commandPings']
        self.pings_danger = self.match_detail_participants['dangerPings']
        self.pings_ennemymissing = self.match_detail_participants['enemyMissingPings']
        self.pings_ennemy_vision = self.match_detail_participants['enemyVisionPings']
        self.pings_get_back = self.match_detail_participants['getBackPings']
        self.pings_hold = self.match_detail_participants['holdPings']
        self.pings_onmyway = self.match_detail_participants['onMyWayPings']
        
        # spells
        
        self.s1cast = self.match_detail_participants['spell1Casts']
        self.s2cast = self.match_detail_participants['spell2Casts']
        self.s3cast = self.match_detail_participants['spell3Casts']
        self.s4cast = self.match_detail_participants['spell4Casts']
        
        # Stat de team :

        self.thisBaronPerso = self.match_detail_challenges['teamBaronKills']
        self.thisElderPerso = self.match_detail_challenges['teamElderDragonKills']
        # thisHeraldPerso = match_detail_challenges['teamRiftHeraldKills']
        self.allitems = {}

        if self.thisId <= 4:
            self.team = 0
            self.n_moba = 1
        # le sort_values permet de mettre les slots vides à la fin    
            for joueur in range(self.nb_joueur):
                liste_items = [self.match_detail['info']['participants'][joueur][f'item{i}'] for i in range(6)]
                liste_items.sort(reverse=True)
                self.allitems[joueur] = liste_items
        else:
            self.team = 1
            self.n_moba = 0
            for joueur in range(self.nb_joueur):
                joueur_id = joueur
                if joueur >= 5:
                    joueur_id -= 5
                else:
                    joueur_id += 5
                liste_items = [self.match_detail['info']['participants'][joueur][f'item{i}'] for i in range(6)]
                liste_items.sort(reverse=True)
                self.allitems[joueur_id] = liste_items 

        self.ban = self.match_detail['info']['teams'][self.team]['bans']
        self.ban_ennemi = self.match_detail['info']['teams'][self.n_moba]['bans']
        self.team_stats = self.match_detail['info']['teams'][self.team]['objectives']
        
        self.champ_dict['-1'] = 'Aucun'
        if len(self.ban) > 0: # s'il y a des ban
            self.liste_ban = []
            for key in self.ban:
                row = self.champ_dict[str(key['championId'])]
                self.liste_ban.append(row)
                
            for key in self.ban_ennemi:
                row = self.champ_dict[str(key['championId'])]
                self.liste_ban.append(row)

        
        else:
            self.thisban = ['-1', '-1', '-1', '-1', '-1', '-1', '-1', '-1', '-1', '-1']
            self.liste_ban = ['-1', '-1', '-1', '-1', '-1', '-1', '-1', '-1', '-1', '-1']
        
        self.thisBaronTeam = self.team_stats['baron']['kills']
        self.thisDragonTeam = self.team_stats['dragon']['kills']
        self.thisHeraldTeam = self.team_stats['riftHerald']['kills']
        self.thisTurretsKillsTeam = self.team_stats['tower']['kills']
        self.thisHordeTeam = self.team_stats['horde']['kills']
        self.thisTowerTeam = self.team_stats['tower']['kills']
        self.thisInhibTeam = self.team_stats['inhibitor']['kills']


        try:
            self.trade_efficience = round(self.thisDamageNoFormat / self.thisDamageTakenNoFormat * 100,2)
        except ZeroDivisionError:
            self.trade_efficience = 0



        try:
            self.thisAtakhanTeam = self.team_stats['atakhan']['kills']
        except:
            self.thisAtakhanTeam = 0


        try:
            self.thisCSAdvantageOnLane = round(
                self.match_detail_challenges['maxCsAdvantageOnLaneOpponent'], 0)
        except Exception:
            self.thisCSAdvantageOnLane = 0

        try:
            self.thisLevelAdvantage = self.match_detail_challenges['maxLevelLeadLaneOpponent']
        except Exception:
            self.thisLevelAdvantage = 0

        try:
            self.AFKTeam = self.match_detail_challenges['hadAfkTeammate']
            self.AFKTeamBool = True
        except Exception:
            self.AFKTeam = 0
            self.AFKTeamBool = False

        self.thisSkillshot_dodged = self.match_detail_challenges['skillshotsDodged']
        self.thisSkillshot_hit = self.match_detail_challenges['skillshotsHit']

        self.thisSkillshot_dodged_per_min = round(
            (self.thisSkillshot_dodged / self.thisTime), 2)


        self.thisSkillshot_hit_per_min = round(
            (self.thisSkillshot_hit / self.thisTime), 2)

        try:
            self.thisTurretPlatesTaken = self.match_detail_challenges['turretPlatesTaken']
        except Exception:
            self.thisTurretPlatesTaken = 0

        try:
            self.ControlWardInRiver = round(
                self.match_detail_challenges['controlWardTimeCoverageInRiverOrEnemyHalf'], 2)
        except Exception:
            self.ControlWardInRiver = 0

        try:
            self.thisVisionAdvantage = round(
                self.match_detail_challenges['visionScoreAdvantageLaneOpponent']*100, 2)
        except Exception:
            self.thisVisionAdvantage = 0

        try:
            self.earliestDrake = fix_temps(round(
                self.match_detail_challenges['earliestDragonTakedown'] / 60, 2))
        except Exception:
            self.earliestDrake = 0

        try:
            self.earliestBaron = fix_temps(round(
                self.match_detail_challenges['earliestBaron'] / 60, 2))
        except Exception:
            self.earliestBaron = 0

        try:
            self.participation_tower = round(
                (self.thisTurretsKillsPerso / self.thisTurretsKillsTeam)*100, 2)
        except Exception:
            self.participation_tower = 0

        try:
            self.petales_sanglants = self.match_detail_challenges['InfernalScalePickup']
        except:
            self.petales_sanglants = 0


        self.enemy_immobilisation = self.match_detail_challenges['enemyChampionImmobilizations']
        self.totaltimeCCdealt = fix_temps(round(
            (int(self.match_detail_participants['totalTimeCCDealt']) / 60), 2))



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
        
        if self.thisQ in ['ARAM', 'CLASH ARAM']:
            try:
                self.snowball = self.match_detail_challenges['snowballsHit']
            except Exception:
                self.snowball = 0
        else:
            self.snowball = -1

        # pseudo

        
        try:
            self.thisRiotIdListe = dict_data(
                self.thisId, self.match_detail, 'riotIdGameName')
        
            self.thisRiotTagListe = dict_data(
                self.thisId, self.match_detail, 'riotIdTagline')
            
            self.thisPseudoListe = self.thisRiotIdListe
        
        except KeyError:
            self.thisPseudoListe = dict_data(
                self.thisId, self.match_detail, 'summonerName')
            self.thisRiotIdListe = self.thisPseudoListe
            self.thisRiotTagListe = ''    
            
        # Correction d'un bug rito



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
        self.thisAllieFeeder = float(self.thisAllieFeeder[:5].max())

        # assists

        self.thisAssistsListe = dict_data(
            self.thisId, self.match_detail, 'assists')

        # gold

        self.thisGoldListe = dict_data(
            self.thisId, self.match_detail, 'goldEarned')

        self.thisChampTeam1 = [self.thisChampNameListe[i] for i in range(5)]
        self.thisChampTeam2 = [self.thisChampNameListe[i]
                               for i in range(5, self.nb_joueur)]

        self.thisGold_team1 = sum(self.thisGoldListe[:5])
        self.thisGold_team2 = sum(self.thisGoldListe[5:self.nb_joueur])

        self.gold_share = round((self.thisGoldNoFormat / self.thisGold_team1) * 100,2)
        self.ecart_gold_team = self.thisGold_team1 - self.thisGold_team2

        self.thisVisionListe = dict_data(
            self.thisId, self.match_detail, 'visionScore')
        
        self.thisPinkListe = dict_data(
            self.thisId, self.match_detail, 'visionWardsBoughtInGame')

        self.thisVisionPerMinListe = [round((self.thisVisionListe[i] / self.thisTime), 1) for i in range(self.nb_joueur)]

        self.thisJungleMonsterKilledListe = dict_data(
            self.thisId, self.match_detail, 'neutralMinionsKilled')
        self.thisMinionListe = dict_data(
            self.thisId, self.match_detail, 'totalMinionsKilled')

        self.thisKDAListe = dict_data(self.thisId, self.match_detail, "kda")
        
        self.thisDamagePerMinuteListe = [round((self.thisDamageListe[i]) / self.thisTime, 1) for i in range(self.nb_joueur)]
        self.thisMinionPerMinListe = [round((self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]) / self.thisTime, 1) for i in range(self.nb_joueur)]
        self.thisTankPerMinListe = [round((self.thisDamageTakenListe[i]) / self.thisTime, 1) for i in range(self.nb_joueur)]


        self.thisLevelListe = dict_data(
            self.thisId, self.match_detail, "champLevel")

        def ecart_role_cs(ally):
            return (self.thisMinionListe[ally] + self.thisJungleMonsterKilledListe[ally]) - (
                self.thisMinionListe[ally+5] + self.thisJungleMonsterKilledListe[ally+5])
        
        def ecart_kills(ally):
            return self.thisKillsListe[ally] - self.thisKillsListe[ally+5]
        
        def ecart_morts(ally):
            return self.thisDeathsListe[ally] - self.thisDeathsListe[ally+5]
        
        def ecart_assists(ally):
            return self.thisAssistsListe[ally] - self.thisAssistsListe[ally+5]
        
        def ecart_dmg(ally):
            return self.thisDamageListe[ally] - self.thisDamageListe[ally+5]
        

        for i, role in enumerate(['top', 'jgl', 'mid', 'adc', 'supp']):
            setattr(self, f'ecart_{role}_cs', ecart_role_cs(i))
            setattr(self, f'ecart_{role}_gold', self.thisGoldListe[i] - self.thisGoldListe[i+5])
            setattr(self, f'ecart_{role}_gold_affiche', self.thisGoldListe[i] - self.thisGoldListe[i+5])
            setattr(self, f'ecart_{role}_vision', self.thisVisionListe[i] - self.thisVisionListe[i+5])
            setattr(self, f'ecart_{role}_kills', ecart_kills(i))
            setattr(self, f'ecart_{role}_morts', ecart_morts(i))
            setattr(self, f'ecart_{role}_assists', ecart_assists(i))
            setattr(self, f'ecart_{role}_dmg', ecart_dmg(i))

        # on crée des variables temporaires pour le kpliste, car si une team ne fait pas de kills, on va diviser par 0, ce qui n'est pas possible
        temp_team_kills = self.thisTeamKills
        temp_team_kills_op = self.thisTeamKillsOp

        if temp_team_kills == 0:
            temp_team_kills = 1
        if temp_team_kills_op == 0:
            temp_team_kills_op = 1            


        self.thisKPListe = [int(round((self.thisKillsListe[i] + self.thisAssistsListe[i]) / (temp_team_kills if i < 5
                                                                                                 else temp_team_kills_op), 2) * 100)
                                for i in range(self.nb_joueur)]


        self.adversaire_direct = {"TOP": self.ecart_top_gold, "JUNGLE": self.ecart_jgl_gold, "MID": self.ecart_mid_gold, "ADC": self.ecart_adc_gold, "SUPPORT": self.ecart_supp_gold}
        
        self.adversaire_direct_cs = {"TOP": self.ecart_top_cs, "JUNGLE": self.ecart_jgl_cs, "MID": self.ecart_mid_cs, "ADC": self.ecart_adc_cs, "SUPPORT": self.ecart_supp_cs}

        self.adversaire_direct_kills = {"TOP": self.ecart_top_kills, "JUNGLE": self.ecart_jgl_kills, "MID": self.ecart_mid_kills, "ADC": self.ecart_adc_kills, "SUPPORT": self.ecart_supp_kills}

        self.adversaire_direct_morts = {"TOP": self.ecart_top_morts, "JUNGLE": self.ecart_jgl_morts, "MID": self.ecart_mid_morts, "ADC": self.ecart_adc_morts, "SUPPORT": self.ecart_supp_morts}

        self.adversaire_direct_assists = {"TOP": self.ecart_top_assists, "JUNGLE" : self.ecart_jgl_assists, "MID": self.ecart_mid_assists, "ADC": self.ecart_adc_assists, "SUPPORT": self.ecart_supp_assists}

        self.adversaire_direct_dmg = {"TOP": self.ecart_top_dmg, "JUNGLE": self.ecart_jgl_dmg, "MID": self.ecart_mid_dmg, "ADC": self.ecart_adc_dmg, "SUPPORT": self.ecart_supp_dmg}

        try:
            self.ecart_gold = self.adversaire_direct[self.thisPosition]
        except KeyError:
            self.ecart_gold = "Indisponible"

        try:
            self.ecart_cs = self.adversaire_direct_cs[self.thisPosition]
        except KeyError:
            self.ecart_cs = "Indisponible"

        try:
            self.ecart_kills = self.adversaire_direct_kills[self.thisPosition]
        except KeyError:
            self.ecart_kills = 0

        try:
            self.ecart_morts = self.adversaire_direct_morts[self.thisPosition]
        except KeyError:
            self.ecart_morts = 0

        try:
            self.ecart_assists = self.adversaire_direct_assists[self.thisPosition]
        except KeyError:
            self.ecart_assists = 0

        try:
            self.ecart_dmg = self.adversaire_direct_dmg[self.thisPosition]
        except KeyError:
            self.ecart_dmg = 0

        # mise en forme

        variables_format = [self.thisGold_team1,
                     self.thisGold_team2,
                     self.ecart_top_gold,
                     self.ecart_jgl_gold,
                     self.ecart_mid_gold,
                     self.ecart_adc_gold,
                     self.ecart_supp_gold,
                     self.ecart_top_cs,
                     self.ecart_jgl_cs,
                    self.ecart_mid_cs,
                    self.ecart_adc_cs,
                    self.ecart_supp_cs,
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
            self.ecart_gold_noformat = self.ecart_gold
            self.ecart_gold = "{:,}".format(
                self.ecart_gold).replace(',', ' ').replace('.', ',')
            self.ecart_gold_permin = round((self.ecart_gold_noformat / self.thisTime), 2)
        else:
            self.ecart_gold_noformat = 0
            self.ecart_gold_permin = 0



        if self.ecart_cs != "Indisponible":  # si nombre
            self.ecart_cs_noformat = self.ecart_cs
            self.ecart_cs = "{:,}".format(
                self.ecart_cs).replace(',', ' ').replace('.', ',')
            self.ecart_cs_permin = round((self.ecart_cs_noformat / self.thisTime), 2)
        else:
            self.ecart_cs_noformat = 0
            self.ecart_cs_permin = 0

        self.thisDamageSelfMitigatedFormat = "{:,}".format(
            self.thisDamageSelfMitigated).replace(',', ' ').replace('.', ',')
        self.thisTotalOnTeammatesFormat = "{:,}".format(
            self.thisTotalOnTeammates).replace(',', ' ').replace('.', ',')


        try:
            self.thisKP = int(
                round((self.thisKills + self.thisAssists) / (self.thisTeamKills), 2) * 100)
        except Exception:
            self.thisKP = 0


        self.thisDamageRatio = round(
            (self.match_detail_challenges['teamDamagePercentage']) * 100, 2)
        self.thisDamageTakenRatio = round(
            (self.match_detail_challenges['damageTakenOnTeamPercentage']) * 100, 2)

        self.thisDamageRatioListe = dict_data(
            self.thisId, self.match_detail, "teamDamagePercentage")
        self.thisDamageTakenRatioListe = dict_data(
            self.thisId, self.match_detail, "damageTakenOnTeamPercentage")
        
        self.DamageGoldRatio = round((self.thisDamageNoFormat/self.thisGoldNoFormat)*100,2)
        




        self.mastery_list = []

        self.thisRiotIdListe = dict_data(
                self.thisId, self.match_detail, 'riotIdGameName')
        
        self.thisRiotTagListe = dict_data(
                self.thisId, self.match_detail, 'riotIdTagline')
        
        for id, tag in zip(self.thisRiotIdListe, self.thisRiotTagListe):
            try:
                id_tag = f'{id}#{tag}'
                masteries_data = await get_masteries_old(id_tag, self.champ_dict, self.session)
                masteries_data.set_index('championId', inplace=True)
                self.mastery_list.append(masteries_data)
            except:
                self.mastery_list.append(pd.DataFrame())

        self.mastery_level = []
        for masteries_df, championid in zip(self.mastery_list, self.thisChampListe):
            try:
                self.mastery_level.append(masteries_df.loc[championid]['level'])
            except:
                self.mastery_level.append(0)


        self.url_game = f'https://www.leagueofgraphs.com/fr/match/euw/{str(self.last_match)[5:]}#participant{int(self.thisId)+1}'

        self.mvp = 0

        self.badges = ''


        
    async def prepare_data_moba(self):


        self.liste_rank = []
        self.liste_tier = []
        self.liste_lp = []
        self.winrate_joueur = {}
        self.winrate_champ_joueur = {}
        self.role_pref = {}
        self.all_role = {}
        self.role_count = {}
        self.dict_serie = {}

        

        if self.activate_mobalytics == 'True':
            # On update le profil mobalytics pour chaque joueur
            for riot_id, riot_tag in zip(self.thisRiotIdListe, self.thisRiotTagListe):
                await update_moba(self.session, riot_id, riot_tag)
            try:
                self.data_mobalytics_complete = await get_mobalytics(f'{self.riot_id}#{self.riot_tag}', self.session, int(self.last_match[5:]))
                self.moba_ok = True
            except:
                self.moba_ok = False
        else:
            self.moba_ok = False

        self.model = pickle.load(open('model/scoring_rf.pkl', 'rb'))

        if self.moba_ok:

            try:
                self.avgtier_ally = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.n_moba]['avgTier']['tier']
                self.avgrank_ally = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.n_moba]['avgTier']['division']

                self.avgtier_enemy = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.team]['avgTier']['tier']
                self.avgrank_enemy = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.team]['avgTier']['division']


            except TypeError:
                self.avgtier_ally = ''
                self.avgrank_ally = ''

                self.avgtier_enemy = ''
                self.avgrank_enemy = ''

            for i in range(self.nb_joueur):
                riot_id = self.thisRiotIdListe[i].lower()
                riot_tag = self.thisRiotTagListe[i].lower()
                pseudo = f"{riot_id}#{riot_tag}"

                # --- RANK ET TIER ---
                try:
                    tier, rank, lp = await get_rank_moba(self.session, riot_id, riot_tag)
                except Exception:
                    rank = ''
                    tier = ''
                    lp = 0
                self.liste_rank.append(rank)
                self.liste_tier.append(tier)
                self.liste_lp.append(lp)

                # --- WINRATE GLOBAL ---
                try:
                    wr_res = await get_wr_ranked(self.session, riot_id, riot_tag)
                    stats = wr_res['data']['lol']['player']['queuesStats']['items']
                    ranked_stats = next((q for q in stats if q.get('virtualQueue', '') == 'RANKED_SOLO'), None)
                    if ranked_stats:
                        wr = int(round(ranked_stats.get('winrate', 0) * 100))
                        nbgames = ranked_stats.get('gamesCount', 0)
                    else:
                        wr, nbgames = 0, 0
                except Exception:
                    wr, nbgames = 0, 0
                self.winrate_joueur[pseudo] = {'winrate': wr, 'nbgames': nbgames}

                # --- WINRATE CHAMPION & STATS PAR CHAMPION ---
                try:
                    self.df_data_stat = await get_stat_champion_by_player_mobalytics(self.session, riot_id, riot_tag)
                    self.df_data_stat['championId'] = self.df_data_stat['championId'].astype(str)
                    self.df_data_stat['championId'] = self.df_data_stat['championId'].replace(self.champ_dict)

                    champ_name = self.thisChampNameListe[i]
                    if champ_name and not self.df_data_stat.empty:
                        filtered = self.df_data_stat[self.df_data_stat['championId'] == champ_name]
                        self.df_data_stat['poids_games'] = (self.df_data_stat['totalMatches'] / self.df_data_stat['totalMatches'].sum() * 100).astype(int)
                        if not filtered.empty:
                            # Calcul winrate, KDA, poids_games...
                            filtered = filtered.copy()
                            filtered['winrate'] = (filtered['wins'] / filtered['totalMatches'] * 100).astype(int)
                            filtered['poids_games'] = (filtered['totalMatches'] / self.df_data_stat['totalMatches'].sum() * 100).astype(int)
                            try:
                                filtered['kda'] = np.round((filtered['kills'] + filtered['assists']) / filtered['deaths'], 2)
                            except ZeroDivisionError:
                                filtered['kda'] = np.round((filtered['kills'] + filtered['assists']) / 1, 2)
                            dict_data_stat = filtered.to_dict(orient='records')[0]
                        else:
                            dict_data_stat = {'championId' : self.thisChampNameListe[i], 'totalMatches' : 1, 'poids_games' : 0, 'winrate' : 50}
                    else:
                        dict_data_stat = ''
                except Exception:
                    dict_data_stat = ''
                self.winrate_champ_joueur[pseudo] = dict_data_stat

                # --- ROLE PREF ---
                try:
                    data_pref_role = await get_role_stats(self.session, self.thisRiotIdListe[i], self.thisRiotTagListe[i])
                    if not data_pref_role.empty:
                        data_pref_role = data_pref_role.sort_values('poids_role', ascending=False)
                        self.role_pref[riot_id] = {
                            'main_role': data_pref_role.iloc[0]['role'],
                            'poids_role': int(data_pref_role.iloc[0]['poids_role'])
                        }
                        # self.all_role[riot_id] = data_pref_role.to_dict('index')
                        # On ne garde que RANKED_SOLO
                        role_df = data_pref_role.copy()
                        # Normalise les noms de rôle et les mets en minuscule
                        role_df['role'] = role_df['role'].str.lower()

                        # Rôles de League standards
                        roles_standard = ['top', 'jungle', 'mid', 'adc', 'support']

                        # Construction du mapping
                        role_dict = {}
                        total_games = role_df['nbgames'].sum() if not role_df.empty else 0
                        for role in roles_standard:
                            if role in role_df['role'].values:
                                row = role_df[role_df['role'] == role].iloc[0]
                                game_count = int(row['nbgames'])
                                win_count = int(row['wins'])
                                poids = int(round((game_count / total_games * 100))) if total_games > 0 else 0
                            else:
                                game_count = 0
                                win_count = 0
                                poids = 0
                            role_dict[role] = {
                                'gameCount': game_count,
                                'winCount': win_count,
                                'poids': poids
                            }

                        self.all_role[riot_id] = role_dict

                        self.role_count[riot_id] = int(data_pref_role['nbgames'].sum())
                    else:
                        self.role_pref[riot_id] = {'main_role': '', 'poids_role': 0}
                        self.all_role[riot_id] = {}
                        self.role_count[riot_id] = 0
                except Exception:
                    self.role_pref[riot_id] = {'main_role': '', 'poids_role': 0}
                    self.all_role[riot_id] = {}
                    self.role_count[riot_id] = 0

                # --- SERIE WIN/LOSE ---
                try:
                    match_history = await get_player_match_history_moba(
                        self.session,
                        riot_id,
                        riot_tag,
                        top=20
                    )
                    serie = detect_win_streak(match_history, self.thisRiotIdListe[i], self.thisRiotTagListe[i])
                    self.dict_serie[riot_id] = serie
                except Exception:
                    self.dict_serie[riot_id] = {'mot': '', 'count': 0}

                # --- POINTS (pas dans Mobalytics, on laisse à -1 comme UGG) ---
                self.dict_serie[riot_id]['carry_points'] = -1
                self.dict_serie[riot_id]['team_points'] = -1
                self.dict_serie[riot_id]['points'] = -1

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


        self.carry_points = -1
        self.team_points = -1

                
                
    async def prepare_data_ugg(self):                       

        
        
        self.liste_rank = []
        self.liste_tier = []
        
        self.winrate_joueur = {}
        
        self.winrate_champ_joueur = {}
        

        self.avgtier_ally = ''
        self.avgrank_ally = ''

        self.avgtier_enemy = ''
        self.avgrank_enemy = ''       
        
        self.role_pref = {}
        self.all_role = {}
        self.role_count = {}
        self.dict_serie = {}
        
        for i in range(self.nb_joueur):
            
            if self.ugg == 'True':
                try:
                    success = await update_ugg(self.session, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i].lower())
                except:
                    pass
                

            

            self.data_rank = await getRanks(self.session, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i].lower(), season=self.season_ugg)

 
 
            
            if self.data_rank != '': 
                try:
                    self.df_rank = pd.DataFrame(self.data_rank['data']['fetchProfileRanks']['rankScores'])
                except TypeError:
                    self.df_rank = ''
            
            self.df_data_stat = await get_stat_champion_by_player(self.session, self.champ_dict, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i].lower(), self.list_season_ugg)

           
            if isinstance(self.df_data_stat, pd.DataFrame):



                self.df_data_stat['poids_games'] = (self.df_data_stat['totalMatches'] / self.df_data_stat['totalMatches'].sum() * 100).astype(int)


                self.df_data_stat = self.df_data_stat[self.df_data_stat['championId'] == self.thisChampNameListe[i]]

                if self.df_data_stat.empty:
                    dict_data_stat = ''
                else:
                    try:
                        self.df_data_stat['kda'] = np.round((self.df_data_stat['kills'] + self.df_data_stat['assists']) /  self.df_data_stat['deaths'],2)
                    except ZeroDivisionError:
                        self.df_stat_kda['kda'] = np.round((self.df_data_stat['kills'] + self.df_data_stat['assists']) /  1,2)
                    dict_data_stat = self.df_data_stat.to_dict(orient='records')[0]
            else:
                dict_data_stat = ''
            

            try:
                if isinstance(self.df_rank, pd.DataFrame):
                    nbgames = self.df_rank.loc[self.df_rank['queueType'] == 'ranked_solo_5x5']['wins'].values[0] + self.df_rank.loc[self.df_rank['queueType'] == 'ranked_solo_5x5']['losses'].values[0]
                    wr = round((self.df_rank.loc[self.df_rank['queueType'] == 'ranked_solo_5x5']['wins'].values[0] / nbgames) * 100)
                else:
                    nbgames = 0
                    wr = 0
            except IndexError:
                wr = 0
                nbgames = 0
            except AttributeError:
                wr = 0
                nbgames = 0
            
            self.winrate_joueur[f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].upper()}'] = {'winrate' : wr, 'nbgames' : nbgames}
            self.winrate_champ_joueur[f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].upper()}'] = dict_data_stat
            


            try:
                rank_joueur = self.df_rank.loc[self.df_rank['queueType'] == 'ranked_solo_5x5']['tier'].values[0]
                tier_joueur = self.df_rank.loc[self.df_rank['queueType'] == 'ranked_solo_5x5']['rank'].values[0]
                self.liste_rank.append(rank_joueur)
                self.liste_tier.append(tier_joueur)
                    
            except:
                self.liste_rank.append('')
                self.liste_tier.append('')

            ###

            self.data_pref_role = await get_role(self.session, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i].lower())

            if isinstance(self.data_pref_role, dict):

                try:

                    self.df_pref_role = pd.DataFrame(self.data_pref_role).T
                    self.df_pref_role['poids'] = (self.df_pref_role['gameCount'] / self.df_pref_role['gameCount'].sum() * 100).astype(int)
                    self.df_pref_role.sort_values('poids', ascending=False, inplace=True)

                    self.role_pref[self.thisRiotIdListe[i].lower()] = {'main_role' : self.df_pref_role.index[0], 'poids_role' : self.df_pref_role.iloc[0]['poids']}

                    self.all_role[self.thisRiotIdListe[i].lower()] = self.df_pref_role.to_dict('index')

                    self.role_count[self.thisRiotIdListe[i].lower()] = self.df_pref_role['gameCount'].sum()
                
                except pd.errors.IntCastingNaNError:
                    continue


            
            ## Detection Serie de Victoire / Defaite + Calcul Score

            self.df_data = await get_player_match_history(self.session, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i], seasonIds=[self.season_ugg])

            # Vérifie si self.df_data existe et contient les données attendues
            try:
                self.df_data_match_history = pd.DataFrame(self.df_data['data']['fetchPlayerMatchSummaries']['matchSummaries'])
                self.df_data_match_history = self.df_data_match_history[self.df_data_match_history['queueType'] == 'ranked_solo_5x5'] # seuls les matchs classés
                self.df_data_match_history['matchCreationTime'] = pd.to_datetime(self.df_data_match_history['matchCreationTime'], unit='ms')

                #### Serie de wins/loses

                # Première valeur
                win_lose = self.df_data_match_history['win'].iloc[0]

                # Compter combien de fois cette valeur apparaît consécutivement depuis le début
                count = (self.df_data_match_history['win'] == win_lose).cumprod().sum()

                mot =  "Victoire" if win_lose else "Defaite"

                self.dict_serie[self.thisRiotIdListe[i].lower()] = {'mot' : mot, 'count' : count}
            except (TypeError, KeyError):
                # Si pas de données, on met une valeur par défaut
                self.dict_serie[self.thisRiotIdListe[i].lower()] = {'mot': '', 'count': 0}


            #### Points 

            try:

                self.df_data_match = self.df_data_match_history[self.df_data_match_history['matchId'] == int(self.last_match[5:])]

                if not self.df_data_match.empty:
                    self.carry_points = self.df_data_match['psHardCarry'].values[0] 
                    self.team_points = self.df_data_match['psTeamPlay'].values[0]
                
                else:
                    self.carry_points = -1
                    self.team_points = -1

                
                self.dict_serie[self.thisRiotIdListe[i].lower()]['carry_points'] = int(self.carry_points)
                self.dict_serie[self.thisRiotIdListe[i].lower()]['team_points'] = int(self.team_points)
                self.dict_serie[self.thisRiotIdListe[i].lower()]['points'] = (self.carry_points + self.team_points) / 2

            except:
                self.df_data_match = pd.DataFrame([])
                self.carry_points = -1
                self.team_points = -1
                self.dict_serie[self.thisRiotIdListe[i].lower()]['carry_points'] = int(self.carry_points)
                self.dict_serie[self.thisRiotIdListe[i].lower()]['team_points'] = int(self.team_points)
                self.dict_serie[self.thisRiotIdListe[i].lower()]['points'] = (self.carry_points + self.team_points) / 2



    # async def prepare_data_riot(self):
    #     self.liste_rank = []
    #     self.liste_tier = []
    #     self.winrate_joueur = {}
    #     self.winrate_champ_joueur = {}
    #     self.role_pref = {}
    #     self.all_role = {}
    #     self.role_count = {}
    #     self.dict_serie = {}

    #     for i in range(self.nb_joueur):
    #         puuid = self.liste_puuid[i]
    #         riot_id = self.thisRiotIdListe[i]
    #         riot_tag = self.thisRiotTagListe[i]

    #         # 1. Récup rank solo
    #         try:
    #             data_rank = await get_data_rank(self.session, self.liste_account_id[i])
    #             soloq = next((e for e in data_rank if e['queueType'] == 'RANKED_SOLO_5x5'), None)
    #             if soloq:
    #                 rank = soloq['tier']
    #                 tier = soloq['rank']
    #                 wins = soloq['wins']
    #                 losses = soloq['losses']
    #                 nbgames = wins + losses
    #                 wr = round(wins / nbgames * 100) if nbgames > 0 else 0
    #             else:
    #                 rank = ''
    #                 tier = ''
    #                 nbgames = 0
    #                 wr = 0
    #         except:
    #             rank = ''
    #             tier = ''
    #             nbgames = 0
    #             wr = 0

    #         self.liste_rank.append(rank)
    #         self.liste_tier.append(tier)
    #         self.winrate_joueur[f'{riot_id.lower()}#{riot_tag.upper()}'] = {'winrate': wr, 'nbgames': nbgames}

    #         # --- FACTORISATION ici ---
    #         try:
    #             # Appel unique pour 50 ranked solo Q
    #             match_ids = await get_list_matchs_with_puuid(
    #                 self.session, puuid, {'queue': 420, 'count': 50, 'api_key': api_key_lol}
    #             )
    #         except Exception as e:
    #             match_ids = []

    #         champ_stats = {}
    #         roles_counter = {}
    #         streak_result = None
    #         streak_count = 0

    #         for idx, match_id in enumerate(match_ids):
    #             try:
    #                 match = await get_match_detail(self.session, match_id, {'api_key': api_key_lol})
    #                 participant = next((p for p in match['info']['participants'] if p['puuid'] == puuid), None)
    #                 if not participant:
    #                     continue

    #                 # --- Stats par champion joué
    #                 champ_id = participant['championId']
    #                 if champ_id not in champ_stats:
    #                     champ_stats[champ_id] = {'kills': 0, 'deaths': 0, 'assists': 0, 'matches': 0, 'wins': 0}
    #                 champ_stats[champ_id]['kills'] += participant['kills']
    #                 champ_stats[champ_id]['deaths'] += participant['deaths']
    #                 champ_stats[champ_id]['assists'] += participant['assists']
    #                 champ_stats[champ_id]['matches'] += 1
    #                 if participant['win']:
    #                     champ_stats[champ_id]['wins'] += 1

    #                 # --- Stat rôle joué
    #                 role = participant.get('teamPosition', participant.get('role', 'UNKNOWN'))
    #                 roles_counter[role] = roles_counter.get(role, 0) + 1

    #                 # --- Série (streak) victoire/défaite sur les 10 premiers matchs
    #                 if idx < 10:
    #                     if streak_result is None:
    #                         streak_result = participant['win']
    #                         streak_count = 1
    #                     elif participant['win'] == streak_result:
    #                         streak_count += 1
    #                     else:
    #                         # On arrête dès que la série se casse
    #                         pass
    #             except Exception as e:
    #                 continue

    #         # --- Champion principal joué sur ce match
    #         champ_id_main = self.thisChampListe[i]
    #         stats = champ_stats.get(champ_id_main, None)
    #         if stats:
    #             deaths = stats['deaths'] if stats['deaths'] != 0 else 1
    #             kda = round((stats['kills'] + stats['assists']) / deaths, 2)
    #             poids_games = int(stats['matches'] / max(sum(v['matches'] for v in champ_stats.values()), 1) * 100)
    #             dict_data_stat = {
    #                 'kills': stats['kills'],
    #                 'deaths': stats['deaths'],
    #                 'assists': stats['assists'],
    #                 'winrate': int(stats['wins'] / stats['matches'] * 100) if stats['matches'] > 0 else 0,
    #                 'poids_games': poids_games,
    #                 'kda': kda,
    #                 'matches': stats['matches']
    #             }
    #         else:
    #             dict_data_stat = ''
    #         self.winrate_champ_joueur[f'{riot_id.lower()}#{riot_tag.upper()}'] = dict_data_stat

    #         # --- Stats de rôles principaux
    #         total_games = sum(roles_counter.values())
    #         if total_games > 0:
    #             df_pref_role = pd.DataFrame.from_dict(roles_counter, orient='index', columns=['gameCount'])
    #             df_pref_role['poids'] = (df_pref_role['gameCount'] / total_games * 100).astype(int)
    #             df_pref_role.sort_values('poids', ascending=False, inplace=True)
    #             main_role = df_pref_role.index[0]
    #             poids_role = df_pref_role.iloc[0]['poids']
    #             self.role_pref[riot_id.lower()] = {'main_role': main_role, 'poids_role': poids_role}
    #             self.all_role[riot_id.lower()] = df_pref_role.to_dict('index')
    #             self.role_count[riot_id.lower()] = total_games
    #         else:
    #             self.role_pref[riot_id.lower()] = {}
    #             self.all_role[riot_id.lower()] = {}
    #             self.role_count[riot_id.lower()] = 0

    #         # --- Streak win/lose
    #         if streak_result is not None:
    #             mot = "Victoire" if streak_result else "Defaite"
    #             self.dict_serie[riot_id.lower()] = {'mot': mot, 'count': streak_count}
    #         else:
    #             self.dict_serie[riot_id.lower()] = {'mot': '', 'count': 0}

    #         # --- Carry/team points (toujours -1 car non dispo)
    #         self.dict_serie[riot_id.lower()]['carry_points'] = -1
    #         self.dict_serie[riot_id.lower()]['team_points'] = -1
    #         self.dict_serie[riot_id.lower()]['points'] = -1





        
        
    async def save_data(self):
        """Sauvegarde l'ensemble des données dans la base de données"""
        
        if self.thisDeaths >= 1:
            self.kda_save = self.thisKDA
        else:
            self.kda_save = round((int(self.thisKills) + int(self.thisAssists)) / (int(self.thisDeaths) + 1), 2)

        df_exists = lire_bdd_perso(f'''SELECT match_id, joueur from matchs
                                   WHERE match_id = '{self.last_match}' 
                                   AND joueur = {self.id_compte}  ''',
                                   index_col=None)
        
        if df_exists.empty:
            requete_perso_bdd(
                '''INSERT INTO matchs(
            match_id, joueur, role, champion, kills, assists, deaths, double, triple, quadra, penta,
            victoire, team_kills, team_deaths, "time", dmg, dmg_ad, dmg_ap, dmg_true, vision_score, cs, cs_jungle, vision_pink, vision_wards, vision_wards_killed,
            gold, cs_min, vision_min, gold_min, dmg_min, solokills, dmg_reduit, heal_total, heal_allies, serie_kills, cs_dix_min, jgl_dix_min,
            baron, drake, team, herald, cs_max_avantage, level_max_avantage, afk, vision_avantage, early_drake, temps_dead,
            item1, item2, item3, item4, item5, item6, kp, kda, mode, season, date, damageratio, tankratio, rank, tier, lp, id_participant, dmg_tank, shield,
            early_baron, allie_feeder, snowball, temps_vivant, dmg_tower, gold_share, mvp, ecart_gold_team, "kills+assists", datetime, temps_avant_premiere_mort, "dmg/gold", ecart_gold, ecart_gold_min,
            split, skillshot_dodged, temps_cc, spells_used, buffs_voles, s1cast, s2cast, s3cast, s4cast, horde, moba, kills_min, deaths_min, assists_min, ecart_cs, petales_sanglants, atakhan, crit_dmg, immobilisation, skillshot_hit, temps_cc_inflige, tower, inhib,
            dmg_true_all, dmg_true_all_min, dmg_ad_all, dmg_ad_all_min, dmg_ap_all, dmg_ap_all_min, dmg_all, dmg_all_min, records, longue_serie_kills, ecart_kills, ecart_deaths, ecart_assists, ecart_dmg, trade_efficience, skillshots_dodge_min, skillshots_hit_min, dmg_par_kills,
            first_tower_time, hardcarry, teamcarry)
            VALUES (:match_id, :joueur, :role, :champion, :kills, :assists, :deaths, :double, :triple, :quadra, :penta,
            :result, :team_kills, :team_deaths, :time, :dmg, :dmg_ad, :dmg_ap, :dmg_true, :vision_score, :cs, :cs_jungle, :vision_pink, :vision_wards, :vision_wards_killed,
            :gold, :cs_min, :vision_min, :gold_min, :dmg_min, :solokills, :dmg_reduit, :heal_total, :heal_allies, :serie_kills, :cs_dix_min, :jgl_dix_min,
            :baron, :drake, :team, :herald, :cs_max_avantage, :level_max_avantage, :afk, :vision_avantage, :early_drake, :temps_dead,
            :item1, :item2, :item3, :item4, :item5, :item6, :kp, :kda, :mode, :season, :date, :damageratio, :tankratio, :rank, :tier, :lp, :id_participant, :dmg_tank, :shield,
            :early_baron, :allie_feeder, :snowball, :temps_vivant, :dmg_tower, :gold_share, :mvp, :ecart_gold_team, :ka, to_timestamp(:date), :time_first_death, :dmgsurgold, :ecart_gold_individuel, :ecart_gold_min,
            :split, :skillshot_dodged, :temps_cc, :spells_used, :buffs_voles, :s1cast, :s2cast, :s3cast, :s4cast, :horde, :moba, :kills_min, :deaths_min, :assists_min, :ecart_cs, :petales_sanglants, :atakhan, :crit_dmg, :immobilisation, :skillshot_hit, :temps_cc_inflige, :tower, :inhib,
            :dmg_true_all, :dmg_true_all_min, :dmg_ad_all, :dmg_ad_all_min, :dmg_ap_all, :dmg_ap_all_min, :dmg_all, :dmg_all_min, :records, :longue_serie_kills, :ecart_kills, :ecart_deaths, :ecart_assists, :ecart_dmg, :trade_efficience, :skillshots_dodge_min, :skillshot_hit_min, :dmg_par_kills,
            :first_tower_time, :hardcarry, :teamcarry);
            UPDATE tracker SET riot_id= :riot_id, riot_tagline= :riot_tagline where id_compte = :joueur;
            INSERT INTO public.matchs_updated(match_id, joueur, updated)
	        VALUES (:match_id, :joueur, true);
            UPDATE prev_lol SET match_id = :match_id where riot_id = :riot_id and riot_tag = :riot_tagline and match_id = '';
            UPDATE prev_lol_features SET match_id = :match_id where riot_id = :riot_id and riot_tag = :riot_tagline and match_id = '' ''',
                {
                    'match_id': self.last_match,
                    'joueur': self.id_compte,
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
                    'kda': self.kda_save,
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
                    'gold_share': self.gold_share,
                    'mvp': self.mvp,
                    'ecart_gold_team': self.ecart_gold_team,
                    'ka': self.thisKills + self.thisAssists,
                    'time_first_death': self.thisTimeLiving,
                    'dmgsurgold' : self.DamageGoldRatio,
                    'ecart_gold_individuel' : self.ecart_gold_noformat,
                    'ecart_gold_min' : self.ecart_gold_permin,
                    'riot_id' : self.riot_id.lower(),
                    'riot_tagline' : self.riot_tag,
                    'split' : self.split,
                    'skillshot_dodged' : self.thisSkillshot_dodged,
                    'temps_cc' : self.time_CC,
                    'spells_used' : self.thisSpellUsed,
                    'buffs_voles' : self.thisbuffsVolees,
                    's1cast' : self.s1cast,
                    's2cast' : self.s2cast,
                    's3cast' : self.s3cast,
                    's4cast' : self.s4cast,
                    'horde' : self.thisHordeTeam,
                    'moba' : self.moba_ok,
                    'kills_min' : self.kills_min,
                    'deaths_min' : self.deaths_min,
                    'assists_min' : self.assists_min,
                    'ecart_cs' : self.ecart_cs_noformat,
                    'petales_sanglants' : self.petales_sanglants,
                    'atakhan' : self.thisAtakhanTeam,
                    'crit_dmg' : self.largest_crit,
                    'immobilisation' : self.enemy_immobilisation,
                    'skillshot_hit' : self.thisSkillshot_hit,
                    'temps_cc_inflige' : self.totaltimeCCdealt,
                    'tower' : self.thisTowerTeam,
                    'inhib' : self.thisInhibTeam,
                    'dmg_true_all' : self.thisDamageTrueAllNoFormat,
                    'dmg_true_all_min' : self.thisDamageTrueAllPerMinute,
                    'dmg_ad_all' : self.thisDamageADAllNoFormat,
                    'dmg_ad_all_min' : self.thisDamageADAllPerMinute,
                    'dmg_ap_all' : self.thisDamageAPAllNoFormat,
                    'dmg_ap_all_min' : self.thisDamageAPAllPerMinute,
                    'dmg_all' : self.thisDamageAllNoFormat,
                    'dmg_all_min' : self.thisDamageAllPerMinute,
                    'records' : True,
                    'longue_serie_kills' : self.thisKillsSeries,
                    'ecart_kills' : self.ecart_kills,
                    'ecart_deaths' : self.ecart_morts,
                    'ecart_assists' : self.ecart_assists,
                    'ecart_dmg' : self.ecart_dmg,
                    'trade_efficience' : self.trade_efficience,
                    'skillshots_dodge_min' : self.thisSkillshot_dodged_per_min,
                    'skillshot_hit_min' : self.thisSkillshot_hit_per_min,
                    'dmg_par_kills' : self.damage_per_kills,
                    'first_tower_time' : self.first_tower_time,
                    'hardcarry' : int(self.carry_points),
                    'teamcarry' : int(self.team_points),

                },
            )


                
            if self.thisQ != 'ARENA 2v2' and self.thisQ != 'OTHER':
                for i in range(10):
                    try:
                        team = 'allie' if i < 5 else 'ennemi'
                        position = str(i % 5 + 1)
                        joueur = f"{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}"
                        tier = self.liste_rank[i]
                        div = self.liste_tier[i]
                        champion = self.thisChampNameListe[i]
                        requete_perso_bdd('''INSERT INTO match_participant (
                            match_id, team, position, joueur, tier, div, champion,
                            tierallie_avg, divallie_avg, tierennemy_avg, divennemy_avg
                        ) VALUES (
                            :match_id, :team, :position, :joueur, :tier, :div, :champion,
                            :tierallie_avg, :divallie_avg, :tierennemy_avg, :divennemy_avg
                        );''',
                        {
                            'match_id': self.last_match,
                            'team': team,
                            'position': position,
                            'joueur': joueur,
                            'tier': tier,
                            'div': div,
                            'champion': champion,
                            'tierallie_avg': self.avgtier_ally,
                            'divallie_avg': self.avgrank_ally,
                            'tierennemy_avg': self.avgtier_enemy,
                            'divennemy_avg': self.avgrank_enemy
                        })
                    except sqlalchemy.exc.IntegrityError:
                        # Si le joueur existe déjà, on ignore l'insertion
                        continue


                    requete_perso_bdd('''INSERT INTO matchs_autres(
                match_id, vision1, vision2, vision3, vision4, vision5, vision6, vision7, vision8, vision9, vision10, pink1, pink2, pink3, pink4, pink5, pink6, pink7, pink8, pink9, pink10,
                ecart_gold_top, ecart_gold_jgl, ecart_gold_mid, ecart_gold_adc, ecart_gold_supp)
                VALUES (:match_id, :v1, :v2, :v3, :v4, :v5, :v6, :v7, :v8, :v9, :v10, :p1, :p2, :p3, :p4, :p5, :p6, :p7, :p8, :p9, :p10, :ecart_top, :ecart_jgl, :ecart_mid, :ecart_adc, :ecart_supp)
                ON CONFLICT (match_id)
                DO NOTHING;''',
                {'match_id' : self.last_match,
                'v1' : self.thisVisionListe[0],
                'v2' : self.thisVisionListe[1],
                'v3' : self.thisVisionListe[2],
                'v4' : self.thisVisionListe[3],
                'v5' : self.thisVisionListe[4],
                'v6' : self.thisVisionListe[5],
                'v7' : self.thisVisionListe[6],
                'v8' : self.thisVisionListe[7],
                'v9' : self.thisVisionListe[8],
                'v10' : self.thisVisionListe[9],
                'p1' : self.thisPinkListe[0],
                'p2' : self.thisPinkListe[1],
                'p3' : self.thisPinkListe[2],
                'p4' : self.thisPinkListe[3],
                'p5' : self.thisPinkListe[4],
                'p6' : self.thisPinkListe[5],
                'p7' : self.thisPinkListe[6],
                'p8' : self.thisPinkListe[7],
                'p9' : self.thisPinkListe[8],
                'p10' : self.thisPinkListe[9],
                'ecart_top' : self.ecart_top_gold_affiche,
                'ecart_jgl' : self.ecart_jgl_gold_affiche,
                'ecart_mid' : self.ecart_mid_gold_affiche,
                'ecart_adc' : self.ecart_adc_gold_affiche,
                'ecart_supp' : self.ecart_supp_gold_affiche
                }
                ) 
            
            requete_perso_bdd('''INSERT INTO matchs_points(
            match_id, hardcarry1, hardcarry2, hardcarry3, hardcarry4, hardcarry5, hardcarry6, hardcarry7, hardcarry8, hardcarry9, hardcarry10,
                         teamcarry1, teamcarry2, teamcarry3, teamcarry4, teamcarry5, teamcarry6, teamcarry7, teamcarry8, teamcarry9, teamcarry10)
            VALUES (:match_id, :hardcarry1, :hardcarry2, :hardcarry3, :hardcarry4, :hardcarry5, :hardcarry6, :hardcarry7, :hardcarry8, :hardcarry9, :hardcarry10,
                         :teamcarry1, :teamcarry2, :teamcarry3, :teamcarry4, :teamcarry5, :teamcarry6, :teamcarry7, :teamcarry8, :teamcarry9, :teamcarry10)

        ON CONFLICT (match_id)
        DO NOTHING;''',
        {'match_id' : self.last_match,
            'hardcarry1' : self.dict_serie.get(self.thisRiotIdListe[0].lower(), {}).get('carry_points', -1),
            'hardcarry2' : self.dict_serie.get(self.thisRiotIdListe[1].lower(), {}).get('carry_points', -1),
            'hardcarry3' : self.dict_serie.get(self.thisRiotIdListe[2].lower(), {}).get('carry_points', -1),
            'hardcarry4' : self.dict_serie.get(self.thisRiotIdListe[3].lower(), {}).get('carry_points', -1),
            'hardcarry5' : self.dict_serie.get(self.thisRiotIdListe[4].lower(), {}).get('carry_points', -1),
            'hardcarry6' : self.dict_serie.get(self.thisRiotIdListe[5].lower(), {}).get('carry_points', -1),
            'hardcarry7' : self.dict_serie.get(self.thisRiotIdListe[6].lower(), {}).get('carry_points', -1),
            'hardcarry8' : self.dict_serie.get(self.thisRiotIdListe[7].lower(), {}).get('carry_points', -1),
            'hardcarry9' : self.dict_serie.get(self.thisRiotIdListe[8].lower(), {}).get('carry_points', -1),
            'hardcarry10' : self.dict_serie.get(self.thisRiotIdListe[9].lower(), {}).get('carry_points', -1),
            'teamcarry1' : self.dict_serie.get(self.thisRiotIdListe[0].lower(), {}).get('team_points', -1),
            'teamcarry2' : self.dict_serie.get(self.thisRiotIdListe[1].lower(), {}).get('team_points', -1),
            'teamcarry3' : self.dict_serie.get(self.thisRiotIdListe[2].lower(), {}).get('team_points', -1),
            'teamcarry4' : self.dict_serie.get(self.thisRiotIdListe[3].lower(), {}).get('team_points', -1),
            'teamcarry5' : self.dict_serie.get(self.thisRiotIdListe[4].lower(), {}).get('team_points', -1),
            'teamcarry6' : self.dict_serie.get(self.thisRiotIdListe[5].lower(), {}).get('team_points', -1),
            'teamcarry7' : self.dict_serie.get(self.thisRiotIdListe[6].lower(), {}).get('team_points', -1),
            'teamcarry8' : self.dict_serie.get(self.thisRiotIdListe[7].lower(), {}).get('team_points', -1),
            'teamcarry9' : self.dict_serie.get(self.thisRiotIdListe[8].lower(), {}).get('team_points', -1),
            'teamcarry10' : self.dict_serie.get(self.thisRiotIdListe[9].lower(), {}).get('team_points', -1)

,
            })


        df_data_champ = await get_data_champ_tags(self.session, self.version['n']['champion']) 

        sauvegarde_bdd(df_data_champ, 'data_champion_tag', index=False)     


    
    async def save_timeline(self):
        
        def unpack_dict_championStats(row):
            return pd.Series(row['championStats'])

        def unpack_dict_damageStats(row):
            return pd.Series(row['damageStats'])
        
        self.df_timeline_load, self.minute = load_timeline(self.data_timeline)  
        
        self.df_timeline_joueur = self.df_timeline_load[self.df_timeline_load['riot_id'] == self.index_timeline]  
        
        self.df_timeline_position = self.df_timeline_joueur[['position', 'timestamp', 'totalGold', 'xp', 'jungleMinionsKilled', 'currentGold', 'level', 'minionsKilled']]

        self.df_timeline_position['total_cs'] = self.df_timeline_position['minionsKilled'] + self.df_timeline_position['jungleMinionsKilled']

        self.df_timeline_position['riot_id'] = self.id_compte
        self.df_timeline_position['match_id'] = self.last_match

        self.df_timeline_position['position_x'] = self.df_timeline_position['position'].apply(lambda x : x['x'])
        self.df_timeline_position['position_y'] = self.df_timeline_position['position'].apply(lambda x : x['y'])
        self.df_timeline_position.drop('position', axis=1, inplace=True)

        self.df_timeline_stats = self.df_timeline_joueur.apply(unpack_dict_championStats, axis=1)
        self.df_timeline_dmg = self.df_timeline_joueur.apply(unpack_dict_damageStats, axis=1)
        
        self.df_timeline_position = pd.concat([self.df_timeline_position,
                                               self.df_timeline_stats,
                                               self.df_timeline_dmg], axis=1)
        
        # self.df_timeline_position['timestamp'] = self.df_timeline_position['timestamp'].apply(fix_temps)
        
        
        self.max_abilityHaste = self.df_timeline_position['abilityHaste'].max()
        self.max_ap = self.df_timeline_position['abilityPower'].max()
        self.max_armor = self.df_timeline_position['armor'].max()
        self.max_ad = self.df_timeline_position['attackDamage'].max()
        self.currentgold = self.df_timeline_position['currentGold'].max()
        self.max_hp = self.df_timeline_position['healthMax'].max()
        self.max_mr = self.df_timeline_position['magicResist'].max()
        self.movement_speed = self.df_timeline_position['movementSpeed'].max()

        def get_value(df, timestamp, column):
            try:
                return df.loc[df['timestamp'] == timestamp, column].values[0]
            except:
                return 0

        # Usage
        self.total_cs_20 = get_value(self.df_timeline_position, 20, 'total_cs')
        self.total_cs_30 = get_value(self.df_timeline_position, 30, 'total_cs')

        self.total_gold_20 = get_value(self.df_timeline_position, 20, 'totalGold')
        self.total_gold_30 = get_value(self.df_timeline_position, 30, 'totalGold')

        self.minions_20 = get_value(self.df_timeline_position, 20, 'minionsKilled')
        self.minions_30 = get_value(self.df_timeline_position, 30, 'minionsKilled')

        self.jgl_killed_20 = get_value(self.df_timeline_position, 20, 'jungleMinionsKilled')
        self.jgl_killed_30 = get_value(self.df_timeline_position, 30, 'jungleMinionsKilled')

        self.totalDamageDone_10 = get_value(self.df_timeline_position, 10, 'totalDamageDoneToChampions')
        self.totalDamageDone_20 = get_value(self.df_timeline_position, 20, 'totalDamageDoneToChampions')
        self.totalDamageDone_30 = get_value(self.df_timeline_position, 30, 'totalDamageDoneToChampions')

        self.totalDamageTaken_10 = get_value(self.df_timeline_position, 10, 'totalDamageTaken')
        self.totalDamageTaken_20 = get_value(self.df_timeline_position, 20, 'totalDamageTaken')
        self.totalDamageTaken_30 = get_value(self.df_timeline_position, 30, 'totalDamageTaken')

        self.trade_efficience_10 = round(self.totalDamageDone_10 / (self.totalDamageTaken_10 + 1) * 100,2)
        self.trade_efficience_20 = round(self.totalDamageDone_20 / (self.totalDamageTaken_20 + 1) * 100,2)
        self.trade_efficience_30 = round(self.totalDamageDone_30 / (self.totalDamageTaken_30 + 1) * 100,2)

        

        
        
        try:
            sauvegarde_bdd(self.df_timeline_position,
                        'data_timeline',
                            methode_save='append',
                            index=False)  
        except sqlalchemy.exc.IntegrityError:
            pass
        


        

    async def save_timeline_event(self):
        self.df_events = pd.DataFrame(self.data_timeline['info']['frames'][1]['events'])

        self.minute = len(self.data_timeline['info']['frames']) - 1

        for i in range(1, self.minute):
            df_timeline2 = pd.DataFrame(
                self.data_timeline['info']['frames'][i]['events'])
            self.df_events = self.df_events.append(df_timeline2)


        self.df_events_joueur = self.df_events[(self.df_events['participantId'] == self.index_timeline) |
                                        (self.df_events['creatorId'] == self.index_timeline) |
                                        (self.df_events['killerId'] == self.index_timeline) |
                                        (self.df_events['victimId'] == self.index_timeline) |
                                        self.df_events['assistingParticipantIds'].apply(lambda x: isinstance(x, list) and self.index_timeline in x)]

        
        self.df_events_team = self.df_events[(self.df_events['teamId'] == self.teamId) | (self.df_events['killerTeamId'] == self.teamId)]
        
        def format_df_events(df):

            df['riot_id'] = self.id_compte
            df['match_id'] = self.last_match

            df['position_x'] = df['position'].apply(lambda x : x['x'] if isinstance(x, dict) else 0)
            df['position_y'] = df['position'].apply(lambda x : x['y'] if isinstance(x, dict) else 0)
            df.drop('position', axis=1, inplace=True)

            df.drop(['victimDamageDealt', 'victimDamageReceived', 'participantId', 'creatorId'], axis=1, inplace=True)
                
            if 'actualStartTime' in df.columns: # cette colonne n'est pas toujours présente
                df.drop(['actualStartTime'], axis=1, inplace=True)

            if 'name' in df.columns: # cette colonne n'est pas toujours présente
                    df.drop(['name'], axis=1, inplace=True)
            df.reset_index(inplace=True, drop=True)    
                
                # on simplifie quelques data
                
            df.loc[(df['type'] == 'CHAMPION_KILL')
                                        & (df['victimId'] == self.index_timeline), 'type'] = 'DEATHS'
                
            df['timestamp'] = np.round(df['timestamp'] / 60000,2)
            
            df['timestamp'] = df['timestamp'].apply(fix_temps)
                    
            df['wardType'] = df['wardType'].map({'YELLOW_TRINKET': 'Trinket jaune',
                                                                        'UNDEFINED': 'Balise Zombie',
                                                                        'CONTROL_WARD': 'Pink',
                                                                        'SIGHT_WARD': 'Ward support',
                                                                        'BLUE_TRINKET': 'Trinket bleu'
                                                                        })
                
            return df
        
        

        self.df_events_joueur = format_df_events(self.df_events_joueur)
        self.df_events_team = format_df_events(self.df_events_team)
 
        if not 'monsterSubType' in self.df_events_team.columns:
            self.df_events_team['monsterSubType'] = ''
 
        # Records
        

        self.df_events_monster_kill = self.df_events_team[self.df_events_team['type'] == 'ELITE_MONSTER_KILL'][['type', 'timestamp', 'monsterType', 'monsterSubType']]
        self.df_events_dragon = self.df_events_monster_kill[self.df_events_monster_kill['monsterType'] == 'DRAGON']
        
        # Temps 4e dragon (soul hextech)
        try:
            index_fourth_dragon = self.df_events_dragon.index[3]
            self.timestamp_fourth_dragon = self.df_events_dragon.loc[index_fourth_dragon, 'timestamp']
        except IndexError: # pas de 4e dragon
            self.timestamp_fourth_dragon = 999.0

        if self.thisDragonTeam < 4:
            self.timestamp_fourth_dragon = 999.0
            
        # Elder 
        
        self.df_events_elder = self.df_events_team[self.df_events_team['monsterSubType'] == 'ELDER_DRAGON']

        if self.df_events_elder.empty:
            self.timestamp_first_elder = 999.0
        else:
            self.timestamp_first_elder = self.df_events_elder['timestamp'].min()
            
        # Horde
        
        self.df_events_horde = self.df_events_team[self.df_events_team['monsterType'] == 'HORDE']

        if self.df_events_horde.empty:
            self.timestamp_first_horde = 999.0
        else:
            self.timestamp_first_horde = self.df_events_horde['timestamp'].min()

        
        self.df_events_atakhan = self.df_events_team[self.df_events_team['monsterType'] == 'ATAKHAN']

        if self.df_events_atakhan.empty:
            self.timestamp_first_atakhan = 999.0
        else:
            self.timestamp_first_atakhan = self.df_events_atakhan['timestamp'].min()
            
        # Autres  
        
        def timestamp_killmulti(df):
            if df.empty:
                return 999
            else:
                return df['timestamp'].min()  
               
        self.df_niveau_max = self.df_events_joueur[self.df_events_joueur['level'] == 18.0]
        
        self.df_first_blood = self.df_events_joueur[self.df_events_joueur['killType'] == 'KILL_FIRST_BLOOD']


        self.df_kills = self.df_events_joueur[self.df_events_joueur['type'].isin(['CHAMPION_KILL', 'CHAMPION_SPECIAL_KILL'])]
        self.df_deaths = self.df_events_joueur[self.df_events_joueur['type'] == 'DEATHS']

 

        self.df_kills_with_jgl_early = self.df_events_joueur[(self.df_events_joueur['type'].isin(['CHAMPION_KILL', 'CHAMPION_SPECIAL_KILL'])) & 
                                                             (self.df_events_joueur['assistingParticipantIds'].apply(lambda x: isinstance(x, list) and (7 in x or 2 in x)))
                                                             & (self.df_events_joueur['timestamp'].between(2, 10))]

        self.df_deaths_with_jgl_early = self.df_events_joueur[(self.df_events_joueur['type'].isin(['DEATHS'])) & 
                                                             (self.df_events_joueur['assistingParticipantIds'].apply(lambda x: isinstance(x, list) and (7 in x or 2 in x)))
                                                             & (self.df_events_joueur['timestamp'].between(2, 10))]

        if not self.df_deaths.empty:

            self.df_deaths['nb_participants'] = self.df_deaths['assistingParticipantIds'].apply(lambda x : len(x) + 1 if isinstance(x, list) else 1)
            self.get_solokilled = self.df_deaths[self.df_deaths['nb_participants'] == 1].shape[0]

        else:
            self.get_solokilled = 0

        if not self.df_kills.empty:

            self.df_kills['nb_participants'] = self.df_kills['assistingParticipantIds'].apply(lambda x : len(x) + 1 if isinstance(x, list) else 1)

            self.df_kills_self = self.df_kills[self.df_kills['killerId'] == self.index_timeline]

            self.gold_with_kills = self.df_kills_self['bounty'].sum() + self.df_kills_self['shutdownBounty'].sum()
            self.bounty_recupere = self.df_kills_self['shutdownBounty'].sum()
        
        else:
            self.gold_with_kills = 0
            self.bounty_recupere = 0

        
        if not self.df_kills_with_jgl_early.empty and self.thisPosition != 'JUNGLE':
            self.kills_with_jgl_early = self.df_kills_with_jgl_early.shape[0]
        
        else:
            self.kills_with_jgl_early = 0

    
        if not self.df_deaths_with_jgl_early.empty and self.thisPosition != 'JUNGLE':
            self.deaths_with_jgl_early = self.df_deaths_with_jgl_early.shape[0]

        else:
            self.deaths_with_jgl_early = 0
        

        


        self.timestamp_niveau_max = timestamp_killmulti(self.df_niveau_max)
        self.timestamp_first_blood = timestamp_killmulti(self.df_first_blood)

            
        if 'multiKillLength' in self.df_events_joueur.columns:    
            self.df_events_doublekills = self.df_events_joueur[self.df_events_joueur['multiKillLength'] == 2.0]
            self.df_events_triplekills = self.df_events_joueur[self.df_events_joueur['multiKillLength'] == 3.0]
            self.df_events_quadrakills = self.df_events_joueur[self.df_events_joueur['multiKillLength'] == 4.0]
            self.df_events_pentakills = self.df_events_joueur[self.df_events_joueur['multiKillLength'] == 5.0]
                
            self.timestamp_doublekill = timestamp_killmulti(self.df_events_doublekills)
            self.timestamp_triplekill = timestamp_killmulti(self.df_events_triplekills)
            self.timestamp_quadrakill = timestamp_killmulti(self.df_events_quadrakills)
            self.timestamp_pentakill = timestamp_killmulti(self.df_events_pentakills)
        
        else:
            self.timestamp_doublekill = 999
            self.timestamp_triplekill = 999
            self.timestamp_quadrakill = 999
            self.timestamp_pentakill = 999           
        


        ### Ecart Gold



        if self.teamId == 100:
            team = ['Team alliée', 'Team adverse']
        elif self.teamId == 200:
            team = ['Team adverse', 'Team alliée']


        self.df_timeline_load['riot_id'] = self.df_timeline_load['participantId']

        self.df_timeline_load['team'] = np.where(
                        self.df_timeline_load['riot_id'] <= 5, team[0], team[1])

        self.df_timeline_load = self.df_timeline_load.groupby(['team', 'timestamp'], as_index=False)[
                        'totalGold'].sum()

        self.df_timeline_adverse = self.df_timeline_load[self.df_timeline_load['team'] == 'Team adverse'].reset_index(
                        drop=True)
        self.df_timeline_alliee = self.df_timeline_load[self.df_timeline_load['team'] == 'Team alliée'].reset_index(
                        drop=True)

        self.df_timeline_diff = pd.DataFrame(columns=['timestamp', 'ecart'])

        self.df_timeline_diff['timestamp'] = self.df_timeline_load['timestamp']

        self.df_timeline_diff['ecart'] = self.df_timeline_alliee['totalGold'] - \
                        (self.df_timeline_adverse['totalGold'])

                    # Cela applique deux fois le timestamp (un pour les adversaires, un pour les alliés...) On supprime la moitié :
        self.df_timeline_diff.dropna(axis=0, inplace=True)




        self.val_min_ecart_gold = self.df_timeline_diff['ecart'].min()
        self.val_max_ecart_gold = self.df_timeline_diff['ecart'].max()


        self.df_timeline_diff['match_id'] = self.last_match
        self.df_timeline_diff['riot_id'] = self.id_compte

        self.df_timeline_diff['gold_adv'] = self.df_timeline_adverse['totalGold']
        self.df_timeline_diff['gold_allie'] = self.df_timeline_alliee['totalGold']

            
        requete_perso_bdd('''UPDATE matchs SET fourth_dragon = :fourth_dragon,
                          first_elder = :first_elder,
                          first_horde = :first_horde,
                          first_double = :first_double,
                          first_triple = :first_triple,
                          first_quadra = :first_quadra,
                          first_penta = :first_penta,
                          first_niveau_max = :first_niveau_max,
                          first_blood = :first_blood,
                          early_atakhan = :first_atakhan,
                          solokilled = :solokilled,
                          gold_avec_kills = :gold_avec_kills,
                          kills_avec_jgl_early = :kills_avec_jgl_early,
                          deaths_with_jgl_early = :deaths_with_jgl_early,
                          shutdown_bounty = :shutdown_bounty,
                          ecart_gold_min_durant_game = :ecart_gold_min_durant_game,
                            ecart_gold_max_durant_game = :ecart_gold_max_durant_game
                        WHERE match_id = :match_id AND joueur = :joueur''',
                    {'fourth_dragon': self.timestamp_fourth_dragon,
                    'first_elder' : self.timestamp_first_elder,
                    'first_horde' : self.timestamp_first_horde,
                    'first_double' : self.timestamp_doublekill,
                    'first_triple' : self.timestamp_triplekill,
                    'first_quadra' : self.timestamp_quadrakill,
                    'first_penta' : self.timestamp_pentakill,
                    'first_niveau_max' : self.timestamp_niveau_max,
                    'first_blood' : self.timestamp_first_blood,
                    'first_atakhan' : self.timestamp_first_atakhan,
                    'solokilled' : self.get_solokilled,
                    'gold_avec_kills' : self.gold_with_kills,
                    'kills_avec_jgl_early' : self.kills_with_jgl_early,
                    'deaths_with_jgl_early' : self.deaths_with_jgl_early,
                    'shutdown_bounty' : self.bounty_recupere,
                    'ecart_gold_min_durant_game' : self.val_min_ecart_gold,
                    'ecart_gold_max_durant_game' : self.val_max_ecart_gold,
                    'match_id': self.last_match,
                    'joueur': self.id_compte})



        
        df_exists = lire_bdd_perso(f'''SELECT match_id, riot_id FROM data_timeline_events WHERE 
        match_id = '{self.last_match}'
        AND riot_id = {self.id_compte}  ''',
        index_col=None)
        
        if df_exists.empty:
            try:
                sauvegarde_bdd(self.df_events_joueur,
                                'data_timeline_events',
                                    methode_save='append',
                                    index=False)  
            except sqlalchemy.exc.IntegrityError:
                pass


        df_exists = lire_bdd_perso(f'''SELECT match_id, riot_id FROM matchs_timestamp_gold WHERE
        match_id = '{self.last_match}'
        AND riot_id = {self.id_compte}  ''',
        index_col=None)

        if df_exists.empty:
            try:
                sauvegarde_bdd(self.df_timeline_diff,
                        'matchs_timestamp_gold',
                            methode_save='append',
                            index=False)  
            except sqlalchemy.exc.IntegrityError:
                pass



        #####  
        
        def filtre_timeline(time):
            df_filtre_timeline = self.df_events_joueur[self.df_events_joueur['timestamp'] <= time]
            # Nombre de kills
            df_filtre_timeline.loc[(df_filtre_timeline['type'] == 'CHAMPION_SPECIAL_KILL') & (df_filtre_timeline['killerId'] == self.index_timeline), 'type'] = 'CHAMPION_KILL'
            # Impliqué mais pas le killer, donc assists
            df_filtre_timeline.loc[(df_filtre_timeline['type'] == 'CHAMPION_KILL') & (df_filtre_timeline['killerId'] != self.index_timeline), 'type'] = 'ASSISTS'
            # On enlève les doublons
            df_filtre_timeline.drop_duplicates(subset=['timestamp', 'killerId', 'type'], inplace=True)
            # On enlève les balises zombies
            df_filtre_timeline = df_filtre_timeline[df_filtre_timeline['wardType'] != 'Balise Zombie']
            # On compte
            df_filtre_timeline = df_filtre_timeline.groupby(['type', 'riot_id', 'match_id'], as_index=False).count()
            
            df_filtre_timeline['type'] = df_filtre_timeline.apply(lambda x : x['type'] + '_' + str(time), axis=1)
            df_filtre_timeline.rename(columns={'timestamp' : 'value'}, inplace=True )
            return df_filtre_timeline[['type', 'riot_id', 'match_id', 'value']]

        self.df_10min = filtre_timeline(10)
        self.df_20min = filtre_timeline(20)
        self.df_30min = filtre_timeline(30)

        self.df_10min.loc[len(self.df_10min)] = ['TOTAL_DMG_10', self.id_compte, self.last_match, self.totalDamageDone_10]
        self.df_10min.loc[len(self.df_10min)] = ['TOTAL_DMG_TAKEN_10', self.id_compte, self.last_match, self.totalDamageTaken_10]
        self.df_10min.loc[len(self.df_10min)] = ['TRADE_EFFICIENCE_10', self.id_compte, self.last_match, self.trade_efficience_10]




        self.df_20min.loc[len(self.df_20min)] = ['TOTAL_CS_20', self.id_compte, self.last_match, self.total_cs_20]
        self.df_20min.loc[len(self.df_20min)] = ['TOTAL_GOLD_20', self.id_compte, self.last_match, self.total_gold_20]
        self.df_20min.loc[len(self.df_20min)] = ['CS_20', self.id_compte, self.last_match, self.minions_20]
        self.df_20min.loc[len(self.df_20min)] = ['JGL_20', self.id_compte, self.last_match, self.jgl_killed_20]
        self.df_20min.loc[len(self.df_20min)] = ['TOTAL_DMG_20', self.id_compte, self.last_match, self.totalDamageDone_20]
        self.df_20min.loc[len(self.df_20min)] = ['TOTAL_DMG_TAKEN_20', self.id_compte, self.last_match, self.totalDamageTaken_20]
        self.df_20min.loc[len(self.df_20min)] = ['TRADE_EFFICIENCE_20', self.id_compte, self.last_match, self.trade_efficience_20]

        self.df_20min.loc[len(self.df_20min)] = ['TOTAL_CS_30', self.id_compte, self.last_match, self.total_cs_30]
        self.df_20min.loc[len(self.df_20min)] = ['TOTAL_GOLD_30', self.id_compte, self.last_match, self.total_gold_30]
        self.df_20min.loc[len(self.df_20min)] = ['CS_30', self.id_compte, self.last_match, self.minions_30]
        self.df_20min.loc[len(self.df_20min)] = ['JGL_30', self.id_compte, self.last_match, self.jgl_killed_30]
        self.df_20min.loc[len(self.df_20min)] = ['TOTAL_DMG_30', self.id_compte, self.last_match, self.totalDamageDone_30]
        self.df_20min.loc[len(self.df_20min)] = ['TOTAL_DMG_TAKEN_30', self.id_compte, self.last_match, self.totalDamageTaken_30]
        self.df_20min.loc[len(self.df_20min)] = ['TRADE_EFFICIENCE_30', self.id_compte, self.last_match, self.trade_efficience_30]


        self.df_time = pd.concat([self.df_10min, self.df_20min, self.df_30min])


        self.df_time_pivot = self.df_time.pivot_table(index=['riot_id', 'match_id'],
                                                      columns='type', values='value',
                                                      aggfunc='sum').reset_index()
        
        def safe_get_first(df, column):
            return int(df[column][0]) if column in df and not df[column].empty else 0

        self.assists_10 = safe_get_first(self.df_time_pivot, 'ASSISTS_10')
        self.assists_20 = safe_get_first(self.df_time_pivot, 'ASSISTS_20')
        self.assists_30 = safe_get_first(self.df_time_pivot, 'ASSISTS_30')
    
        self.deaths_10 = safe_get_first(self.df_time_pivot, 'DEATHS_10')
        self.deaths_20 = safe_get_first(self.df_time_pivot, 'DEATHS_20')
        self.deaths_30 = safe_get_first(self.df_time_pivot, 'DEATHS_30')

        self.champion_kill_10 = safe_get_first(self.df_time_pivot, 'CHAMPION_KILL_10')
        self.champion_kill_20 = safe_get_first(self.df_time_pivot, 'CHAMPION_KILL_20')
        self.champion_kill_30 = safe_get_first(self.df_time_pivot, 'CHAMPION_KILL_30')

        self.level_10 = safe_get_first(self.df_time_pivot, 'LEVEL_UP_10')
        self.level_20 = safe_get_first(self.df_time_pivot, 'LEVEL_UP_20')
        self.level_30 = safe_get_first(self.df_time_pivot, 'LEVEL_UP_30')

        self.jgl_20= safe_get_first(self.df_time_pivot, 'JGL_20')
        self.jgl_30 = safe_get_first(self.df_time_pivot, 'JGL_30')

        self.WARD_KILL_10 = safe_get_first(self.df_time_pivot, 'WARD_KILL_10')
        self.WARD_KILL_20 = safe_get_first(self.df_time_pivot, 'WARD_KILL_20')
        self.WARD_KILL_30 = safe_get_first(self.df_time_pivot, 'WARD_KILL_30')

        self.WARD_PLACED_10 = safe_get_first(self.df_time_pivot, 'WARD_KILL_10')
        self.WARD_PLACED_20 = safe_get_first(self.df_time_pivot, 'WARD_KILL_20')
        self.WARD_PLACED_30 = safe_get_first(self.df_time_pivot, 'WARD_KILL_30')

    

        df_exists = lire_bdd_perso(f'''SELECT match_id, riot_id FROM data_timeline_palier WHERE 
        match_id = '{self.last_match}'
        AND riot_id = {self.id_compte}  ''',
        index_col=None)
        
        if df_exists.empty:
            try:
                sauvegarde_bdd(self.df_time_pivot,
                                        'data_timeline_palier',
                                            methode_save='append',
                                            index=False) 
            except sqlalchemy.exc.IntegrityError:
                pass
       

    # async def clutch_factor(self):
    #     """
    #     Retourne le nombre de participations clutch (baron/elder/tour nexus) pour le joueur de la partie.
    #     Utilise la timeline déjà présente dans self.data_timeline.
    #     """
    #     if not self.data_timeline:
    #         return 0

    #     clutch_score = 0
    #     player_id = self.thisId + 1  # participantId (1-indexed)
    #     actions = []

    #     # Cherche dans les events de la timeline
    #     for frame in self.data_timeline['info']['frames']:
    #         for event in frame.get('events', []):
    #             # Baron/Elder kill
    #             if event['type'] == 'ELITE_MONSTER_KILL' and event['monsterType'] in ['BARON_NASHOR', 'ELDER_DRAGON']:
    #                 if event.get('killerId') == player_id:
    #                     clutch_score += 3
    #                     actions.append((event['monsterType'], event['timestamp']))
    #             # Dernière tourelle (approche simplifiée, à affiner)
    #             if event['type'] == 'BUILDING_KILL' and event.get('buildingType') == 'TOWER_BUILDING':
    #                 if event.get('killerId') == player_id and event.get('timestamp', 0) > 1800000:
    #                     clutch_score += 2
    #                     actions.append(('TOWER', event['timestamp']))
    #     return clutch_score, actions


    # async def tilt_proof(self):
    #     """
    #     Retourne le KDA du joueur après avoir subi 3 deaths consécutives.
    #     """
    #     if not self.data_timeline:
    #         return "No timeline"
    #     player_id = self.thisId + 1

    #     deaths, kills, assists = [], [], []
    #     for frame in self.data_timeline['info']['frames']:
    #         for event in frame.get('events', []):
    #             # Death
    #             if event['type'] == 'CHAMPION_KILL' and event.get('victimId') == player_id:
    #                 deaths.append(event['timestamp'])
    #             # Kill
    #             if event['type'] == 'CHAMPION_KILL' and event.get('killerId') == player_id:
    #                 kills.append(event['timestamp'])
    #             # Assist
    #             if event['type'] == 'CHAMPION_KILL' and 'assistingParticipantIds' in event:
    #                 if player_id in event['assistingParticipantIds']:
    #                     assists.append(event['timestamp'])

    #     if len(deaths) < 3:
    #         return "Pas assez de deaths"
    #     pivot = deaths[2]
    #     post_kills = len([k for k in kills if k > pivot])
    #     post_deaths = len([d for d in deaths if d > pivot])
    #     post_assists = len([a for a in assists if a > pivot])
    #     if post_deaths == 0:
    #         return post_kills + post_assists
    #     return round((post_kills + post_assists) / post_deaths, 2)
        




    async def perfect_farm_window(self, cs_min=10):
        """
        Calcule la plus longue période (en minutes) où le joueur maintient un CS/min > 10.
        Utilise la timeline (self.data_timeline) et les minions à chaque minute.
        """
        if not self.data_timeline:
            return 0

        
        cs_per_minute = []
        total_minions = 0

        # On parcourt chaque frame du timeline pour récupérer le farm cumulé
        for minute, frame in enumerate(self.data_timeline['info']['frames'][1:], 1):
            cs = frame['participantFrames'][str(self.index_timeline)]['minionsKilled'] + \
                frame['participantFrames'][str(self.index_timeline)].get('jungleMinionsKilled', 0)
            cs_per_minute.append(cs)
        
        max_window = 0
        window = 0

        for i, cs in enumerate(cs_per_minute):
            rate = cs / (i+1)
            if rate >= cs_min:
                window += 1
                max_window = max(max_window, window)
            else:
                window = 0

        return max_window  # en minutes consécutives
    


    # async def clutch_deaths(self):
    #     """
    #     Compte le nombre de fois où le joueur meurt en dernier de son équipe (1vX).
    #     Utilise la timeline.
    #     """
    #     if not self.data_timeline:
    #         return 0

    #     player_id = self.thisId + 1
    #     team_id = self.teamId
    #     participants = self.match_detail['info']['participants']
    #     deaths = 0

    #     for frame in self.data_timeline['info']['frames']:
    #         for event in frame.get('events', []):
    #             if event['type'] == 'CHAMPION_KILL' and event.get('victimId') == player_id:
    #                 # On regarde combien de mates sont vivants à cet instant
    #                 time = event['timestamp']
    #                 alive = []
    #                 for p in range(1, 11):
    #                     # Cherche la dernière mort du mate avant ce death
    #                     last_death = max([e['timestamp'] for f in self.data_timeline['info']['frames']
    #                                     for e in f.get('events', [])
    #                                     if e['type'] == 'CHAMPION_KILL'
    #                                     and e.get('victimId') == p
    #                                     and e['timestamp'] < time], default=-1)
    #                     # Vivant s'il n'est pas mort dans les 30 dernières sec
    #                     if p != player_id and participants[p-1]['teamId'] == team_id:
    #                         if time - last_death > 30000:
    #                             alive.append(p)
    #                 if not alive:  # personne n'est vivant à part toi
    #                     deaths += 1
    #     return deaths

    async def reverse_sweep(self):
        """
        Retourne True si l'équipe du joueur était derrière en gold, tours, dragons à 15min, mais gagne la partie.
        """
        participants = self.match_detail['info']['participants']
        team_id = self.teamId
        # Cherche gold/tour/dragon à 15min dans timeline
        try:
            frame_15 = self.data_timeline['info']['frames'][15]  # frame 15 = 15min
        except (IndexError, KeyError, TypeError):
            return False  # timeline trop courte

        team_gold = sum([frame_15['participantFrames'][str(i+1)]['totalGold'] for i, p in enumerate(participants) if p['teamId'] == team_id])
        opp_gold = sum([frame_15['participantFrames'][str(i+1)]['totalGold'] for i, p in enumerate(participants) if p['teamId'] != team_id])

        my_team = [i+1 for i,p in enumerate(participants) if p['teamId']==team_id]
        opp_team = [i+1 for i,p in enumerate(participants) if p['teamId']!=team_id]

        # Towers à 15min
        my_towers = frame_15['participantFrames'][str(my_team[0])].get('towerKills',0)
        opp_towers = frame_15['participantFrames'][str(opp_team[0])].get('towerKills',0)
        # Dragons (pas dans frame, donc check events)
        drake_events = []
        for f in self.data_timeline['info']['frames'][:16]:
            for e in f.get('events', []):
                if e['type']=='ELITE_MONSTER_KILL' and e['monsterType']=='DRAGON':
                    drake_events.append(e)
        my_drakes = len([d for d in drake_events if participants[d['killerId']-1]['teamId']==team_id])
        opp_drakes = len([d for d in drake_events if participants[d['killerId']-1]['teamId']!=team_id])

        # Condition : en retard sur tout à 15min, victoire finale
        ahead = team_gold > opp_gold and my_towers > opp_towers and my_drakes > opp_drakes
        behind = team_gold < opp_gold and my_towers < opp_towers and my_drakes < opp_drakes
        win = self.thisWinBool
        return behind and win

    async def deep_vision(self):
        """
        Compte le nombre de pinks/wards posées par le joueur dans la moitié ennemie de la map.
        (Nécessite que la timeline fournisse les events de ward avec position et team)
        """
        if not self.data_timeline:
            return 0

        
        team_id = self.teamId
        total_deep_wards = 0

        for frame in self.data_timeline['info']['frames']:
            for event in frame.get('events', []):
                if event['type'] in ['WARD_PLACED'] and event.get('creatorId') == self.index_timeline:
                    x = event.get('position', {}).get('x', 0)
                    # Pour blue side, la moitié ennemie c'est x > 7500; pour red, x < 7500
                    if (team_id == 100 and x > 7500) or (team_id == 200 and x < 7500):
                        total_deep_wards += 1
        return total_deep_wards

    

    # async def comeback_kda(self, deaths_threshold=5):
    #     """
    #     Retourne le KDA du joueur après avoir atteint 5 deaths (après un early très difficile).
    #     """
    #     if not self.data_timeline:
    #         return "No timeline"
    #     player_id = self.thisId + 1

    #     deaths, kills, assists = [], [], []
    #     for frame in self.data_timeline['info']['frames']:
    #         for event in frame.get('events', []):
    #             # Death
    #             if event['type'] == 'CHAMPION_KILL' and event.get('victimId') == player_id:
    #                 deaths.append(event['timestamp'])
    #             # Kill
    #             if event['type'] == 'CHAMPION_KILL' and event.get('killerId') == player_id:
    #                 kills.append(event['timestamp'])
    #             # Assist
    #             if event['type'] == 'CHAMPION_KILL' and 'assistingParticipantIds' in event:
    #                 if player_id in event['assistingParticipantIds']:
    #                     assists.append(event['timestamp'])

    #     if len(deaths) < deaths_threshold:
    #         return "Pas assez de deaths"
    #     pivot = deaths[deaths_threshold-1]
    #     post_kills = len([k for k in kills if k > pivot])
    #     post_deaths = len([d for d in deaths if d > pivot])
    #     post_assists = len([a for a in assists if a > pivot])
    #     if post_deaths == 0:
    #         return post_kills + post_assists
    #     return round((post_kills + post_assists) / post_deaths, 2)



    async def fight_participation(self, min_fight_size=3, fight_radius=1200, fight_interval=10000):
        """
        Pourcentage de teamfights où le joueur a participé (kill, assist, ou présence physique dans le fight_radius).
        """
        if not self.data_timeline:
            return 0
        
        participants = self.match_detail['info']['participants']
        fights = []
        last_fight_time = 0

        # Construction des fights groupés (par fenêtre de fight_interval)
        for frame in self.data_timeline['info']['frames']:
            for event in frame.get('events', []):
                if event['type'] == 'CHAMPION_KILL':
                    time = event['timestamp']
                    if fights and abs(time - last_fight_time) < fight_interval:
                        fights[-1]['events'].append(event)
                    else:
                        fights.append({'events': [event]})
                    last_fight_time = time

        my_participation = 0
        total_fights = 0

        for fight in fights:
            involved = set()
            event_times = []
            fight_positions = []
            # On construit la liste des positions des kills du fight
            for ev in fight['events']:
                event_times.append(ev['timestamp'])
                if 'position' in ev:
                    fight_positions.append((ev['position']['x'], ev['position']['y']))
                involved.add(ev['killerId'])
                involved.add(ev['victimId'])
                if 'assistingParticipantIds' in ev:
                    involved.update(ev['assistingParticipantIds'])
            if len(involved) < min_fight_size:
                continue
            total_fights += 1

            # Participation directe : kill/assist
            if self.index_timeline in involved:
                my_participation += 1
                continue

            # Participation par présence : On prend le tick le plus proche du fight pour le joueur
            participated = False
            for fight_time, fight_pos in zip(event_times, fight_positions):
                # Cherche la frame la plus proche en temps
                closest_frame = min(
                    self.data_timeline['info']['frames'],
                    key=lambda f: abs(f['timestamp'] - fight_time)
                )
                pos = closest_frame['participantFrames'][str(self.index_timeline)].get('position', None)
                if pos:
                    dx = pos['x'] - fight_pos[0]
                    dy = pos['y'] - fight_pos[1]
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist <= fight_radius:
                        participated = True
                        break
            if participated:
                my_participation += 1

        if total_fights == 0:
            return 0
        return round(100 * my_participation / total_fights, 1)

    

    async def kills_from_behind(self):
        """
        Nombre de kills réalisés alors que l'équipe du joueur était derrière en gold.
        """
        if not self.data_timeline:
            return 0
        
        team_id = self.teamId
        participants = self.match_detail['info']['participants']
        kills_behind = 0

        # Calcul du gold de chaque team à chaque frame
        team_gold_frames = []
        for frame in self.data_timeline['info']['frames']:
            my_gold = sum([frame['participantFrames'][str(i+1)]['totalGold'] for i, p in enumerate(participants) if p['teamId'] == team_id])
            opp_gold = sum([frame['participantFrames'][str(i+1)]['totalGold'] for i, p in enumerate(participants) if p['teamId'] != team_id])
            team_gold_frames.append((my_gold, opp_gold, frame['timestamp']))

        # Pour chaque kill du joueur, regarde la situation gold au moment du kill
        for frame in self.data_timeline['info']['frames']:
            for event in frame.get('events', []):
                if event['type'] == 'CHAMPION_KILL' and event.get('killerId') == self.index_timeline:
                    # Cherche la frame la plus proche avant ce kill
                    times = [abs(event['timestamp']-g[2]) for g in team_gold_frames]
                    idx = times.index(min(times))
                    my_gold, opp_gold, _ = team_gold_frames[idx]
                    if my_gold < opp_gold:
                        kills_behind += 1
        return kills_behind

    # async def objective_stealer(self):
    #     """
    #     Nombre de fois où le joueur a pris un drake/baron/herald contre la présence de membres adverses.
    #     """
    #     if not self.data_timeline:
    #         return 0

    #     participants = self.match_detail['info']['participants']
    #     team_id = self.teamId
    #     objectives = 0

    #     for frame in self.data_timeline['info']['frames']:
    #         for event in frame.get('events', []):
    #             if event['type'] == 'ELITE_MONSTER_KILL' and event.get('killerId') == self.index_timeline and event['monsterType'] in ['BARON_NASHOR', 'DRAGON', 'RIFTHERALD']:
    #                 # Présence ennemie : au moins 1 adversaire vivant à ce moment
    #                 time = event['timestamp']
    #                 opp_alive = False
    #                 for i, p in enumerate(participants):
    #                     if p['teamId'] != team_id:
    #                         # Cherche la dernière mort avant ce moment
    #                         last_death = max([e['timestamp'] for f in self.data_timeline['info']['frames']
    #                                         for e in f.get('events', [])
    #                                         if e['type'] == 'CHAMPION_KILL' and e.get('victimId') == i+1 and e['timestamp'] < time], default=-1)
    #                         # Si pas mort dans les 10 dernières sec, on considère vivant
    #                         if time - last_death > 10000:
    #                             opp_alive = True
    #                 if opp_alive:
    #                     objectives += 1
    #     return objectives

    async def roam_score(self):
        """
        Nombre de roams réussis avant 15min : kill/assist obtenu sur une lane différente de la sienne avant 900000ms.
        """
        if not self.data_timeline:
            return 0
        
        participants = self.match_detail['info']['participants']
        my_lane = self.match_detail_participants.get('individualPosition', None)
        roams = 0

        for frame in self.data_timeline['info']['frames']:
            for event in frame.get('events', []):
                if event['timestamp'] > 900000:
                    continue
                if event['type'] == 'CHAMPION_KILL':
                    # Est-ce un kill/assist du joueur sur une autre lane ?
                    if (event.get('killerId') == self.index_timeline or (self.index_timeline in event.get('assistingParticipantIds', []))):
                        victim_id = event.get('victimId')
                        if victim_id:
                            victim = participants[victim_id-1]
                            victim_lane = victim.get('individualPosition', None)
                            if my_lane and victim_lane and my_lane != victim_lane:
                                roams += 1
        return roams

    async def lane_pressure(self):
        """
        % de frames (1/m) où le joueur est sur sa lane naturelle entre 3 et 15 min.
        """
        if not self.data_timeline:
            return 0
        
        my_lane = self.match_detail_participants.get('individualPosition', None)
        lane_zones = {
            'TOP': lambda x, y: x < 4000 and y > 9500,
            'MID': lambda x, y: 5200 < x < 11800 and 5200 < y < 11800,
            'BOTTOM': lambda x, y: x > 11000 and y < 3300,
        }
        total_frames = 0
        on_lane_frames = 0
        for i, frame in enumerate(self.data_timeline['info']['frames']):
            time = frame['timestamp']
            if 180000 < time < 900000 and str(self.index_timeline) in frame['participantFrames']:
                pos = frame['participantFrames'][str(self.index_timeline)].get('position', None)
                if pos and my_lane in lane_zones:
                    total_frames += 1
                    if lane_zones[my_lane](pos['x'], pos['y']):
                        on_lane_frames += 1
        if total_frames == 0:
            return 0
        return round(100 * on_lane_frames / total_frames, 1)

    # async def engage_or_die(self):
    #     """
    #     Nombre de fois où le joueur a flash-in puis meurt dans les 5 secondes suivantes (engage fatal).
    #     """
    #     if not self.data_timeline:
    #         return 0
        
    #     engages = 0
    #     flash_spell_slot = 4  # Flash slot (4 ou 5, selon le mapping Riot)

    #     # On repère les flashes utilisés, puis check mort dans les 5 sec
    #     for frame in self.data_timeline['info']['frames']:
    #         for event in frame.get('events', []):
    #             if event['type'] == 'SKILL_CAST' and event.get('participantId') == self.index_timeline and event.get('skillSlot', None) == flash_spell_slot:
    #                 flash_time = event['timestamp']
    #                 # Check mort dans les 5 sec
    #                 for f in self.data_timeline['info']['frames']:
    #                     for e in f.get('events', []):
    #                         if e['type'] == 'CHAMPION_KILL' and e.get('victimId') == self.index_timeline and 0 < e['timestamp'] - flash_time <= 5000:
    #                             engages += 1
    #     return engages

    # async def flash_save(self):
    #     """
    #     Nombre de fois où le joueur flash puis a moins de 10% HP au tick suivant sans mourir dans les 10 sec.
    #     """
    #     if not self.data_timeline:
    #         return 0
    #     player_id = self.thisId + 1
    #     saves = 0
    #     flash_spell_slot = 4  # à adapter selon l'API
    #     max_hp = self.match_detail_participants.get('stats', {}).get('championMaxHealth', 2000)

    #     for i, frame in enumerate(self.data_timeline['info']['frames']):
    #         for event in frame.get('events', []):
    #             if event['type'] == 'SKILL_CAST' and event.get('participantId') == player_id and event.get('skillSlot', None) == flash_spell_slot:
    #                 flash_time = event['timestamp']
    #                 # On prend la frame suivante
    #                 if i + 1 < len(self.data_timeline['info']['frames']):
    #                     next_frame = self.data_timeline['info']['frames'][i+1]
    #                     hp = next_frame['participantFrames'][str(player_id)].get('currentHealth', 1000)
    #                     if hp < 0.1 * max_hp:
    #                         # Check si mort dans les 10 sec
    #                         died = False
    #                         for f in self.data_timeline['info']['frames']:
    #                             for e in f.get('events', []):
    #                                 if e['type'] == 'CHAMPION_KILL' and e.get('victimId') == player_id and 0 < e['timestamp'] - flash_time < 10000:
    #                                     died = True
    #                         if not died:
    #                             saves += 1
    #     return saves

    async def first_to_die(self):
        """
        True si le joueur est le premier à mourir dans la partie.
        """
        if not self.data_timeline:
            return False

        deaths = []
        for frame in self.data_timeline['info']['frames']:
            for event in frame.get('events', []):
                if event['type'] == 'CHAMPION_KILL':
                    deaths.append((event['timestamp'], event['victimId']))
        if not deaths:
            return False
        deaths.sort()
        return deaths[0][1] == self.index_timeline

    async def turning_point_minute(self):
        """
        Minute où l'équipe du joueur est passée devant au gold (ou plus grand comeback).
        """
        participants = self.match_detail['info']['participants']
        team_id = self.teamId
        gold_diff = []
        for i, frame in enumerate(self.data_timeline['info']['frames']):
            my_gold = sum([frame['participantFrames'][str(j+1)]['totalGold'] for j, p in enumerate(participants) if p['teamId'] == team_id])
            opp_gold = sum([frame['participantFrames'][str(j+1)]['totalGold'] for j, p in enumerate(participants) if p['teamId'] != team_id])
            gold_diff.append(my_gold - opp_gold)
        for i in range(1, len(gold_diff)):
            if gold_diff[i-1] < 0 and gold_diff[i] >= 0:
                return i  # minute où lead gold devient positif
        return None  # Jamais passé devant

    async def worst_death(self):
        """
        Renvoie la mort du joueur qui a donné l'objectif le plus coûteux juste après (baron/tour).
        """
        if not self.data_timeline:
            return None

        participants = self.match_detail['info']['participants']
        deaths = []
        for frame in self.data_timeline['info']['frames']:
            for event in frame.get('events', []):
                if event['type'] == 'CHAMPION_KILL' and event.get('victimId') == self.index_timeline:
                    deaths.append(event['timestamp'])
        worst_impact = 0
        worst_death_time = None
        for death in deaths:
            impact = 0
            # Check les 40 sec après la mort pour baron/tour
            for frame in self.data_timeline['info']['frames']:
                for event in frame.get('events', []):
                    if death < event['timestamp'] < death + 40000:
                        if event['type'] == 'ELITE_MONSTER_KILL' and event['monsterType'] == 'BARON_NASHOR':
                            impact += 5
                        if event['type'] == 'BUILDING_KILL' and event.get('buildingType') == 'TOWER_BUILDING':
                            impact += 2
            if impact > worst_impact:
                worst_impact = impact
                worst_death_time = death
        if worst_death_time:
            return worst_death_time // 60000, worst_impact
        else:
            return None




    async def detect_2v2_skirmishes(self, window=0.2):
        """
        Détecte les skirmishes 2v2 dans le match à partir de self.df_events.
        Retourne une liste de dicts avec infos sur chaque skirmish détecté.
        """
        df = self.df_events.copy()

        df['timestamp'] = np.round(df['timestamp'] / 60000,2)
            
        # df['timestamp'] = df['timestamp'].apply(fix_temps)


        # Filtre les kills seulement
        df_kill = df[df['type'] == 'CHAMPION_KILL'].copy()
        if df_kill.empty:
            return []

        # Mapping participantId -> teamId
        participants = self.match_detail['info']['participants']
        team_mapping = {p['participantId']: p['teamId'] for p in participants}

        skirmishes = []
        visited = set()

        for idx, row in df_kill.iterrows():
            t = row['timestamp']
            # Fenêtre autour du kill
            window_kills = df_kill[(df_kill['timestamp'] >= t - window) & (df_kill['timestamp'] <= t + window)]
            kills_idx_tuple = tuple(sorted(window_kills.index))
            if kills_idx_tuple in visited or len(window_kills) < 2:
                continue
            visited.add(kills_idx_tuple)

            involved = set()
            for _, kill in window_kills.iterrows():
                involved.add(kill['killerId'])
                involved.add(kill['victimId'])
                # Ajoute les assists si présents
                if 'assistingParticipantIds' in kill and isinstance(kill['assistingParticipantIds'], list):
                    involved.update(kill['assistingParticipantIds'])
            # Nettoie les non-joueurs
            involved = {pid for pid in involved if pid in team_mapping}
            # On veut 2 joueurs par équipe exactement
            if len(involved) == 4:
                teams = [team_mapping[pid] for pid in involved]
                if teams.count(100) == 2 and teams.count(200) == 2:
                    kills_100 = sum(team_mapping[kill['killerId']] == 100 for _, kill in window_kills.iterrows())
                    kills_200 = sum(team_mapping[kill['killerId']] == 200 for _, kill in window_kills.iterrows())
                    if kills_100 > 0 or kills_200 > 0:
                        winner = None
                        if kills_100 > kills_200:
                            winner = 100
                        elif kills_200 > kills_100:
                            winner = 200
                        skirmishes.append({
                            "timestamp": int(t),
                            "joueurs_100": [self.thisChampNameListe[int(pid - 1)] for pid in involved if team_mapping[pid] == 100],
                            "joueurs_200": [self.thisChampNameListe[int(pid - 1)] for pid in involved if team_mapping[pid] == 200],
                            "kills_100": kills_100,
                            "kills_200": kills_200,
                            "winner": winner
                        })


        return skirmishes


    async def detect_2v3_skirmishes(self, window=0.2):
        """
        Détecte les skirmishes 2v3 dans le match à partir de self.df_events.
        Retourne une liste de dicts avec infos sur chaque skirmish détecté.
        """
        df = self.df_events.copy()
        df['timestamp'] = np.round(df['timestamp'] / 60000, 2)

        # Filtre les kills seulement
        df_kill = df[df['type'] == 'CHAMPION_KILL'].copy()
        if df_kill.empty:
            return []

        # Mapping participantId -> teamId
        participants = self.match_detail['info']['participants']
        team_mapping = {p['participantId']: p['teamId'] for p in participants}

        skirmishes = []
        visited = set()

        for idx, row in df_kill.iterrows():
            t = row['timestamp']
            # Fenêtre autour du kill
            window_kills = df_kill[(df_kill['timestamp'] >= t - window) & (df_kill['timestamp'] <= t + window)]
            kills_idx_tuple = tuple(sorted(window_kills.index))
            if kills_idx_tuple in visited or len(window_kills) < 2:
                continue
            visited.add(kills_idx_tuple)

            involved = set()
            for _, kill in window_kills.iterrows():
                involved.add(kill['killerId'])
                involved.add(kill['victimId'])
                # Ajoute les assists si présents
                if 'assistingParticipantIds' in kill and isinstance(kill['assistingParticipantIds'], list):
                    involved.update(kill['assistingParticipantIds'])
            # Nettoie les non-joueurs
            involved = {pid for pid in involved if pid in team_mapping}
            
            # On veut 2 joueurs d'une team et 3 joueurs de l'autre team
            team_100 = [pid for pid in involved if team_mapping[pid] == 100]
            team_200 = [pid for pid in involved if team_mapping[pid] == 200]
            sizes = (len(team_100), len(team_200))
            
            if sorted(sizes) == [2, 3]:  # 2 d'une équipe et 3 de l'autre
                kills_100 = sum(team_mapping[kill['killerId']] == 100 for _, kill in window_kills.iterrows())
                kills_200 = sum(team_mapping[kill['killerId']] == 200 for _, kill in window_kills.iterrows())
                if kills_100 > 0 or kills_200 > 0:
                    winner = None
                    if kills_100 > kills_200:
                        winner = 100
                    elif kills_200 > kills_100:
                        winner = 200
                    skirmishes.append({
                        "timestamp": int(t),
                        "joueurs_100": [self.thisChampNameListe[int(pid - 1)] for pid in team_100],
                        "joueurs_200": [self.thisChampNameListe[int(pid - 1)] for pid in team_200],
                        "kills_100": kills_100,
                        "kills_200": kills_200,
                        "winner": winner
                    })
        return skirmishes



      

    def calcul_scoring(self, i):
            """Calcule la performance d'un joueur
            """

            score = self.model.predict(pd.DataFrame([[self.thisKillsListe[i],
                                                 self.thisAssistsListe[i],
                                                 self.thisDeathsListe[i],
                                                 self.thisDoubleListe[i],
                                                 self.thisTripleListe[i],
                                                 self.thisQuadraListe[i],
                                                 self.thisPentaListe[i],
                                                 self.thisDamagePerMinuteListe[i],
                                                 self.thisMinionPerMinListe[i],
                                                 self.thisVisionPerMinListe[i],
                                                 self.thisKPListe[i],
                                                 self.thisKDAListe[i],
                                                 self.thisTankPerMinListe[i]]]))
            
            return score  
    
    async def detection_joueurs_pro(self):
        df_data_pro = lire_bdd_perso('''SELECT data_acc_proplayers.*, data_proplayers.home, data_proplayers.role, data_proplayers.team_plug 
                                        FROM data_acc_proplayers
                                        LEFT JOIN data_proplayers ON data_acc_proplayers.joueur = data_proplayers.plug
                                        WHERE region = 'EUW' ''', index_col=None).T

        df_data_pro['tag'] = df_data_pro['compte'].apply(lambda x: x.split('#')[1].upper() if '#' in x else '')
        df_data_pro['compte'] = df_data_pro['compte'].apply(lambda x: x.split('#')[0])

        self.observations_proplayers = ''
        for num_joueur, (joueur, riot_tag) in enumerate(zip(self.thisPseudoListe, self.thisRiotTagListe)):
            riot_tag = riot_tag.upper()
            match_df = df_data_pro[(df_data_pro['compte'] == joueur) & (df_data_pro['tag'] == riot_tag)]

            if not match_df.empty:
                name_joueur = match_df['joueur'].values[0]
                role_joueur = match_df['role'].values[0]
                team_joueur = match_df['team_plug'].values[0]
                champ_joueur = self.thisChampNameListe[num_joueur]
                emote_champ = emote_champ_discord.get(champ_joueur.capitalize(), f'({champ_joueur})')
                emote = ':blue_circle:' if num_joueur <= 4 else ':red_circle:'

                if team_joueur in ('', None):
                    self.observations_proplayers += f'{emote} **{name_joueur}** {emote_champ} : {role_joueur} \n'
                else:
                    self.observations_proplayers += f'{emote} **{name_joueur}** {emote_champ} : {role_joueur} chez {team_joueur} \n'

                       
    async def calcul_badges(self, sauvegarder):
        # TODO : Faire une table qui récapitule si un badge a été obtenu par un joueur dans une game spécifique
        if self.thisQ in ['ARAM', 'CLASH ARAM']:
            # couronnes pour aram
            settings = lire_bdd_perso(
                f'SELECT index, score_aram as score from achievements_settings')
        else:  # couronnes si autre mode de jeu
            settings = lire_bdd_perso(
                f'SELECT index, score as score from achievements_settings')

        settings = settings.to_dict()
        

        
        def insight_text(slug, values, type):
                  
            type_comment = {'Positive' : ':green_circle:', 'Negative' : ':red_circle:', '': ':first_place:'}


            dict_insight = {
                        # 'never_slacking' : f'\n{type_comment[type]} **{values[0]}** cs en mid game',
                        'teamfight_god' : f'\n{type_comment[type]} Gagné **{values[0]}** sur **{values[1]}** teamfights',
                        'lane_tyrant' : f"\n{type_comment[type]} **{values[0]}** gold d'avance à 15 min",
                        'stomp' : f"\n{type_comment[type]} **{values[0]}** gold d'avance",
                        'how_could_you' : f"\n{type_comment[type]} **{values[0]}** wards placés",
                        'not_fan_of_wards' : f"\n{type_comment[type]} Placé **{values[0]}** wards",
                        'servant_of_darkness' : f"\n{type_comment[type]} Détruit **{values[0]}** wards",
                        'good_guy' : f"\n{type_comment[type]} Acheté **{values[0]}** pink",
                        # 'no_dragons_taken' : f"\n{type_comment[type]} Aucun dragon",
                        # 'no_rift_heralds_taken' : f"\n{type_comment[type]} Aucun herald",
                        # 'no_objectives_taken' : f"\n{type_comment[type]} Aucun objectif",
                        'pick_up_artist' : f"\n{type_comment[type]} Sécurisé **{values[0]}** picks",
                        "wanderer" : f"\n{type_comment[type]} Roam pour sécuriser kills et objectifs",
                        'survivor' : f"\n{type_comment[type]} Seulement  **{values[0]}** mort(s)",
                        'elite_skirmisher' : f"\n{type_comment[type]} Gagné **{values[0]}** escarmouches sur **{values[1]}**",
                        # 'on_fire' : f"\n{type_comment[type]} **{round(values[0],2)}** KDA",
                        "wrecking_ball" : f"\n{type_comment[type]} **{values[0]}** DMG aux structures",
                        "ouch_you_hurt" : f"\n{type_comment[type]} **{values[0]}** DMG infligés",
                        "goblin_hoarder" : f"\n{type_comment[type]} **{int(values[0])}** Gold / min",
                        # "bringer_of_carnage" : f"\n{type_comment[type]} **{values[0]}** Kills",
                        "anti_kda_player" : f"\n{type_comment[type]} **{round(values[0],2)}** KDA",
                        # "what_powerspike" : f"\n{type_comment[type]} Pas atteint le niveau 11",
                        "not_fan_of_farming" : f"\n {type_comment[type]} **{int(values[0])}** farm / min",
                        # "immortal" : f"\n {type_comment[type]} Immortel",
                        "visionary" : f"\n {type_comment[type]} **{values[0]}** wards placés",
                        "no_control" : f"\n{type_comment[type]} 0 pink",
                        "blood_thirsty" : f"\n{type_comment[type]} Tu as réussi **{values[0]}** ganks dans les 10 premières minutes.",
                        "superior_jungler" : f"\n{type_comment[type]} Tu as réussi plus de ganks avec **{values[0]}**",
                        "comeback_king" : f"\n {type_comment[type]} Tu as réussi à comeback après un début difficile",
                        "safety_first" : f"\n{type_comment[type]} Tu as placé assez de vision pour préparer les objectifs neutres",
                        'no_damage_to_turrets' : f"\n{type_comment[type]} **0** DMG sur les tours",
                        'mvp' : f"\n{type_comment[type]} **Meilleur joueur**"}
            
            if not self.thisQ in ['ARAM', 'CLASH ARAM']:
                dict_insight['ready_to_rumble'] = f"\n{type_comment[type]} Proactif en early avec **{values[0]}** kills/assists avant 15 minutes"
                
            if slug == 'early_game_farmer' and values[0] >= 85: # on l'ajoute à partir de 85 cs, car le calcul de base est trop gentil (65-70 cs)
                dict_insight['early_game_farmer'] = f'\n{type_comment[type]} Farm en early avec **{values[0]}** cs à 10 minutes',
                
                
            return dict_insight.get(slug,'')


        self.observations = ''
        txt_sql = ''
                 
        def add_sql(txt_sql, name, values, last_match, id_compte):
            if len(values) != 3:
                values.append(0)
                values.append(0)
                
            if (values[0] == 0):
                txt_sql += f'''UPDATE data_badges SET {name} = True WHERE match_id = '{last_match}' and joueur = '{id_compte}';'''
            elif (values[0] != 0 and values[1] == 0):
                txt_sql += f'''UPDATE data_badges SET {name} = True, {name}_value = {values[0]} WHERE match_id = '{last_match}' and joueur = '{id_compte}';'''
            else:
                txt_sql += f'''UPDATE data_badges SET {name} = True, {name}_value1 = {values[0]}, {name}_value2 = {values[1]} WHERE match_id = '{last_match}' and joueur = '{id_compte}';'''
            
            return txt_sql
        
        try:
            for insight in self.badges:
                self.observations += insight_text(insight['slug'], insight['values'], insight['type'])
                if insight['slug'] in ['teamfight_god',
                                'lane_tyrant',
                                'stomp',
                                'how_could_you',
                                'not_fan_of_wards',
                                'servant_of_darkness',
                                'good_guy',
                                'pick_up_artist',
                                'wanderer',
                                'survivor',
                                'elite_skirmisher',
                                'wrecking_ball',
                                'ouch_you_hurt',
                                'goblin_hoarder',
                                'anti_kda_player',
                                'not_fan_of_farming',
                                'visionary',
                                'no_control',
                                'blood_thirsty',
                                'superior_jungler',
                                'comeback_king',
                                'safety_first',
                                'no_damage_to_turrets',
                                'mvp']:
                    txt_sql += add_sql(txt_sql, insight['slug'], insight['values'], self.last_match, self.id_compte)
        except TypeError as e: # si pas de badges
            pass
            
        # Autres : 
        
        if self.thisDouble >= 3:
            self.observations += f"\n:green_circle: :two: **{self.thisDouble}** doublé"
            txt_sql += add_sql(txt_sql, 'double', [self.thisDouble], self.last_match, self.id_compte)
            
        if self.thisTriple >= 2:
            self.observations += f"\n:green_circle: :three: **{self.thisTriple}** triplé"
            txt_sql += add_sql(txt_sql, 'triple', [self.thisTriple], self.last_match, self.id_compte)
            
        if self.thisQuadra >= 2:
            self.observations += f"\n:green_circle: :four: **{self.thisQuadra}** quadra"
            txt_sql += add_sql(txt_sql, 'quadra', [self.thisQuadra], self.last_match, self.id_compte)
            
        if self.thisPenta >= 1:
            self.observations += f"\n:green_circle: :five: **{self.thisPenta}** penta"
            txt_sql += add_sql(txt_sql, 'penta', [self.thisPenta], self.last_match, self.id_compte)
            
        if self.thisTotalHealed >= 5000:
            self.observations += f"\n:green_circle: **{self.thisTotalHealed}** HP soignés"
            txt_sql += add_sql(txt_sql, 'heal', [self.thisTotalHealed], self.last_match, self.id_compte)
            
        if self.thisTotalShielded >= 3000:
            self.observations += f"\n:green_circle: :shield: **{self.thisTotalShielded} ** boucliers"
            txt_sql += add_sql(txt_sql, 'shield', [self.thisTotalShielded], self.last_match, self.id_compte)
            
        if self.thisVisionAdvantage >= 60 and not self.thisQ in ['ARAM', 'CLASH ARAM']:
            self.observations += f"\n:green_circle: :eye: **{self.thisVisionAdvantage}**% AV vision"
            txt_sql += add_sql(txt_sql, 'vision_avantage', [self.thisVisionAdvantage], self.last_match, self.id_compte)
        
        elif self.thisVisionAdvantage <= -50 and not self.thisQ in ['ARAM', 'CLASH ARAM']:
            self.observations += f"\n:red_circle: :eye: **{self.thisVisionAdvantage}**% AV vision"
            txt_sql += add_sql(txt_sql, 'vision_avantage', [self.thisVisionAdvantage], self.last_match, self.id_compte)
            
        if self.thisSoloKills >= 1:
            self.observations += f"\n:green_circle: :karate_uniform: **{self.thisSoloKills}** solokills"
            txt_sql += add_sql(txt_sql, 'solokills', [self.thisSoloKills], self.last_match, self.id_compte)
            
        if self.thisMinionPerMin >= 7:
            self.observations += f'\n:green_circle: :ghost: **{self.thisMinionPerMin}** cs/min'
            txt_sql += add_sql(txt_sql, 'minion_min', [self.thisMinionPerMin], self.last_match, self.id_compte)
 

        # pour only ranked/normal game
        if self.thisQ in ['RANKED', 'NORMAL', 'FLEX']:
            if int(self.thisLevelAdvantage) >= settings['Ecart_Level']['score']:
                self.observations +=\
                        f"\n **:green_circle: :wave: {self.thisLevelAdvantage} niveaux d'avance sur ton adversaire**"
                txt_sql += add_sql(txt_sql, 'level_avantage', [self.thisLevelAdvantage], self.last_match, self.id_compte)


            if (float(self.thisDragonTeam) >= settings['Dragon']['score']):
                self.observations += f"\n **:green_circle: :dragon: Âme du dragon **"
                txt_sql += add_sql(txt_sql, 'dragon', [self.thisDragonTeam], self.last_match, self.id_compte)

            if (int(self.thisDanceHerald) >= 1):
                self.observations += f"\n **:green_circle: :dancer: Danse avec l'Herald **"
                txt_sql += add_sql(txt_sql, 'herald_dance', [0], self.last_match, self.id_compte)

            if (int(self.thisPerfectGame) >= 1):
                self.observations += f"\n:green_circle: :sunny: Perfect Game"
                txt_sql += add_sql(txt_sql, 'perfect_game', [0], self.last_match, self.id_compte)


            if int(self.thisDeaths) == int(settings['Ne_pas_mourir']['score']):
                self.observations += "\n **:green_circle: :heart: N'est pas mort de la game ** \n "
                txt_sql += add_sql(txt_sql, 'ne_pas_mourir', [0], self.last_match, self.id_compte)


            if float(self.thisVisionPerMin) >= settings['Vision/min(support)']['score'] and str(self.thisPosition) == "SUPPORT":
                self.observations +=\
                        f"\n **:green_circle: :eye: {self.thisVisionPerMin} Vision / min **"
                txt_sql += add_sql(txt_sql, 'vision_min', [self.thisVisionPerMin], self.last_match, self.id_compte)


            if int(self.thisVisionPerMin) >= settings['Vision/min(autres)']['score'] and str(self.thisPosition) != "SUPPORT":
                self.observations +=\
                        f"\n **:green_circle: :eye: {self.thisVisionPerMin} Vision / min **"
                txt_sql += add_sql(txt_sql, 'vision_min', [self.thisVisionPerMin], self.last_match, self.id_compte)


            if int(self.thisCSAdvantageOnLane) >= settings['CSAvantage']['score']:
                self.observations +=\
                        f"\n **:green_circle: :ghost: {self.thisCSAdvantageOnLane} CS d'avance sur ton adversaire**"
                txt_sql += add_sql(txt_sql, 'cs_avantage', [self.thisCSAdvantageOnLane], self.last_match, self.id_compte)
                        
                        


        # pour tous les modes
        if self.thisQ != 'ARENA 2v2':

            # if int(self.thisKP) >= settings['KP']['score']:
            #     self.observations +=\
            #             f"\n **:green_circle: :dagger: {self.thisKP}% KP **"
            #     txt_sql += add_sql(txt_sql, 'kp', [self.thisKP], self.last_match,self.id_compte)


            # if int(self.thisDamageRatio) >= settings['%_dmg_équipe']['score']:
            #     self.observations +=\
            #             f"\n **:green_circle: :dart: {self.thisDamageRatio}% DMG de ton équipe **"
            #     txt_sql += add_sql(txt_sql, 'damage_ratio', [self.thisDamageRatio], self.last_match, self.id_compte)


            if int(self.thisDamageTakenRatio) >= settings['%_dmg_tank']['score']:
                self.observations +=\
                        f"\n **:green_circle: :shield: {self.thisDamageTakenRatio}% Tanking de ton équipe **"
                txt_sql += add_sql(txt_sql, 'tank_ratio', [self.thisDamageTakenRatio], self.last_match, self.id_compte)
                        
        if len(self.observations) > 1000:
            self.observations2 = self.observations[1000:]
            self.observations = self.observations[:1000]
        else:
            self.observations2 = ''

        requete_perso_bdd(f'''INSERT INTO data_badges(
	                match_id, joueur)
	                VALUES ('{self.last_match}', '{self.id_compte}');''')
        
        if txt_sql != '' and sauvegarder:
            requete_perso_bdd(txt_sql)
            
    async def detection_smurf(self):
        
        self.observations_smurf = ''
        
        for num, (joueur, stat) in enumerate(self.winrate_joueur.items()):
            if joueur != f'{self.riot_id.lower()}#{self.riot_tag.upper()}' and stat['winrate'] >= 70 and stat['nbgames'] >= 20:
                if num <= 4:
                    emote = ':blue_circle:'
                else:
                    emote = ':red_circle:'
                self.observations_smurf += f'{emote} **{joueur.split("#")[0]}** : WR : {stat["winrate"]}% ({stat["nbgames"]} parties) \n'

                
        for num, (joueur, stat) in enumerate(self.winrate_champ_joueur.items()):
            if isinstance(stat, dict):
                if joueur != f'{self.riot_id.lower()}#{self.riot_tag.upper()}' and stat['winrate'] >= 70 and stat['totalMatches'] >= 15:
                    emote_champ = emote_champ_discord.get(stat["championId"].capitalize(), stat["championId"])
                    if num <= 4:
                        emote = ':blue_circle:'
                    else:
                        emote = ':red_circle:'
                    self.observations_smurf += f'{emote} **{joueur.split("#")[0]}** : WR : {stat["winrate"]}% ({stat["totalMatches"]} parties) sur {emote_champ} \n'

                

    async def detection_mauvais_joueur(self):
        
        self.observations_mauvais_joueur = ''
        
        for num, (joueur, stat) in enumerate(self.winrate_joueur.items()):
            if joueur != f'{self.riot_id.lower()}#{self.riot_tag.upper()}' and stat['winrate'] <= 40 and stat['nbgames'] >= 20:
                if num <= 4:
                    emote = ':blue_circle:'
                else:
                    emote = ':red_circle:'
                self.observations_mauvais_joueur += f'{emote} **{joueur.split("#")[0]}** : WR : {stat["winrate"]}% ({stat["nbgames"]} parties) \n'

                
        for num, (joueur, stat) in enumerate(self.winrate_champ_joueur.items()):
            if isinstance(stat, dict):
                if joueur != f'{self.riot_id.lower()}#{self.riot_tag.upper()}' and stat['winrate'] <= 40 and stat['totalMatches'] >= 15:
                    emote_champ = emote_champ_discord.get(stat["championId"].capitalize(), stat["championId"])
                    if num <= 4:
                        emote = ':blue_circle:'
                    else:
                        emote = ':red_circle:'
                    self.observations_mauvais_joueur += f'{emote} **{joueur.split("#")[0]}** : WR : {stat["winrate"]}% ({stat["totalMatches"]} parties) sur {emote_champ} \n'

                
    async def detection_first_time(self):

        self.first_time = ''

        dict_pos = {0 : 'top',
                        1 : 'jungle',
                        2 : 'mid',
                        3 : 'adc',
                        4 : 'support',
                        5 : 'top',
                        6 : 'jungle',
                        7 : 'mid',
                        8 : 'adc',
                        9 : 'support'}
                
        for num, (joueur, stat) in enumerate(self.winrate_champ_joueur.items()):
            
            if isinstance(stat, dict):
                if joueur != f'{self.riot_id.lower()}#{self.riot_tag.upper()}' and stat['totalMatches'] <= 5:
                    if num <= 4:
                        emote = ':blue_circle:'
                    else:
                        emote = ':red_circle:'
                    emote_champ = emote_champ_discord.get(stat["championId"].capitalize(), stat["championId"])

                    self.first_time += f'{emote} **{joueur.split("#")[0]}** : {stat["totalMatches"]} games sur {emote_champ} \n'


            pseudo = joueur.split("#")[0]


            if pseudo in self.all_role.keys():
                if num <= 4:
                    emote = ':blue_circle:'
                else:
                    emote = ':red_circle:'

                role = dict_pos[num]
                main_role = self.role_pref[pseudo]['main_role']
                poids_main_role = self.role_pref[pseudo]['poids_role']
                emote_champ = emote_champ_discord.get(self.thisChampNameListe[num].capitalize(), self.thisChampNameListe[num].capitalize())

                try:
                    if self.all_role[pseudo][role]['poids'] <= 15 and self.role_count[pseudo] > 30:

                        self.first_time += f'{emote} **{pseudo}** {emote_champ} Autofill ({role.upper()}) : Main {main_role.upper()} ({poids_main_role}%) \n'
                except KeyError:
                    pass




    async def detection_otp(self):

        self.otp = ''
                
        for num, (joueur, stat) in enumerate(self.winrate_champ_joueur.items()):
            if isinstance(stat, dict):
                if joueur != f'{self.riot_id.lower()}#{self.riot_tag.upper()}' and stat['totalMatches'] >= 20 and stat['poids_games'] > 70:
                    emote_champ = emote_champ_discord.get(stat["championId"].capitalize(), stat["championId"])
                    if num <= 4:
                        emote = ':blue_circle:'
                    else:
                        emote = ':red_circle:'
                    

                    self.otp += f'{emote} **{joueur.split("#")[0]}** : {emote_champ} {stat["poids_games"]}% pick | {stat["winrate"]}% WR \n'



    async def detection_serie_victoire(self):

        self.serie_victoire = ''
        for i, (joueur, stats) in enumerate(self.dict_serie.items()):
            if stats['count'] >= 5:
                emote = ':green_circle:' if i <= 4 else ':red_circle:'
                mot = 'V' if  stats['mot'] == 'Victoire' else 'D'
                self.serie_victoire += f'{emote} **{joueur}** : {mot} : {stats["count"]} consécutives  \n'

        

    async def detection_gap(self):

        # Calcul des écarts de points entre les joueurs et leurs adversaires

        self.txt_gap = ''
        
        if hasattr(self, 'df_data_match'):
            roles = ['TOP', 'JGL', 'MID', 'ADC', 'SUPP']
            self.ecarts_gap = {}
            self.emote_gap = {}
            self.max_ecart_role = None
            self.max_ecart_valeur = 0

            if not self.df_data_match.empty:
                for i in range(5):
                    joueur = self.thisRiotIdListe[i].lower()
                    adversaire = self.thisRiotIdListe[i + 5].lower()

                    points_joueur = self.dict_serie[joueur]['points']
                    points_adversaire = self.dict_serie[adversaire]['points']

                    ecart = points_joueur - points_adversaire
                    ecart = 0 if points_joueur == 0 or points_adversaire == 0 else ecart
                    role = roles[i]
                    self.emote_gap[role] = ':green_circle:' if ecart > 0 else ':red_circle:'
                    self.ecarts_gap[role] = abs(ecart)

                    # # Vérifie si cet écart est le plus important en valeur absolue
                    # if abs(ecart) > abs(self.max_ecart_valeur):
                    #     self.max_ecart_valeur = abs(ecart)
                    #     self.max_ecart_role = role

            
            for key, value in self.ecarts_gap.items():
                if value > 20:
                    emote = self.emote_gap[key]
                    self.txt_gap += f'{emote}**{key}** GAP | '
            

        # if self.max_ecart_role is not None:
        #     if self.max_ecart_valeur > 20:
        #         self.txt_gap += f'**{self.max_ecart_role}** GAP \n'



    async def traitement_objectif(self):
        # 1. Récupérer les objectifs "en attente" (match_id IS NULL) pour ce joueur
        objectifs_en_attente = lire_bdd_perso(f'''
            SELECT * FROM objectifs_lol_suivi
            WHERE id_compte = {self.id_compte}
            AND match_id IS NULL
        ''', index_col=None).transpose()

        for _, obj in objectifs_en_attente.iterrows():
            objectif_id = obj['objectif_id']
            valeur_attendue = obj['valeur_attendue']

            # 2. Check s'il existe déjà pour cette partie
            check = lire_bdd_perso(f'''
                SELECT 1 FROM objectifs_lol_suivi
                WHERE id_compte = {self.id_compte}
                AND match_id = '{self.last_match}'
                AND objectif_id = {objectif_id}
                LIMIT 1
            ''', index_col=None)
            if not check.empty:
                continue  # On passe, déjà inséré

            # 2. Sélectionne la stat réelle selon le type d’objectif
            if objectif_id == 1:  # CS/min
                valeur_obtenue = self.thisMinionPerMin
                atteint = valeur_obtenue >= valeur_attendue
            elif objectif_id == 2:  # KP%
                valeur_obtenue = self.thisKP
                atteint = valeur_obtenue >= valeur_attendue
            elif objectif_id == 3:  # KDA
                if self.thisDeaths != 0:
                    valeur_obtenue = self.thisKDA
                else:
                    valeur_obtenue = self.thisKills + self.thisAssists
                atteint = valeur_obtenue >= valeur_attendue
            elif objectif_id == 4:  # Deaths max
                valeur_obtenue = self.thisDeaths
                atteint = valeur_obtenue <= valeur_attendue  # <= car c’est un max

            else:
                valeur_obtenue = 0
                atteint = False

            # 3. Insère le résultat dans la BDD (pour cette partie)
            requete_perso_bdd("""
                INSERT INTO objectifs_lol_suivi
                (id_compte, match_id, objectif_id, valeur_attendue, valeur_obtenue, atteint, date_partie)
                VALUES
                (:id_compte, :match_id, :objectif_id, :valeur_attendue, :valeur_obtenue, :atteint, NOW())
            """, {
                'id_compte': self.id_compte,
                'match_id': self.last_match,
                'objectif_id': objectif_id,
                'valeur_attendue': valeur_attendue,
                'valeur_obtenue': valeur_obtenue,
                'atteint': atteint,
            })

    async def show_objectifs(self):
        objectifs = lire_bdd_perso(f'''
            SELECT suiv.*, types.nom, types.description
            FROM objectifs_lol_suivi suiv
            JOIN objectifs_lol_types types ON suiv.objectif_id = types.id
            WHERE suiv.id_compte = {self.id_compte}
            AND suiv.match_id = '{self.last_match}'
        ''', index_col=None).transpose()

        if not objectifs.empty:
            txt = ''
            description = "🎯 Objectifs personnels :\n"
            for _, data in objectifs.iterrows():
                etat = "✅" if data['atteint'] else "❌"
                txt += f"- {etat} {data['description']} ({data['valeur_attendue']}): {round(data['valeur_obtenue'],2)}\n"
            
            return description, txt
        else:
            return None, None
    


    async def resume_general(self,
                             name_img,
                             embed,
                             difLP):

        '''Resume global de la game

        Parameters
        -----------
        name_img : nom de l'image enregistré'''


        mode_couleur = {'light' : {'principal' : (255, 255, 255), # blanc
                                   'secondaire' : (230, 230, 230), # gris
                                   'texte' : (0, 0, 0)}} # noir
        
        
        mode = 'light'

        principal = mode_couleur[mode]['principal']
        secondaire = mode_couleur[mode]['secondaire']
        fill = mode_couleur[mode]['texte']
 

        # Gestion de l'image 2
        lineX = 3050
        lineY = 100


        
        x_ecart = 125
        x_kills = 1000 + 280
        x_score = x_kills - 160
        x_deaths = x_kills + 100
        x_assists = x_deaths + 100
        x_level = x_score - 125

        x_kda = x_assists + 110

        x_kp = x_kda + 150

        x_cs = x_kp + 150

        x_vision = x_cs + 150

        x_dmg_percent = x_vision + 110

        x_dmg_taken = x_dmg_percent + 260

        x_kill_total = 850
        x_objectif = 1800


        x_name = 260
        y = 120
        y_name = y - 60
        x_rank = 2250

        x_metric = 120
        y_metric = 400

        font = charger_font(50)
        font_little = charger_font(40)        


        im = Image.new("RGBA", (lineX, lineY * 13 + 190),
                       principal)  # Ligne blanche
        d = ImageDraw.Draw(im)

        line = Image.new("RGB", (lineX, 190), secondaire)  # Ligne grise
        im.paste(line, (0, 0))

        if len(self.riot_id) <= 12: # Sinon trop long et écrase le kda
            d.text((x_name-240, y_name+60), self.riot_id, font=font, fill=fill)


            im.paste(im=await get_image("avatar", self.avatar, self.session, 100, 100, self.version['n']['profileicon']),
                    box=(x_name-240, y_name-50))

            im.paste(im=await get_image("champion", self.thisChampName, self.session, 100, 100, self.version['n']['profileicon']),
                    box=(x_name-120, y_name-50))
        else:
            im.paste(im=await get_image("avatar", self.avatar, self.session, 100, 100, self.version['n']['profileicon']),
                    box=(x_name-240, y_name-20))

            im.paste(im=await get_image("champion", self.thisChampName, self.session, 100, 100, self.version['n']['profileicon']),
                    box=(x_name-120, y_name-20))

        d.text((x_name+1000, y_name-20),
               f"Niveau {self.level_summoner}", font=font_little, fill=fill)


        try:
            if not self.thisQ in ['ARAM', 'CLASH ARAM']:
                data_last_season = get_data_bdd(f'''SELECT index, tier, rank from suivi_s{self.last_season} where index = {self.id_compte} ''')
                data_last_season = data_last_season.mappings().all()[0]
                self.tier_last_season = data_last_season['tier']
                self.rank_last_season = data_last_season['rank']
            else:
                data_last_season = get_data_bdd(f'''SELECT index, rank from ranked_aram_s{self.season-1} where index = {self.id_compte} ''')
                self.tier_last_season = data_last_season.mappings().all()[0]['rank']

            img_tier_last_season = await get_image("tier", self.tier_last_season, self.session, 100, 100)

            im.paste(img_tier_last_season,(x_name+1250, y_name-50), img_tier_last_season.convert('RGBA'))
            if not self.thisQ in ['ARAM', 'CLASH ARAM']:
                d.text((x_name+1350, y_name-30), f'{self.rank_last_season}', font=font, fill=fill)   

        except Exception:
            pass  

        if not self.thisQ in ["ARAM", 'CLASH ARAM']:  # si ce n'est pas le mode aram, on prend la soloq normal
            if self.thisTier != ' ':  # on vérifie que le joueur a des stats en soloq, sinon il n'y a rien à afficher

                requete_perso_bdd('''UPDATE matchs SET ecart_lp = :ecart_lp WHERE match_id = :match_id AND joueur = :id_compte''', {'ecart_lp': difLP,
                                                                                                                        'match_id': self.last_match,
                                                                                                                        'id_compte': self.id_compte})
                img_rank = await get_image('tier', self.thisTier, self.session, 220, 220)

                im.paste(img_rank, (x_rank, y-140), img_rank.convert('RGBA'))

                d.text((x_rank+220, y-110),
                       f'{self.thisTier} {self.thisRank}', font=font, fill=fill)
                d.text((x_rank+220, y-45),
                       f'{self.thisLP} LP ({difLP})', font=font_little, fill=fill)


                d.text(
                        (x_rank+220, y+10), f'{self.thisVictory}W {self.thisLoose}L     {self.thisWinrateStat}% ', font=font_little, fill=fill)
            else:  # si pas de stats en soloq
                d.text((x_rank+220, y-45), 'En placement', font=font, fill=fill)

        else:  # si c'est l'aram, le traitement est différent

            data_aram = get_data_bdd(f''' SELECT ranked_aram_s{self.season}.index,wins, losses, lp, games, k, d, a, ranked_aram_s{self.season}.activation, rank, serie
                                     from ranked_aram_s{self.season}
                                     INNER JOIN tracker on tracker.id_compte = ranked_aram_s{self.season}.index
                                     WHERE tracker.id_compte = :id_compte ''',
                                     {'id_compte': self.id_compte}).mappings().all()

            wins_actual = data_aram[0]['wins']
            losses_actual = data_aram[0]['losses']
            lp_actual = data_aram[0]['lp']
            games_actual = data_aram[0]['games']
            k_actual = data_aram[0]['k']
            d_actual = data_aram[0]['d']
            a_actual = data_aram[0]['a']
            activation = data_aram[0]['activation']
            rank_actual = data_aram[0]['rank']
            serie_wins = data_aram[0]['serie']

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
                        points = 50 if str(self.thisWinId) == 'True' else 0
                    elif wr >= 60:
                        points = 30 if str(self.thisWinId) == 'True' else -10
                    elif wr <= 40:
                        points = 10 if str(self.thisWinId) == "True" else -20
                    else:
                        if str(self.thisWinId) == "True":
                            points = dict_points[int(wr)][0]
                        else:
                            points = dict_points[int(wr)][1]

                lp = lp_actual + points
                
                # TODO : serie de wins
                
                if self.thisWinBool:
                    serie_wins = serie_wins + 1
                else:
                    serie_wins = 0
                
                if serie_wins > 1:    
                    bonus_lp_serie = serie_wins * 2
                else:
                    bonus_lp_serie = 0 
                    
                lp = lp + bonus_lp_serie  

                # rank

                ranks = [
                    ('IRON', 100),
                    ('BRONZE', 200),
                    ('SILVER', 300),
                    ('GOLD', 500),
                    ('PLATINUM', 800),
                    ('EMERALD', 1100),
                    ('DIAMOND', 1400),
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
                        name="Changement d'elo", value=f" :star: {emote_rank_discord[rank]} Tu es passé de **{rank_actual}** à **{rank}**")

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
                requete_perso_bdd(f'''UPDATE ranked_aram_s{self.season}
                                    SET wins = :wins,
                                    losses = :losses,
                                    lp = :lp,
                                    games = :games,
                                    k = :k,
                                    d = :d,
                                    a = :a,
                                    rank = :rank,
                                    serie = :serie
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
                                   'index': self.id_compte,
                                   'match_id': self.last_match,
                                   'serie' : serie_wins})  

                requete_perso_bdd('''UPDATE matchs SET ecart_lp = :ecart_lp WHERE match_id = :match_id AND joueur = :joueur''', {'ecart_lp': difLP,
                                                                                                                        'match_id': self.last_match,
                                                                                                                        'joueur': self.id_compte})     

        line = Image.new("RGB", (lineX, lineY), secondaire)  # Ligne grise

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

        for i in range(13):
            if i % 2 == 0:
                draw_gray_line(i)
            elif i == 1:
                draw_blue_line(i)
            elif i == 7:
                draw_red_line(i)

            if not self.thisQ  in ["ARAM", "CLASH ARAM"] and i == dict_position[self.thisPosition]:
                draw_light_blue_line(i)

        draw_black_line()

        # Ban 

        x_ecart_ban = 90

        for i, champ_ban in enumerate(self.liste_ban):
        
            if champ_ban != '-1' and champ_ban != 'Aucun':
                if i <= 4:
                    x_ban = 300 + (i * x_ecart_ban)
                    y_ban = lineY + 200

                    im.paste(im=await get_image("champion", champ_ban, self.session, 80, 80, self.version['n']['profileicon']),
                                box=(x_ban, y_ban))
                
                else:

                    x_ban = 300 + ((i-5) * x_ecart_ban)
                    y_ban = 7* lineY + 200     

                    im.paste(im=await get_image("champion", champ_ban, self.session, 80, 80, self.version['n']['profileicon']),
                                box=(x_ban, y_ban))          

        # match
        d.text((10, 20 + 190), self.thisQ, font=font, fill=fill)

        money = await get_image('gold', 'dragon', self.session, 60, 60)

        im.paste(money, (10, 120 + 190), money.convert('RGBA'))
        d.text((83, 120 + 190), f'{round(self.thisGold_team1/1000,1)}k',
               font=font, fill=principal)
        im.paste(money, (10, 720 + 190), money.convert('RGBA'))
        d.text((83, 720 + 190), f'{round(self.thisGold_team2/1000,1)}k', font=font, fill=fill)

        if self.moba_ok:
            try:
                self.img_ally_avg = await get_image('tier', self.avgtier_ally.upper(), self.session, 100, 100)

                im.paste(self.img_ally_avg, (x_score-365, 120-20 + 190), self.img_ally_avg.convert('RGBA'))

                d.text((x_name+300, 120 + 190), str(
                            self.avgrank_ally), font=font, fill=principal)

            except FileNotFoundError:
                self.img_ally_avg = 'UNRANKED'
            try:
                self.img_enemy_avg = await get_image('tier', self.avgtier_enemy.upper(), self.session, 100, 100)

                im.paste(self.img_enemy_avg, (x_score-365, 720-20 + 190), self.img_enemy_avg.convert('RGBA'))

            except FileNotFoundError:
                self.img_enemy_avg = 'UNRANKED'

            d.text((x_name+300, 720 + 190), str(
                        self.avgrank_enemy), font=font, fill=fill)

        for y in range(123 + 190, 724 + 190, 600):
            color = principal if y == 123 + 190 else fill
            d.text((x_level-10, y), 'LVL', font=font, fill=color)
            # d.text((x_name, y), 'Name', font=font, fill=color)


            d.text((x_kills, y), 'K', font=font, fill=color)
            d.text((x_deaths, y), 'D', font=font, fill=color)
            d.text((x_assists, y), 'A', font=font, fill=color)
            d.text((x_kda, y), 'KDA', font=font, fill=color)
            d.text((x_kp+10, y), 'KP', font=font, fill=color)
            d.text((x_cs, y), 'CS', font=font, fill=color)
            d.text((x_dmg_percent+30, y), "DMG", font=font, fill=color)
            d.text((x_dmg_taken+10, y), 'TANK', font=font, fill=color)
            d.text((x_score-20, y), 'MVP', font=font, fill=color)

            if not self.thisQ in ["ARAM", "CLASH ARAM"]:
                d.text((x_vision, y), 'VS', font=font, fill=color)

        # participants
        initial_y = 223 + 190
        


        array_scoring = np.array([]) # qu'on va mettre du plus grand au plus petit
        liste = []  # en ordre en fonction des joueurs
        for i in range(0,10):
            liste.append(self.calcul_scoring(i))
            scoring_joueur = liste[i]
            array_scoring = np.append(array_scoring, scoring_joueur)

        array_scoring_trie = array_scoring.copy()
        array_scoring_trie.sort()
            



            
        for i in range(self.nb_joueur):
            im.paste(
                im=await get_image("champion", self.thisChampNameListe[i], self.session, profil_version=self.version['n']['champion']),
                box=(10, initial_y-13),
            )

            if self.mastery_level[i] >= 100:
                x_mastery = 15
                font_mastery = font_little
            elif self.mastery_level[i] >= 10:
                x_mastery = 20
                font_mastery = font
            else:
                x_mastery = 35
                font_mastery = font

            d.text((x_mastery, initial_y),
                   str(self.mastery_level[i]), font=font_mastery, fill=principal)
            
            # couleur
            if i <= 4:
                ecart_level = self.thisLevelListe[i] - self.thisLevelListe[i+5]

                if ecart_level > 0:
                    fill_level = (0, 128, 0)
                elif ecart_level < 0:
                    fill_level = (255, 0, 0)
                else:
                    fill_level = fill
            else:
                fill_level = fill

            d.text((x_level, initial_y),
                   str(self.thisLevelListe[i]), font=font, fill=fill_level)


            if self.thisRiotIdListe[i] == '' or self.thisRiotIdListe[i] == ' ':
                d.text((x_name, initial_y),
                    self.thisPseudoListe[i], font=font, fill=fill)
            else:
                d.text((x_name, initial_y),
                    self.thisRiotIdListe[i], font=font, fill=fill)

            # rank

            if self.moba_ok:
                try:
                    rank_joueur = self.liste_tier[i]
                    tier_joueur = self.liste_rank[i]

                    if rank_joueur in ['MASTER', 'GRANDMASTER', 'CHALLENGER']:
                        tier_joueur = self.liste_lp[i]

                except:
                    rank_joueur = ''
                    tier_joueur = ''
            else:
                try:
                    
                    data_rank = await getRanks(self.session, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i].lower(), season=self.season_ugg)
                    df_rank = pd.DataFrame(data_rank['data']['fetchProfileRanks']['rankScores'])
                    rank_joueur = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['tier'].values[0]
                    tier_joueur = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['rank'].values[0]


                    if rank_joueur.upper() in ['MASTER', 'GRANDMASTER', 'CHALLENGER']:
                        tier_joueur = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['lp'].values[0]

                except:
                    rank_joueur = ''
                    tier_joueur = ''

            if rank_joueur != '' and rank_joueur != 'UNRANKED':
                img_rank_joueur = await get_image('tier', rank_joueur.upper(), self.session, 100, 100)

                im.paste(img_rank_joueur, (x_score-365, initial_y-20), img_rank_joueur.convert('RGBA'))

                d.text((x_score-265, initial_y), str(
                        tier_joueur), font=font, fill=fill)


            scoring = np.where(array_scoring_trie == liste[i])[0][0] + 1
            if self.thisRiotIdListe[i].lower().replace(' ', '') == self.riot_id:
                requete_perso_bdd('''UPDATE matchs
                                      SET mvp = :mvp 
                                      WHERE match_id = :match_id
                                      AND joueur = :joueur''',
                                      {'mvp' : int(scoring),
                                       'match_id' : self.last_match,
                                       'joueur' : self.id_compte})
                
            color_scoring = {1 : (0,128,0), 2 : (89,148,207), 3 : (191,64,191), 8 : (220,20,60), 9 : (220,20,60), 10 : (220,20,60)}


            d.text((x_score+20, initial_y),
                    str(scoring),
                    font=font,
                    fill=color_scoring.get(scoring, fill))

            if len(str(self.thisKillsListe[i])) == 1:
                d.text((x_kills, initial_y), str(
                    self.thisKillsListe[i]), font=font, fill=fill)
            else:
                d.text((x_kills - 20, initial_y),
                       str(self.thisKillsListe[i]), font=font, fill=fill)

            if len(str(self.thisDeathsListe[i])) == 1:
                d.text((x_deaths, initial_y), str(
                    self.thisDeathsListe[i]), font=font, fill=fill)
            else:
                d.text((x_deaths - 20, initial_y),
                       str(self.thisDeathsListe[i]), font=font, fill=fill)

            if len(str(self.thisAssistsListe[i])) == 1:
                d.text((x_assists, initial_y), str(
                    self.thisAssistsListe[i]), font=font, fill=fill)
            else:
                d.text((x_assists - 20, initial_y),
                       str(self.thisAssistsListe[i]), font=font, fill=fill)

            fill_color = range_value(i, self.thisKDAListe, True)

            # Recentrer le résultat quand chiffre rond
            if len(str(round(self.thisKDAListe[i], 2))) == 1:
                d.text((x_kda + 35, initial_y),
                       str(round(self.thisKDAListe[i], 2)), font=font, fill=fill_color)
            else:
                d.text((x_kda, initial_y), str(
                    round(self.thisKDAListe[i], 2)), font=font, fill=fill_color)

            fill_color = range_value(i, self.thisKPListe, True)

            d.text((x_kp, initial_y), str(
                self.thisKPListe[i]) + "%", font=font, fill=fill_color)

            fill_color = range_value(i, np.array(self.thisMinionListe) +
                               np.array(self.thisJungleMonsterKilledListe))

            if len(str(self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i])) != 2:
                d.text((x_cs, initial_y), str(
                    self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]), font=font, fill=fill_color)
            else:
                d.text((x_cs + 10, initial_y), str(
                    self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]), font=font, fill=fill_color)

            if not self.thisQ in ["ARAM", "CLASH ARAM"]:

                fill_color = range_value(i, self.thisVisionListe)

                d.text((x_vision, initial_y), str(
                    self.thisVisionListe[i]), font=font, fill=fill_color)

            fill_color = range_value(i, self.thisDamageListe)

            d.text((x_dmg_percent, initial_y),
                   f'{int(self.thisDamageListe[i]/1000)}k ({int(self.thisDamageRatioListe[i]*100)}%)', font=font, fill=fill_color)

            fill_color = range_value(i, np.array(
                self.thisDamageTakenListe) + np.array(self.thisDamageSelfMitigatedListe))

            d.text((x_dmg_taken + 25, initial_y),
                   f'{int(self.thisDamageTakenListe[i]/1000) + int(self.thisDamageSelfMitigatedListe[i]/1000)}k', font=font, fill=fill_color)
            

            n = 0
            for image in self.allitems[i]:
                if image != 0:
                    im.paste(await get_image("items", image, self.session, resize_x=65, resize_y=65, profil_version=self.version['n']['item']),
                            box=(x_dmg_taken + 150 + n, initial_y))
                    n += 80

            initial_y += 200 if i == 4 else 100
        if not self.thisQ in ["ARAM", "CLASH ARAM"]:
            y_ecart = 220 + 190
            for ecart in [self.ecart_top_gold_affiche, self.ecart_jgl_gold_affiche, self.ecart_mid_gold_affiche, self.ecart_adc_gold_affiche, self.ecart_supp_gold_affiche]:
                if ecart > 0:
                    d.text((x_ecart, y_ecart), str(round(ecart/1000, 1)
                                                   ) + "k", font=font, fill=(0, 128, 0))
                else:
                    d.text((x_ecart-10, y_ecart), str(round(ecart/1000, 1)
                                                      ) + "k", font=font, fill=(255, 0, 0))

                y_ecart = y_ecart + 100



        if not self.thisQ in ["ARAM", "CLASH ARAM"]:


            tower = await get_image('monsters', 'tower', self.session, resize_y=100)
            inhibiteur = await get_image('monsters', 'inhibitor', self.session)
            drk = await get_image('monsters', 'dragon', self.session)
            elder = await get_image('monsters', 'elder', self.session)
            herald = await get_image('monsters', 'herald', self.session)
            nashor = await get_image('monsters', 'nashor', self.session)
            horde = await get_image('monsters', 'horde', self.session)
            atakhan = await get_image('monsters', 'atakhan', self.session)

            im.paste(tower, (x_objectif - 400, 190), tower.convert('RGBA'))
            d.text((x_objectif - 400 + 100, 25 + 190), str(self.thisTowerTeam),
                   font=font, fill=fill)
            
            im.paste(inhibiteur, (x_objectif - 200, 10 + 190), inhibiteur.convert('RGBA'))
            d.text((x_objectif - 200 + 100, 25 + 190), str(self.thisInhibTeam),
                   font=font, fill=fill)

            im.paste(drk, (x_objectif, 10 + 190), drk.convert('RGBA'))
            d.text((x_objectif + 100, 25 + 190), str(self.thisDragonTeam),
                   font=font, fill=fill)

            im.paste(elder, (x_objectif + 200, 10 + 190), elder.convert('RGBA'))
            d.text((x_objectif + 200 + 100, 25 + 190),
                   str(self.thisElderPerso), font=font, fill=fill)

            im.paste(herald, (x_objectif + 400, 10 + 190), herald.convert('RGBA'))
            d.text((x_objectif + 400 + 100, 25 + 190),
                   str(self.thisHeraldTeam), font=font, fill=fill)

            im.paste(nashor, (x_objectif + 600, 10 + 190), nashor.convert('RGBA'))
            d.text((x_objectif + 600 + 100, 25 + 190),
                   str(self.thisBaronTeam), font=font, fill=fill)
            
            im.paste(horde, (x_objectif + 800, 10 + 190), horde.convert('RGBA'))
            d.text((x_objectif + 800 + 100, 25 + 190),
                   str(self.thisHordeTeam), font=font, fill=fill)
            
            im.paste(atakhan, (x_objectif + 1000, 10 + 190), atakhan.convert('RGBA'))
            d.text((x_objectif + 1000 + 100, 25 + 190),
                   str(self.thisAtakhanTeam), font=font, fill=fill)

        img_timer = await get_image('timer', 'timer', self.session)
        img_blue_epee = await get_image('epee', 'blue', self.session)
        img_red_epee = await get_image('epee', 'red', self.session)

        im.paste(img_timer, (x_kill_total-500, 10 + 190),
                 img_timer.convert('RGBA'))
        d.text((x_kill_total -500 + 100, 23 + 190), f'{(int(self.thisTime))}m',
               font=font, fill=fill)

        im.paste(img_blue_epee, (x_kill_total - 100, 10 + 190),
                 img_blue_epee.convert('RGBA'))
        d.text((x_kill_total - 100 + 100, 23 + 190), str(self.thisTeamKills),
               font=font, fill=fill)

        im.paste(img_red_epee, (x_kill_total + 200, 10 + 190),
                 img_red_epee.convert('RGBA'))
        d.text((x_kill_total + 200 + 100, 23 + 190),
               str(self.thisTeamKillsOp), font=font, fill=fill)

        # Stat du jour
        if self.thisQ in ['ARAM', 'CLASH ARAM']:
            suivi_24h = lire_bdd(f'ranked_aram_S{self.season}', 'dict')
        else:
            suivi_24h = lire_bdd(f'suivi_S{self.season}', 'dict')

        if self.thisQ not in ['ARAM', 'CLASH ARAM', 'FLEX']:

            difwin = int(self.thisVictory) - \
                        int(suivi_24h[self.id_compte]["wins_jour"])
            diflos = int(self.thisLoose) - \
                        int(suivi_24h[self.id_compte]["losses_jour"])

            if (difwin + diflos) > 0:  # si pas de ranked aujourd'hui, inutile
                d.text((x_metric + 850, y_name+50),
                           f'Victoires 24h : {difwin}', font=font_little, fill=fill)
                d.text((x_metric + 1460, y_name+50),
                           f'Defaites 24h : {diflos}', font=font_little, fill=fill)


        elif self.thisQ in ['ARAM', 'CLASH ARAM'] and activation:

            difwin = wins - \
                        int(suivi_24h[self.id_compte]["wins_jour"])
            diflos = losses - \
                        int(suivi_24h[self.id_compte]["losses_jour"])

            if (difwin + diflos) > 0:  # si pas de ranked aujourd'hui, inutile
                if serie_wins > 0:
                    d.text((x_metric + 850, y_name+50),
                       
                           f'Victoires 24h : {difwin} (S : {serie_wins})', font=font_little, fill=fill)
                else:
                    d.text((x_metric + 850, y_name+50),
                       
                           f'Victoires 24h : {difwin}', font=font_little, fill=fill)                    
                d.text((x_metric + 1460, y_name+50),
                           f'Defaites 24h : {diflos}', font=font_little, fill=fill)
                

        time = 10 if self.thisQ == 'ARAM' else 15
        
        stats_joueur_split = lire_bdd_perso(f'''SELECT tracker.id_compte, avg(kills) as kills, avg(deaths) as deaths, avg(assists) as assists, 
                    (count(victoire) filter (where victoire = True)) as victoire,
                    avg(kp) as kp,
                    count(victoire) as nb_games,
                    (avg(mvp) filter (where mvp != 0)) as mvp
                    from matchs
                    INNER JOIN tracker on matchs.joueur = tracker.id_compte
                    WHERE tracker.id_compte = {self.id_compte}
                    and champion = '{self.thisChampName}'
                    and season = {self.season}
                    and mode = '{self.thisQ}'
                    and time > {time}
                    and split = {self.split}
                    GROUP BY tracker.id_compte''', index_col='id_compte').transpose()

        if not stats_joueur_split.empty:
            k = round(
                    stats_joueur_split.loc[self.id_compte, 'kills'], 1)
            deaths = round(
                    stats_joueur_split.loc[self.id_compte, 'deaths'], 1)
            a = round(
                    stats_joueur_split.loc[self.id_compte, 'assists'], 1)
            kp = int(stats_joueur_split.loc[self.id_compte, 'kp'])

            if deaths == 0:
                kda = round((k+a),2)
            else:
                kda = round((k+a)/deaths,2)

            if kda >= 10: # sinon cela donne 4 chiffres, et dépasse le cadre du texte
                kda = round(kda, 1)            
                
            try:
                mvp = round(stats_joueur_split.loc[self.id_compte, 'mvp'], 1)
            except TypeError:
                mvp = 0

            ratio_victoire = int((stats_joueur_split.loc[self.id_compte, 'victoire'] / stats_joueur_split.loc[self.id_compte, 'nb_games'])*100)
            nb_games = int(stats_joueur_split.loc[self.id_compte, 'nb_games'])
                


            if mvp == 0:
                d.text((x_metric + 300, y_name-50),
                           f' {nb_games} P', font=font_little, fill=fill)
            else:

                d.text((x_metric + 300, y_name-50),
                           f' {nb_games} Parties | {mvp} MVP', font=font_little, fill=fill)
                
            if ratio_victoire >= 60:
                color_victoire = (255, 119, 0)
            elif ratio_victoire >= 50:
                color_victoire = (85, 85, 255)
            elif ratio_victoire <= 30 and nb_games >= 10:
                color_victoire = (220, 20, 60)
            else:
                color_victoire = fill
                
            d.text((x_metric + 300, y_name+10),
                           f' {ratio_victoire}% V', font=font_little, fill=color_victoire)    
            

            if kda >= 5:
                color_kda = (255, 119, 0) # (255, 140, 0)
            elif kda >= 4:
                color_kda = (85, 85, 255)
            elif kda >= 3:
                color_kda = (0, 128, 0)
            elif kda < 1:
                color_kda = (220, 20, 60)
            else:
                color_kda = fill
            


            
            d.text((x_metric + 300, y_name+70),
                           f' {kda}', font=font_little, fill=color_kda)     

            d.text((x_metric + 410, y_name+70),
                           f'({k} / {deaths} / {a})', font=font_little, fill=fill)     

                


        im.save(f'{name_img}.png')

        # si sauvegarde 

        # buffer = BytesIO() 
        # b.save(buffer, format='PNG')
        # image_bytes = buffer.getvalue()

        # requete_perso_bdd('''INSERT INTO match_images (match_id, image) VALUES (:match_id, :image)
        #                 ON CONFLICT (match_id) DO NOTHING''',
        #                 dict_params={'match_id': self.last_match, 'image': image_bytes})        

        await self.session.close()

        return embed


