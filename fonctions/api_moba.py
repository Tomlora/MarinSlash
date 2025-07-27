import time
import sys
import os
import traceback
from aiohttp import ClientSession
import pandas as pd
import asyncio
from utils.params import api_key_lol, my_region, region, api_moba, url_api_moba


def split_riot_id(pseudo):
    if "#" in pseudo:
        game_name, tag_line = pseudo.split("#", 1)
    else:
        game_name, tag_line = pseudo, ""
    return game_name, tag_line


async def update_moba(session, gameName, tagLine, source="WEB"):
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
    async with session.post(url_api_moba, headers=headers, json=payload) as resp:
        result = await resp.json()
        return result

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

    while attempts < 5:
        try:

          async with session.post(url_api_moba, headers=headers, json=json_data) as resp:
            result = await resp.json()
            break 
        
        except:
            attempts += 1
            await asyncio.sleep(5) 

            if attempts >= 5:
                return ''

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

    attemps = 0

    while attemps < 5:
        try:
          async with session.post(url, headers=headers, json=json_data) as resp:
              res_json = await resp.json()

              roles = res_json['data']['lol']['player']['rolesStats']['roles']



              df = pd.DataFrame(roles)
              df = df[df['queue'] == 'RANKED_SOLO']
              df['nbgames'] = df['wins'] + df['looses']
              df['poids_role'] = df['nbgames'] / df['nbgames'].sum() * 100

              break
        
        except (KeyError, TypeError):
            attemps += 1
            await asyncio.sleep(5)

            if attemps >= 5:
                return pd.DataFrame()
            
    
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
async def get_player_match_history_moba(session, riot_id, riot_tag, top=20, skip=0, region="EUW"):


    query = """
query PlayerMatchHistory($region: Region!, $gameName: String!, $tagLine: String!, $top: Int!, $skip: Int!) {
  lol {
    player(region: $region, gameName: $gameName, tagLine: $tagLine) {
      matchesHistory(
        top: $top,
        skip: $skip,
        filter: { queue: RANKED_SOLO }
      ) {
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


async def get_stat_champion_by_player_mobalytics(session, riot_id, riot_tag):
    url_api_moba = "https://stg.mobalytics.gg/api/lol/graphql/v1/query"

    query = """
    query LolPlayerChampionsStats($region: Region!, $gameName: String!, $tagLine: String!) {
      lol {
        player(region: $region, gameName: $gameName, tagLine: $tagLine) {
          championsMatchups(
            filter: {queue : RANKED_SOLO }
            sort: { items: [{ sort: DESC, field: GAMES }] },
            mode: Best,
            top: 1000,
            skip: 0
          ) {
            items {
              championId
              role
              wins
              looses
              kda { kills deaths assists }
              csm
              damagePerMinute
              gpm
              cs
              wards
              lp
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
    json_data = {
        'query': query,
        'variables': variables
    }
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0',
    }

    async with session.post(url_api_moba, headers=headers, json=json_data) as resp:
        result = await resp.json()
        try:
            items = result['data']['lol']['player']['championsMatchups']['items']
            df = pd.DataFrame(items)
            # Aplatir le dict kda
            if not df.empty and 'kda' in df.columns:
                df_kda = df['kda'].apply(pd.Series)
                df = pd.concat([df.drop('kda', axis=1), df_kda], axis=1)
            # Calcul colonne "totalMatches"
            if not df.empty:
                df["totalMatches"] = df["wins"] + df["looses"]
            return df
        except Exception as e:
            # Tu peux log l'erreur ici si tu veux
            return pd.DataFrame()

# df_data_stat = await get_stat_champion_by_player_mobalytics(client, 'tomlora', 'EUW')



# async def get_rank_moba(session, riot_id, riot_tag):

#     query = """
#     query LolSearchQuery($region: Region!, $text: ID!) {
#       search(region: $region, text: $text) {
#         summoners {
#           gameName
#           tagLine
#           icon
#           region
#           queue {
#             tier
#             division
#             lp
#           }
#         }
#       }
#     }
#     """

#     variables = {
#         "region": "EUW",    # Adapter la région si besoin
#         "text": f"{riot_id}#{riot_tag}"  # Adapter le nom du joueur
#     }

#     headers = {
#         "User-Agent": "Mozilla/5.0",
#         "Content-Type": "application/json"
#     }

#     payload = {
#         "query": query,
#         "variables": variables
#     }

#     attemps = 0

#     # while attemps < 5:
#     #     try:
#     async with session.post(url_api_moba, headers=headers, json=payload) as resp:
#                 result = await resp.json()

#     tier = result['data']['search']['summoners'][0]['queue']['tier']
#     rank = result['data']['search']['summoners'][0]['queue']['division']

#         #   break
        
#         # except:
#         #     attemps += 1
#         #     await asyncio.sleep(5)

#         #     if attemps >= 5:
#         #         tier = ''
#         #         rank = ''
    
#     return tier, rank


async def get_rank_moba(session, riot_id, riot_tag):

    query = """
    query GetPlayerQueuesStats(
      $region: Region!,
      $gameName: String!,
      $tagLine: String!
    ) {
      lol {
        player(region: $region, gameName: $gameName, tagLine: $tagLine) {
          queuesStats {
            items {
              virtualQueue
              rank {
                tier
                division
              }
              lp
              wins
              losses
              winrate
              gamesCount
            }
          }
        }
      }
    }
    """

    variables = {
        "region": "EUW",
        "gameName": riot_id,
        "tagLine":  riot_tag
    }

    headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json"
        }

    payload = {
            "query": query,
            "variables": variables
        }

    attemps = 0


    division_map = {
        '1': 'I',
        '2': 'II',
        '3': 'III',
        '4': 'IV'
    }



    while attemps < 5:
      try:
          async with session.post(url_api_moba, headers=headers, json=payload) as resp:
                          result = await resp.json()



          queues = result['data']['lol']['player']['queuesStats']['items']

          # On filtre seulement RANKED_SOLO
          solo = [q for q in queues if q['virtualQueue'] == 'RANKED_SOLO']



          # Tu peux accéder au premier (si tu veux un seul dict)
          if solo:
              tier = solo[0]['rank']['tier']
              division = str(solo[0]['rank']['division'])
              rank = division_map.get(division, division)
              lp = solo[0]['lp']


        
          break

      except:
          attemps += 1
          await asyncio.sleep(5)

          if attemps >= 5:
            return '', '', 0
        
    return tier, rank, lp



async def test_mobalytics_api():

    query = """
    query LolPlayerChampionsStats($region: Region!, $gameName: String!, $tagLine: String!) {
      lol {
        player(region: $region, gameName: $gameName, tagLine: $tagLine) {
          gameName
          tagLine
          region
        }
      }
    }
    """
    variables = {
        "region": 'EUW',
        "gameName": 'Tomlora',
        "tagLine": 'EUW'
    }
    json_data = {"query": query, "variables": variables}
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    async with ClientSession() as session:
        try:
            async with session.post(url_api_moba, headers=headers, json=json_data, timeout=8) as resp:
                res = await resp.json()
                player = res.get('data', {}).get('lol', {}).get('player')
                if player is None:
                    return f"""❌ L'API Mobalytics ne retourne aucun joueur (player=None).\n Vérifie le pseudo/tag/région, ou que l'API est bien disponible.\n Erreur brute : {res}"""
                    
                else:
                    return f"""✅ L'API Mobalytics répond !\n Trouvé : {player['gameName']}#{player['tagLine']} (région: {player['region']})"""
        except Exception as e:
            return f"❌ Exception lors de l'appel API : {e}"


