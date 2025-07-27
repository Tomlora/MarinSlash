import os
import pandas as pd
import warnings
import interactions
from interactions import SlashCommandOption, Extension, SlashContext, slash_command, listen, Task,IntervalTrigger
from fonctions.channels_discord import chan_discord, rgb_to_discord
import sys
from utils.params import Version
from fonctions.gestion_bdd import (lire_bdd,
                                   sauvegarde_bdd,
                                   get_data_bdd,
                                   lire_bdd_perso,
                                   requete_perso_bdd)
from utils.emoji import emote_rank_discord, emote_champ_discord
from utils.lol import dict_rankid
import aiohttp
import re

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

async def get_data_trait(session):
    url = 'https://raw.communitydragon.org/pbe/plugins/rcp-be-lol-game-data/global/fr_fr/v1/tfttraits.json'
    async with session.get(url) as response:
        if response.status == 200:
            data = await response.json()
        else:
            data = None

        return data

async def matchtft_by_puuid(summonerName, idgames: int, session, puuid = None):
    
    if puuid is None:
            me = await get_summonertft_by_name(session, summonerName)
            puuid = me['puuid']
            
    liste_matchs = await get_matchs_by_puuid(session, puuid)
    if len(liste_matchs) == 0:
        return None, None, None
    last_match = liste_matchs[idgames]
    match = await get_matchs_details_tft(session, last_match)
    match = pd.DataFrame(match)
    return match, last_match, puuid


class tft(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    # ----------------------------- test

    @listen()
    async def on_startup(self):
        self.updatetft.start()

    async def stats_tft(self, summonername, session, idgames: int = 0, puuid = None):
        match_detail, id_match, puuid = await matchtft_by_puuid(summonername, idgames, session, puuid)

        if not isinstance(match_detail, pd.DataFrame):
            return {}

        summonername = summonername.lower()
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
        set_tft = match_detail['info']['tft_set_number']

        if thisQId == 1100:
            thisQ = "RANKED"
        else:
            thisQ = "NORMAL"

        # Durée

        thisTime = int(round(match_detail['info']['game_length'] / 60, 0))

        data_trait = await get_data_trait(session)
        df_traits_data = pd.json_normalize(data_trait)

        # augments = stats_joueur['augments']

        # msg_augment = ''

        # for augment in augments:
        #     augment = augment.replace(
        #         'TFT6_Augment_', '').replace('TFT7_Augment_', '').replace('TFT8_Augment_', '').replace('TFT9_Augment_', '').replace('TFT10_Augment_', '')
        #     msg_augment = f'{msg_augment} | {augment}'

        # Classement

        classement = stats_joueur['placement']

        # on sauvegarde si ranked
        
        df_exists = lire_bdd_perso(f'''SELECT match_id, joueur from trackertft_stats
                                   WHERE match_id = '{id_match}' 
                                   AND joueur = (SELECT id_compte from trackertft where index = '{summonername.lower()}')  ''',
                                   index_col=None)
        


        # Stats

        last_round = stats_joueur['last_round']
        level = stats_joueur['level']
        gold_restants = stats_joueur['gold_left']
        dmg_total = stats_joueur['total_damage_to_players']

        # Calcul last round

        if last_round < 12:
            first = 2
            second = last_round - 4
        elif last_round < 19:
            first = 3
            second = last_round - 11
        elif last_round < 26:
            first = 4
            second = last_round - 18
        elif last_round < 32:
            first = 5
            second = last_round - 25
        elif last_round < 39:
            first = 6
            second = last_round - 32
        elif last_round < 46:
            first = 7
            second = last_round - 39

        last_round = f'{first}-{second}'

        # Stats

        suivi_profil = lire_bdd_perso('''SELECT trackertft.index, suivitft."LP", suivitft.tier, 
                                      suivitft.rank from suivitft
                                      INNER JOIN trackertft ON trackertft.id_compte = suivitft.index''', 'dict')
        
        try:
            profil = await get_stats_ranked(session, summonername)
            profil = profil[0]
            ranked = True
            wins = profil['wins']
            losses = profil['losses']
            wr = round((wins/(int(wins)+int(losses)))*100, 0)
            tier = profil['tier']
            rank = profil['rank']
            lp = profil['leaguePoints']

            # Gain/Perte de LP

            try:
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

        if ranked:
            if difLP > 0:
                difLP = "+" + str(difLP)
            elif difLP < 0:
                difLP = str(difLP)

            classement_old = suivi_profil[summonername]['tier'] + \
                " " + suivi_profil[summonername]['rank']
            classement_new = tier + " " + rank

            if dict_rankid[classement_old] > dict_rankid[classement_new]:  # 19-18
                difrank = dict_rankid[classement_old] - dict_rankid[classement_new]
                difLP = (100 * difrank) + lp - int(suivi_profil[summonername]['LP'])
                difLP = "Démote :arrow_down: / -" + str(difLP)

            elif dict_rankid[classement_old] < dict_rankid[classement_new]:
                difrank = dict_rankid[classement_old] - dict_rankid[classement_new]
                difLP = (100 * difrank) - lp + int(suivi_profil[summonername]['LP'])
                difLP = "Promotion :arrow_up: / +" + str(difLP)

            requete_perso_bdd('''UPDATE suivitft
                              SET tier = :tier, rank = :rank, "LP" = :lp WHERE index = (SELECT id_compte FROM trackertft where index = :summonername)''', {'tier': tier,
                                                                                                          'rank': rank,
                                                                                                          'lp': lp,
                                                                                                          'summonername': summonername})


        # Embed

        data = get_data_bdd(f'SELECT "R", "G", "B" from tracker WHERE index= :index', {
                            'index': summonername})
        data = data.fetchall()
        
        

        emote_classement = {1: ':one:',
                            2: ':two:',
                            3: ':three:',
                            4: ':four:',
                            5: ':five:',
                            6: ':six:',
                            7: ':seven:',
                            8: ':eight:'}

        embed = interactions.Embed(
            title=f"** {summonername.upper()} ** vient de finir ** {emote_classement[classement]}ème ** sur tft (R : {last_round}) ({thisQ})", color=interactions.Color.from_rgb(data[0][0], data[0][1], data[0][2]))

        embed.add_field(name="Durée de la game :",
                        value=f'{thisTime} minutes')

        # Stats
        if ranked:
            embed.add_field(name=f'{emote_rank_discord[tier]} {rank} | {lp}LP ({difLP})',
                            value=f'Winrate : **{wr}%** \n', inline=False)

        else:
            embed.add_field(name=f'Non-classe',
                            value=f'En placement', inline=False)

        # embed.add_field(name="Augments : ",
        #                 value=msg_augment, inline=False)

        # on va créer un dataframe pour les sort plus facilement

        df_traits = pd.DataFrame(stats_joueur['traits'])
        df_traits = df_traits.sort_values(by='tier_current', ascending=False)
        
        

        # [0] est l'index
        for set in df_traits.iterrows():
            # Supprime 'Set' suivi de chiffres et '_' ainsi que 'TFT_' suivi de chiffres
            name = re.sub(r'(Set\d+_|TFT\d+_)', '', set[1]['name'])

            if df_traits_data is not None:
                name_fr = df_traits_data.loc[df_traits_data['trait_id'] == set[1]['name'], 'display_name'].values[0]
            else:
                name_fr = name

            tier_current = set[1]['tier_current']
            tier_total = set[1]['tier_total']
            nb_units = set[1]['num_units']

            embed.add_field(
                name=name_fr, value=f"{tier_current} / {tier_total} \nUnités: {nb_units}", inline=True)

        dic_rarity = {0: "1",
                      1: "2",
                      2: "3",
                      4: "4",
                      6: "5",
                      7 : "6",
                      8: "6"}

        # pareil ici

        df_mobs = pd.DataFrame(stats_joueur['units'])
        df_mobs = df_mobs.sort_values(by='tier', ascending=False)
        
        inline=False
        for mob in df_mobs.iterrows():
            monster_name = re.sub(r'tft\d+_', '', mob[1]['character_id'], flags=re.IGNORECASE)  # Remplace TFT suivi de chiffres (insensible à la casse)
                    
            monster_tier = mob[1]['tier']
            
            def afficher_etoiles(monster_tier):
                return '⭐' * int(monster_tier)
            
            # afficher un nombre de stars en fonction de monster_tier:
            
            rarity = mob[1]['rarity']
            embed.add_field(name=f'{emote_champ_discord[monster_name.capitalize().replace(" ", "")]} ({dic_rarity[rarity]}:moneybag:)',
                            value=afficher_etoiles(monster_tier), inline=inline)
            inline = True

        embed.add_field(name="Stats :bar_chart: : ", value=f':money_with_wings: : **{gold_restants}** | Level : **{level}** | DMG infligés : **{dmg_total}**', inline=False)

        embed.set_footer(
            text=f'Version {Version} by Tomlora - Match {id_match}')

      
        if df_exists.empty:
            requete_perso_bdd('''INSERT INTO trackertft_stats(joueur, match_id, mode, top, gold, level, dmg, last_round, set)
        VALUES ( (SELECT id_compte FROM trackertft where index = :joueur), :match_id, :mode, :top, :gold, :level, :dmg, :last_round, :set);''',
                {'joueur': summonername.lower(),
                'match_id': id_match,
                'mode': thisQ,
                'top': classement,
                'gold' : gold_restants,
                'level' : level,
                'dmg' : dmg_total,
                'last_round' : last_round,
                'set' : set_tft})
            
            id_compte = lire_bdd_perso(f'''SELECT id_compte FROM trackertft where index = '{summonername.lower()}' ''', index_col=None).loc['id_compte'][0]
            df_traits['joueur'] = id_compte
            df_traits['id'] = id_match
            
            df_mobs['joueur'] = id_compte
            df_mobs['id'] = id_match
            
            
            sauvegarde_bdd(df_traits, 'trackertft_traits', 'append')
            sauvegarde_bdd(df_mobs, 'trackertft_mobs', 'append')
            

        return embed

    @slash_command(name="gametft",
                                    description="Recap tft",
                                    options=[
                                        SlashCommandOption(name="summonername",
                                                    description="Nom du joueur",
                                                    type=interactions.OptionType.STRING,
                                                    required=True),
                                        SlashCommandOption(name="idgames",
                                                    description="numero de la game",
                                                    type=interactions.OptionType.INTEGER,
                                                    required=False,
                                                    min_value=0,
                                                    max_value=10)])
    async def gametft(self,
                      ctx: SlashContext,
                      summonername,
                      idgames: int = 0):

        await ctx.defer(ephemeral=False)
        
        puuid = lire_bdd_perso(f'''SELECT puuid from trackertft where index = '{summonername.lower()}' ''', index_col=None).loc['puuid'][0]

        session = aiohttp.ClientSession()

        embed = await self.stats_tft(summonername, session, idgames, puuid)

        await session.close()

        await ctx.send(embeds=embed)

    async def printLivetft(self, summonername: str, discord_server_id: chan_discord, session):
        
        puuid = lire_bdd_perso(f'''SELECT puuid from trackertft where index = '{summonername.lower()}' ''', index_col=None).loc['puuid'][0]

        embed = await self.stats_tft(summonername, session, idgames=0, puuid=puuid)

        channel = await self.bot.fetch_channel(discord_server_id.tft)

        if embed != {}:
            await channel.send(embeds=embed)

    @Task.create(IntervalTrigger(minutes=5))
    async def updatetft(self):

        session = aiohttp.ClientSession()
        data = get_data_bdd('''SELECT trackertft.index, trackertft.id, trackertft.puuid, tracker.server_id from trackertft
                    INNER JOIN tracker on trackertft.index = tracker.index''')
        
        for joueur, id_game, puuid, server_id in data:

            match_detail, id_match, puuid = await matchtft_by_puuid(joueur, 0, session, puuid)

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

    @slash_command(name="tftadd",
                                    description="Ajoute le joueur au suivi",
                                    options=[
                                        SlashCommandOption(
                                            name="summonername",
                                            description="Nom du joueur",
                                            type=interactions.OptionType.STRING,
                                            required=True)])
    async def tftadd(self,
                     ctx: SlashContext,
                     summonername):


        session = aiohttp.ClientSession()


        await ctx.defer(ephemeral=False)

        try:
            profil = await get_stats_ranked(session, summonername)
            profil = profil[0]
            

            tier = profil['tier']
            rank = profil['rank']
            lp = profil['leaguePoints']

        except:
            tier = 'Non-classe'
            rank = '0'
            lp = 0
            
        match_detail, id_match, puuid = await matchtft_by_puuid(summonername, 0, session)
        # ajout du summonername (clé) et de l'id de la dernière game(getId)
        
        requete_perso_bdd('''INSERT INTO trackertft(index, id, puuid)
                          VALUES (:index, :id, :puuid);''',
                          dict_params={'index': summonername.lower(),
                                       'id': id_match,
                                       'puuid': puuid,
                                       'LP': lp,
                                       'tier': tier,
                                       'rank': rank})
        
        requete_perso_bdd('''INSERT INTO suivitft(index, "LP", tier, rank)
                          VALUES ( (SELECT id_compte FROM trackertft where index = :summonername), :LP, :tier, :rank); ''',
                          dict_params={'index': summonername.lower(),
                                       'id': id_match,
                                       'puuid': puuid,
                                       'LP': lp,
                                       'tier': tier,
                                       'rank': rank})
        
        await ctx.send(summonername + " was successfully added to live-feed!")
        # except:
        # await ctx.send("Oops! There is no summoner with that name!")

    @slash_command(name='tftlist',
                                    description='Affiche la liste des joueurs suivis')
    async def tftlist(self, ctx):

        data = lire_bdd('trackertft', 'dict')
        response = ""

        for key in data.keys():
            response += key.upper() + ", "

        response = response[:-2]
        embed = interactions.Embed(
            title="Live feed list", description=response, color=interactions.Color.random())

        await ctx.send(embeds=embed)


def setup(bot):
    tft(bot)
