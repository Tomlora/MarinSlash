import pandas as pd
import aiohttp
import os
from fonctions.gestion_bdd import (lire_bdd, lire_bdd_perso, requete_perso_bdd, get_tag)
from fonctions.gestion_challenge import (get_data_joueur_challenges,
                                         challengeslol)
from utils.emoji import emote_rank_discord
from fonctions.word import suggestion_word
import time
import plotly.express as px
import plotly.graph_objects as go
import dataframe_image as dfi
import interactions
from interactions import SlashCommandChoice, SlashCommandOption, Extension, SlashContext, slash_command, listen, Task, TimeTrigger
from fonctions.permissions import isOwner_slash


class Challenges(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self.defis = lire_bdd('challenges').transpose(
        ).sort_values(by="name", ascending=True)

    @listen()
    async def on_startup(self):

        self.challenges_maj.start()

    @Task.create(TimeTrigger(hour=6, minute=0))
    async def challenges_maj(self):
        '''Chaque jour, à 6h, on actualise les challenges.
        Cette requête est obligatoirement à faire une fois par jour, sur un créneau creux pour éviter de surcharger les requêtes Riot'''


        session = aiohttp.ClientSession()
            # Ceux dont les challenges sont activés, sont maj à chaque game
        liste_summonername = lire_bdd_perso(
                'SELECT * from tracker where challenges = false', 'dict', index_col='id_compte')

        for id_compte, data in liste_summonername.items():

            try:
                challenges = challengeslol(
                        id_compte, data['puuid'], session)
                await challenges.preparation_data()
                await challenges.sauvegarde()

                time.sleep(10)
            except KeyError:
                pass

        await session.close()
        print('Les challenges ont été mis à jour.')
        
    @slash_command(name='lol_challenges', description='Challenges League of Legends')
    async def lol_challenges(self, ctx: SlashContext):
        pass

    @lol_challenges.subcommand("help",
                   sub_cmd_description="Explication des challenges")
    async def challenges_help(self, ctx: SlashContext):

        nombre_de_defis = len(self.defis['name'].unique())

        em = interactions.Embed(
            title="Challenges", description="Explication des challenges", inline=False)
        em.add_field(name="**Conditions**",
                     value="`Avoir joué depuis le patch 12.9  \nDisponible dans tous les modes de jeu`", inline=False)
        em.add_field(name="**Mise à jour des challenges**",
                     value=f"`Mis à jour tous les jours à 6h`", inline=False)
        em.add_field(name="**Defis disponibles**",
                     value=f"`Il existe {nombre_de_defis} défis disponibles.`", inline=False)

        await ctx.send(embeds=em)

    @lol_challenges.subcommand("classement",
                   sub_cmd_description="Classement des points de challenge",
                   options=[
                       SlashCommandOption(name='top',
                                          description='Afficher le top X',
                                          type=interactions.OptionType.INTEGER,
                                          required=False,
                                          min_value=5,
                                          max_value=100),
                       SlashCommandOption(name='view',
                                          description='Vue du classement',
                                          type=interactions.OptionType.STRING,
                                          required=False,
                                          choices=[
                                              SlashCommandChoice(
                                                  name='general', value='general'),
                                              SlashCommandChoice(
                                                  name='serveur', value='serveur')
                                          ])
                   ])
    async def challenges_classement(self,
                                    ctx: SlashContext,
                                    top: int = None,
                                    view: str = 'general'):

        if view == 'general':
            bdd_user_total = lire_bdd_perso(f'''SELECT challenges_total.* , tracker.riot_id
                                            from challenges_total
                        INNER join tracker on challenges_total.index = tracker.id_compte''',
                        index_col='riot_id').transpose()
            title = 'Classement général des points de défis'

        else:
            bdd_user_total = lire_bdd_perso(f'''SELECT challenges_total.* , tracker.riot_id
                                            from challenges_total
                        INNER join tracker on challenges_total.index = tracker.id_compte
                        where tracker.server_id = {int(ctx.guild_id)} ''',
                        index_col='riot_id').transpose()
            title = f'Classement des points de défis du serveur {ctx.guild.name}'

        await ctx.defer(ephemeral=False)

        bdd_user_total.sort_values(by='current', ascending=False, inplace=True)

        if top != None:
            bdd_user_total = bdd_user_total.head(top)
            title = f'{title} - Top {top}'

        fig = px.pie(bdd_user_total, values="current",
                     names=bdd_user_total.index, title=title)
        fig.update_traces(textinfo='label+value')
        fig.update_layout(showlegend=False)

        fig.write_image(f'plot.png')
        file = interactions.File(f'plot.png')
        # On prépare l'embed
        embed = interactions.Embed(color=interactions.Color.random())
        embed.set_image(url=f'attachment://plot.png')
        fig.write_image('plot.png')
        await ctx.send(embeds=embed, files=file)
        os.remove('plot.png')

    @lol_challenges.subcommand("profil",
                               sub_cmd_description="Profil du compte",
                   options=[
                       SlashCommandOption(name="riot_id",
                                          description="Nom du joueur",
                                          type=interactions.OptionType.STRING,
                                          required=True),
                        SlashCommandOption(name="riot_tag",
                                          description="Nom du joueur",
                                          type=interactions.OptionType.STRING,
                                          required=False),
                                          ])
    async def challenges_profil(self,
                                ctx: SlashContext,
                                riot_id: str,
                                riot_tag = None):

        session = aiohttp.ClientSession()

        if riot_tag == None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')
        
        riot_id = riot_id.replace(' ', '').lower()
        riot_tag = riot_tag.upper()
        
        bdd = lire_bdd_perso(f'''select id_compte, puuid from tracker where riot_id = '{riot_id}' and riot_tagline = '{riot_tag}' ''', index_col=None).T
        id_compte = bdd.iloc[0]['id_compte']
        puuid = bdd.iloc[0]['puuid']
        
        total_user, total_category, total_challenges, total_to_save = await get_data_joueur_challenges(id_compte, session, puuid)

        total_user = total_user[id_compte]

        def stats(categorie):
            level = total_category[categorie]['level']
            points = total_category[categorie]['current']
            max_points = total_category[categorie]['max']
            # x100 car pourcentage. On retient deux chhiffres après la virgule.
            percentile = round(total_category[categorie]['percentile']*100, 2)
            liste_stats = [categorie, level, points, max_points, percentile]
            return liste_stats

        await ctx.defer(ephemeral=False)

        liste_teamwork = stats('TEAMWORK')
        liste_collection = stats('COLLECTION')
        liste_expertise = stats('EXPERTISE')
        liste_imagination = stats('IMAGINATION')
        liste_veterancy = stats('VETERANCY')

        msg = ""  # txt

        fig = go.Figure()
        i = 0

        # dict de paramètres
        domain = {0: [0, 0], 1: [0, 2], 2: [1, 1],
                  3: [2, 0], 4: [2, 2]}  # position
        color = ["red", "blue", "yellow", "magenta", "green"]  # color

        for argument in [liste_teamwork, liste_collection, liste_expertise, liste_imagination, liste_veterancy]:
            # dict de parametres

            msg = msg + \
                f"{argument[0]} : ** {argument[2]} ** points / ** {argument[3]} ** possibles (niveau {emote_rank_discord[argument[1]]}) . Seulement **{argument[4]}**% des joueurs font mieux \n"
            fig.add_trace(go.Indicator(value=argument[2],
                                       title={
                                           'text': argument[0] + " (" + argument[1] + ")", 'font': {'size': 16}},
                                       gauge={'axis': {'range': [0, argument[3]]},
                                              'bar': {'color': color[i]}},
                                       mode="number+gauge",
                                       domain={'row': domain[i][0], 'column': domain[i][1]}))
            fig.update_layout(
                grid={'rows': 3, 'columns': 3, 'pattern': "independent"})
            i = i+1

        fig.write_image('plot.png')
        # txt
        await ctx.send(f'Le joueur {riot_id} a : \n{msg}\n __TOTAL__  : **{total_user["current"]}** / **{total_user["max"]}** (niveau {emote_rank_discord[total_user["level"]]}). Seulement **({round(total_user["percentile"]*100,2)}%** des joueurs font mieux.)', files=interactions.File('plot.png'))
        await session.close()
        os.remove('plot.png')

    @lol_challenges.subcommand("best",
                               sub_cmd_description="Meilleur classement pour les defis",
                   options=[SlashCommandOption(name="riot_id",
                                               description="Nom du joueur",
                                               type=interactions.OptionType.STRING,
                                               required=True),
                            SlashCommandOption(name="riot_tag",
                                               description="Tag du joueur",
                                               type=interactions.OptionType.STRING,
                                               required=False),
                            SlashCommandOption(name='minimum',
                                               description='Position minimum',
                                               type=interactions.OptionType.INTEGER,
                                               required=False,
                                               min_value=1,
                                               max_value=1000000)])
    async def challenges_best(self,
                              ctx: SlashContext,
                              riot_id: str,
                              riot_tag: str = None,
                              minimum: int = 1000000):

        # tous les summonername sont en minuscule :
        riot_id = riot_id.lower().replace(' ', '')

        if riot_tag == None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')
        riot_tag = riot_tag.upper()
        # charge la data
        data = lire_bdd_perso(f'''SELECT "Joueur", value, percentile, level, level_number, position, challenges.*, tracker.riot_id
                              from challenges_data
                                          INNER JOIN challenges ON challenges_data."challengeId" = challenges."challengeId"
                                          INNER JOIN tracker on tracker.id_compte = challenges_data."Joueur"
                                          where tracker.riot_id = '{riot_id}' and tracker.riot_tagline = '{riot_tag}' ''').transpose()

        # colonne position en float
        data['position'] = data['position'].astype('float')
        # on vire les non classements
        data = data[data['position'] != 0]

        if data.shape[0] != 0:  # s'il y a des données
            # on trie
            data.sort_values(['position'], ascending=True, inplace=True)
            # on retient ce qui nous intéresse
            data = data[['name', 'value', 'level',
                         'shortDescription', 'position']]
            
            data = data[data['position'] <= minimum]
            # index
            data.set_index('name', inplace=True)
            dfi.export(data, 'image.png', max_cols=-1,
                       max_rows=-1, table_conversion="matplotlib")

            await ctx.send(files=interactions.File('image.png'))

            os.remove('image.png')
        else:
            await ctx.send(f"Pas de ranking pour {riot_id} :(.")

    @lol_challenges.subcommand("tracker",
                               sub_cmd_description="Modifier la liste des challenges à ajouter / exclure dans le tracker",
                                    options=[
                                            SlashCommandOption(name="riot_id",
                                                       description="Nom du joueur",
                                                       type=interactions.OptionType.STRING,
                                                       required=True),
                                            SlashCommandOption(name="nom_challenge",
                                                       description="Nom du challenge à exclure",
                                                       type=interactions.OptionType.STRING,
                                                       required=True),
                                            SlashCommandOption(name='action',
                                                               description='Action à mener',
                                                               type=interactions.OptionType.STRING,
                                                               required=True,
                                                               choices=[
                                                                   SlashCommandChoice(name='inclure', value='inclure'),
                                                                   SlashCommandChoice(name='exclure', value='exclure')
                                                                   ]
                                                               ),
                                            SlashCommandOption(name='riot_tag',
                                                               description='Tag du joueur',
                                                               type=interactions.OptionType.STRING,
                                                               required=False)
                                            ]
                                    )
    async def modifier_challenges(self, ctx: SlashContext, riot_id, nom_challenge:str, action:str, riot_tag:str = None):

        # traitement des variables :

        riot_id = riot_id.lower().replace(' ', '')
        nom_challenge = nom_challenge.lower()

        await ctx.defer(ephemeral=True)

        df = lire_bdd('challenges').transpose()
        df['name'] = df['name'].str.lower()
        df.set_index('name', inplace=True)
        
        if riot_tag == None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')
        
        riot_id = riot_id.replace(' ', '').lower()
        riot_tag = riot_tag.upper()
        
        bdd = lire_bdd_perso(f'''select id_compte, puuid from tracker where riot_id = '{riot_id}' and riot_tagline = '{riot_tag}' ''', index_col=None).T
        id_compte = bdd.iloc[0]['id_compte']

        try:
            df.loc[nom_challenge, 'challengeId']
        except:
            suggestion = suggestion_word(nom_challenge, df.index.tolist())
            await ctx.send(f"Ce challenge n'existe pas. Souhaitais-tu dire : **{suggestion}**", ephemeral=True)
            return None

        if action == 'exclure':

            nb_row = requete_perso_bdd('''INSERT INTO challenge_exclusion("challengeId", index) VALUES (:challengeid, :summonername);''',
                            dict_params={'challengeid':df.loc[nom_challenge, 'challengeId'],
                                        'summonername': id_compte},
                            get_row_affected=True)

            if nb_row > 0:
                await ctx.send(f'Le challenge {nom_challenge} a été exclu du tracking', ephemeral=True)
            else:
                await ctx.send("Ce joueur ou le challenge n'existe pas", ephemeral=True)

        elif action == 'inclure':

            nb_row = requete_perso_bdd('''DELETE FROM challenge_exclusion WHERE "challengeId" = :challengeid AND index = :summonername;''',
                            dict_params={'challengeid':df.loc[nom_challenge, 'challengeId'],
                                        'summonername': id_compte},
                            get_row_affected=True)

            if nb_row > 0:
                await ctx.send(f'Le challenge {nom_challenge} a été réinclus au tracking', ephemeral=True)
            else:
                await ctx.send("Ce joueur n'existe pas ou ce challenge n'était pas exclu", ephemeral=True)

    @lol_challenges.subcommand("manage",
                               sub_cmd_description="Modifier la liste des challenges à ajouter / exclure dans le tracker. Admin only",
                                    options=[SlashCommandOption(name="nom_challenge",
                                                       description="Nom du challenge à exclure",
                                                       type=interactions.OptionType.STRING,
                                                       required=True),
                                            SlashCommandOption(name='action',
                                                               description='Action à mener',
                                                               type=interactions.OptionType.STRING,
                                                               required=True,
                                                               choices=[
                                                                   SlashCommandChoice(name='inclure', value='inclure'),
                                                                   SlashCommandChoice(name='exclure', value='exclure')
                                                                   ]
                                                               )
                                            ]
                                    )
    async def modifier_challenges_all(self, ctx: SlashContext, nom_challenge:str, action:str):

        # traitement des variables :

        if isOwner_slash(ctx):

            id_compte = -1
            nom_challenge = nom_challenge.lower()

            await ctx.defer(ephemeral=False)

            df = lire_bdd('challenges').transpose()
            df['name'] = df['name'].str.lower()
            df.set_index('name', inplace=True)

            try:
                df.loc[nom_challenge, 'challengeId']
            except:
                suggestion = suggestion_word(nom_challenge, df.index.tolist())
                await ctx.send(f"Ce challenge n'existe pas. Souhaitais-tu dire : **{suggestion}**", ephemeral=True)
                return None

            if action == 'exclure':

                nb_row = requete_perso_bdd('''INSERT INTO challenge_exclusion("challengeId", index) VALUES (:challengeid, :summonername);''',
                                dict_params={'challengeid':df.loc[nom_challenge, 'challengeId'],
                                            'summonername': id_compte},
                                get_row_affected=True)

                if nb_row > 0:
                    await ctx.send(f'Le challenge {nom_challenge} a été exclu du tracking pour tous les joueurs', ephemeral=True)
                else:
                    await ctx.send("Le challenge n'existe pas", ephemeral=True)

            elif action == 'inclure':

                nb_row = requete_perso_bdd('''DELETE FROM challenge_exclusion WHERE "challengeId" = :challengeid AND index = :summonername;''',
                                dict_params={'challengeid':df.loc[nom_challenge, 'challengeId'],
                                            'summonername': id_compte},
                                get_row_affected=True)

                if nb_row > 0:
                    await ctx.send(f'Le challenge {nom_challenge} a été réinclus au tracking pour tous les joueurs', ephemeral=True)
                else:
                    await ctx.send("Ce challenge n'était pas exclu", ephemeral=True)
        
        else:
            ctx.send("Tu n'as pas l'autorisation d'utiliser cette commande")



def setup(bot):
    Challenges(bot)
