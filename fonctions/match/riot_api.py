"""
Appels à l'API Riot Games.
Gestion des requêtes vers les différents endpoints de l'API LoL.
"""

import aiohttp
import asyncio
import pandas as pd
from io import BytesIO
from PIL import Image
from utils.params import api_key_lol, region, my_region


# ============================================================================
# VERSION ET DONNÉES STATIQUES
# ============================================================================

async def get_version(session: aiohttp.ClientSession):
    """Récupère la version actuelle du jeu."""
    async with session.get("https://ddragon.leagueoflegends.com/realms/euw.json") as session_version:
        version = await session_version.json()
    return version


async def get_champ_list(session: aiohttp.ClientSession, version):
    """Récupère la liste des champions."""
    champions_versions = version['n']['champion']
    async with session.get(f"https://ddragon.leagueoflegends.com/cdn/{champions_versions}/data/fr_FR/champion.json") as session_champlist:
        current_champ_list = await session_champlist.json()
    return current_champ_list


async def get_data_champ_tags(session, version):
    """Récupère les tags (rôles) des champions."""
    async with session.get(f'https://ddragon.leagueoflegends.com/cdn/{version}/data/fr_FR/champion.json') as session_summoner:
        me = await session_summoner.json()
        df = pd.DataFrame(me['data']).T
        df = df[['key', 'name', 'tags']]
    return df


async def get_challenges_config(session):
    """Récupère la configuration des challenges."""
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/challenges/v1/challenges/config?api_key={api_key_lol}') as challenge_config:
        return await challenge_config.json()


# ============================================================================
# DONNÉES JOUEUR
# ============================================================================

async def get_summoner_by_riot_id(session: aiohttp.ClientSession, riot_id, riot_tag):
    """Récupère les informations d'un joueur par son Riot ID."""
    async with session.get(
        f'https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{riot_id}/{riot_tag}',
        params={'api_key': api_key_lol}
    ) as session_summoner:
        me = await session_summoner.json()
    return me


async def get_summoner_by_puuid(puuid, session):
    """Récupère les informations d'un joueur par son PUUID."""
    async with session.get(
        f'https://europe.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}',
        params={'api_key': api_key_lol}
    ) as session_summoner:
        me = await session_summoner.json()
    return me


async def get_summoner_by_name(session: aiohttp.ClientSession, key):
    """Récupère les informations d'un joueur par son nom (ancienne méthode)."""
    async with session.get(
        f'https://{my_region}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{key}',
        params={'api_key': api_key_lol}
    ) as session_summoner:
        me = await session_summoner.json()
    return me


async def get_summonerinfo_by_puuid(puuid, session):
    """Récupère les informations détaillées d'un joueur par son PUUID."""
    async with session.get(
        f'https://{my_region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}',
        params={'api_key': api_key_lol}
    ) as session_summoner:
        me = await session_summoner.json()
        if session_summoner.status != 200:
            print(session_summoner.reason)
    return me


async def get_league_by_puuid(session: aiohttp.ClientSession, me):
    """Récupère les stats de ligue d'un joueur."""
    async with session.get(
        f"https://{my_region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{me}",
        params={'api_key': api_key_lol}
    ) as session_league:
        stats = await session_league.json()
    return stats


async def get_data_rank(session, puuid):
    """Récupère le rang d'un joueur."""
    async with session.get(
        f'https://{my_region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}?api_key={api_key_lol}'
    ) as session_rank:
        if session_rank.status == 404:
            return ''
        return await session_rank.json()


async def get_champion_masteries(session, puuid):
    """Récupère les maîtrises de champion d'un joueur."""
    async with session.get(
        f'https://{my_region}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}',
        params={'api_key': api_key_lol}
    ) as data_masteries:
        return await data_masteries.json()


# ============================================================================
# MATCHS
# ============================================================================

async def get_list_matchs_with_me(session: aiohttp.ClientSession, me, params):
    """Récupère la liste des matchs d'un joueur."""
    attemps = 0

    while attemps < 5:
        try:
            async with session.get(
                f'https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{me["puuid"]}/ids?',
                params=params
            ) as session_match:
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


async def get_list_matchs_with_puuid(session: aiohttp.ClientSession, puuid, params=None, queue=None):
    """Récupère la liste des matchs par PUUID."""
    if params is None:
        params = {'start': 0, 'count': 20, 'api_key': api_key_lol}
        
    if queue is not None:
        params['queue'] = queue
        
    attemps = 0

    while attemps < 5:
        try:
            async with session.get(
                f'https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?',
                params=params
            ) as session_match:
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
    """Récupère les détails d'un match."""
    attemps = 0

    while attemps < 5:
        try:
            async with session.get(
                f'https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}',
                params=params
            ) as session_match_detail:
                if session_match_detail.status != 200:
                    print(session_match_detail.status)
                    print(session_match_detail.reason)
                match_detail_stats = await session_match_detail.json()
                break
        except:
            attemps += 1
            await asyncio.sleep(5)
            if attemps >= 5:
                match_detail_stats = ''

    return match_detail_stats


async def get_match_timeline(session: aiohttp.ClientSession, match_id):
    """Récupère la timeline d'un match."""
    async with session.get(
        f'https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline',
        params={'api_key': api_key_lol}
    ) as session_timeline:
        match_detail_timeline = await session_timeline.json()
    return match_detail_timeline


# ============================================================================
# SPECTATEUR
# ============================================================================

async def get_spectator(session, puuid):
    """Récupère les données d'une partie en cours."""
    async with session.get(
        f'https://{my_region}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}?api_key={api_key_lol}'
    ) as session_spectator:
        if session_spectator.status == 404:
            return None
        return await session_spectator.json()


# ============================================================================
# IMAGES
# ============================================================================

async def get_image(type, name, session: aiohttp.ClientSession, resize_x=80, resize_y=80, profil_version='13.6.1'):
    """
    Récupère une image depuis l'API Riot ou les fichiers locaux.
    
    Parameters:
        type: Type d'image (champion, tier, avatar, items, monsters, epee, timer, gold, autre, kda)
        name: Nom/ID de l'élément
        session: Session aiohttp
        resize_x, resize_y: Dimensions de redimensionnement
        profil_version: Version du profil pour les URLs
    """
    url_mapping = {
        "champion": f"https://ddragon.leagueoflegends.com/cdn/{profil_version}/img/champion/{name}.png",
        "tier": f"./img/{name}.png",
        "avatar": f"https://ddragon.leagueoflegends.com/cdn/{profil_version}/img/profileicon/{name}.png",
        "items": f'https://ddragon.leagueoflegends.com/cdn/{profil_version}/img/item/{name}.png',
        "monsters": f'./img/monsters/{name}.png',
        "epee": f'./img/epee/{name}.png',
        "timer": f'./img/timer/{name}.png',
        "gold": './img/money.png',
        "autre": f'{name}.png',
        "kda": f'./img/rectangle/{name}.png',
    }

    url = url_mapping.get(type)
    if url is None:
        raise ValueError(f"Invalid image type: {type}")

    if "./" in url or type == 'autre':
        img = Image.open(url)
    else:
        response = await session.get(url)
        response.raise_for_status()
        img_raw = await response.read()
        img = Image.open(BytesIO(img_raw))
    img = img.resize((resize_x, resize_y))

    return img


# ============================================================================
# FONCTIONS COMBINÉES
# ============================================================================

async def match_by_puuid_with_summonername(summonerName, idgames: int, session,
                                           index=0, queue=0, count=20):
    """Récupère un match par nom de joueur."""
    params_me = {'api_key': api_key_lol}
    if queue == 0:
        params_my_match = {'start': index, 'count': count, 'api_key': api_key_lol}
    else:
        params_my_match = {'queue': queue, 'start': index, 'count': count, 'api_key': api_key_lol}

    me = await get_summoner_by_name(session, summonerName)
    my_matches = await get_list_matchs_with_me(session, me, params_my_match)
    last_match = my_matches[idgames]
    match_detail_stats = await get_match_detail(session, last_match, params_me)

    return last_match, match_detail_stats, me


async def match_by_puuid_with_puuid(puuid, idgames: int, session,
                                    index=0, queue=0, count=20, id_game=None):
    """Récupère un match par PUUID."""
    params_me = {'api_key': api_key_lol}
    if queue == 0:
        params_my_match = {'start': index, 'count': count, 'api_key': api_key_lol}
    else:
        params_my_match = {'queue': queue, 'start': index, 'count': count, 'api_key': api_key_lol}

    if id_game is None:
        my_matches = await get_list_matchs_with_puuid(session, puuid, params_my_match)
        last_match = my_matches[idgames]
    else:
        last_match = str(id_game)
        if 'EUW' not in last_match:
            last_match = f'EUW1_{last_match}'
    match_detail_stats = await get_match_detail(session, last_match, params_me)

    return last_match, match_detail_stats


async def getId_with_summonername(summonerName: str, session: aiohttp.ClientSession):
    """Récupère l'ID d'une game à partir du nom du joueur."""
    from fonctions.gestion_bdd import lire_bdd
    import sys
    import traceback
    
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


async def getId_with_puuid(puuid: str, session: aiohttp.ClientSession):
    """Récupère l'ID d'une game à partir du PUUID."""
    from fonctions.gestion_bdd import lire_bdd
    import sys
    import traceback
    
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
