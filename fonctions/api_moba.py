import time
import sys
import os
import traceback
from aiohttp import ClientSession
import pandas as pd


api_moba = os.environ.get('API_moba')
url_api_moba = os.environ.get('url_moba')

api_key_lol = os.environ.get('API_LOL')
my_region = 'euw1'
region = "EUROPE"


def split_riot_id(pseudo):
    if "#" in pseudo:
        game_name, tag_line = pseudo.split("#", 1)
    else:
        game_name, tag_line = pseudo, ""
    return game_name, tag_line

async def get_mobalytics(pseudo: str, session, match_id):
    

    query = """
query LolMatchDetailsQuery($region: Region!, $gameName: String!, $tagLine: String!, $matchId: Int!) {
  lol {
    player(region: $region, gameName: $gameName, tagLine: $tagLine) {
      match(matchId: $matchId) {
        id
        seasonId
        queue
        startedAt
        duration
        patch
        teams {
          avgTier {
            tier
            division
          }
        }
        participants {
          gameName
          tagLine
          region
          championId
          championLevel
          team
          role
        }
      }
    }
  }
}
    """

    game_name, tag_line = split_riot_id(pseudo)

    variables = {
        'region': 'EUW',
        'gameName': game_name,
        'tagLine': tag_line,
        'matchId': int(match_id),
    }

    json_data = {
        'query': query,
        'variables': variables
    }

    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0',
    }

    attempts = 0

    async with session.post(url_api_moba, headers=headers, json=json_data) as resp:
      result = await resp.json()

      return result


    attempts = 0
    while attempts < 5:
        try:
            async with session.post(url_api_moba, headers={'authority':'app.mobalytics.gg','accept':'*/*','accept-language':'en_us','content-type':'application/json','origin':'https://app.mobalytics.gg','sec-ch-ua-mobile':'?0','sec-ch-ua-platform':'"Windows"','sec-fetch-dest':'empty','sec-fetch-mode':'cors','sec-fetch-site':'same-origin','sec-gpc':'1','x-moba-client':'mobalytics-web','x-moba-proxy-gql-ops-name':'LolMatchDetailsQuery'}, json=json_data) as session_match_detail:
                match_detail_stats = await session_match_detail.json()  # detail du match sélectionné
                df_moba = pd.DataFrame(match_detail_stats['data']['lol']['player']['match']['participants'])
        except:
            attempts += 1

            if attempts >= 5:
                async with session.post(url_api_moba, headers={'authority':'app.mobalytics.gg','accept':'*/*','accept-language':'en_us','content-type':'application/json','origin':'https://app.mobalytics.gg','sec-ch-ua-mobile':'?0','sec-ch-ua-platform':'"Windows"','sec-fetch-dest':'empty','sec-fetch-mode':'cors','sec-fetch-site':'same-origin','sec-gpc':'1','x-moba-client':'mobalytics-web','x-moba-proxy-gql-ops-name':'LolMatchDetailsQuery'}, json=json_data) as session_match_detail:
                    match_detail_stats = await session_match_detail.json()  # detail du match sélectionné
                    df_moba = pd.DataFrame(match_detail_stats['data']['lol']['player']['match']['participants'])

    return df_moba, match_detail_stats



async def update_moba(session, gameName, tagLine, source="WEB"):
    url = "https://stg.mobalytics.gg/api/lol/graphql/v1/query"
    mutation = """
    mutation LolRefreshProfilesMutation($input: LolRefreshProfilesInput!) {
      lol {
        refreshProfiles(input: $input) {
          notificationsDetails
          errors {
            message
          }
        }
      }
    }
    """
    payload = {
        "query": mutation,
        "variables": {
            "input": {
                "source": source,
                "inputs": [{
                    "region": 'EUW',
                    "gameName": gameName,
                    "tagLine": tagLine
                }]
            }
        }
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    async with session.post(url, headers=headers, json=payload) as resp:
        result = await resp.json()
        return result


async def get_wr_ranked(session, riot_id, riot_tag):

    query = """
    query LolPlayerQueuesStatsType($region: Region!, $gameName: String!, $tagLine: String!) {
      lol {
        player(region: $region, gameName: $gameName, tagLine: $tagLine) {
          queuesStats {
            items {
              __typename
              wins
              losses
              winrate
              gamesCount
              virtualQueue
            }
          }
        }
      }
    }
    """

    variables = {
        "region": "EUW",
        "gameName": riot_id,
        "tagLine": riot_tag
    }

    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0',
    }

    json_data = {
        "query": query,
        "variables": variables,
    }

    async with session.post(url_api_moba, headers=headers, json=json_data) as resp:
        return await resp.json()

async def get_role_stats(session, game_name, tag_line, region='EUW'):
    url = "https://stg.mobalytics.gg/api/lol/graphql/v1/query"
    query = """
    query GetPlayerRoleStats($region: Region!, $gameName: String!, $tagLine: String!) {
      lol {
        player(region: $region, gameName: $gameName, tagLine: $tagLine) {
          rolesStats {
            roles {
              queue
              role
              wins
              looses

            }
          }
        }
      }
    }
    """
    variables = {
        'region': region,
        'gameName': game_name,
        'tagLine': tag_line,
    }
    json_data = {'query': query, 'variables': variables}
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0',
    }
    async with session.post(url, headers=headers, json=json_data) as resp:
        res_json = await resp.json()
        try:
            roles = res_json['data']['lol']['player']['rolesStats']['roles']
        except (KeyError, TypeError):
            return pd.DataFrame()  # Retourne un DF vide si problème


        df = pd.DataFrame(roles)
        df['nbgames'] = df['wins'] + df['looses']
        df['poids_role'] = df['nbgames'] / df['nbgames'].sum() * 100
        return df



#### Detection Victoire/Defaite 


def detect_win_streak(match_list, pseudo, tag):
    # On suppose que match_list est trié du plus récent au plus vieux
    streak_result = None  # "WON" ou "LOST"
    streak_count = 0

    for match in match_list:
        # Trouver le participant
        found = None
        for p in match['participants']:
            if p['gameName'].lower() == pseudo.lower() and p['tagLine'].lower() == tag.lower():
                found = p
                break

        if not found:
            continue  # Pas trouvé, on skip

        player_team = found['team']
        # Chercher le résultat de la team
        team_result = next((t['result'] for t in match['teams'] if t['id'] == player_team), None)
        if not team_result:
            continue  # Erreur structure

        # Initialiser la streak sur le premier match
        if streak_result is None:
            streak_result = team_result
            streak_count = 1
        elif team_result == streak_result:
            streak_count += 1
        else:
            break  # Fin de série

    mot = "Victoire" if streak_result == "WON" else "Défaite"
    return {"mot": mot, "count": streak_count}




# Appel asynchrone de l'API Mobalytics
async def get_player_match_history(session, riot_id, riot_tag, top=20, skip=0, region="EUW"):


    query = """
query PlayerMatchHistory($region: Region!, $gameName: String!, $tagLine: String!, $top: Int!, $skip: Int!) {
  lol {
    player(region: $region, gameName: $gameName, tagLine: $tagLine) {
      matchesHistory(top: $top, skip: $skip) {
        matches {
          id
          startedAt
          duration
          queue
          teams {
            id
            result
          }
          participants {
            gameName
            tagLine
            team
          }
        }
      }
    }
  }
}

    """
    variables = {
        "region": region,
        "gameName": riot_id,
        "tagLine": riot_tag,
        "top": int(top),
        "skip": int(skip)
    }
    json_data = {"query": query, "variables": variables}
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    async with session.post(url_api_moba, headers=headers, json=json_data) as resp:
        res = await resp.json()
        return res['data']['lol']['player']['matchesHistory']['matches']


# Exemple d'utilisation :
# serie = detect_win_streak(matches, pseudo="Tomlora", tag="EUW")
