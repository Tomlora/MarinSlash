from bs4 import BeautifulSoup
import json
import time
import sys
import os
import traceback
from aiohttp import ClientSession
from fonctions.match import get_summoner_by_riot_id, get_champion_masteries, getLiveGame, getPlayerStats
import pandas as pd

api_moba = os.environ.get('API_moba')
# Gets the mast matches from mobalytics




def wait(seconds):
    print("Waiting....")
    for i in range(seconds, 0, -1):
        sys.stdout.write(str(i) + " ")
        sys.stdout.flush()
        time.sleep(1)


async def get_past_matches(summonerName: str, match_id : str, session : ClientSession):
    url = "https://app.mobalytics.gg/api/lol/graphql/v1/query"
    
    payload = {
            'operationName': "LolMatchDetailsQuery",
            'variables': {
                'region' : 'EUW',
                'summonerName': summonerName,
                'matchId' : match_id,
            },
            'extensions': {
                'persistedQuery': {
                    'version': 1,
                    'sha256Hash': api_moba,
                }
            },
        }

    headers = {'authority':'app.mobalytics.gg',
               'accept':'*/*',
               'accept-language':'en_us',
               'content-type':'application/json',
               'origin':'https://app.mobalytics.gg',
               'sec-ch-ua-mobile':'?0','sec-ch-ua-platform':'"Windows"',
               'sec-fetch-dest':'empty','sec-fetch-mode':'cors',
               'sec-fetch-site':'same-origin','sec-gpc':'1',
               'x-moba-client':'mobalytics-web',
               'x-moba-proxy-gql-ops-name':'LolMatchDetailsQuery'}
    try:
        async with session.post(url, headers=headers, json=payload) as session_match_detail:
            response = await session_match_detail.json()  # detail du match sélectionné
        data_match = response["data"]["lol"]["player"]["match"]
    
        return data_match
    except Exception:
        print('Erreur get_past_matches')
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
        traceback_msg = ''.join(traceback_details)
        print(traceback_msg)
        return None
    
async def get_live_match(summonerName: str, session:ClientSession):

    url = "https://u.gg/api"
    
    def trouver_indice_hashtag(chaine):
        for indice, caractere in enumerate(chaine):
            if caractere == '#':
                return indice
        return -1
    indice = trouver_indice_hashtag(summonerName)
    
    riot_id = summonerName[:indice]
    riot_tag = summonerName[indice+1:]


    response = await getLiveGame(session, riot_id, riot_tag)

    if response["data"]["getLiveGame"] == None:
        return 'Aucun'

    live_game_data = {}

    live_game_data["gameType"] = response["data"]["getLiveGame"]["gameType"]

    live_game_data["participants"] = []

    for summoner in response["data"]["getLiveGame"]["teamA"]:
        live_game_data["participants"].append(
            {
                "championLosses": summoner["championLosses"],
                "championId": summoner["championId"],
                "championWins": summoner["championWins"],
                "currentRole": summoner["currentRole"],
                "summonerName": summoner["riotUserName"] + "#" + summoner["riotTagLine"],
                "team": "BLUE",
            }
        )
    for summoner in response["data"]["getLiveGame"]["teamB"]:
        live_game_data["participants"].append(
            {
                "championLosses": summoner["championLosses"],
                "championId": summoner["championId"],
                "championWins": summoner["championWins"],
                "currentRole": summoner["currentRole"],
                "summonerName": summoner["riotUserName"] + "#" + summoner["riotTagLine"],
                "team": "RED",
            }
        )
    return live_game_data



# Gets the mastery_list of a player from championmastery.gg


async def get_masteries(summonerName: str, championIds, session : ClientSession) -> dict:
    
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
        riot_id = summonerNameTag[:indice].lower()
        riot_tag = summonerNameTag[indice+1:].lower()
        
    try: # si le tag est EUW, championmastery fonctionne bien. En revanche, si ce n'est pas le cas, il peut se tromper de joueur.
        
        # url = f"https://championmastery.gg/summoner?summoner={summonerName_url}&region=EUW"
        url = f'https://championmastery.gg/player?riotId={riot_id}%23{riot_tag}&region=EUW&lang=en_US'
        
        df = pd.read_html(url, header=0)[0].head(-1) # la dernière ligne est un total
        
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
        print(f"Erreur Masteries {summonerName_url} : Retour à l'API")
        mastery_list = []
        me = await get_summoner_by_riot_id(session, riot_id, riot_tag)
        puuid = me['puuid']
                
        data_masteries : dict = await get_champion_masteries(session, puuid)
                
        for value in data_masteries:
            mastery = value['championPoints']
            level = value['championLevel']
            championId = value['championId']
                
            mastery_list.append({"mastery": mastery, 'level' : level, "championId": championId})              
        

    mastery_dict = {
        "summonerName": summonerName,
        "region": "EUW",
        "mastery": mastery_list,
    }

    return mastery_dict['mastery']


async def get_winrates(summonerName: str, session : ClientSession):
    url = "https://u.gg/api"
    
    summonerNameTag = summonerName
    
    summonerWinrate = {}

    def trouver_indice_hashtag(chaine):
        for indice, caractere in enumerate(chaine):
            if caractere == '#':
                return indice
        return -1
    indice = trouver_indice_hashtag(summonerName)
    
    if indice != -1:
        summonerName = summonerName[:indice]
        tagline = summonerNameTag[indice+1:]
    

    try:
        # For season 12
        
        response = await getPlayerStats(session, summonerName, tagline)

        playerStats = response

        for playerStatistics in playerStats["data"]["fetchPlayerStatistics"]:
            if playerStatistics["__typename"] == "PlayerStatistics":
                for championPerformance in playerStatistics[
                    "basicChampionPerformances"
                ]:
                    summonerWinrate[championPerformance["championId"]] = dict()
                    summonerWinrate[championPerformance["championId"]][
                        "totalMatches"
                    ] = championPerformance["totalMatches"]
                    summonerWinrate[championPerformance["championId"]][
                        "wins"
                    ] = championPerformance["wins"]

        
        season_boucle = [20, 21, 22, 23] # For season 13 (split 1, split 2) / season 14 (split 1)
        
        for season in season_boucle:
            response = await getPlayerStats(session, summonerName, tagline, season=season)

            playerStats = response

            for playerStatistics in playerStats["data"]["fetchPlayerStatistics"]:
                if playerStatistics["__typename"] == "PlayerStatistics":
                    for championPerformance in playerStatistics[
                        "basicChampionPerformances"
                    ]:
                        if championPerformance["championId"] in summonerWinrate:
                            summonerWinrate[championPerformance["championId"]][
                                "totalMatches"
                            ] += championPerformance["totalMatches"]
                            summonerWinrate[championPerformance["championId"]][
                                "wins"
                            ] += championPerformance["wins"]
                        else:
                            summonerWinrate[championPerformance["championId"]] = dict()
                            summonerWinrate[championPerformance["championId"]][
                                "totalMatches"
                            ] = championPerformance["totalMatches"]
                            summonerWinrate[championPerformance["championId"]][
                                "wins"
                            ] = championPerformance["wins"]

        winrate_list = []

        for championId, champion in summonerWinrate.items():
            winrate_list.append(
                {
                    "championID": championId,
                    "winrate": (champion["wins"] / champion["totalMatches"] * 100),
                }
            )

        winrate_dict = {
            "summonerName": summonerName,
            "region": "EUW",
            "winrate": winrate_list,
        }

        return winrate_dict['winrate']
    except Exception:
        print(summonerName)
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
        traceback_msg = ''.join(traceback_details)
        print(traceback_msg)
        return None


async def get_player_match_history(session, summonerName, tagline,  role=[], regionId="euw1", championId=[], queueType=[420], seasonIds=[21,22,23], page=1):
    
    url = "https://u.gg/api"
    headers = {
                "Accept-Encoding":"gzip, deflate, br",
                "Accept":"*/*",
                "Content-Type": "application/json",
                "Connection": "keep-alive",
                "User-Agent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
            }

    payload = {
            "operationName": "FetchMatchSummaries",
            "variables": {
                "championId": championId,
                "queueType": queueType,
                "regionId": regionId,
                "role":role,
                "seasonIds":seasonIds,
                "riotUserName": summonerName,
                "riotTagLine" : tagline,
                "page":page
            },
            "query": "query FetchMatchSummaries($championId: [Int], $page: Int, $queueType: [Int], $regionId: String!, $role: [Int], $seasonIds: [Int]!, $riotUserName: String!, $riotTagLine : String!) {  fetchPlayerMatchSummaries(    championId: $championId    page: $page    queueType: $queueType   regionId: $regionId    role: $role    seasonIds: $seasonIds    riotUserName: $riotUserName  riotTagLine : $riotTagLine) {    finishedMatchSummaries    totalNumMatches    matchSummaries {      assists      championId      cs      damage      deaths      gold      items      jungleCs      killParticipation      kills      level      matchCreationTime      matchDuration      matchId      maximumKillStreak      primaryStyle      queueType      regionId      role      runes      subStyle      summonerName      summonerSpells      psHardCarry      psTeamPlay      lpInfo {        lp        placement        promoProgress        promoTarget        promotedTo {          tier          rank          __typename        }        __typename      }      teamA {        championId        summonerName        teamId        role        hardCarry        teamplay        __typename      }      teamB {        championId        summonerName        teamId        role        hardCarry        teamplay        __typename      }      version      visionScore      win      __typename    }    __typename  }}"
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


    # return json.loads(x.text)["data"]["updatePlayerProfile"]["success"]
    
    

async def getRanks(session : ClientSession, summonerName, tagline, regionId='euw1', season=23):
    """Avopir le rank et le tier d'un joueur"""
    
    url = "https://u.gg/api"
    headers = {
                "Accept-Encoding":"gzip, deflate, br",
                "Accept":"*/*",
                "Content-Type": "application/json",
                "Connection": "keep-alive",
                "User-Agent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
            }
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
        

        # response = requests.post(url, headers=headers, json=payload)

    async with session.post(url, headers=headers, json=payload) as session_match_detail:
        response = await session_match_detail.json()  # detail du match sélectionné
        
    return response



async def getRankings(session : ClientSession, summonerName, tagline, regionId='euw1', season=23, queueType=420):
    """Avoir le classement du joueur"""
    
    url = "https://u.gg/api"
    headers = {
                "Accept-Encoding":"gzip, deflate, br",
                "Accept":"*/*",
                "Content-Type": "application/json",
                "Connection": "keep-alive",
                "User-Agent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
            }
    
    payload = {
                "operationName": "GetOverallPlayerRanking",
                "variables": {
                    "regionId": regionId,
                    "riotUserName": summonerName,
                    "riotTagLine" : tagline,
                    # "seasonId": season,
                    'queueType': queueType
                },
                "query": """query GetOverallPlayerRanking($queueType: Int, $riotUserName: String, $riotTagLine:String, $regionId: String) {
    overallRanking(queueType: $queueType, riotUserName: $riotUserName, riotTagLine: $riotTagLine,  regionId: $regionId) {
        overallRanking
        totalPlayerCount
        }
        }"""}
        


        # response = requests.post(url, headers=headers, json=payload)

    async with session.post(url, headers=headers, json=payload) as session_match_detail:
        response = await session_match_detail.json()  # detail du match sélectionné
        
    return response



