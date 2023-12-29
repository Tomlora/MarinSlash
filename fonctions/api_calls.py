from bs4 import BeautifulSoup
import json
import time
import sys
import os
import traceback
from aiohttp import ClientSession
from fonctions.match import get_summoner_by_riot_id, get_champion_masteries

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
    except:
        return None


# Gets the mastery_list of a player from championmastery.gg


async def get_masteries(summonerName: str, championIds, session : ClientSession) -> dict:
    
    championIds = {v: k for k, v in championIds.items()} # on inverse clé et value
    summonerName_url = summonerName.replace(' ', '+')
    summonerNameTag = summonerName.replace(' ', '')
    
    def trouver_indice_hashtag(chaine):
        for indice, caractere in enumerate(chaine):
            if caractere == '#':
                return indice
        return -1
    indice = trouver_indice_hashtag(summonerName_url)
    
    if indice != -1:
        summonerName_url = summonerName_url[:indice]
    url = f"https://championmastery.gg/summoner?summoner={summonerName_url}&region=EUW"
    
    response = await session.get(url)
    
    content = await response.text()
 

    soup = BeautifulSoup(content, "html.parser")
    results = soup.find("tbody", id="tbody")
    
    mastery_list = []
    try:
        job_elements = results.find_all("tr")

        

        for job_element in job_elements:
            data = []
            data = job_element.text.splitlines()[0]
            premier_chiffre = None
            position_premier_chiffre = None

            for position, caractere in enumerate(data):
                if caractere.isdigit():
                    premier_chiffre = caractere
                    position_premier_chiffre = position
                    break
            
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
            
            champion_name = correction_name(data[:position_premier_chiffre]) 
            
            chiffres = [caractere for caractere in data[position_premier_chiffre+1:] if caractere.isdigit()]
            
            championId = int(championIds[champion_name])
            mastery = int(''.join(chiffres))
            mastery_list.append({"mastery": mastery, "championId": championId})
        
    except AttributeError:
        try:
            riot_id = summonerNameTag[:indice]
            riot_tag = summonerNameTag[indice+1:]

            me = await get_summoner_by_riot_id(session, riot_id, riot_tag)

            puuid = me['puuid']
            
            data_masteries : dict = await get_champion_masteries(session, puuid)
            
            for value in data_masteries:
                mastery = value['championPoints']
                championId = value['championId']
            
                mastery_list.append({"mastery": mastery, "championId": championId})
        except Exception:
            print(summonerName)
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
            traceback_msg = ''.join(traceback_details)
            print(traceback_msg)
            
        

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
        payload = {
                "operationName": "getPlayerStats",
                "variables": {
                    "riotUserName": summonerName,
                    "riotTagLine" : tagline,
                    "regionId": "euw1",
                    "role": 7,
                    "seasonId": 18,
                    "queueType": [420],
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

        # For season 13 (split 2)
        payload = {
                "operationName": "getPlayerStats",
                "variables": {
                    "riotUserName": summonerName,
                    "riotTagLine" : tagline,
                    "regionId": "euw1",
                    "role": 7,
                    "seasonId": 21,
                    "queueType": [420],
                },
                "query": "query getPlayerStats($queueType: [Int!], $regionId: String!, $role: [Int!], $seasonId: Int!, $riotUserName: String!, $riotTagLine : String!) {\n  fetchPlayerStatistics(\n    queueType: $queueType\n    riotUserName: $riotUserName\n    riotTagLine: $riotTagLine\n      regionId: $regionId\n    role: $role\n    seasonId: $seasonId\n  ) {\n    basicChampionPerformances {\n      assists\n      championId\n      cs\n      damage\n      damageTaken\n      deaths\n      gold\n      kills\n      totalMatches\n      wins\n      lpAvg\n    }\n    exodiaUuid\n    puuid\n    queueType\n    regionId\n    role\n    seasonId\n    __typename\n  }\n}"
            }

        async with session.post(url, headers=headers, json=payload) as session_match_detail:
            response = await session_match_detail.json()  # detail du match sélectionné

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
