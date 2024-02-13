import os
import pandas as pd
import warnings
from fonctions.gestion_bdd import lire_bdd, get_data_bdd, requete_perso_bdd, lire_bdd_perso, sauvegarde_bdd
from fonctions.params import saison
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

# TODO : rajouter temps en vie

warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'

def fix_temps(duree):
    '''Convertit le temps en secondes en minutes et secondes'''
    minutes = int(duree)
    secondes = int((duree - minutes) * 60)/100
    
    return minutes + secondes

def label_tier(x):
    dict_chg_tier = lire_bdd_perso('SELECT * from data_rank', index_col='nom')\
                                                                                    .T\
                                                                                        .to_dict()['tier']
                                                                                        
    for key, value in dict_chg_tier.items():
        try:
            dict_chg_tier[key] = int(value)    
        except:
            continue   
    return dict_chg_tier.get(x,0)

def label_rank(x):
    dict_chg_rank = {'IV': 1,
                    'III': 2,
                    'II': 3,
                    'I': 4}
    return dict_chg_rank[x]


def get_id_account_bdd(riot_id, riot_tag):
    id_acc = lire_bdd_perso(f'''SELECT * from tracker where riot_id = '{riot_id.replace(' ', '')}' and riot_tagline = '{riot_tag}' ''').loc['id_compte'].values[0]
    return id_acc


label_ward = {'YELLOW TRINKET': 1,
                'UNDEFINED': 2,
                'CONTROL_WARD': 3,
                'SIGHT_WARD': 4,
                'BLUE_TRINKET': 5}


dict_rankid = lire_bdd_perso('SELECT * from data_rank_soloq', index_col='rank')\
                                                                                    .T\
                                                                                        .to_dict()['id']

elo_lp = {'IRON': 0,
          'BRONZE': 1,
          'SILVER': 2,
          'GOLD': 3,
          'PLATINUM': 4,
           'EMERALD' : 5,
          'DIAMOND': 6,
          'MASTER': 7,
          'GRANDMASTER': 8,
          'CHALLENGER': 9,
          'FIRST_GAME': 0}


emote_rank_discord = lire_bdd_perso('SELECT * from data_rank', index_col='nom')\
                                                                                    .T\
                                                                                        .to_dict()\
                                                                                            ['icon_identifiant']


emote_champ_discord = lire_bdd_perso('SELECT * from data_champion', index_col='nom')\
                                                                                    .T\
                                                                                        .to_dict()\
                                                                                            ['icon_identifiant']

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


dict_id_q = lire_bdd_perso('SELECT * from data_queue', index_col='identifiant')\
                                                                                    .T\
                                                                                        .to_dict()['mode']


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
            return ['inconnu'], ['inconnu'], 0, ['#']
        
        elif max_min_rows.empty and rank:
            return ['inconnu'], ['inconnu'], 0, ['#'], 0

        joueur = []
        champion = []
        url_game = []

        # on regarde chaque ligne où il y a le record
        for lig, data in max_min_rows.iterrows():


            if data['riot_id'] not in joueur and mention(data['discord'], 'membre') not in joueur: # on affiche qu'une game du joueur. Pas besoin de toutes...

                if identifiant == 'riot_id':
                    joueur.append(data['riot_id'])
                elif identifiant == 'discord':
                    joueur.append(mention(data['discord'], 'membre'))

                champion.append(data['champion'])

                url_game.append(f'https://www.leagueofgraphs.com/fr/match/euw/{str(data["match_id"])[5:]}#participant{int(data["id_participant"])+1}')
                
                

    except Exception:
        # exc_type, exc_value, exc_traceback = sys.exc_info()
        # traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
        # traceback_msg = ''.join(traceback_details)
        # print(traceback_msg)
        if rank:
            return ['inconnu'], ['inconnu'], 0, ['#'], 0
        else:
            return ['inconnu'], ['inconnu'], 0, ['#']

    if rank:
        return joueur, champion, record, url_game, rank_value
    else:
        return joueur, champion, record, url_game


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


async def get_image(type, name, session: aiohttp.ClientSession, resize_x=80, resize_y=80, profil_version='13.6.1'):
    url_mapping = {
        "champion": f"https://ddragon.leagueoflegends.com/cdn/{profil_version}/img/champion/{name}.png",
        "tier": f"./img/{name}.png",
        "avatar": f"https://ddragon.leagueoflegends.com/cdn/{profil_version}/img/profileicon/{name}.png",
        "items": f'https://ddragon.leagueoflegends.com/cdn/{profil_version}/img/item/{name}.png',
        "monsters": f'./img/monsters/{name}.png',
        "epee": f'./img/epee/{name}.png',
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


async def getRanks(session : aiohttp.ClientSession, summonerName, tagline, regionId='euw1', season=22):
    url = "https://u.gg/api"
    """Avopir le rank et le tier d'un joueur"""
    payload = {
                "operationName": "fetchProfileRanks",
                "variables": {
                    "regionId": regionId,
                    "riotUserName": summonerName,
                    "riotTagLine" : tagline,
                    "seasonId": season,
                },
                "query": """query fetchProfileRanks($regionId: String!, $riotUserName: String!, $riotTagLine : String!, $seasonId: Int!) { fetchProfileRanks(regionId: $regionId, riotUserName: $riotUserName, riotTagLine: $riotTagLine, seasonId: $seasonId) { rankScores {lastUpdatedAt
                        losses
                        lp
                        promoProgress
                        queueType
                        rank
                        role
                        tier
                        seasonId
                        wins
                        }
                    }
                    }"""
                #  "query": "query getPlayerStats($queueType: [Int!], $regionId: String!, $role: [Int!], $seasonId: Int!, $riotUserName: String!, $riotTagLine : String!) {\n  fetchPlayerStatistics(\n    queueType: $queueType\n    riotUserName: $riotUserName\n    riotTagLine: $riotTagLine\n      regionId: $regionId\n    role: $role\n    tier: $tier\n    rank : $rank\n     seasonId: $seasonId\n  ) {\n    basicChampionPerformances {\n  assists\n      championId\n      cs\n      damage\n      damageTaken\n      deaths\n      gold\n      kills\n      totalMatches\n      wins\n      lpAvg\n    }\n    exodiaUuid\n    puuid\n    queueType\n    regionId\n    role\n    seasonId\n    __typename\n  }\n}"
            }
        
    headers = {
            "Accept-Encoding":"gzip, deflate, br",
            "Accept":"*/*",
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "User-Agent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
          }

        # response = requests.post(url, headers=headers, json=payload)

    async with session.post(url, headers=headers, json=payload) as session_match_detail:
        response = await session_match_detail.json()  # detail du match sélectionné
        
    return response

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
    return me


async def get_league_by_summoner(session: aiohttp.ClientSession, me):
    if isinstance(me, str):
        async with session.get(f"https://{my_region}.api.riotgames.com/lol/league/v4/entries/by-summoner/{me}",
                                params={'api_key': api_key_lol}) as session_league:
                stats = await session_league.json()
    else:
        async with session.get(f"https://{my_region}.api.riotgames.com/lol/league/v4/entries/by-summoner/{me['id']}",
                            params={'api_key': api_key_lol}) as session_league:
            stats = await session_league.json()
    return stats


async def get_list_matchs_with_me(session: aiohttp.ClientSession, me, params):
    async with session.get(f'https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{me["puuid"]}/ids?', params=params) as session_match:
        my_matches = await session_match.json()
    return my_matches


async def get_list_matchs_with_puuid(session: aiohttp.ClientSession, puuid, params):
    async with session.get(f'https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?', params=params) as session_match:
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
        return await challenge_config.json()
    
async def get_spectator(session, id):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/spectator/v4/active-games/by-summoner/{id}?api_key={api_key_lol}') as session_spectator:
        if session_spectator.status == 404:
            return None
        return await session_spectator.json()


async def get_champion_masteries(session, puuid):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}', params={'api_key': api_key_lol}) as data_masteries:    
        return await data_masteries.json()


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

def dict_data_arena(thisId: int, match_detail, info):
    

    return [match_detail['info']['participants'][i][info] for i in range(8)]

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
                         count=20):
    params_me = {'api_key': api_key_lol}
    if queue == 0:
        params_my_match = {'start': index,
                           'count': count, 'api_key': api_key_lol}
    else:
        params_my_match = {'queue': queue, 'start': index,
                           'count': count, 'api_key': api_key_lol}

    my_matches = await get_list_matchs_with_puuid(session, puuid, params_my_match)
    last_match = my_matches[idgames]  # match n° idgames
    # detail du match sélectionné
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
    except KeyError as e:
        print(f'error keyerror : {puuid}')
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
        traceback_msg = ''.join(traceback_details)
        print(traceback_msg)
        data = lire_bdd('tracker').transpose()
        return str(data.loc[data['puuid'] == puuid]['id'].values[0])
    except asyncio.exceptions.TimeoutError:
        print('error')
        data = lire_bdd('tracker').transpose()
        return str(data.loc[data['puuid'] == puuid]['id'].values[0])
    except Exception:
        print('error')
        data = lire_bdd('tracker').transpose()
        return str(data.loc[data['puuid'] == puuid]['id'].values[0])
    
    
async def get_spectator_data(puuid, session):
    me = await get_summoner_by_puuid(puuid, session)
    id = me['id']
    data = await get_spectator(session, id )

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

async def getPlayerStats(session : aiohttp.ClientSession, summonerName, tagline, regionId='euw1', role=7, season=18, queueType=420):
    url = "https://u.gg/api"
    payload = {
                "operationName": "getPlayerStats",
                "variables": {
                    "riotUserName": summonerName,
                    "riotTagLine" : tagline,
                    "regionId": regionId,
                    "role": role,
                    "seasonId": season,
                    "queueType": [queueType],
                },
                "query": "query getPlayerStats($queueType: [Int!], $regionId: String!, $role: [Int!], $seasonId: Int!, $riotUserName: String!, $riotTagLine : String!) {\n  fetchPlayerStatistics(\n    queueType: $queueType\n    riotUserName: $riotUserName\n    riotTagLine: $riotTagLine\n      regionId: $regionId\n    role: $role\n    seasonId: $seasonId\n  ) {\n    basicChampionPerformances {\n      assists\n      championId\n      cs\n      damage\n      damageTaken\n      deaths\n      gold\n      kills\n      totalMatches\n      wins\n      lpAvg\n    }\n    exodiaUuid\n    puuid\n    queueType\n    regionId\n    role\n    seasonId\n    __typename\n  }\n}"
            }
        
    headers = {
            "Accept-Encoding":"gzip, deflate, br",
            "Accept":"*/*",
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "User-Agent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
          }

        # response = requests.post(url, headers=headers, json=payload)

    async with session.post(url, headers=headers, json=payload) as session_match_detail:
        response = await session_match_detail.json()  # detail du match sélectionné
        
    return response

async def getLiveGame(session : aiohttp.ClientSession, riot_id, riot_tag, region='euw1'):
    url = "https://u.gg/api"


    payload = {
            "operationName": "GetLiveGame",
            "variables": {"riotUserName": riot_id,
                          "riotTagLine" : riot_tag,
                          "regionId": region},
            "query": "query GetLiveGame($regionId: String!, $riotUserName: String!, $riotTagLine : String!) {\n  getLiveGame(regionId: $regionId, riotUserName: $riotUserName, riotTagLine: $riotTagLine) {\n    gameLengthSeconds\n    gameType\n    teamA {\n      banId\n      championId\n      championLosses\n      championWins\n      championStats {\n        kills\n        deaths\n        assists\n        __typename\n      }\n      currentRole\n      onRole\n      partyNumber\n      previousSeasonRankScore {\n        lastUpdatedAt\n        losses\n        lp\n        promoProgress\n        queueType\n        rank\n        role\n        seasonId\n        tier\n        wins\n        __typename\n      }\n      currentSeasonRankScore {\n        lastUpdatedAt\n        losses\n        lp\n        promoProgress\n        queueType\n        rank\n        role\n        seasonId\n        tier\n        wins\n        __typename\n      }\n      roleDatas {\n        games\n        roleName\n        wins\n        __typename\n      }\n      summonerIconId\n      riotUserName\n      riotTagLine\n   summonerRuneA\n      summonerRuneB\n      summonerRuneData\n      summonerSpellA\n      summonerSpellB\n      threatLevel\n      __typename\n    }\n    teamB {\n      banId\n      championId\n      championLosses\n      championWins\n      championStats {\n        kills\n        deaths\n        assists\n        __typename\n      }\n      currentRole\n      onRole\n      partyNumber\n      previousSeasonRankScore {\n        lastUpdatedAt\n        losses\n        lp\n        promoProgress\n        queueType\n        rank\n        role\n        seasonId\n        tier\n        wins\n        __typename\n      }\n      currentSeasonRankScore {\n        lastUpdatedAt\n        losses\n        lp\n        promoProgress\n        queueType\n        rank\n        role\n        seasonId\n        tier\n        wins\n        __typename\n      }\n      roleDatas {\n        games\n        roleName\n        wins\n        __typename\n      }\n      summonerIconId\n      riotUserName\n      riotTagLine\n     summonerRuneA\n      summonerRuneB\n      summonerRuneData\n      summonerSpellA\n      summonerSpellB\n      threatLevel\n      __typename\n    }\n    __typename\n  }\n}\n",
        }

    headers = {
            "Accept-Encoding":"gzip, deflate, br",
            "Accept":"*/*",
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "User-Agent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
          }

    async with session.post(url, headers=headers, json=payload) as session_match_detail:
        response = await session_match_detail.json()  # detail du match sélectionné
        
        return response
    
    
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

class matchlol():

    def __init__(self,
                 id_compte,
                 riot_id,
                 riot_tag,
                 idgames: int,
                 queue: int = 0,
                 index: int = 0,
                 count: int = 20,
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


        self.nb_joueur = 8 if self.thisQ == 'ARENA 2v2' else 10

    async def prepare_data(self):
        """Récupère les données de la game"""

        self.champ_dict = {}
        for key in self.current_champ_list['data']:
            row = self.current_champ_list['data'][key]
            self.champ_dict[row['key']] = row['id']

        # Detail de chaque champion...

        try:
            self.dic = {(self.match_detail['info']['participants'][i]['riotIdGameName']).lower(
            ).replace(" ", ""): i for i in range(self.nb_joueur)}
        except KeyError: # game ancienne, où le riotid n'existait pas
            self.dic = {(self.match_detail['info']['participants'][i]['summonerName']).lower(
            ).replace(" ", ""): i for i in range(self.nb_joueur)}
            
        # stats
        try:
            self.thisId = self.dic[
                self.riot_id.lower().replace(" ", "")]  # cherche le pseudo dans le dico et renvoie le nombre entre 0 et 9
        except KeyError: # changement de pseudo ? On va faire avec le puuid
            
            self.dic = {(self.match_detail['metadata']['participants'][i]) : i for i in range(self.nb_joueur)}
            self.thisId = self.dic[self.puuid]


        self.match_detail_participants = self.match_detail['info']['participants'][self.thisId]
        self.match_detail_challenges = self.match_detail_participants['challenges']
        self.thisPosition = self.match_detail_participants['teamPosition']
        self.season = 14  # TODO a modifier quand changement de saison
        self.split = 1

        if (str(self.thisPosition) == "MIDDLE"):
            self.thisPosition = "MID"
        elif (str(self.thisPosition) == "BOTTOM"):
            self.thisPosition = "ADC"
        elif (str(self.thisPosition) == "UTILITY"):
            self.thisPosition = "SUPPORT"

        self.summonerName = self.match_detail_participants['summonerName'].lower().replace(' ', '')
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

        for item in self.thisItems:
            if item != 0:  # si = 0, il n'y a pas d'items
                self.data_item.append(self.data['data'][str(item)]['name'])

        self.data_item = (' | '.join(self.data_item))

        self.thisMinionPerMin = round((self.thisMinion / self.thisTime), 2)
        self.thisVisionPerMin = round((self.thisVision / self.thisTime), 2)
        self.thisGoldPerMinute = round((self.thisGold / self.thisTime), 2)
        self.thisDamagePerMinute = round(
            int(self.match_detail_participants['totalDamageDealtToChampions']) / self.thisTime, 0)

        async with self.session.get(f"https://{my_region}.api.riotgames.com/lol/league/v4/entries/by-summoner/{self.info_account['id']}",
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

        self.thisPseudoListe = dict_data(
            self.thisId, self.match_detail, 'summonerName')
        
        try:
            self.thisRiotIdListe = dict_data(
                self.thisId, self.match_detail, 'riotIdGameName')
        
            self.thisRiotTagListe = dict_data(
                self.thisId, self.match_detail, 'riotIdTagline')
        
        except KeyError:
            self.thisRiotIdListe = self.thisPseudoListe
            self.thisRiotTagListe = ''         
            
            

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

            self.ecart_top_cs = ecart_role_cs(0)
            self.ecart_jgl_cs = ecart_role_cs(1)
            self.ecart_mid_cs = ecart_role_cs(2)
            self.ecart_adc_cs = ecart_role_cs(3)
            self.ecart_supp_cs = ecart_role_cs(4)

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

            self.ecart_top_cs = ecart_role_cs(0)
            self.ecart_jgl_cs = ecart_role_cs(1)
            self.ecart_mid_cs = ecart_role_cs(2)
            self.ecart_adc_cs = ecart_role_cs(3)
            self.ecart_supp_cs = ecart_role_cs(4)

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
            self.ecart_gold_noformat = self.ecart_gold
            self.ecart_gold = "{:,}".format(
                self.ecart_gold).replace(',', ' ').replace('.', ',')
            self.ecart_gold_permin = round((self.ecart_gold_noformat / self.thisTime), 2)
        else:
            self.ecart_gold_noformat = 0
            self.ecart_gold_permin = 0

        self.thisDamageSelfMitigatedFormat = "{:,}".format(
            self.thisDamageSelfMitigated).replace(',', ' ').replace('.', ',')
        self.thisTotalOnTeammatesFormat = "{:,}".format(
            self.thisTotalOnTeammates).replace(',', ' ').replace('.', ',')


        try:
            self.thisKP = int(
                round((self.thisKills + self.thisAssists) / (self.thisTeamKills), 2) * 100)
        except Exception:
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
        
        self.DamageGoldRatio = round((self.thisDamageNoFormat/self.thisGoldNoFormat)*100,2)

        # stats mobalytics

        if self.thisQ == 'RANKED':
            self.data_timeline = await get_match_timeline(self.session, self.last_match)
            self.index_timeline = self.data_timeline['metadata']['participants'].index(self.puuid) + 1
        else:
            self.data_timeline = ''  
            self.index_timeline = 0
            
            
        try:
            self.data_mobalytics, self.data_mobalytics_complete = await get_mobalytics(self.summonerName, self.session, int(self.last_match[5:]))
            self.moba_ok = True
        except:
            self.moba_ok = False
            self.model = pickle.load(open('model/scoring_rf.pkl', 'rb'))


        if self.moba_ok:
            self.avgtier_ally = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.n_moba]['avgTier']['tier']
            self.avgrank_ally = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.n_moba]['avgTier']['division']

            self.avgtier_enemy = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.team]['avgTier']['tier']
            self.avgrank_enemy = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.team]['avgTier']['division']

            if self.thisId >= 5:
                dict_id = {5 : 0, 6 : 1, 7: 2, 8: 3, 9 : 4 }

                id_mobalytics = dict_id[self.thisId]
            else:
                id_mobalytics = self.thisId

            self.mvp = int(self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == f'{self.thisRiotIdListe[id_mobalytics]}#{self.thisRiotTagListe[id_mobalytics]}']['mvpScore'].values[0])

            self.badges = self.data_mobalytics_complete['data']['lol']['player']['match']['subject']['badges']
        
        else:
            self.mvp = 0
            self.badges = ''
            self.avgtier_ally = ''
            self.avgrank_ally = ''
            self.avgtier_enemy = ''
            self.avgrank_enemy = ''

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
        except (IndexError, AttributeError):  # on va avoir une index error si le joueur est en placement, car Riot ne fournit pas dans son api les données de placement
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

        self.url_game = f'https://www.leagueofgraphs.com/fr/match/euw/{str(self.last_match)[5:]}#participant{int(self.thisId)+1}'
        
        self.liste_rank = []
        self.liste_tier = []
        
        self.winrate_joueur = {}
        

        
        for i in range(self.nb_joueur):
            data_rank = await getRanks(self.session, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i].lower())
            df_rank = pd.DataFrame(data_rank['data']['fetchProfileRanks']['rankScores'])
            
            try:
                nbgames = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['wins'].values[0] + df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['losses'].values[0]
                wr = round((df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['wins'].values[0] / nbgames) * 100)
            except IndexError:
                wr = 0
                nbgames = 0
            
            self.winrate_joueur[f'{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}'] = {'winrate' : wr, 'nbgames' : nbgames}
            
            if self.moba_ok:
                try:
                    self.liste_rank.append(self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == f'{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}']['rank'].values[0]['tier'])
                    self.liste_tier.append(self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == f'{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}']['rank'].values[0]['division'])
                except IndexError:
                    try:
                        data_mobalytics_copy = self.data_mobalytics.copy()
                        data_mobalytics_copy['summonerName'] = data_mobalytics_copy['summonerName'].apply(lambda x : x.lower())
                        self.liste_rank.append(data_mobalytics_copy.loc[data_mobalytics_copy['summonerName'] == f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].lower()}']['rank'].values[0]['tier'])
                        self.liste_tier.append(data_mobalytics_copy.loc[data_mobalytics_copy['summonerName'] == f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].lower()}']['rank'].values[0]['division'])
                    except IndexError:
                        self.liste_rank.append('')
                        self.liste_tier.append('')
            else:
                try:
                    rank_joueur = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['tier'].values[0]
                    tier_joueur = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['rank'].values[0]
                    self.liste_rank.append(rank_joueur)
                    self.liste_tier.append(tier_joueur)
                    
                except IndexError:
                    self.liste_rank.append('')
                    self.liste_tier.append('')


        

    async def prepare_data_arena(self):
        """Récupère les données de la game"""

        self.champ_dict = {}
        for key in self.current_champ_list['data']:
            row = self.current_champ_list['data'][key]
            self.champ_dict[row['key']] = row['id']
            
            
        try:
            self.dic = {(self.match_detail['info']['participants'][i]['riotIdGameName']).lower(
            ).replace(" ", ""): i for i in range(self.nb_joueur)}
        except KeyError: # game ancienne, où le riotid n'existait pas
            self.dic = {(self.match_detail['info']['participants'][i]['summonerName']).lower(
            ).replace(" ", ""): i for i in range(self.nb_joueur)}
            
        # stats
        try:
            self.thisId = self.dic[
                self.riot_id.lower().replace(" ", "")]  # cherche le pseudo dans le dico et renvoie le nombre entre 0 et 9
        except KeyError: # changement de pseudo ? On va faire avec le puuid
            
            self.dic = {(self.match_detail['metadata']['participants'][i]) : i for i in range(self.nb_joueur)}
            self.thisId = self.dic[self.puuid]


        self.match_detail_participants = self.match_detail['info']['participants'][self.thisId]
        self.summonerName = self.match_detail_participants['summonerName'].lower().replace(' ', '')
        
        self.season = 14  # TODO a modifier quand changement de saison


        self.timestamp = str(self.match_detail['info']['gameCreation'])[
            :-3]  # traduire avec datetime.date.fromtimestamp()
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
        self.thisTimeLiving = round(fix_temps(round(
            (int(self.match_detail_participants['longestTimeSpentLiving']) / 60), 2)),2)
        
        self.thisAugmentlist = [self.match_detail_participants['playerAugment1'], self.match_detail_participants['playerAugment2'],
                                self.match_detail_participants['playerAugment3'], self.match_detail_participants['playerAugment4']]

        

        self.thisWin = ' '
        self.thisTime = fix_temps(round(
            (int(self.match_detail['info']['gameDuration']) / 60), 2))
        
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

        self.thisDoubleListe = dict_data_arena(
            self.thisId, self.match_detail, 'doubleKills')
        self.thisTripleListe = dict_data_arena(
            self.thisId, self.match_detail, 'tripleKills')
        self.thisQuadraListe = dict_data_arena(
            self.thisId, self.match_detail, 'quadraKills')
        self.thisPentaListe = dict_data_arena(
            self.thisId, self.match_detail, 'pentaKills')

        self.thisTimeSpendDead = fix_temps(round(
            float(self.match_detail_participants['totalTimeSpentDead'])/60, 2))

        self.thisTimeSpendAlive = fix_temps(round(
            self.thisTime - self.thisTimeSpendDead, 2))

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


        self.info_account = await get_summonerinfo_by_puuid(self.puuid, self.session)

        # item6 = ward. Pas utile

        # on transpose les items

        async with self.session.get(f"https://ddragon.leagueoflegends.com/cdn/{self.version['n']['item']}/data/fr_FR/item.json") as itemlist:
            self.data = await itemlist.json()
            
        async with self.session.get('https://raw.communitydragon.org/pbe/plugins/rcp-be-lol-game-data/global/fr_fr/v1/cherry-augments.json') as augmentlist:
            self.data_augment = await augmentlist.json()
            
        self.data_augment = pd.DataFrame(self.data_augment)    
        
        self.thisAugment = self.data_augment[self.data_augment['id'].isin(self.thisAugmentlist)]
        
        self.descriptionAugment = ''
        for num, (id, augment) in enumerate(self.thisAugment.iterrows()):
            self.descriptionAugment += f'- **{augment["nameTRA"]}**\n'

        self.data_item = []

        for item in self.thisItems:
            if item != 0:  # si = 0, il n'y a pas d'items
                self.data_item.append(self.data['data'][str(item)]['name'])

        self.data_item = (' | '.join(self.data_item))


        self.thisDamagePerMinute = round(
            int(self.match_detail_participants['totalDamageDealtToChampions']) / self.thisTime, 0)

        async with self.session.get(f"https://{my_region}.api.riotgames.com/lol/league/v4/entries/by-summoner/{self.info_account['id']}",
                                    params=self.params_me) as session4:
            self.thisStats = await session4.json()  # detail du match sélectionné
        self.thisWinrateStat = ' '
        self.thisWinrate = ' '
        self.thisRank = ' '
        self.thisLP = ' '

        if int(self.thisDeaths) >= 1:
            self.thisKDA = float(round((self.thisKills + self.thisAssists) / self.thisDeaths, 2))
        else:
            self.thisKDA =  float(round((self.thisKills + self.thisAssists) / (self.thisDeaths + 1), 2))

        # total kills

        self.thisKillsListe = dict_data_arena(
            self.thisId, self.match_detail, 'kills')
        # deaths

        self.thisDeathsListe = dict_data_arena(
            self.thisId, self.match_detail, 'deaths')


        # assists

        self.thisAssistsListe = dict_data_arena(
            self.thisId, self.match_detail, 'assists')

        self.thisKDAListe = [float(round((self.thisKillsListe[i] + self.thisAssistsListe[i]) / (self.thisDeathsListe[i]), 2)) if self.thisDeathsListe[i] >= 1 
                             else float(round((self.thisKillsListe[i] + self.thisAssistsListe[i]) / (self.thisDeathsListe[i] + 1), 2)) for i in range(self.nb_joueur)]

        # Page record 2


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

        # thisHeraldPerso = match_detail_challenges['teamRiftHeraldKills']
        self.allitems = {}


        for joueur in range(self.nb_joueur):
            liste_items = [self.match_detail['info']['participants'][joueur][f'item{i}'] for i in range(6)]
            liste_items.sort(reverse=True)
            self.allitems[joueur] = liste_items


        self.thisWin = self.match_detail_participants['placement']

        self.thisPosition = dict_data_arena(
            self.thisId, self.match_detail, 'placement')



        self.thisDamageListe = dict_data_arena(
            self.thisId, self.match_detail, 'totalDamageDealtToChampions')
        self.thisDamageTakenListe = dict_data_arena(
            self.thisId, self.match_detail, 'totalDamageTaken')
        self.thisDamageSelfMitigatedListe = dict_data_arena(
            self.thisId, self.match_detail, 'damageSelfMitigated')
        self.thisShieldListe = dict_data_arena(
            self.thisId, self.match_detail, 'totalDamageShieldedOnTeammates')


        # pseudo

        self.thisPseudoListe = dict_data_arena(
            self.thisId, self.match_detail, 'summonerName')

        self.thisRiotIdListe = dict_data_arena(
            self.thisId, self.match_detail, 'riotIdGameName')
        
        self.thisRiotTagListe = dict_data_arena(
            self.thisId, self.match_detail, 'riotIdTagline')

        # champ id

        self.thisChampListe = dict_data_arena(
            self.thisId, self.match_detail, 'championId')

        # champ

        self.thisChampNameListe = [
            self.champ_dict[str(champ)] for champ in self.thisChampListe]


        self.thisTeamKills = 0
        self.thisTeamKillsOp = 0

        for i, kill in enumerate(self.thisKillsListe):
            if i < 5:
                self.thisTeamKills += kill
            else:
                self.thisTeamKillsOp += kill


        # Alliés feeder
        self.thisAllieFeeder = np.array(self.thisDeathsListe)
        self.thisAllieFeeder = float(self.thisAllieFeeder[:5].max())


        self.thisChampTeam1 = [self.thisChampNameListe[i] for i in range(5)]
        self.thisChampTeam2 = [self.thisChampNameListe[i]
                               for i in range(5, self.nb_joueur)]

        # Augment

        self.augment1list = dict_data_arena(
        self.thisId, self.match_detail, 'playerAugment1')

        self.augment2list = dict_data_arena(
        self.thisId, self.match_detail, 'playerAugment2')

        self.augment3list = dict_data_arena(
        self.thisId, self.match_detail, 'playerAugment3')

        self.augment4list = dict_data_arena(
        self.thisId, self.match_detail, 'playerAugment4')


        # mise en forme

        variables_format = [
                     self.thisDamage,
                     self.thisDamageAD,
                     self.thisDamageAP,
                     self.thisDamageTrue,
                     self.thisDamageTaken,
                     self.thisDamageTakenAD,
                     self.thisDamageTakenAP,
                     self.thisDamageTakenTrue,
                     ]

        for var in variables_format:
            var = "{:,}".format(var).replace(',', ' ').replace('.', ',')


        self.thisDamageSelfMitigatedFormat = "{:,}".format(
            self.thisDamageSelfMitigated).replace(',', ' ').replace('.', ',')
        self.thisTotalOnTeammatesFormat = "{:,}".format(
            self.thisTotalOnTeammates).replace(',', ' ').replace('.', ',')
        
        self.DamageGoldRatio = round((self.thisDamageNoFormat/self.thisGoldNoFormat)*100,2)

        try:
            self.thisKP = int(
                round((self.thisKills + self.thisAssists) / (self.thisTeamKills), 2) * 100)
        except Exception:
            self.thisKP = 0

        self.thisDamageRatio = []
        self.thisDamageRatio = [round(self.thisDamageListe[i]/(np.sum(self.thisDamageListe)),2) for i in range(self.nb_joueur)]
        try:
            self.thisShieldRatio = [round(self.thisShieldListe[i]/(np.sum(self.thisShieldListe)),2) for i in range(self.nb_joueur)]
        except ValueError:
            self.thisShieldRatio = [0 for i in range(self.nb_joueur)]
            

        
        self.ecart_gold_noformat = 0
        self.ecart_gold_permin = 0
        
        if self.thisQ == 'RANKED':
            self.data_timeline = await get_match_timeline(self.session, self.last_match)
            self.index_timeline = self.data_timeline['metadata']['participants'].index(self.puuid) + 1
        else:
            self.data_timeline = ''  
            self.index_timeline = 0


        try:


            for i in range(len(self.thisStats)):
                if str(self.thisStats[i]['queueType']) == 'CHERRY':
                    self.i = i
                    break

            self.thisWinrate = int(self.thisStats[self.i]['wins']) / (
                int(self.thisStats[self.i]['wins']) + int(self.thisStats[self.i]['losses']))
            self.thisWinrateStat = str(int(self.thisWinrate * 100))
            # self.thisRank = str(self.thisStats[self.i]['rank'])
            # self.thisTier = str(self.thisStats[self.i]['tier'])
            self.thisLP = str(self.thisStats[self.i]['leaguePoints'])
            self.thisVictory = str(self.thisStats[self.i]['wins'])
            self.thisLoose = str(self.thisStats[self.i]['losses'])
            self.thisWinStreak = str(self.thisStats[self.i]['hotStreak'])
        except (IndexError, AttributeError):  # on va avoir une index error si le joueur est en placement, car Riot ne fournit pas dans son api les données de placement
            self.thisWinrate = '0'
            self.thisWinrateStat = '0'
            self.thisRank = 'En placement'
            self.thisTier = " "
            self.thisLP = '0'
            self.thisVictory = '0'
            self.thisLoose = '0'
            self.thisWinStreak = '0'

        self.url_game = f'https://www.leagueofgraphs.com/fr/match/euw/{str(self.last_match)[5:]}#participant{int(self.thisId)+1}'
        
        self.liste_rank = []
        self.liste_tier = []
        self.winrate_joueur = {}
        

        
        for i in range(self.nb_joueur):
            data_rank = await getRanks(self.session, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i].lower())
            df_rank = pd.DataFrame(data_rank['data']['fetchProfileRanks']['rankScores'])
            
            try:
                nbgames = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['wins'].values[0] + df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['losses'].values[0]
                wr = round((df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['wins'].values[0] / nbgames) * 100)
            except IndexError:
                wr = 0
                nbgames = 0
            
            self.winrate_joueur[f'{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}'] = {'winrate' : wr, 'nbgames' : nbgames}
            
            if self.moba_ok:
                try:
                    self.liste_rank.append(self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == f'{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}']['rank'].values[0]['tier'])
                    self.liste_tier.append(self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == f'{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}']['rank'].values[0]['division'])
                except IndexError:
                    try:
                        data_mobalytics_copy = self.data_mobalytics.copy()
                        data_mobalytics_copy['summonerName'] = data_mobalytics_copy['summonerName'].apply(lambda x : x.lower())
                        self.liste_rank.append(data_mobalytics_copy.loc[data_mobalytics_copy['summonerName'] == f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].lower()}']['rank'].values[0]['tier'])
                        self.liste_tier.append(data_mobalytics_copy.loc[data_mobalytics_copy['summonerName'] == f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].lower()}']['rank'].values[0]['division'])
                    except IndexError:
                        self.liste_rank.append('')
                        self.liste_tier.append('')
            else:
                try:
                    rank_joueur = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['tier'].values[0]
                    tier_joueur = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['rank'].values[0]
                    self.liste_rank.append(rank_joueur)
                    self.liste_tier.append(tier_joueur)
                    
                except IndexError:
                    self.liste_rank.append('')
                    self.liste_tier.append('')

                
        self.thisVisionListe = [0,0,0,0,0,0,0,0]
        self.thisPinkListe = [0,0,0,0,0,0,0,0]


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
            ban1, ban2, ban3, ban4, ban5, ban_adv1, ban_adv2, ban_adv3, ban_adv4, ban_adv5, split)
            VALUES (:match_id, :joueur, :role, :champion, :kills, :assists, :deaths, :double, :triple, :quadra, :penta,
            :result, :team_kills, :team_deaths, :time, :dmg, :dmg_ad, :dmg_ap, :dmg_true, :vision_score, :cs, :cs_jungle, :vision_pink, :vision_wards, :vision_wards_killed,
            :gold, :cs_min, :vision_min, :gold_min, :dmg_min, :solokills, :dmg_reduit, :heal_total, :heal_allies, :serie_kills, :cs_dix_min, :jgl_dix_min,
            :baron, :drake, :team, :herald, :cs_max_avantage, :level_max_avantage, :afk, :vision_avantage, :early_drake, :temps_dead,
            :item1, :item2, :item3, :item4, :item5, :item6, :kp, :kda, :mode, :season, :date, :damageratio, :tankratio, :rank, :tier, :lp, :id_participant, :dmg_tank, :shield,
            :early_baron, :allie_feeder, :snowball, :temps_vivant, :dmg_tower, :gold_share, :mvp, :ecart_gold_team, :ka, to_timestamp(:date), :time_first_death, :dmgsurgold, :ecart_gold_individuel, :ecart_gold_min,
            :ban1, :ban2, :ban3, :ban4, :ban5, :ban_adv1, :ban_adv2, :ban_adv3, :ban_adv4, :ban_adv5, :split);
            UPDATE tracker SET riot_id= :riot_id, riot_tagline= :riot_tagline where id_compte = :joueur''',
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
                    'ban1' : self.liste_ban[0],
                    'ban2' : self.liste_ban[1],
                    'ban3' : self.liste_ban[2],
                    'ban4' : self.liste_ban[3],
                    'ban5' : self.liste_ban[4],
                    'ban_adv1' : self.liste_ban[5],
                    'ban_adv2' : self.liste_ban[6],
                    'ban_adv3' : self.liste_ban[7],
                    'ban_adv4' : self.liste_ban[8],
                    'ban_adv5' : self.liste_ban[9],
                    'split' : self.split
                },
            )

        if self.thisQ != 'ARENA 2v2' and self.thisQ != 'OTHER':
            requete_perso_bdd('''INSERT INTO matchs_joueur(
            match_id, allie1, allie2, allie3, allie4, allie5, ennemi1, ennemi2, ennemi3, ennemi4, ennemi5,
        tier1, div1, tier2, div2, tier3, div3, tier4, div4, tier5, div5, tier6, div6, tier7, div7, tier8, div8, tier9, div9, tier10, div10,
        tierallie_avg, divallie_avg, tierennemy_avg, divennemy_avg, champ1, champ2, champ3, champ4, champ5, champ6, champ7, champ8, champ9, champ10)
            VALUES (:match_id, :allie1, :allie2, :allie3, :allie4, :allie5, :ennemi1, :ennemi2, :ennemi3, :ennemi4, :ennemi5,
        :t1, :d1, :t2, :d2, :t3, :d3, :t4, :d4, :t5, :d5, :t6, :d6, :t7, :d7, :t8, :d8, :t9, :d9, :t10, :d10,
        :tier_allie, :div_allie, :tier_ennemy, :div_ennemy,
        :c1, :c2, :c3, :c4, :c5, :c6, :c7, :c8, :c9, :c10)
        ON CONFLICT (match_id)
        DO NOTHING;''',
        {'match_id' : self.last_match,
                'allie1' : f'{self.thisRiotIdListe[0]}#{self.thisRiotTagListe[0]}',
            'allie2' : f'{self.thisRiotIdListe[1]}#{self.thisRiotTagListe[1]}',
            'allie3' : f'{self.thisRiotIdListe[2]}#{self.thisRiotTagListe[2]}',
            'allie4' : f'{self.thisRiotIdListe[3]}#{self.thisRiotTagListe[3]}',
            'allie5' : f'{self.thisRiotIdListe[4]}#{self.thisRiotTagListe[4]}',
            'ennemi1' : f'{self.thisRiotIdListe[5]}#{self.thisRiotTagListe[5]}',
            'ennemi2' : f'{self.thisRiotIdListe[6]}#{self.thisRiotTagListe[6]}',
            'ennemi3' : f'{self.thisRiotIdListe[7]}#{self.thisRiotTagListe[7]}',
            'ennemi4' : f'{self.thisRiotIdListe[8]}#{self.thisRiotTagListe[8]}',
            'ennemi5' : f'{self.thisRiotIdListe[9]}#{self.thisRiotTagListe[9]}',
            't1' : self.liste_rank[0],
            'd1' : self.liste_tier[0],
            't2' : self.liste_rank[1],
            'd2' : self.liste_tier[1],
            't3' : self.liste_rank[2],
            'd3' : self.liste_tier[2],
            't4' : self.liste_rank[3],
            'd4' : self.liste_tier[3],
            't5' : self.liste_rank[4],
            'd5' : self.liste_tier[4],
            't6' : self.liste_rank[5],
            'd6' : self.liste_tier[5],
            't7' : self.liste_rank[6],
            'd7' : self.liste_tier[6],
            't8' : self.liste_rank[7],
            'd8' : self.liste_tier[7],
            't9' : self.liste_rank[8],
            'd9' : self.liste_tier[8],
            't10' : self.liste_rank[9],
            'd10' : self.liste_tier[9],
            'tier_allie' : self.avgtier_ally,
            'div_allie' : self.avgrank_ally,
            'tier_ennemy' : self.avgtier_enemy,
            'div_ennemy' : self.avgrank_enemy,
            'c1' : self.thisChampNameListe[0],
            'c2' : self.thisChampNameListe[1],
            'c3' : self.thisChampNameListe[2],
            'c4' : self.thisChampNameListe[3],
            'c5' : self.thisChampNameListe[4],
            'c6' : self.thisChampNameListe[5],
            'c7' : self.thisChampNameListe[6],
            'c8' : self.thisChampNameListe[7],
            'c9' : self.thisChampNameListe[8],
            'c10' : self.thisChampNameListe[9],
            })

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
    
    async def save_timeline(self):
        
        def unpack_dict_championStats(row):
            return pd.Series(row['championStats'])

        def unpack_dict_damageStats(row):
            return pd.Series(row['damageStats'])
        
        df_timeline_load, self.minute = load_timeline(self.data_timeline)  
        
        self.df_timeline_joueur = df_timeline_load[df_timeline_load['riot_id'] == self.index_timeline]  
        
        self.df_timeline_position = self.df_timeline_joueur[['position', 'timestamp', 'totalGold', 'xp', 'jungleMinionsKilled', 'currentGold', 'level']]

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

        self.df_events_joueur['riot_id'] = self.id_compte
        self.df_events_joueur['match_id'] = self.last_match

        self.df_events_joueur['position_x'] = self.df_events_joueur['position'].apply(lambda x : x['x'] if isinstance(x, dict) else 0)
        self.df_events_joueur['position_y'] = self.df_events_joueur['position'].apply(lambda x : x['y'] if isinstance(x, dict) else 0)
        self.df_events_joueur.drop('position', axis=1, inplace=True)

        self.df_events_joueur.drop(['victimDamageDealt', 'victimDamageReceived', 'participantId', 'creatorId'], axis=1, inplace=True)
        
        if 'actualStartTime' in self.df_events_joueur.columns: # cette colonne n'est pas toujours présente
            self.df_events_joueur.drop(['actualStartTime'], axis=1, inplace=True)

        if 'name' in self.df_events_joueur.columns: # cette colonne n'est pas toujours présente
            self.df_events_joueur.drop(['name'], axis=1, inplace=True)
        self.df_events_joueur.reset_index(inplace=True, drop=True)    
        
        # on simplifie quelques data
        
        self.df_events_joueur.loc[(self.df_events_joueur['type'] == 'CHAMPION_KILL')
                                  & (self.df_events_joueur['victimId'] == self.index_timeline), 'type'] = 'DEATHS'
        
        self.df_events_joueur['timestamp'] = np.round(self.df_events_joueur['timestamp'] / 60000,2)
            
        self.df_events_joueur['wardType'] = self.df_events_joueur['wardType'].map({'YELLOW_TRINKET': 'Trinket jaune',
                                                                'UNDEFINED': 'Balise Zombie',
                                                                'CONTROL_WARD': 'Pink',
                                                                'SIGHT_WARD': 'Ward support',
                                                                'BLUE_TRINKET': 'Trinket bleu'
                                                                })
 
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


    async def add_couronnes(self, points):
        """Ajoute les couronnes dans la base de données"""

        requete_perso_bdd('''UPDATE matchs SET couronne = :points WHERE match_id = :match_id AND joueur = :joueur''', {'points': points,
                                                                                                                       'match_id': self.last_match,
                                                                                                                       'joueur': self.id_compte})

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
        df_data_pro = lire_bdd_perso('''SELECT data_acc_proplayers.*, data_proplayers.home, data_proplayers.role, data_proplayers.team_plug from data_acc_proplayers
                                LEFT JOIN data_proplayers ON data_acc_proplayers.joueur = data_proplayers.plug''', index_col=None).T
        
        self.observations_proplayers = ''
        for num_joueur, joueur in enumerate(self.thisPseudoListe):
            if joueur in df_data_pro['compte'].tolist():
                name_joueur = df_data_pro.loc[df_data_pro['compte'] == joueur, 'joueur'].values[0]
                role_joueur = df_data_pro.loc[df_data_pro['compte'] == joueur, 'role'].values[0]
                team_joueur = df_data_pro.loc[df_data_pro['compte'] == joueur, 'team_plug'].values[0]
                champ_joueur = self.thisChampNameListe[num_joueur]
                if team_joueur == '':
                    self.observations_proplayers += f':stadium: **{name_joueur}** ({champ_joueur}) : {role_joueur} \n'
                else: 
                    self.observations_proplayers += f':stadium: **{name_joueur}** ({champ_joueur}) : {role_joueur} chez {team_joueur} \n'
                       
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
                self.observations += "\n **:green_circle: :heart: N'est pas mort de la game ** \n ** :crown: :star: PERFECT KDA **"
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

            if int(self.thisKP) >= settings['KP']['score']:
                self.observations +=\
                        f"\n **:green_circle: :dagger: {self.thisKP}% KP **"
                txt_sql += add_sql(txt_sql, 'kp', [self.thisKP], self.last_match,self.id_compte)


            if int(self.thisDamageRatio) >= settings['%_dmg_équipe']['score']:
                self.observations +=\
                        f"\n **:green_circle: :dart: {self.thisDamageRatio}% DMG de ton équipe **"
                txt_sql += add_sql(txt_sql, 'damage_ratio', [self.thisDamageRatio], self.last_match, self.id_compte)


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
        
        for joueur, stat in self.winrate_joueur.items():
            if joueur != f'{self.riot_id}#{self.riot_tag}' and stat['winrate'] >= 70 and stat['nbgames'] >= 10:
                self.observations_smurf += f':eyes: **{joueur}** : WR : {stat["winrate"]}% ({stat["nbgames"]} parties) \n'
        
            
            
    async def resume_general(self,
                             name_img,
                             embed,
                             difLP):

        '''Resume global de la game

        Parameters
        -----------
        name_img : nom de l'image enregistré'''



 

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

        font = charger_font(50)
        font_little = charger_font(40)        


        im = Image.new("RGBA", (lineX, lineY * 13 + 190),
                       (255, 255, 255))  # Ligne blanche
        d = ImageDraw.Draw(im)

        line = Image.new("RGB", (lineX, 190), (230, 230, 230))  # Ligne grise
        im.paste(line, (0, 0))

        fill = (0, 0, 0)
        d.text((x_name, y_name), self.riot_id, font=font, fill=fill)

        im.paste(im=await get_image("avatar", self.avatar, self.session, 100, 100, self.version['n']['profileicon']),
                 box=(x_name-240, y_name-20))

        im.paste(im=await get_image("champion", self.thisChampName, self.session, 100, 100, self.version['n']['profileicon']),
                 box=(x_name-120, y_name-20))

        d.text((x_name+700, y_name-20),
               f"Niveau {self.level_summoner}", font=font_little, fill=fill)

        last_season = self.season - 1

        if last_season == 13: # pour split la saison en 2
            last_season = '13_old'

        try:
            if not self.thisQ in ['ARAM', 'CLASH ARAM']:
                data_last_season = get_data_bdd(f'''SELECT index, tier from suivi_s{last_season} where index = {self.id_compte} ''')
                self.tier_last_season = data_last_season.mappings().all()[0]['tier']
            else:
                data_last_season = get_data_bdd(f'''SELECT index, rank from ranked_aram_s{self.season-1} where index = {self.id_compte} ''')
                self.tier_last_season = data_last_season.mappings().all()[0]['rank']

            img_tier_last_season = await get_image("tier", self.tier_last_season, self.session, 100, 100)

            im.paste(img_tier_last_season,(x_name+950, y_name-50), img_tier_last_season.convert('RGBA'))
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

            data_aram = get_data_bdd(f''' SELECT ranked_aram_s{saison}.index,wins, losses, lp, games, k, d, a, ranked_aram_s{saison}.activation, rank, serie
                                     from ranked_aram_s{saison}
                                     INNER JOIN tracker on tracker.id_compte = ranked_aram_s{saison}.index
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
                requete_perso_bdd(f'''UPDATE ranked_aram_s{saison}
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

        # match
        d.text((10, 20 + 190), self.thisQ, font=font, fill=(0, 0, 0))

        money = await get_image('gold', 'dragon', self.session, 60, 60)

        im.paste(money, (10, 120 + 190), money.convert('RGBA'))
        d.text((83, 120 + 190), f'{self.thisGold_team1}',
               font=font, fill=(255, 255, 255))
        im.paste(money, (10, 720 + 190), money.convert('RGBA'))
        d.text((83, 720 + 190), f'{self.thisGold_team2}', font=font, fill=(0, 0, 0))

        if self.moba_ok:
            try:
                self.img_ally_avg = await get_image('tier', self.avgtier_ally.upper(), self.session, 100, 100)

                im.paste(self.img_ally_avg, (x_name+200, 120-20 + 190), self.img_ally_avg.convert('RGBA'))

                d.text((x_name+300, 120 + 190), str(
                            self.avgrank_ally), font=font, fill=(0, 0, 0))

            except FileNotFoundError:
                self.img_ally_avg = 'UNRANKED'
            try:
                self.img_enemy_avg = await get_image('tier', self.avgtier_enemy.upper(), self.session, 100, 100)

                im.paste(self.img_enemy_avg, (x_name+200, 720-20 + 190), self.img_enemy_avg.convert('RGBA'))

            except FileNotFoundError:
                self.img_enemy_avg = 'UNRANKED'

            d.text((x_name+300, 720 + 190), str(
                        self.avgrank_enemy), font=font, fill=(0, 0, 0))

        for y in range(123 + 190, 724 + 190, 600):
            fill = (255, 255, 255) if y == 123 + 190 else (0, 0, 0)
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

            if not self.thisQ in ["ARAM", "CLASH ARAM"]:
                d.text((x_vision, y), 'VS', font=font, fill=fill)

        # participants
        initial_y = 223 + 190
        
        if self.moba_ok == False:

            array_scoring = np.array([]) # qu'on va mettre du plus grand au plus petit
            liste = []  # en ordre en fonction des joueurs
            for i in range(0,10):
                liste.append(self.calcul_scoring(i))
                scoring_joueur = liste[i]
                array_scoring = np.append(array_scoring, scoring_joueur)

            array_scoring_trie = array_scoring.copy()
            array_scoring_trie.sort()
            
            self.model = ''


            
        for i in range(self.nb_joueur):
            im.paste(
                im=await get_image("champion", self.thisChampNameListe[i], self.session, profil_version=self.version['n']['champion']),
                box=(10, initial_y-13),
            )

            d.text((x_name, initial_y),
                   self.thisRiotIdListe[i], font=font, fill=(0, 0, 0))

            # rank

            if self.moba_ok:
                try:
                    rank_joueur = self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == f'{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}']['rank'].values[0]['tier']
                    tier_joueur = self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == f'{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}']['rank'].values[0]['division']
                except IndexError:
                    try:
                        data_mobalytics_copy = self.data_mobalytics.copy()
                        data_mobalytics_copy['summonerName'] = data_mobalytics_copy['summonerName'].apply(lambda x : x.lower())
                        rank_joueur = data_mobalytics_copy.loc[data_mobalytics_copy['summonerName'] == f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].lower()}']['rank'].values[0]['tier']
                        tier_joueur = data_mobalytics_copy.loc[data_mobalytics_copy['summonerName'] == f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].lower()}']['rank'].values[0]['division']
                    except IndexError:
                        rank_joueur = ''
                        tier_joueur = ''
            else:
                try:
                    
                    data_rank = await getRanks(self.session, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i].lower())
                    df_rank = pd.DataFrame(data_rank['data']['fetchProfileRanks']['rankScores'])
                    rank_joueur = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['tier'].values[0]
                    tier_joueur = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['rank'].values[0]
                except IndexError:
                    rank_joueur = ''
                    tier_joueur = ''

            if rank_joueur != '':
                img_rank_joueur = await get_image('tier', rank_joueur.upper(), self.session, 100, 100)

                im.paste(img_rank_joueur, (x_score-200, initial_y-20), img_rank_joueur.convert('RGBA'))

                d.text((x_score-100, initial_y), str(
                        tier_joueur), font=font, fill=(0, 0, 0))

            if self.moba_ok:
                try:
                    scoring = self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == f'{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}']['mvpScore'].values[0]
                except IndexError:
                    try:
                        scoring = data_mobalytics_copy.loc[data_mobalytics_copy['summonerName'] == f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].lower()}']['mvpScore'].values[0]
                    except IndexError:
                        scoring = '?'    

            else:
                scoring = np.where(array_scoring_trie == liste[i])[0][0] + 1
                if self.thisRiotIdListe[i].lower().replace(' ', '') == self.riot_id:
                    requete_perso_bdd('''UPDATE matchs
                                      SET mvp = :mvp 
                                      WHERE match_id = :match_id
                                      AND joueur = :joueur''',
                                      {'mvp' : int(scoring),
                                       'match_id' : self.last_match,
                                       'joueur' : self.id_compte})
                
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

            if not self.thisQ in ["ARAM", "CLASH ARAM"]:

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

        n = 0
        for image in self.thisItems:
            if image != 0:
                im.paste(await get_image("items", image, self.session, profil_version=self.version['n']['item']),
                         box=(350 + n, 10 + 190))
                n += 100

        if not self.thisQ in ["ARAM", "CLASH ARAM"]:

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
        if self.thisQ in ['ARAM', 'CLASH ARAM']:
            suivi_24h = lire_bdd(f'ranked_aram_S{saison}', 'dict')
        else:
            suivi_24h = lire_bdd(f'suivi_S{saison}', 'dict')

        if self.thisQ not in ['ARAM', 'CLASH ARAM', 'FLEX']:

            difwin = int(self.thisVictory) - \
                        int(suivi_24h[self.id_compte]["wins_jour"])
            diflos = int(self.thisLoose) - \
                        int(suivi_24h[self.id_compte]["losses_jour"])

            if (difwin + diflos) > 0:  # si pas de ranked aujourd'hui, inutile
                d.text((x_metric + 650, y_name+50),
                           f'Victoires 24h : {difwin}', font=font_little, fill=(0, 0, 0))
                d.text((x_metric + 1120, y_name+50),
                           f'Defaites 24h : {diflos}', font=font_little, fill=(0, 0, 0))


        elif self.thisQ in ['ARAM', 'CLASH ARAM'] and activation:

            difwin = wins - \
                        int(suivi_24h[self.id_compte]["wins_jour"])
            diflos = losses - \
                        int(suivi_24h[self.id_compte]["losses_jour"])

            if (difwin + diflos) > 0:  # si pas de ranked aujourd'hui, inutile
                d.text((x_metric + 650, y_name+50),
                           f'Victoires 24h : {difwin}', font=font_little, fill=(0, 0, 0))
                d.text((x_metric + 1120, y_name+50),
                           f'Defaites 24h : {diflos}', font=font_little, fill=(0, 0, 0))


        im.save(f'{name_img}.png')

        await self.session.close()

        return embed


    async def test(self,
                             name_img,
                             embed,
                             difLP):

        '''Resume global de la game

        Parameters
        -----------
        name_img : nom de l'image enregistré'''
        


        # Gestion de l'image 2
        lineX = 2600
        lineY = 100

        x_name = 350

        lineX = 2600
        lineY = 100

        x_name = 290
        y = 120
        y_name = y - 60
        x_rank = 1750
        x_objectif = 1700

        y_avatar = 320
        y_pseudo = y_avatar + 100
        y_rank = y_pseudo + 50

        x_kill_total = 1000

        x_center = 236 * 5 + 70

        y_ecart_gold = y_rank+60
        y_score = y_ecart_gold + 50
        y_items = y_score + 80
        y_kda = y_items + 200

        if self.thisQ == 'ARAM': # Vu qu'il n'y a pas de VS, on augmente
            y_kda += 50
        y_kda_raccourci = y_kda-50

        y_KP = y_kda+100
        y_cs = y_KP + 120
        y_dmg = y_cs + 80
        y_tank = y_dmg + 100
        y_vision = y_tank + 100
        x_metric = 120


        font = charger_font(50)
        font_little = charger_font(40)
        font_dmg = charger_font(35)
        font_very_little = charger_font(30)
        font_very_very_little = charger_font(25)


        im = Image.new("RGBA", (lineX, lineY * 13 + 190),
                       (255, 255, 255))  # Ligne blanche
        d = ImageDraw.Draw(im)

        line = Image.new("RGB", (lineX, 300), (230, 230, 230))  # Ligne grise
        im.paste(line, (0, 0))

        fill = (0, 0, 0)
        d.text((x_name, y_name), self.riot_id, font=font, fill=fill)

        im.paste(im=await get_image("avatar", self.avatar, self.session, 100, 100, self.version['n']['profileicon']),
                 box=(x_name-240, y_name-20))

        im.paste(im=await get_image("champion", self.thisChampName, self.session, 100, 100, self.version['n']['profileicon']),
                 box=(x_name-120, y_name-20))

        d.text((x_name+700, y_name-20),
               f"Niveau {self.level_summoner}", font=font_little, fill=fill)

        try:
            if self.thisQ != 'ARAM':
                data_last_season = get_data_bdd(f'''SELECT index, tier from suivi_s{self.season-1} where index = {self.id_compte} ''')
                self.tier_last_season = data_last_season.mappings().all()[0]['tier']
            else:
                data_last_season = get_data_bdd(f'''SELECT index, rank from ranked_aram_s{self.season-1} where index = {self.id_compte} ''')
                self.tier_last_season = data_last_season.mappings().all()[0]['rank']

            img_tier_last_season = await get_image("tier", self.tier_last_season, self.session, 100, 100)

            im.paste(img_tier_last_season,(x_name+950, y_name-50), img_tier_last_season.convert('RGBA'))
        except Exception:
            pass  

        if self.thisQ != "ARAM":  # si ce n'est pas le mode aram, on prend la soloq normal
            if self.thisTier != ' ':  # on vérifie que le joueur a des stats en soloq, sinon il n'y a rien à afficher

                requete_perso_bdd('''UPDATE matchs SET ecart_lp = :ecart_lp WHERE match_id = :match_id AND joueur = :joueur''', {'ecart_lp': difLP,
                                                                                                                        'match_id': self.last_match,
                                                                                                                        'joueur': self.id_compte})
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

            data_aram = get_data_bdd(f''' SELECT ranked_aram_s{saison}.index,wins, losses, lp, games, k, d, a, ranked_aram_s{saison}.activation, rank, serie
                                     from ranked_aram_s{saison}
                                     INNER JOIN tracker on tracker.id_compte = ranked_aram_s{saison}.index
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
                
                if self.thisWinBool:
                    serie_wins = serie_wins + 1
                else:
                    serie_wins = 0

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

        line = Image.new("RGB", (lineX, lineY), (230, 230, 230))  # Ligne grise

        dict_position = {"TOP": 2, "JUNGLE": 3,
                         "MID": 4, "ADC": 5, "SUPPORT": 6}

        def draw_black_line_verticale(i:int):
            draw = ImageDraw.Draw(im)
            draw.line((i, 300, i, 2000), fill=(0, 0, 0), width=5)

        def draw_light_blue_line(i:int):

            # Créer une nouvelle image transparente
            square = Image.new("RGBA", (236, 25), (0, 0, 255, 128))

            # Dessiner un carré bleu sur l'image transparente
            draw = ImageDraw.Draw(square)
            draw.rectangle((236, 220, 236, 1000), fill=(0, 0, 255, 128), outline=None)

            # Coller l'image transparente sur l'image originale
            im.paste(square, (i-115, 295), square)

        def draw_black_line() -> None:
            im.paste(Image.new("RGB", (lineX, 3),
                     (0, 0, 0)), (0, 180))

        draw_black_line()



        def drawProgressBar(x, y, w, h, progress, bg="black", fg="blue"):

            draw = ImageDraw.Draw(im)
            # draw background
            draw.ellipse((x+w, y, x+h+w, y+h), fill=bg)
            draw.ellipse((x, y, x+h, y+h), fill=bg)
            draw.rectangle((x+(h/2), y, x+w+(h/2), y+h), fill=bg)

            # draw progress bar
            w *= progress
            draw.ellipse((x+w, y, x+h+w, y+h),fill=fg)
            draw.ellipse((x, y, x+h, y+h),fill=fg)
            draw.rectangle((x+(h/2), y, x+w+(h/2), y+h),fill=fg)


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

        if self.moba_ok == False:

            array_scoring = np.array([]) # qu'on va mettre du plus grand au plus petit
            liste = []  # en ordre en fonction des joueurs
            for i in range(0,10):
                liste.append(self.calcul_scoring(i))
                scoring_joueur = liste[i]
                array_scoring = np.append(array_scoring, scoring_joueur)

            array_scoring_trie = array_scoring.copy()
            array_scoring_trie.sort()
            
            self.model = ''
            
        for i in range(self.nb_joueur):
            
            
            if self.thisQ != "ARAM" and i == dict_position[self.thisPosition]:
                draw_light_blue_line((i)*165)

            draw_black_line_verticale((i+1)*236)
            n = i

            if i >= 5:
                n += 1

            im.paste(im=await get_image("champion", self.thisChampNameListe[i], self.session, 100, 100, self.version['n']['champion']),
                 box=(236*n+70, y_avatar))

            if len(self.thisPseudoListe[i])  > 14:
                font_text = font_very_very_little
                ecart_pseudo = 20
            elif len(self.thisPseudoListe[i]) > 8:
                font_text = font_very_very_little
                ecart_pseudo = 30
            elif len(self.thisPseudoListe[i]) < 5:
                font_text = font_little
                ecart_pseudo = 80
            else:
                font_text = font_little
                ecart_pseudo = 50

            pseudo = self.thisPseudoListe[i]
            d.text((236*n+ecart_pseudo, y_pseudo),
                   pseudo, font=font_text, fill=(0, 0, 0))

            # rank

            if self.moba_ok:
                try:
                    rank_joueur = self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == f'{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}']['rank'].values[0]['tier']
                    tier_joueur = self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == f'{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}']['rank'].values[0]['division']
                except IndexError:
                    try:
                        data_mobalytics_copy = self.data_mobalytics.copy()
                        data_mobalytics_copy['summonerName'] = data_mobalytics_copy['summonerName'].apply(lambda x : x.lower())
                        rank_joueur = data_mobalytics_copy.loc[data_mobalytics_copy['summonerName'] == f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].lower()}']['rank'].values[0]['tier']
                        tier_joueur = data_mobalytics_copy.loc[data_mobalytics_copy['summonerName'] == f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].lower()}']['rank'].values[0]['division']
                    except IndexError:
                        rank_joueur = ''
                        tier_joueur = ''

                if rank_joueur != '':
                    img_rank_joueur = await get_image('tier', rank_joueur.upper(), self.session, 60, 60)

                    im.paste(img_rank_joueur, (236*n +70, y_rank), img_rank_joueur.convert('RGBA'))

                    d.text((236*n +150, y_rank), str(
                            tier_joueur), font=font, fill=(0, 0, 0))

            if self.moba_ok:
                try:
                    scoring = self.data_mobalytics.loc[self.data_mobalytics['summonerName'] == f'{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}']['mvpScore'].values[0]
                except IndexError:
                    try:
                        scoring = data_mobalytics_copy.loc[data_mobalytics_copy['summonerName'] == f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].lower()}']['mvpScore'].values[0]
                    except IndexError:
                        scoring = '?'    
            else:
                scoring = np.where(array_scoring_trie == liste[i])[0][0] + 1
                
            color_scoring = {1 : (0,128,0), 2 : (89,148,207), 3 : (67,89,232), 10 : (220,20,60)}

            ecart_scoring = 90 if scoring == 10 else 100
            d.text((236*n+ecart_scoring, y_score),
                    str(scoring),
                    font=font,
                    fill=color_scoring.get(scoring, (0,0,0)))

            kda_abrege = str(round(self.thisKDAListe[i],1))

            if len(kda_abrege) == 3:
                ecart_kda_abrege = 90
            elif len(kda_abrege) >= 4:
                ecart_kda_abrege = 70
            else:
                ecart_kda_abrege = 110

            fill = range_value(i, self.thisKDAListe, True)
            d.text((236*n +ecart_kda_abrege, y_kda_raccourci),
                       kda_abrege, font=font_little, fill=fill)

            kda = f'{self.thisKillsListe[i]}/{self.thisDeathsListe[i]}/{self.thisAssistsListe[i]}'

            if len(kda) == 5:
                ecart_kda = 60
            if len(kda) == 6:
                ecart_kda = 55
            elif len(kda) >= 7:
                ecart_kda = 40
            else:
                ecart_kda = 70
            d.text((236*n + ecart_kda, y_kda),
                       kda, font=font_little, fill=fill)

            fill, top_kp = range_value(i, self.thisKPListe, True, True)
            d.text((236*n +70, y_KP),
                       str(self.thisKPListe[i]) + "%", font=font, fill=fill)

            fill = range_value(i, self.thisDamageListe, True)

            if int(self.thisDamageRatioListe[i]*100) < 10:
                font_dmg_i = font_little
            else:
                font_dmg_i = font_dmg


            d.text((236*n+30, y_dmg),
                   f'{int(self.thisDamageListe[i]/1000)}k ({int(self.thisDamageRatioListe[i]*100)}%)', font=font_dmg_i, fill=fill)

            fill = range_value(i, np.array(self.thisMinionListe) +
                               np.array(self.thisJungleMonsterKilledListe))

            total_cs = self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]

            decalage_cs = 85 if total_cs < 100 else 70
            d.text((236*n+decalage_cs, y_cs), str(
                    total_cs), font=font, fill=fill)

            fill = range_value(i, np.array(self.thisDamageTakenListe) +
                               np.array(self.thisDamageSelfMitigatedListe))

            if int(self.thisDamageSelfMitigatedListe[i]/1000) >= 100:
                font_tank = font_dmg
            else:
                font_tank = font_little

            d.text((236*n+30, y_tank),
                   f'{int(self.thisDamageTakenListe[i]/1000)}k / {int(self.thisDamageSelfMitigatedListe[i]/1000)}k', font=font_tank, fill=fill)

            if self.thisQ != 'ARAM':
                fill, top_vision = range_value(i, self.thisVisionListe, True, True)

                decalage_vision = 85 if self.thisVisionListe[i] < 10 else 70
                d.text((236*n+decalage_vision, y_vision), str(
                        self.thisVisionListe[i]), font=font, fill=fill)


            if i <= 4:
                color = 'blue'
                drawProgressBar(236*n+45, y_tank+70, 120, 15, (self.thisDamageTakenListe[i] + self.thisDamageSelfMitigatedListe[i])/(np.sum(self.thisDamageTakenListe[:5]) + np.sum(self.thisDamageSelfMitigatedListe[:5])), fg=color)

                if self.thisQ != 'ARAM':
                    if top_vision=='max':
                        drawProgressBar(236*n+45, y_vision+70, 120, 15, (self.thisVisionListe[i])/np.sum(self.thisVisionListe[:5]), fg='green')
                    elif top_vision=='min':
                        drawProgressBar(236*n+45, y_vision+70, 120, 15, (self.thisVisionListe[i])/np.sum(self.thisVisionListe[:5]), fg='#8B0000')
                    else:
                        drawProgressBar(236*n+45, y_vision+70, 120, 15, (self.thisVisionListe[i])/np.sum(self.thisVisionListe[:5]), fg=color)
            else:
                color = 'red'
                drawProgressBar(236*n+45, y_tank+70, 120, 15, (self.thisDamageTakenListe[i] + self.thisDamageSelfMitigatedListe[i])/(np.sum(self.thisDamageTakenListe[5:]) + np.sum(self.thisDamageSelfMitigatedListe[5:])), fg=color)
                if self.thisQ != 'ARAM':
                    if top_vision == 'max':
                        drawProgressBar(236*n+45, y_vision+70, 120, 15, (self.thisVisionListe[i])/np.sum(self.thisVisionListe[5:]), fg='green')
                    elif top_vision == 'min':
                        drawProgressBar(236*n+45, y_vision+70, 120, 15, (self.thisVisionListe[i])/np.sum(self.thisVisionListe[5:]), fg='#8B0000')
                    else:
                        drawProgressBar(236*n+45, y_vision+70, 120, 15, (self.thisVisionListe[i])/np.sum(self.thisVisionListe[5:]), fg=color)
            if top_kp == 'max': 
                drawProgressBar(236*n+45, y_KP+70, 120, 15, self.thisKPListe[i]/100, fg='green')
            elif top_kp == 'min':
                drawProgressBar(236*n+45, y_KP+70, 120, 15, self.thisKPListe[i]/100, fg='#8B0000')
            else:
                drawProgressBar(236*n+45, y_KP+70, 120, 15, self.thisKPListe[i]/100, fg=color)
            drawProgressBar(236*n+45, y_dmg+70, 120, 15, self.thisDamageRatioListe[i], fg=color)


        fill = (0,0,0)


        d.text((x_center, y_kda-30), 'KDA', font=font, fill=fill)
        d.text((x_center, y_score), 'MVP', font=font, fill=fill)
        d.text((x_center+5, y_KP+20), 'KP', font=font, fill=fill)
        d.text((x_center+5, y_cs), 'CS', font=font, fill=fill)
        d.text((x_center-15, y_dmg+20), 'DMG', font=font, fill=fill)
        d.text((x_center-15, y_tank+20), 'TANK', font=font, fill=fill)


        if self.thisQ != "ARAM":
            d.text((x_center+5, y_vision+20), 'VS', font=font, fill=fill)
            n_ecart = 0
            for ecart in [self.ecart_top_gold_affiche, self.ecart_jgl_gold_affiche, self.ecart_mid_gold_affiche, self.ecart_adc_gold_affiche, self.ecart_supp_gold_affiche]:
                if ecart > 0:
                    d.text((236*n_ecart+80, y_ecart_gold), str(round(ecart/1000, 1)
                                                   ) + "k", font=font_little, fill=(0, 128, 0))
                else:
                    d.text((236*n_ecart+80, y_ecart_gold), str(round(ecart/1000, 1)
                                                      ) + "k", font=font_little, fill=(255, 0, 0))

                n_ecart += 1




        # match
        d.text((10, 20 + 190), self.thisQ, font=font, fill=(0, 0, 0))




        for joueur, items in self.allitems.items():
            if joueur > 4:
                joueur += 1
            for nb, item in enumerate(items):
                if item != 0:
                    if nb < 3:
                        im.paste(await get_image("items", item, self.session, 50,50, self.version['n']['profileicon']),
                                box=(236*joueur+40+nb*50, y_items))
                    else:
                        nb = nb - 3
                        im.paste(await get_image("items", item, self.session, 50,50, self.version['n']['profileicon']),
                                box=(236*joueur+40+nb*50, y_items+60))




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


        # Stat du jour
        if self.thisQ == 'ARAM':
            suivi_24h = lire_bdd(f'ranked_aram_S{saison}', 'dict')
        else:
            suivi_24h = lire_bdd(f'suivi_S{saison}', 'dict')

        if self.thisQ not in ['ARAM', 'FLEX']:
            try:
                difwin = int(self.thisVictory) - \
                        int(suivi_24h[self.id_compte]["wins_jour"])
                diflos = int(self.thisLoose) - \
                        int(suivi_24h[self.id_compte]["losses_jour"])

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
                        int(suivi_24h[self.id_compte]["wins_jour"])
                diflos = losses - \
                        int(suivi_24h[self.id_compte]["losses_jour"])

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
    
    async def test_arena(self,
                             name_img,
                             embed,
                             difLP):

        '''Resume global de la game

        Parameters
        -----------
        name_img : nom de l'image enregistré'''
        

        # model = pickle.load(open('model/scoring_rf.pkl', 'rb'))
        
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

        lineX = 2600
        lineY = 100

        x_name = 290
        y = 120
        y_name = y - 60
        x_rank = 1750
        x_objectif = 1700

        y_avatar = 320
        y_pseudo = y_avatar + 100
        y_rank = y_pseudo + 50

        x_kill_total = 1000
        
        ecart = 290
        
        x_center = 236 * 5 + 70
        
        y_ecart_gold = y_rank+60
        y_score = y_ecart_gold + 50
        y_items = y_score + 80
        y_kda = y_items + 200
        
        y_kda_raccourci = y_kda-50
        
        y_KP = y_kda+100
        y_cs = y_KP + 50
        y_dmg = y_cs + 120
        y_tank = y_dmg + 120

        font = charger_font(50)
        font_little = charger_font(40)
        font_dmg = charger_font(35)
        font_very_little = charger_font(30)
        font_very_very_little = charger_font(25)


        im = Image.new("RGBA", (lineX, lineY * 13 + 190),
                       (255, 255, 255))  # Ligne blanche
        d = ImageDraw.Draw(im)
        
        line = Image.new("RGB", (lineX, 300), (230, 230, 230))  # Ligne grise
        im.paste(line, (0, 0))

        fill = (0, 0, 0)
        d.text((x_name, y_name), self.riot_id, font=font, fill=fill)

        im.paste(im=await get_image("avatar", self.avatar, self.session, 100, 100, self.version['n']['profileicon']),
                 box=(x_name-240, y_name-20))

        im.paste(im=await get_image("champion", self.thisChampName, self.session, 100, 100, self.version['n']['profileicon']),
                 box=(x_name-120, y_name-20))

        d.text((x_name+700, y_name-20),
               f"Niveau {self.level_summoner}", font=font_little, fill=fill)

        d.text((x_rank+220, y-60),
                       f'{self.thisLP} LP', font=font_little, fill=fill)
        
        d.text((x_rank+220, y-20), f'{self.thisVictory}W {self.thisLoose}L     {self.thisWinrateStat}% ', font=font_little, fill=fill)


            
        
        line = Image.new("RGB", (lineX, lineY), (230, 230, 230))  # Ligne grise
        

        
        def draw_black_line_verticale(i:int):
            draw = ImageDraw.Draw(im)
            draw.line((i, ecart, i, 2000), fill=(0, 0, 0), width=5)
            
        def draw_line(i:int, color):
            
            # Créer une nouvelle image transparente
            square = Image.new("RGBA", (295, 25), color)

            # Dessiner un carré bleu sur l'image transparente
            draw = ImageDraw.Draw(square)
            draw.rectangle((ecart, 220, ecart, 1000), fill=color, outline=None)

            # Coller l'image transparente sur l'image originale
            im.paste(square, (i, 295), square)

            
        def draw_black_line() -> None:
            im.paste(Image.new("RGB", (lineX, 3),
                     (0, 0, 0)), (0, 180))
            
        draw_black_line()

        
            
        def drawProgressBar(x, y, w, h, progress, bg="black", fg="blue"):
            
            draw = ImageDraw.Draw(im)
            # draw background
            draw.ellipse((x+w, y, x+h+w, y+h), fill=bg)
            draw.ellipse((x, y, x+h, y+h), fill=bg)
            draw.rectangle((x+(h/2), y, x+w+(h/2), y+h), fill=bg)

            # draw progress bar
            w *= progress
            draw.ellipse((x+w, y, x+h+w, y+h),fill=fg)
            draw.ellipse((x, y, x+h, y+h),fill=fg)
            draw.rectangle((x+(h/2), y, x+w+(h/2), y+h),fill=fg)

                        
        for i in range(self.nb_joueur):
            
            color_position = {1 : (0,0,255,128),
                           2 : (0,255,0,128),
                           3 : (255,0,0,128),
                           4 : (128,0,128,128)}

            n_color = i
            
            if i >= 4:
                n_color = i+1
            

            draw_line((n_color)*ecart, color_position[self.thisPosition[i]])
            

                    
            draw_black_line_verticale((i+1)*ecart)    
            n = i
            
            if i >= 4:
                n += 1
                    
            im.paste(im=await get_image("champion", self.thisChampNameListe[i], self.session, 100, 100, self.version['n']['champion']),
                 box=(ecart*n+95, y_avatar))
            
            if len(self.thisRiotIdListe[i])  > 14:
                font_text = font_very_very_little
                ecart_pseudo = 60
            elif len(self.thisRiotIdListe[i]) > 8:
                font_text = font_very_very_little
                ecart_pseudo = 55
            elif len(self.thisRiotIdListe[i]) < 5:
                font_text = font_little
                ecart_pseudo = 100
            else:
                font_text = font_little
                ecart_pseudo = 75
                
            pseudo = self.thisRiotIdListe[i]
            d.text((ecart*n+ecart_pseudo, y_pseudo),
                   pseudo, font=font_text, fill=(0, 0, 0))
             
            color_scoring = {1 : (0,128,0),
                             2 : (89,148,207),
                             3 : (67,89,232),
                             4 : (220,20,60)}

                 
            d.text((ecart*n+118, y_score-30),
                    str(self.thisPosition[i]),
                    font=font,
                    fill=color_scoring.get(self.thisPosition[i], (0,0,0)))
                
            kda_abrege = str(round(self.thisKDAListe[i],1))
            
            if len(kda_abrege) == 3:
                ecart_kda_abrege = 110
            elif len(kda_abrege) >= 4:
                ecart_kda_abrege = 95
            else:
                ecart_kda_abrege = 135
                
            fill = range_value_arena(i, self.thisKDAListe, True)    
            d.text((ecart*n +ecart_kda_abrege, y_kda_raccourci),
                       kda_abrege, font=font_little, fill=fill)
            
            kda = f'{self.thisKillsListe[i]}/{self.thisDeathsListe[i]}/{self.thisAssistsListe[i]}'
            
            if len(kda) == 5:
                ecart_kda = 75
            if len(kda) == 6:
                ecart_kda = 70
            elif len(kda) >= 7:
                ecart_kda = 55
            else:
                ecart_kda = 85
            d.text((ecart*n + ecart_kda, y_kda),
                       kda, font=font_little, fill=fill)

            color = 'blue'
            
            fill = range_value_arena(i, self.thisDamageListe, True)
            
            d.text((ecart*n+50, y_cs),
                   f'{int(self.thisShieldListe[i]/1000)}k ({int(self.thisShieldRatio[i]*100)}%)', font=font_dmg, fill=fill)
            
            drawProgressBar(ecart*n+60, y_cs+70, 120, 15, (self.thisShieldListe[i]/(np.sum(self.thisShieldListe))), fg=color)
            
            
            d.text((ecart*n+50, y_dmg),
                   f'{int(self.thisDamageListe[i]/1000)}k ({int(self.thisDamageRatio[i]*100)}%)', font=font_dmg, fill=fill)
            

            
            drawProgressBar(ecart*n+60, y_dmg+70, 120, 15, (self.thisDamageListe[i]/(np.sum(self.thisDamageListe))), fg=color)
            
            
            fill = range_value_arena(i, np.array(self.thisDamageTakenListe) +
                               np.array(self.thisDamageSelfMitigatedListe))
            
            if int(self.thisDamageSelfMitigatedListe[i]/1000) >= 100:
                font_tank = font_dmg
            else:
                font_tank = font_little
                
            d.text((ecart*n+50, y_tank),
                   f'{int(self.thisDamageTakenListe[i]/1000)}k / {int(self.thisDamageSelfMitigatedListe[i]/1000)}k', font=font_tank, fill=fill)
            
            
            drawProgressBar(ecart*n+60, y_tank+70, 120, 15, (self.thisDamageTakenListe[i] + self.thisDamageSelfMitigatedListe[i])/(np.sum(self.thisDamageTakenListe) + np.sum(self.thisDamageSelfMitigatedListe)), fg=color)

            

        fill = (0,0,0)
    
            
        d.text((x_center, y_kda-30), 'KDA', font=font, fill=fill)

        d.text((x_center-30, y_cs), 'SHIELD', font=font, fill=fill)
        d.text((x_center-15, y_dmg+20), 'DMG', font=font, fill=fill)
        d.text((x_center-15, y_tank+20), 'TANK', font=font, fill=fill)
                            
        # match
        d.text((10, 20 + 190), self.thisQ, font=font, fill=(0, 0, 0))


                

        for joueur, items in self.allitems.items():
            if joueur > 3:
                joueur += 1
            for nb, item in enumerate(items):
                if item != 0:
                    if nb < 3:
                        im.paste(await get_image("items", item, self.session, 50,50, self.version['n']['profileicon']),
                                box=(ecart*joueur+60+nb*50, y_items))
                    else:
                        nb = nb - 3
                        im.paste(await get_image("items", item, self.session, 50,50, self.version['n']['profileicon']),
                                box=(ecart*joueur+60+nb*50, y_items+60))
                                


        im.save(f'{name_img}.png')

        await self.session.close()
        
        return embed