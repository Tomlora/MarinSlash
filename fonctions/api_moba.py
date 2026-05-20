import asyncio
import pandas as pd
from curl_cffi.requests import AsyncSession
from utils.params import api_key_lol, my_region, region, api_moba, url_api_moba as URL_API_MOBA


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) "
    "Gecko/20100101 Firefox/150.0"
)


# Sécurité : si utils.params pointe encore vers stg.mobalytics.gg,
# on force l'endpoint prod qui a fonctionné avec curl_cffi.
if "stg.mobalytics.gg" in URL_API_MOBA:
    URL_API_MOBA = "https://mobalytics.gg/api/lol/graphql/v1/query"


def split_riot_id(pseudo):
    if "#" in pseudo:
        game_name, tag_line = pseudo.split("#", 1)
    else:
        game_name, tag_line = pseudo, ""
    return game_name, tag_line


from urllib.parse import quote

def make_referer(game_name, tag_line, region="EUW"):
    profile_slug = f"{game_name.lower()}-{tag_line.lower()}"
    safe_profile_slug = quote(profile_slug, safe="")

    return (
        f"https://mobalytics.gg/lol/profile/"
        f"{region.lower()}/{safe_profile_slug}/overview"
    )


async def moba_post(operation_name, query, variables, referer=None, attempts_max=5, timeout=30):
    headers = {
        "accept": "*/*",
        "accept-language": "en_us",
        "content-type": "application/json",
        "origin": "https://mobalytics.gg",
        "referer": referer or "https://mobalytics.gg/",
        "user-agent": USER_AGENT,
        "x-moba-client": "mobalytics-web",
        "x-moba-proxy-gql-ops-name": operation_name,
    }

    payload = {
        "operationName": operation_name,
        "query": query,
        "variables": variables,
    }

    last_error = None

    for attempt in range(attempts_max):
        try:
            async with AsyncSession(impersonate="chrome120") as curl_session:
                response = await curl_session.post(
                    URL_API_MOBA,
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )

            content_type = response.headers.get("content-type", "")

            if response.status_code == 403 and "Just a moment" in response.text:
                raise RuntimeError("Bloqué par Cloudflare.")

            if response.status_code >= 400:
                raise RuntimeError(
                    f"Erreur HTTP {response.status_code}\n"
                    f"Content-Type: {content_type}\n"
                    f"Réponse:\n{response.text[:1000]}"
                )

            if "application/json" not in content_type:
                raise RuntimeError(
                    f"Réponse non JSON\n"
                    f"Content-Type: {content_type}\n"
                    f"Réponse:\n{response.text[:1000]}"
                )

            data = response.json()

            if data.get("errors"):
                raise RuntimeError(f"Erreur GraphQL: {data['errors']}")

            return data

        except Exception as exc:
            last_error = exc

            if attempt < attempts_max - 1:
                await asyncio.sleep(5)
            else:
                raise RuntimeError(
                    f"Échec Mobalytics après {attempts_max} tentatives: {last_error}"
                ) from last_error


async def update_moba(session, game_name, tag_line, source="WEB"):
    # session conservé volontairement pour compatibilité avec ton code existant.
    _ = session

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

    variables = {
        "input": {
            "source": source,
            "inputs": [
                {
                    "region": "EUW",
                    "gameName": game_name,
                    "tagLine": tag_line,
                }
            ],
        }
    }

    data = await moba_post(
        operation_name="LolRefreshProfilesMutation",
        query=mutation,
        variables=variables,
        referer=make_referer(game_name, tag_line),
    )

    refresh = data.get("data", {}).get("lol", {}).get("refreshProfiles", {})
    errors = refresh.get("errors") or []
    real_errors = [error for error in errors if error is not None]

    if real_errors:
        raise RuntimeError(f"Erreur Mobalytics: {real_errors}")

    return refresh


async def get_mobalytics(pseudo: str, session, match_id, attempts_max=5):
    # session conservé volontairement pour compatibilité avec ton code existant.
    _ = session

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
        "region": "EUW",
        "gameName": game_name,
        "tagLine": tag_line,
        "matchId": int(match_id),
    }

    try:
        return await moba_post(
            operation_name="LolMatchDetailsQuery",
            query=query,
            variables=variables,
            referer=make_referer(game_name, tag_line),
            attempts_max=attempts_max,
        )
    except Exception as exc:
        print(f"Échec get_mobalytics après {attempts_max} tentatives: {exc}")
        return ""


async def get_wr_ranked(session, riot_id, riot_tag):
    # session conservé volontairement pour compatibilité avec ton code existant.
    _ = session

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
        "tagLine": riot_tag,
    }

    return await moba_post(
        operation_name="LolPlayerQueuesStatsType",
        query=query,
        variables=variables,
        referer=make_referer(riot_id, riot_tag),
    )


async def get_role_stats(session, game_name, tag_line, region="EUW"):
    # session conservé volontairement pour compatibilité avec ton code existant.
    _ = session

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
        "region": region,
        "gameName": game_name,
        "tagLine": tag_line,
    }

    try:
        res_json = await moba_post(
            operation_name="GetPlayerRoleStats",
            query=query,
            variables=variables,
            referer=make_referer(game_name, tag_line, region),
            attempts_max=5,
        )

        roles = (
            res_json
            .get("data", {})
            .get("lol", {})
            .get("player", {})
            .get("rolesStats", {})
            .get("roles", [])
        )

        if not roles:
            return pd.DataFrame()

        df = pd.DataFrame(roles)
        df = df[df["queue"] == "RANKED_SOLO"].copy()

        if df.empty:
            return df

        df["nbgames"] = df["wins"] + df["looses"]
        total_games = df["nbgames"].sum()
        df["poids_role"] = 0 if total_games == 0 else df["nbgames"] / total_games * 100

        return df

    except Exception:
        return pd.DataFrame()


def detect_win_streak(match_list, pseudo, tag):
    """
    Détecte la série actuelle de victoires ou défaites d'un joueur.

    match_list doit être triée du match le plus récent au plus ancien.
    Retourne par exemple:
    {"mot": "Victoire", "count": 3, "result": "WON"}
    """

    streak_result = None
    streak_count = 0

    pseudo = pseudo.lower()
    tag = tag.lower()

    for match in match_list:
        participants = match.get("participants", [])
        teams = match.get("teams", [])

        found = next(
            (
                p for p in participants
                if p.get("gameName", "").lower() == pseudo
                and p.get("tagLine", "").lower() == tag
            ),
            None,
        )

        if not found:
            continue

        player_team = found.get("team")
        team_result = next(
            (t.get("result") for t in teams if t.get("id") == player_team),
            None,
        )

        if team_result not in ("WON", "LOST"):
            continue

        if streak_result is None:
            streak_result = team_result
            streak_count = 1
        elif team_result == streak_result:
            streak_count += 1
        else:
            break

    if streak_result is None:
        return {"mot": None, "count": 0, "result": None}

    mot = "Victoire" if streak_result == "WON" else "Défaite"
    return {"mot": mot, "count": streak_count, "result": streak_result}


async def get_player_match_history_moba(
    session,
    riot_id,
    riot_tag,
    top=20,
    skip=0,
    region="EUW",
):
    # session conservé volontairement pour compatibilité avec ton code existant.
    _ = session

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
        "skip": int(skip),
    }

    res_json = await moba_post(
        operation_name="PlayerMatchHistory",
        query=query,
        variables=variables,
        referer=make_referer(riot_id, riot_tag, region),
        attempts_max=5,
    )

    return (
        res_json
        .get("data", {})
        .get("lol", {})
        .get("player", {})
        .get("matchesHistory", {})
        .get("matches", [])
    )


async def get_stat_champion_by_player_mobalytics(session, riot_id, riot_tag, region="EUW"):
    # session conservé volontairement pour compatibilité avec ton code existant.
    _ = session

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
              kda {
                kills
                deaths
                assists
              }
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
        "region": region,
        "gameName": riot_id,
        "tagLine": riot_tag,
    }

    try:
        result = await moba_post(
            operation_name="LolPlayerChampionsStats",
            query=query,
            variables=variables,
            referer=make_referer(riot_id, riot_tag, region),
            attempts_max=5,
        )

        items = (
            result
            .get("data", {})
            .get("lol", {})
            .get("player", {})
            .get("championsMatchups", {})
            .get("items", [])
        )

        df = pd.DataFrame(items)

        if df.empty:
            return df

        if "kda" in df.columns:
            df_kda = df["kda"].apply(pd.Series)
            df = pd.concat([df.drop("kda", axis=1), df_kda], axis=1)

        df["totalMatches"] = df["wins"] + df["looses"]
        return df

    except Exception:
        return pd.DataFrame()


async def get_rank_moba(session, riot_id, riot_tag, region="EUW"):
    # session conservé volontairement pour compatibilité avec ton code existant.
    _ = session

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
        "region": region,
        "gameName": riot_id,
        "tagLine": riot_tag,
    }

    division_map = {
        "1": "I",
        "2": "II",
        "3": "III",
        "4": "IV",
    }

    try:
        result = await moba_post(
            operation_name="GetPlayerQueuesStats",
            query=query,
            variables=variables,
            referer=make_referer(riot_id, riot_tag, region),
            attempts_max=5,
        )

        queues = (
            result
            .get("data", {})
            .get("lol", {})
            .get("player", {})
            .get("queuesStats", {})
            .get("items", [])
        )

        solo = [q for q in queues if q.get("virtualQueue") == "RANKED_SOLO"]

        if not solo:
            return "", "", 0

        solo_queue = solo[0]
        rank_data = solo_queue.get("rank") or {}

        tier = rank_data.get("tier") or ""
        division = str(rank_data.get("division") or "")
        rank = division_map.get(division, division)
        lp = solo_queue.get("lp") or 0

        return tier, rank, lp

    except Exception:
        return "", "", 0


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
        "region": "EUW",
        "gameName": "Tomlora",
        "tagLine": "EUW",
    }

    try:
        res = await moba_post(
            operation_name="LolPlayerChampionsStats",
            query=query,
            variables=variables,
            referer="https://mobalytics.gg/lol/profile/euw/tomlora-euw/overview",
            attempts_max=1,
            timeout=8,
        )

        player = res.get("data", {}).get("lol", {}).get("player")

        if player is None:
            return (
                "❌ L'API Mobalytics ne retourne aucun joueur (player=None).\n"
                "Vérifie le pseudo/tag/région, ou que l'API est bien disponible.\n"
                f"Erreur brute : {res}"
            )

        return (
            "✅ L'API Mobalytics répond !\n"
            f"Trouvé : {player['gameName']}#{player['tagLine']} "
            f"(région: {player['region']})"
        )

    except Exception as e:
        return f"❌ Exception lors de l'appel API : {e}"
