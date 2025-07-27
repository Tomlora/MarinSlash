import interactions
from interactions import SlashCommandOption, SlashCommandChoice, Extension, SlashContext, slash_command
import pandas as pd
from utils.params import Version
import aiohttp


class Anilist(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self.url = 'https://graphql.anilist.co'

    async def __extract_anime(self, term, session: aiohttp.ClientSession, page=1, perpage=3):
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

        async with session.post(self.url, json={'query': animeIDQS, 'variables': preset}) as anime:
            if anime.status != 200:
                raise Exception(f"Data post unsuccessful. ({anime.status})")
            try:
                extracted_data = await anime.json()
            except ValueError:
                return None
            except TypeError:
                return None
            else:
                return extracted_data

    @slash_command(
        name="anime_season",
        description="Calendrier des sorties",
        options=[
            SlashCommandOption(
                    name='nb_anime',
                    description="Combien d'animés ?",
                    type=interactions.OptionType.INTEGER,
                    required=False),
            SlashCommandOption(name='year',
                               description='Quelle année ?',
                               type=interactions.OptionType.INTEGER,
                               required=False,
                               min_value=1998,
                               max_value=2030),
            SlashCommandOption(name='season',
                               description='Quelle saison ?',
                               type=interactions.OptionType.STRING,
                               required=False,
                               choices=[
                                   SlashCommandChoice(
                                       name='hiver', value='WINTER'),
                                   SlashCommandChoice(
                                       name='printemps', value='SPRING'),
                                   SlashCommandChoice(
                                       name='ete', value='SUMMER'),
                                   SlashCommandChoice(
                                       name='automne', value='FALL')
                               ])
        ])
    async def anime_season(self,
                           ctx: SlashContext,
                           nb_anime: int = 10,
                           year=2022,
                           season: str = 'SUMMER'):
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

        await ctx.defer(ephemeral=False)

        session = aiohttp.ClientSession()

        preset = {"season": season, "seasonYear": year}

        async with session.post(self.url,
                                json={'query': anime_season, 'variables': preset}) as anime:

            if anime.status != 200:
                raise Exception(f"Data post unsuccessful. ({anime.reason})")

            try:
                self.schedule = await anime.json()
            except ValueError:
                return None
            except TypeError:
                return None
            else:
                self.schedule = await anime.json()

        name_anime = []
        airing = []
        airing_restant = []
        nb_ep = []
        cover_img = []
        for anime in self.schedule['data']['Page']['media']:
            if anime['nextAiringEpisode'] != None:  # déjà sorti sinon
                name_anime.append(anime['title']['romaji'])
                airing.append(anime['nextAiringEpisode']['airingAt'])
                airing_restant.append(
                    anime['nextAiringEpisode']['timeUntilAiring'])
                nb_ep.append(anime['nextAiringEpisode']['episode'])
                cover_img.append(anime['coverImage']['medium'])

        pd_anime = pd.DataFrame({'Nom': name_anime, 'Date': airing,
                                'Restant': airing_restant, 'Ep': nb_ep, 'Cover': cover_img})
        pd_anime.sort_values(by=['Date'], ascending=True, inplace=True)

        embed = interactions.Embed(
            title=f"** Schedule Anime **")

        for key, value in pd_anime.head(nb_anime).iterrows():
            name = value['Nom']
            date = value['Date']
            ep = value['Ep']
            embed.add_field(name=f' {name} (Ep {ep})',
                            value=f'Disponible dans <t:{date}:R>')

        embed.set_footer(text=f'Version {Version} by Tomlora')

        await ctx.send(embeds=embed)

        await session.close()

    async def _get_anime_id(self, sQ, session):
        anime_list = []
        data = await self.__extract_anime(sQ, session)
        for i in range(len(data['data']['Page']['media'])):
            curr_anime = data['data']['Page']['media'][i]['title']['romaji']
            anime_list.append(curr_anime)

        # returns the first anime found
        try:
            anime_ID = data['data']['Page']['media'][0]['id']
        except IndexError:
            anime_ID = "Not found"

        return anime_ID

    @slash_command(name="anime", description="Cherche un anime",
                   options=[SlashCommandOption(
                       name='anime',
                       description="nom de l'animé",
                       type=interactions.OptionType.STRING,
                       required=True
                   )])
    async def anime(self,
                    ctx: SlashContext,
                    anime):
        self.id = anime

        session = aiohttp.ClientSession()
        ctx.defer(ephemeral=False)

        self.name = await self._get_anime_id(self.id, session)

        if self.name == "Not found":
            ctx.send(f'{anime} non trouvé')

            # graphql api query
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
        studios (isMain : true) {
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

        embed = interactions.Embed(title='Anime')

        session = aiohttp.ClientSession()
        async with session.post(self.url, json={'query': query, 'variables': variables}) as anime:
            response = await anime.json()

        answer_complete = response["data"]["Page"]["media"][0]
        name = answer_complete['title']['romaji']
        description = answer_complete['description'].replace(
            "<br>", "")[:900]  # on veut éviter une description trop longue
        nb_ep = answer_complete['episodes']
        genres = ', '.join(answer_complete['genres'])
        cover = answer_complete['coverImage']['medium']
        season = answer_complete['season']
        year = answer_complete['seasonYear']
        score = answer_complete['averageScore']
        studios = answer_complete['studios']['nodes'][0]['name']

        embed.set_thumbnail(url=cover)

        embed.add_field(name=f'{name} (Studio : {studios})',
                        value=description, inline=False)
        embed.add_field(name="Nb episodes", value=nb_ep)
        embed.add_field(name="Saison", value=f'{season} {year}')
        embed.add_field(name="Note", value=f'{score}')
        embed.add_field(name="Genres", value=genres, inline=False)

        embed.set_footer(text=f'Version {Version} by Tomlora')

        await ctx.send(embeds=embed)

        await session.close()


def setup(bot):
    Anilist(bot)
