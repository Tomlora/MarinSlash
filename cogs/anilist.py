import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice
import requests
import json
import pandas as pd
from main import Var_version





class Anilist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url = 'https://graphql.anilist.co'
        
        
    def __extract_anime(self, term, page=1, perpage=3):
      animeIDQS = """\
            query ($query: String, $page: Int, $perpage: Int) {
                Page (page: $page, perPage: $perpage) {
                    pageInfo {
                        total
                        currentPage
                        lastPage
                        hasNextPage
                    }
                    media (search: $query, type: ANIME) {
                        id
                        title {
                            romaji
                            english
                        }
                        coverImage {
                            large
                        }
                        averageScore
                        popularity
                        episodes
                        season
                        hashtag
                        isAdult
                    }
                }
            }
        """
      preset = {"query": term, "page": page, "perpage": perpage}
      req = requests.post(self.url,
                          json={'query': animeIDQS, 'variables': preset})

      if req.status_code != 200:
            raise Exception(f"Data post unsuccessful. ({req.status_code})")

      try:
          extracted_data = json.loads(req.text)
      except ValueError:
          return None
      except TypeError:
          return None
      else:
          return extracted_data
      
    @cog_ext.cog_slash(name="anime_season", description="Calendrier des sorties")
    async def anime_season(self, ctx, nb_anime:int=10):
        season = "SUMMER"
        year = 2022
        anime_season = """\
        query ($season : MediaSeason, $seasonYear : Int) {
    Page {
        media(season : $season, seasonYear : $seasonYear, type: ANIME) {
        id
        title {
            romaji
            english
            native
        }
        episodes
        description
        format
        status
        duration
        genres
        tags {
            name
        }
        studios {
            nodes {
            name
            }
        }
        startDate {
            year
            month
            day
        }
        endDate {
            year
            month
            day
        }
        season
        seasonYear
        seasonInt
        countryOfOrigin
        coverImage {
            medium
            large
            extraLarge
        }
        bannerImage
        source
        hashtag
        synonyms
        meanScore
        averageScore
        nextAiringEpisode {
            timeUntilAiring
            airingAt
        }
        trailer {
            id
            thumbnail
            site
        }
        staff(sort: FAVOURITES_DESC) {
            edges {
            node {
                name {
                full
                }
                id
            }
            }
        }
        characters(role: MAIN) {
            edges {
            node {
                name {
                full
                }
            }
            }
        }
        nextAiringEpisode {
            episode
            timeUntilAiring
            airingAt
        }
        }
    }
    }
            """
            
        ctx.defer(hidden=False)
         
        preset = {"season": season, "seasonYear": year}
        req = requests.post(self.url,
                                json={'query': anime_season, 'variables': preset})

        if req.status_code != 200:
                raise Exception(f"Data post unsuccessful. ({req.reason})")

        try:
            extracted_data = json.loads(req.text)
            self.schedule = extracted_data
        except ValueError:
            return None
        except TypeError:
            return None
        else:
            self.schedule = extracted_data  
                
        name_anime = []
        airing = []
        airing_restant = []
        nb_ep = []
        cover_img = []
        for anime in self.schedule['data']['Page']['media']:
            if anime['nextAiringEpisode'] != None: # déjà sorti sinon
                name_anime.append(anime['title']['romaji'])
                airing.append(anime['nextAiringEpisode']['airingAt'])
                airing_restant.append(anime['nextAiringEpisode']['timeUntilAiring'])
                nb_ep.append(anime['nextAiringEpisode']['episode'])
                cover_img.append(anime['coverImage']['medium'])
                
        pd_anime = pd.DataFrame({'Nom' : name_anime, 'Date' : airing, 'Restant' : airing_restant, 'Ep' : nb_ep, 'Cover' : cover_img})
        pd_anime.sort_values(by=['Date'], ascending=True, inplace=True)
        
        embed = discord.Embed(
                title=f"** Schedule Anime **") 
        
        for key, value in pd_anime.head(nb_anime).iterrows():
            name = value['Nom']
            date = value['Date']
            ep = value['Ep']
            embed.add_field(name=f' {name} (Ep {ep})', value=f'Disponible dans <t:{date}:R>')
            
        embed.set_footer(text=f'Version {Var_version} by Tomlora')
            
        await ctx.send(embed=embed)
            
    def _get_anime_id(self, sQ):
        anime_list = []
        data = self.__extract_anime(sQ)
        for i in range(len(data['data']['Page']['media'])):
            curr_anime = data['data']['Page']['media'][i]['title']['romaji']
            anime_list.append(curr_anime)

        # returns the first anime found
        try:
            anime_ID = data['data']['Page']['media'][0]['id']
        except IndexError:
            anime_ID = "Not found"

        return anime_ID
        
    # à faire    
    async def anime(self, ctx, anime):
        self.id = anime
        self.name = self._get_anime_id(self.id)
        
        if self.name == "Not found":
            ctx.send(f'{anime} non trouvé')
        
        ctx.defer(hidden=False)
            #graphql api query
        query = '''
    query ($id: Int, $page: Int, $perPage: Int, $search: String) {
    Page(page: $page, perPage: $perPage) {
        media(id: $id, search: $search, type: ANIME) {
        id
        title {
            romaji
            english
            native
        }
        episodes
        description
        format
        status
        duration
        genres
        tags {
            name
        }
        studios {
            nodes {
            name
            }
        }
        startDate {
            year
            month
            day
        }
        endDate {
            year
            month
            day
        }
        season
        seasonYear
        seasonInt
        countryOfOrigin
        coverImage {
            medium
            large
            extraLarge
        }
        bannerImage
        source
        hashtag
        synonyms
        meanScore
        averageScore
        nextAiringEpisode {
            timeUntilAiring
            airingAt
        }
        trailer {
            id
            thumbnail
            site
        }
        staff(sort: FAVOURITES_DESC) {
            edges {
            node {
                name {
                full
                }
                id
            }
            }
        }
        characters(role: MAIN) {
            edges {
            node {
                name {
                full
                }
            }
            }
        }
        }
    }
    }
        '''

        variables = {'id': self.name}
        
        embed = discord.Embed(title='Anime') 

        response = requests.post(self.url, json={'query': query, 'variables': variables})
        answer_complete = json.loads(response.text)["data"]["Page"]["media"][0]
        name = answer_complete['title']['romaji']
        description = answer_complete['description']
        nb_ep = answer_complete['episodes']
        genres = ', '.join(answer_complete['genres'])
        cover = answer_complete['coverImage']['medium']
        season = answer_complete['season']
        year = answer_complete['seasonYear']
        score = answer_complete['averageScore']
        
        embed.set_thumbnail(url=cover)
        
        embed.add_field(name=name, value=description, inline=False)
        embed.add_field(name="Nb episodes", value=nb_ep)
        embed.add_field(name="Saison", value=f'{season} {year}')
        embed.add_field(name="Note", value=f'{score}')
        embed.add_field(name="Genres", value=genres, inline=False)
            
        embed.set_footer(text=f'Version {Var_version} by Tomlora')
        
        
        await ctx.send(embed=embed)
        

def setup(bot):
    bot.add_cog(Anilist(bot))