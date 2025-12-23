import os
import pandas as pd
import warnings
import interactions
from interactions import SlashCommandOption, Extension, SlashContext, slash_command, listen, Task,IntervalTrigger
from fonctions.channels_discord import chan_discord, rgb_to_discord
import sys
from utils.params import Version, set_tft
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


async def get_stats_ranked(session: aiohttp.ClientSession, puuid):

    async with session.get(f'https://{my_region}.api.riotgames.com/tft/league/v1/by-puuid/{puuid}', params={'api_key': api_key_tft}) as stats_ranked_tft:
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

async def matchtft_by_puuid(idgames: int, session, puuid = None):
    
           
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
        match_detail, id_match, puuid = await matchtft_by_puuid(idgames, session, puuid)

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
            profil = await get_stats_ranked(session, puuid)
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
                      8: "6",
                      9: "5"}

        # pareil ici

        df_mobs = pd.DataFrame(stats_joueur['units'])
        df_mobs = df_mobs.sort_values(by='tier', ascending=False)
        
        inline=False
        for mob in df_mobs.iterrows():
            monster_name = re.sub(r'tft\d+_', '', mob[1]['character_id'], flags=re.IGNORECASE)  # Remplace TFT suivi de chiffres (insensible à la casse)
                    
            monster_tier = mob[1]['tier']

            monster_emote = emote_champ_discord.get(monster_name.capitalize().replace(" ", ""), monster_name)
            
            def afficher_etoiles(monster_tier):
                return '⭐' * int(monster_tier)
            
            # afficher un nombre de stars en fonction de monster_tier:
            
            rarity = mob[1]['rarity']
            if len(embed.fields) < 25:
                embed.add_field(name=f'{monster_emote} ({dic_rarity[rarity]}:moneybag:)',
                                value=afficher_etoiles(monster_tier), inline=inline)
                inline = True

        if len(embed.fields) < 25:
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
                                                    max_value=20)])
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

    async def printLivetft(self, summonername: str, discord_server_id: chan_discord, session, puuid):
        
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

            match_detail, id_match, puuid = await matchtft_by_puuid(0, session, puuid)

            if str(id_game) != id_match:  # value -> ID de dernière game enregistrée dans id_data != ID de la dernière game via l'API Rito / #key = summonername // value = numéro de la game
                try:

                    discord_server_id = chan_discord(server_id)
                    await self.printLivetft(joueur, discord_server_id, session, puuid)
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

    # =====================================================
    # NOUVELLES COMMANDES
    # =====================================================

    @slash_command(name="tftstats",
                   description="Statistiques globales d'un joueur TFT",
                   options=[
                       SlashCommandOption(name="summonername",
                                          description="Nom du joueur",
                                          type=interactions.OptionType.STRING,
                                          required=True),
                       SlashCommandOption(name='set',
                                          description='Numéro du set',
                                          type=interactions.OptionType.INTEGER,
                                          required=False),
                       SlashCommandOption(name="mode",
                                          description="Mode de jeu",
                                          type=interactions.OptionType.STRING,
                                          required=False,
                                          choices=[
                                              {"name": "Ranked", "value": "RANKED"},
                                              {"name": "Normal", "value": "NORMAL"},
                                              {"name": "Tous", "value": "ALL"}
                                          ])])
    async def tftstats(self, ctx: SlashContext, summonername: str, set : int = set_tft, mode: str = "ALL"):
        await ctx.defer(ephemeral=False)

        summonername = summonername.lower()

        # Filtre par mode
        mode_filter = "" if mode == "ALL" else f"AND mode = '{mode}'"

        # Récupération des stats
        df_stats = lire_bdd_perso(f'''
            SELECT top, gold, level, dmg, mode, set 
            FROM trackertft_stats 
            WHERE joueur = (SELECT id_compte FROM trackertft WHERE index = '{summonername}')
            and "set" = {set} 
            {mode_filter}
        ''', index_col=None).T

        if df_stats.empty:
            await ctx.send(f"Aucune statistique trouvée pour **{summonername.upper()}**.")
            return

        # Calculs
        total_games = len(df_stats)
        avg_placement = round(df_stats['top'].mean(), 2)
        top1_count = len(df_stats[df_stats['top'] == 1])
        top4_count = len(df_stats[df_stats['top'] <= 4])
        top1_rate = round((top1_count / total_games) * 100, 1)
        top4_rate = round((top4_count / total_games) * 100, 1)
        avg_gold = round(df_stats['gold'].mean(), 1)
        avg_level = round(df_stats['level'].mean(), 1)
        avg_dmg = round(df_stats['dmg'].mean(), 0)

        # Distribution des placements
        placement_dist = df_stats['top'].value_counts().sort_index()

        # Récupérer les couleurs du joueur
        data = get_data_bdd(f'SELECT "R", "G", "B" from tracker WHERE index = :index', {'index': summonername})
        data = data.fetchall()
        
        if data:
            color = interactions.Color.from_rgb(data[0][0], data[0][1], data[0][2])
        else:
            color = interactions.Color.random()

        # Création de l'embed
        mode_text = "Toutes parties" if mode == "ALL" else mode
        embed = interactions.Embed(
            title=f"📊 Statistiques TFT - {summonername.upper()}",
            description=f"**{total_games}** parties analysées ({mode_text})",
            color=color
        )

        embed.add_field(
            name="🏆 Placements",
            value=f"**Moyenne** : {avg_placement}\n**Top 1** : {top1_count} ({top1_rate}%)\n**Top 4** : {top4_count} ({top4_rate}%)",
            inline=True
        )

        embed.add_field(
            name="📈 Moyennes",
            value=f"**Or restant** : {avg_gold}\n**Niveau** : {avg_level}\n**Dégâts** : {int(avg_dmg)}",
            inline=True
        )

        # Distribution visuelle des placements
        dist_text = ""
        for i in range(1, 9):
            count = placement_dist.get(i, 0)
            percentage = round((count / total_games) * 100, 1) if total_games > 0 else 0
            bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
            dist_text += f"`{i}` {bar} {count} ({percentage}%)\n"

        embed.add_field(
            name="📊 Distribution des placements",
            value=dist_text,
            inline=False
        )

        embed.set_footer(text=f'Version {Version} by Tomlora')
        await ctx.send(embeds=embed)


    @slash_command(name="tftleaderboard",
                   description="Classement des joueurs TFT suivis")
    async def tftleaderboard(self, ctx: SlashContext):
        await ctx.defer(ephemeral=False)

        # Récupérer tous les joueurs avec leur rang
        df_leaderboard = lire_bdd_perso('''
            SELECT trackertft.index as joueur, suivitft."LP", suivitft.tier, suivitft.rank
            FROM suivitft
            INNER JOIN trackertft ON trackertft.id_compte = suivitft.index
        ''', index_col=None).T

        if df_leaderboard.empty:
            await ctx.send("Aucun joueur suivi trouvé.")
            return

        # Ajouter une colonne pour le tri basé sur dict_rankid
        df_leaderboard['rank_value'] = df_leaderboard.apply(
            lambda row: dict_rankid.get(f"{row['tier']} {row['rank']}", 0), axis=1
        )
        
        # Trier par rank_value (desc) puis par LP (desc)
        df_leaderboard = df_leaderboard.sort_values(
            by=['rank_value', 'LP'], 
            ascending=[False, False]
        ).reset_index(drop=True)

        # Création de l'embed
        embed = interactions.Embed(
            title="🏆 Classement TFT",
            description="Classement des joueurs suivis par rang",
            color=interactions.Color.from_rgb(255, 215, 0)  # Or
        )

        # Emotes pour le podium
        podium_emotes = {0: "🥇", 1: "🥈", 2: "🥉"}

        leaderboard_text = ""
        for idx, row in df_leaderboard.iterrows():
            position = podium_emotes.get(idx, f"`{idx + 1}.`")
            joueur = row['joueur'].upper()
            tier = row['tier']
            rank = row['rank']
            lp = row['LP']
            
            emote = emote_rank_discord.get(tier, "")
            
            if tier == 'Non-classe':
                leaderboard_text += f"{position} **{joueur}** - Non classé\n"
            else:
                leaderboard_text += f"{position} **{joueur}** - {emote} {tier} {rank} ({lp} LP)\n"

        embed.add_field(name="Classement", value=leaderboard_text or "Aucun joueur", inline=False)
        embed.set_footer(text=f'Version {Version} by Tomlora')

        await ctx.send(embeds=embed)


    @slash_command(name="tftcompo",
                   description="Compositions les plus jouées/performantes",
                   options=[
                       SlashCommandOption(name="summonername",
                                          description="Nom du joueur",
                                          type=interactions.OptionType.STRING,
                                          required=True),
                       SlashCommandOption(name='set',
                                          description='Numéro du set',
                                          type=interactions.OptionType.INTEGER,
                                          required=False),
                       SlashCommandOption(name="tri",
                                          description="Trier par",
                                          type=interactions.OptionType.STRING,
                                          required=False,
                                          choices=[
                                              {"name": "Plus jouées", "value": "count"},
                                              {"name": "Meilleur placement moyen", "value": "avg_top"}
                                          ])])
    async def tftcompo(self, ctx: SlashContext, summonername: str, set: int = set_tft, tri: str = "count"):
        await ctx.defer(ephemeral=False)

        summonername = summonername.lower()

        # Récupérer les traits avec les placements
        df_traits = lire_bdd_perso(f'''
            SELECT t.name, t.tier_current, t.tier_total, t.num_units, t.id, s.top
            FROM trackertft_traits t
            INNER JOIN trackertft_stats s ON t.id = s.match_id AND t.joueur = s.joueur
            WHERE t.joueur = (SELECT id_compte FROM trackertft WHERE index = '{summonername}')
            AND set = {set}
            AND t.tier_current > 0
        ''', index_col=None).T

        if df_traits.empty:
            await ctx.send(f"Aucune composition trouvée pour **{summonername.upper()}**.")
            return

        # Nettoyer les noms de traits
        df_traits['name_clean'] = df_traits['name'].apply(
            lambda x: re.sub(r'(Set\d+_|TFT\d+_)', '', x)
        )

        # Agréger par trait
        trait_stats = df_traits.groupby('name_clean').agg(
            count=('id', 'nunique'),
            avg_top=('top', 'mean'),
            total_units=('num_units', 'sum')
        ).reset_index()

        # Trier
        if tri == "count":
            trait_stats = trait_stats.sort_values('count', ascending=False)
        else:
            trait_stats = trait_stats.sort_values('avg_top', ascending=True)

        # Top 10
        trait_stats = trait_stats.head(10)

        # Couleurs du joueur
        data = get_data_bdd(f'SELECT "R", "G", "B" from tracker WHERE index = :index', {'index': summonername})
        data = data.fetchall()
        
        if data:
            color = interactions.Color.from_rgb(data[0][0], data[0][1], data[0][2])
        else:
            color = interactions.Color.random()

        # Création de l'embed
        tri_text = "les plus jouées" if tri == "count" else "les plus performantes"
        embed = interactions.Embed(
            title=f"🎯 Compositions {tri_text} - {summonername.upper()}",
            color=color
        )

        compo_text = ""
        for idx, row in trait_stats.iterrows():
            name = row['name_clean']
            count = row['count']
            avg_top = round(row['avg_top'], 2)
            compo_text += f"**{name}** : {count} parties | Moy. {avg_top}\n"

        embed.add_field(name="Top 10 Traits", value=compo_text or "Aucune donnée", inline=False)
        embed.set_footer(text=f'Version {Version} by Tomlora')

        await ctx.send(embeds=embed)


    @slash_command(name="tftcompare",
                   description="Comparer deux joueurs TFT",
                   options=[
                       SlashCommandOption(name="joueur1",
                                          description="Premier joueur",
                                          type=interactions.OptionType.STRING,
                                          required=True),
                       SlashCommandOption(name="joueur2",
                                          description="Deuxième joueur",
                                          type=interactions.OptionType.STRING,
                                          required=True),
                       SlashCommandOption(name='set',
                                          description='Numéro du set',
                                          type=interactions.OptionType.INTEGER,
                                          required=False)])
    async def tftcompare(self, ctx: SlashContext, joueur1: str, joueur2: str, set: int = set_tft):
        await ctx.defer(ephemeral=False)

        joueur1 = joueur1.lower()
        joueur2 = joueur2.lower()

        def get_player_stats(summonername):
            df = lire_bdd_perso(f'''
                SELECT top, gold, level, dmg
                FROM trackertft_stats 
                WHERE joueur = (SELECT id_compte FROM trackertft WHERE index = '{summonername}')
                AND set = {set}
            ''', index_col=None).T
            
            if df.empty:
                return None
            
            total = len(df)
            return {
                'games': total,
                'avg_top': round(df['top'].mean(), 2),
                'top1': len(df[df['top'] == 1]),
                'top4': len(df[df['top'] <= 4]),
                'top1_rate': round((len(df[df['top'] == 1]) / total) * 100, 1),
                'top4_rate': round((len(df[df['top'] <= 4]) / total) * 100, 1),
                'avg_gold': round(df['gold'].mean(), 1),
                'avg_level': round(df['level'].mean(), 1),
                'avg_dmg': round(df['dmg'].mean(), 0)
            }

        stats1 = get_player_stats(joueur1)
        stats2 = get_player_stats(joueur2)

        if not stats1:
            await ctx.send(f"Aucune statistique trouvée pour **{joueur1.upper()}**.")
            return
        if not stats2:
            await ctx.send(f"Aucune statistique trouvée pour **{joueur2.upper()}**.")
            return

        # Fonction pour afficher qui est meilleur
        def compare(val1, val2, lower_is_better=False):
            if lower_is_better:
                if val1 < val2:
                    return "🟢", "🔴"
                elif val1 > val2:
                    return "🔴", "🟢"
            else:
                if val1 > val2:
                    return "🟢", "🔴"
                elif val1 < val2:
                    return "🔴", "🟢"
            return "🟡", "🟡"

        embed = interactions.Embed(
            title=f"⚔️ {joueur1.upper()} vs {joueur2.upper()}",
            color=interactions.Color.from_rgb(138, 43, 226)
        )

        # Comparaisons
        comparisons = [
            ("Parties jouées", stats1['games'], stats2['games'], False),
            ("Placement moyen", stats1['avg_top'], stats2['avg_top'], True),
            ("Top 1 rate", f"{stats1['top1_rate']}%", f"{stats2['top1_rate']}%", False),
            ("Top 4 rate", f"{stats1['top4_rate']}%", f"{stats2['top4_rate']}%", False),
            ("Or moyen", stats1['avg_gold'], stats2['avg_gold'], False),
            ("Niveau moyen", stats1['avg_level'], stats2['avg_level'], False),
            ("Dégâts moyens", int(stats1['avg_dmg']), int(stats2['avg_dmg']), False),
        ]

        j1_text = ""
        j2_text = ""

        for label, v1, v2, lower_better in comparisons:
            # Convertir pour comparaison numérique si pourcentage
            v1_num = float(str(v1).replace('%', '')) if isinstance(v1, str) else v1
            v2_num = float(str(v2).replace('%', '')) if isinstance(v2, str) else v2
            
            e1, e2 = compare(v1_num, v2_num, lower_better)
            j1_text += f"{e1} **{label}** : {v1}\n"
            j2_text += f"{e2} **{label}** : {v2}\n"

        embed.add_field(name=joueur1.upper(), value=j1_text, inline=True)
        embed.add_field(name=joueur2.upper(), value=j2_text, inline=True)

        embed.set_footer(text=f'Version {Version} by Tomlora • 🟢 Meilleur | 🔴 Moins bon | 🟡 Égalité')

        await ctx.send(embeds=embed)


    @slash_command(name="tftunits",
                   description="Champions les plus joués par un joueur",
                   options=[
                       SlashCommandOption(name="summonername",
                                          description="Nom du joueur",
                                          type=interactions.OptionType.STRING,
                                          required=True),
                       SlashCommandOption(name='set',
                                          description='Numéro du set',
                                          type=interactions.OptionType.INTEGER,
                                          required=False),
                       SlashCommandOption(name="tri",
                                          description="Trier par",
                                          type=interactions.OptionType.STRING,
                                          required=False,
                                          choices=[
                                              {"name": "Plus joués", "value": "count"},
                                              {"name": "Meilleur placement", "value": "avg_top"}
                                          ])])
    async def tftunits(self, ctx: SlashContext, summonername: str, set: int = set_tft, tri: str = "count"):
        await ctx.defer(ephemeral=False)

        summonername = summonername.lower()

        # Récupérer les unités avec les placements
        df_units = lire_bdd_perso(f'''
            SELECT m.character_id, m.tier, m.rarity, m.id, s.top
            FROM trackertft_mobs m
            INNER JOIN trackertft_stats s ON m.id = s.match_id AND m.joueur = s.joueur
            WHERE m.joueur = (SELECT id_compte FROM trackertft WHERE index = '{summonername}')
            AND set = {set}
        ''', index_col=None).T

        if df_units.empty:
            await ctx.send(f"Aucune unité trouvée pour **{summonername.upper()}**.")
            return

        # Nettoyer les noms
        df_units['name_clean'] = df_units['character_id'].apply(
            lambda x: re.sub(r'tft\d+_', '', x, flags=re.IGNORECASE)
        )

        # Agréger par unité
        unit_stats = df_units.groupby('name_clean').agg(
            count=('id', 'nunique'),
            avg_top=('top', 'mean'),
            avg_tier=('tier', 'mean')
        ).reset_index()

        # Trier
        if tri == "count":
            unit_stats = unit_stats.sort_values('count', ascending=False)
        else:
            unit_stats = unit_stats.sort_values('avg_top', ascending=True)

        # Top 15
        unit_stats = unit_stats.head(15)

        # Couleurs du joueur
        data = get_data_bdd(f'SELECT "R", "G", "B" from tracker WHERE index = :index', {'index': summonername})
        data = data.fetchall()
        
        if data:
            color = interactions.Color.from_rgb(data[0][0], data[0][1], data[0][2])
        else:
            color = interactions.Color.random()

        # Création de l'embed
        tri_text = "les plus joués" if tri == "count" else "les plus performants"
        embed = interactions.Embed(
            title=f"👾 Champions {tri_text} - {summonername.upper()}",
            color=color
        )

        units_text = ""
        for idx, row in unit_stats.iterrows():
            name = row['name_clean'].capitalize()
            count = row['count']
            avg_top = round(row['avg_top'], 2)
            avg_tier = round(row['avg_tier'], 1)
            
            # Récupérer l'emote du champion
            emote = emote_champ_discord.get(name.replace(" ", ""), name)
            stars = "⭐" * int(round(avg_tier))
            
            units_text += f"{emote} **{name}** {stars} : {count} parties | Moy. {avg_top}\n"

        embed.add_field(name="Top 15 Champions", value=units_text or "Aucune donnée", inline=False)
        embed.set_footer(text=f'Version {Version} by Tomlora')

        await ctx.send(embeds=embed)


def setup(bot):
    tft(bot)
