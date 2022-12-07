import os
import pandas as pd
import warnings
import interactions
from interactions import Option, Extension, CommandContext
from interactions.ext.tasks import create_task, IntervalTrigger
from fonctions.channels_discord import chan_discord, rgb_to_discord
import sys
from fonctions.params import Version
from fonctions.gestion_bdd import (lire_bdd,
                                   sauvegarde_bdd,
                                   get_data_bdd,
                                   requete_perso_bdd)
from fonctions.match import dict_rankid
import aiohttp

warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'


# https://www.youtube.com/watch?v=IolxqkL7cD8
api_key_tft = os.environ.get('API_tft')

my_region = 'euw1'
region = "europe"


async def get_summonertft_by_name(session: aiohttp.ClientSession, summonername):
    async with session.get(f'https://{my_region}.api.riotgames.com/tft/summoner/v1/summoners/by-name/{summonername}', params={'api_key': api_key_tft}) as session_summoner_tft:
        me = await session_summoner_tft.json()  # informations sur le joueur
    return me


async def get_stats_ranked(session: aiohttp.ClientSession, summonername):

    me = await get_summonertft_by_name(session, summonername)
    async with session.get(f'https://{my_region}.api.riotgames.com/tft/league/v1/entries/by-summoner/{me["id"]}', params={'api_key': api_key_tft}) as stats_ranked_tft:
        stats = await stats_ranked_tft.json()  # informations sur le joueur
    return stats


async def get_matchs_by_puuid(session, puuid):
    async with session.get(f'https://{region}.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids?start=0&count=20', params={'api_key': api_key_tft}) as matchs_tft:
        matchs = await matchs_tft.json()  # informations sur le joueur
    return matchs


async def get_matchs_details_tft(session, match_id):
    async with session.get(f'https://{region}.api.riotgames.com/tft/match/v1/matches/{match_id}', params={'api_key': api_key_tft}) as matchs_details:
        match_data = await matchs_details.json()  # informations sur le joueur
    return match_data


async def matchtft_by_puuid(summonerName, idgames: int, session):
    me = await get_summonertft_by_name(session, summonerName)
    puuid = me['puuid']
    liste_matchs = await get_matchs_by_puuid(session, puuid)
    last_match = liste_matchs[idgames]
    match = await get_matchs_details_tft(session, last_match)
    match = pd.DataFrame(match)
    return match, last_match, puuid


class tft(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    # ----------------------------- test

    @interactions.extension_listener
    async def on_start(self):
        self.task1 = create_task(IntervalTrigger(60*5))(self.updatetft)
        self.task1.start()

    async def stats_tft(self, summonername, session, idgames: int = 0, ):
        match_detail, id_match, puuid = await matchtft_by_puuid(summonername, idgames, session)

        # identifier le joueur via son puuid

        dic = {
            (match_detail['info']['participants'][0]['puuid']): 0,
            (match_detail['info']['participants'][1]['puuid']): 1,
            (match_detail['info']['participants'][2]['puuid']): 2,
            (match_detail['info']['participants'][3]['puuid']): 3,
            (match_detail['info']['participants'][4]['puuid']): 4,
            (match_detail['info']['participants'][5]['puuid']): 5,
            (match_detail['info']['participants'][6]['puuid']): 6,
            (match_detail['info']['participants'][7]['puuid']): 7,
        }

        thisQ = ' '

        thisId = dic[puuid]

        stats_joueur = match_detail['info']['participants'][thisId]

        # classé ?

        thisQId = match_detail['info']['queue_id']

        if thisQId == 1100:
            thisQ == "RANKED"
        else:
            thisQ == "NORMAL"

        # Durée

        thisTime = round(match_detail['info']['game_length'] / 60, 0)

        augments = stats_joueur['augments']

        msg_augment = ''

        for augment in augments:
            augment = augment.replace(
                'TFT6_Augment_', '').replace('TFT7_Augment_', '').replace('TFT8_Augment_', '')
            msg_augment = f'{msg_augment} | {augment}'

        # Classement

        classement = stats_joueur['placement']

        # Stats

        last_round = stats_joueur['last_round']
        level = stats_joueur['level']
        joueurs_elimines = stats_joueur['players_eliminated']
        gold_restants = stats_joueur['gold_left']

        # Stats

        try:
            profil = await get_stats_ranked(session, summonername)[0]
            ranked = True
            wins = profil['wins']
            losses = profil['losses']
            wr = round((wins/(int(wins)+int(losses)))*100, 0)
            tier = profil['tier']
            rank = profil['rank']
            lp = profil['leaguePoints']

            # Gain/Perte de LP

            try:
                suivi_profil = lire_bdd('suivitft', 'dict')
                lp_before_this_game = int(suivi_profil[summonername]['LP'])
                difLP = lp - lp_before_this_game
            except:
                lp_before_this_game = 0
                difLP = lp - lp_before_this_game

        except:

            wins = 0
            losses = 0
            wr = 0
            ranked = False

            tier = 'Non-classe'
            rank = '0'
            lp = 0
            difLP = 0

        summonername = summonername.lower()

        if ranked:
            if difLP > 0:
                difLP = "+" + str(difLP)
            elif difLP < 0:
                difLP = str(difLP)

            classement_old = suivi_profil[summonername]['tier'] + \
                " " + suivi_profil[summonername]['rank']
            classement_new = tier + " " + rank

            if dict_rankid[classement_old] > dict_rankid[classement_new]:  # 19-18
                difLP = 100 + lp - int(suivi_profil[summonername]['LP'])
                difLP = "Démote / -" + str(difLP)

            elif dict_rankid[classement_old] < dict_rankid[classement_new]:
                difLP = 100 - lp + int(suivi_profil[summonername]['LP'])
                difLP = "Promotion / +" + str(difLP)

            suivi_profil[summonername]['tier'] = tier
            suivi_profil[summonername]['rank'] = rank
            suivi_profil[summonername]['LP'] = lp

            sauvegarde_bdd(suivi_profil, 'suivitft')

        # Embed
        
        data = get_data_bdd(f'SELECT "R", "G", "B" from tracker WHERE index= :index', {
                            'index': summonername})
        data = data.fetchall()
        color = rgb_to_discord(data[0][0], data[0][1], data[0][2])

        summonername = summonername.upper()



        embed = interactions.Embed(
            title=f"** {summonername} ** vient de finir ** {classement}ème ** sur tft", color=color)

        embed.add_field(name="Durée de la game :",
                        value=f'{thisTime} minutes')
        
                # Stats
        if ranked:
            embed.add_field(name=f'Current rank : {tier} {rank} | {lp}LP ({difLP})',
                            value=f'winrate : {wr}% \nVictoires : {wins} | Defaites : {losses} ', inline=False)
        else:
            embed.add_field(name=f'Current rank : Non-classe',
                            value=f'En placement', inline=False)

        embed.add_field(name="Augments : ",
                        value=msg_augment, inline=False)

        # on va créer un dataframe pour les sort plus facilement

        df_traits = pd.DataFrame(stats_joueur['traits'])
        df_traits = df_traits.sort_values(by='tier_current', ascending=False)

        # [0] est l'index
        for set in df_traits.iterrows():
            name = set[1]['name'].replace('Set8_', '')
            tier_current = set[1]['tier_current']
            tier_total = set[1]['tier_total']
            nb_units = set[1]['num_units']

            embed.add_field(
                name=name, value=f"Tier: {tier_current} / {tier_total} \nNombre d'unités: {nb_units}", inline=True)

        # dic_rarity = {1 : "Blanc",
        #               2 : "Vert",
        #               3:"Bleu",
        #               4:"Violet",
        #               5:"Gold"}

        # pareil ici

        df_mobs = pd.DataFrame(stats_joueur['units'])
        df_mobs = df_mobs.sort_values(by='tier', ascending=False)

        for mob in df_mobs.iterrows():
            monster_name = mob[1]['character_id'].replace(
                'tft8_', '').replace('TFT8_', '')
            monster_tier = mob[1]['tier']
            embed.add_field(name=f'{monster_name}',
                            value=f':star: : {monster_tier}', inline=True)
            
        embed.add_field(name="Stats :bar_chart: : ", value=f':money_with_wings: : {gold_restants} \n\
                        Level : {level} \n\
                        Dernier round : {last_round}', inline=False)

        embed.set_footer(
            text=f'Version {Version} by Tomlora - Match {id_match}')

        return embed

    @interactions.extension_command(name="gametft",
                                    description="Recap tft",
                                    options=[Option(name="summonername",
                                                    description="Nom du joueur",
                                                    type=interactions.OptionType.STRING,
                                                    required=True),
                                             Option(name="idgames",
                                                    description="numero de la game",
                                                    type=interactions.OptionType.INTEGER,
                                                    required=False,
                                                    min_value=0,
                                                    max_value=10)])
    async def gametft(self, ctx: CommandContext, summonername, idgames: int = 0):

        await ctx.defer(ephemeral=False)

        session = aiohttp.ClientSession()

        embed = await self.stats_tft(summonername, session, idgames)

        await ctx.send(embeds=embed)

    async def printLivetft(self, summonername: str, discord_server_id: chan_discord, session):

        embed = await self.stats_tft(summonername, session, idgames=0)

        channel = await interactions.get(client=self.bot,
                                         obj=interactions.Channel,
                                         object_id=discord_server_id.tft)

        if embed != {}:
            await channel.send(embeds=embed)

    async def updatetft(self):

        session = aiohttp.ClientSession()
        data = get_data_bdd('''SELECT trackertft.index, trackertft.id, tracker.server_id from trackertft
                    INNER JOIN tracker on trackertft.index = tracker.index''')
        for joueur, id_game, server_id in data:

            match_detail, id_match, puuid = await matchtft_by_puuid(joueur, 0, session)

            if str(id_game) != id_match:  # value -> ID de dernière game enregistrée dans id_data != ID de la dernière game via l'API Rito / #key = summonername // value = numéro de la game
                try:

                    discord_server_id = chan_discord(server_id)
                    await self.printLivetft(joueur, discord_server_id, session)
                except:
                    print(f"erreur {joueur}")  # joueur qui a posé pb
                    print(sys.exc_info())  # erreur

                requete_perso_bdd(f'UPDATE trackertft SET id = :id WHERE index = :index', {
                                  'id': id_match, 'index': joueur})

        await session.close()

    @interactions.extension_command(name="tftadd",
                                    description="Ajoute le joueur au suivi",
                                    options=[Option(
                                        name="summonername",
                                        description="Nom du joueur",
                                        type=interactions.OptionType.STRING,
                                        required=True)])
    async def tftadd(self, ctx: CommandContext, *, summonername):
        # TODO : à simplifier
        # TODO : refaire tftremove
        session = aiohttp.ClientSession()
        data = lire_bdd('trackertft', 'dict')
        suivi_profil = lire_bdd('suivitft', 'dict')

        await ctx.defer(ephemeral=False)

        profil = get_stats_ranked(summonername)[0]

        tier = profil['tier']
        rank = profil['rank']
        lp = profil['leaguePoints']
        match_detail, id_match, puuid = await matchtft_by_puuid(summonername, 0, session)
        # ajout du summonername (clé) et de l'id de la dernière game(getId)
        data[summonername] = {'id': id_match}
        suivi_profil[summonername] = {'LP': lp, 'tier': tier, 'rank': rank}
        data = pd.DataFrame.from_dict(data, orient="index")
        suivi_profil = pd.DataFrame.from_dict(suivi_profil, orient="index")
        sauvegarde_bdd(data, 'trackertft')
        sauvegarde_bdd(suivi_profil, 'suivitft')

        await ctx.send(summonername + " was successfully added to live-feed!")
        # except:
        # await ctx.send("Oops! There is no summoner with that name!")

    @interactions.extension_command(name='tftlist',
                                    description='Affiche la liste des joueurs suivis')
    async def tftlist(self, ctx):

        data = lire_bdd('trackertft', 'dict')
        response = ""

        for key in data.keys():
            response += key.upper() + ", "

        response = response[:-2]
        embed = interactions.Embed(
            title="Live feed list", description=response, colour=interactions.Color.blurple())

        await ctx.send(embeds=embed)


def setup(bot):
    tft(bot)
