"""
Fonctions de gestion des maîtrises et statistiques joueurs.
Récupération des données de maîtrise, stats par champion, détection de patterns.
"""

import sys
import traceback
import pandas as pd
import numpy as np
import aiohttp

from fonctions.api_calls import getPlayerStats, getRanks, update_ugg, get_role, get_player_match_history
from fonctions.api_moba import (
    update_moba, get_mobalytics, get_player_match_history_moba,
    get_role_stats, get_wr_ranked, detect_win_streak,
    get_stat_champion_by_player_mobalytics, get_rank_moba
)
from .riot_api import get_summoner_by_riot_id, get_champion_masteries
from utils.params import api_key_lol


async def get_masteries_old(summonerName: str, championIds, session: aiohttp.ClientSession) -> dict:
    """
    Récupère les maîtrises de champion d'un joueur.
    Utilise championmastery.gg en priorité, puis l'API Riot en fallback.
    """
    championIds = {v: k for k, v in championIds.items()}  # Inverse clé et valeur
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
        
    try:
        url = f'https://championmastery.gg/player?riotId={riot_id}%23{riot_tag}&region=EUW&lang=en_US'
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()
                df = pd.read_html(text, header=0)[0].head(-1)
        
        mastery_list = []
        try:
            def correction_name(mot: str):
                mot = mot.replace("'", "").replace(" ", "").replace(".", "")
                corrections = {
                    'KaiSa': 'Kaisa',
                    'LeBlanc': 'Leblanc',
                    'KhaZix': 'Khazix',
                    'VelKoz': 'Velkoz',
                    'Wukong': 'MonkeyKing',
                    'ChoGath': 'Chogath',
                    'Nunu&Willump': 'Nunu',
                    'RenataGlasc': 'Renata',
                    'BelVeth': 'Belveth'
                }
                return corrections.get(mot, mot)
            
            df['Champion name'] = df['Champion name'].apply(correction_name)
            
            for index, data in df.iterrows():
                championId = int(championIds[data['Champion name']])
                mastery = int(data['Points'])
                level = int(data['Level'])
                mastery_list.append({"mastery": mastery, 'level': level, "championId": championId})
            
        except AttributeError:
            try:
                me = await get_summoner_by_riot_id(session, riot_id, riot_tag)
                puuid = me['puuid']
                
                data_masteries: dict = await get_champion_masteries(session, puuid)
                
                for value in data_masteries:
                    mastery = value['championPoints']
                    level = value['championLevel']
                    championId = value['championId']
                    mastery_list.append({"mastery": mastery, 'level': level, "championId": championId})
                    
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
                    
            data_masteries: dict = await get_champion_masteries(session, puuid)
                    
            for value in data_masteries:
                mastery = value['championPoints']
                level = value['championLevel']
                championId = value['championId']
                mastery_list.append({"mastery": mastery, 'level': level, "championId": championId})

        except:
            print(f"Erreur avec l'API pour {summonerName_url} {riot_tag}")
            mastery_list.append({"mastery": 1, 'level': 0, 'championId': 1})

    mastery_dict = {
        "summonerName": summonerName,
        "region": "EUW",
        "mastery": mastery_list,
    }

    return pd.DataFrame(mastery_dict['mastery'])


async def get_stat_champion_by_player(session, champ_dict, riot_id, riot_tag, season=23):
    """
    Récupère les statistiques d'un joueur par champion.
    
    Parameters:
        session: Session aiohttp
        champ_dict: Dictionnaire de mapping des champions
        riot_id: Riot ID du joueur
        riot_tag: Tag Riot du joueur
        season: Saison (int ou liste de saisons)
    
    Returns:
        DataFrame avec les stats par champion ou chaîne vide si erreur
    """
    if isinstance(season, int):
        data_stat = await getPlayerStats(session, riot_id, riot_tag, season=season)

        if data_stat == '':
            return ''
        
        try:
            df_data_stat = pd.DataFrame(data_stat['data']['fetchPlayerStatistics'][0]['basicChampionPerformances'])
        except TypeError:
            return ''
        
        if 'championId' not in df_data_stat.columns:
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
            
            if 'championId' not in df_data_stat.columns:
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
    """
    Détecte les duos fréquents dans l'historique de matchs d'un joueur.
    
    Returns:
        dict: Paires de joueurs avec leur nombre de parties ensemble (>5)
    """
    from .riot_api import get_list_matchs_with_puuid, get_match_detail
    
    summoner_data = await get_summoner_by_riot_id(session, riot_id, riot_tag)
    match_ids = await get_list_matchs_with_puuid(
        session, summoner_data['puuid'],
        {'start': 0, 'count': count, 'api_key': api_key_lol}
    )

    duo_tracker = {}

    for match_id in match_ids:
        match_details = await get_match_detail(session, match_id, {'api_key': api_key_lol})
        participants = match_details['info']['participants']
        
        team = {p['summonerName']: p['teamId'] for p in participants}

        for player1 in team:
            for player2 in team:
                if player1 != player2 and team[player1] == team[player2]:
                    duo_key = tuple(sorted([player1, player2]))
                    if duo_key not in duo_tracker:
                        duo_tracker[duo_key] = 0
                    duo_tracker[duo_key] += 1

    return {duo: count for duo, count in duo_tracker.items() if count > 5}


async def get_spectator_data(puuid, session):
    """
    Récupère les données d'une partie en cours.
    
    Returns:
        tuple: (url_opgg, type_queue, id_game, champion_joueur, icon_url) ou None si pas de partie
    """
    from .riot_api import get_spectator, get_version, get_champ_list
    from utils.lol import dict_id_q
    
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
    current_champ_list = await get_champ_list(session, version)

    champ_dict = {}
    for key in current_champ_list['data']:
        row = current_champ_list['data'][key]
        champ_dict[row['key']] = row['id']

    df['champion'] = df['championId'].astype('str').map(champ_dict)

    champ_joueur = df.loc[df['summonerName'] == summonerName, 'champion'].values[0]
    id_icon = df.loc[df['summonerName'] == summonerName, 'profileIconId'].values[0]
    icon = f'https://ddragon.leagueoflegends.com/cdn/{version["n"]["profileicon"]}/img/profileicon/{id_icon}.png'

    df['summonerName'] = df['summonerName'].str.replace(' ', '%20')

    liste_joueurs = ''.join(joueur + ',' for joueur in df['summonerName'].tolist())
    url = f'https://www.op.gg/multisearch/euw?summoners={liste_joueurs}'

    return url, thisQ, id_game, champ_joueur, icon
