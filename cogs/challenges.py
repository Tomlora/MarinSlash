import pandas as pd
import ast
import aiohttp
import os
from fonctions.gestion_bdd import (lire_bdd, lire_bdd_perso)


from fonctions.gestion_challenge import (get_data_joueur_challenges,
                                         challengeslol)
from fonctions.params import heure_challenge
import time
import plotly.express as px
import plotly.graph_objects as go
import datetime
import dataframe_image as dfi
import interactions
from interactions import Option, Extension, CommandContext
from interactions.ext.tasks import create_task, IntervalTrigger
from interactions.ext.wait_for import wait_for_component, setup as stp


class Challenges(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self.defis = lire_bdd('challenges').transpose(
        ).sort_values(by="name", ascending=True)

        stp(self.bot)

    @interactions.extension_listener
    async def on_start(self):

        self.task1 = create_task(IntervalTrigger(60*60))(self.challenges_maj)
        self.task1.start()

    async def challenges_maj(self):
        '''Chaque jour, à 6h, on actualise les challenges.
        Cette requête est obligatoirement à faire une fois par jour, sur un créneau creux pour éviter de surcharger les requêtes Riot'''

        currentHour = datetime.datetime.now().hour

        if currentHour == heure_challenge:

            session = aiohttp.ClientSession()
            liste_summonername = lire_bdd_perso('SELECT * from tracker where challenges = false', 'dict') # Ceux dont les challenges sont activés, sont maj à chaque game


            for summonername, data in liste_summonername.items():

                try:
                    challenges = challengeslol(summonername, data['puuid'], session)
                    await challenges.preparation_data()
                    await challenges.sauvegarde()

                    time.sleep(10)
                except KeyError:
                    pass

            await session.close()
            print('Les challenges ont été mis à jour.')

    @interactions.extension_command(name="challenges_help",
                                    description="Explication des challenges")
    async def challenges_help(self, ctx: CommandContext):

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

    @interactions.extension_command(name="challenges_classement",
                                    description="Classement des points de challenge")
    async def challenges_classement(self, ctx: CommandContext):

        bdd_user_total = lire_bdd('challenges_total').transpose()

        fig = px.pie(bdd_user_total, values="current",
                     names=bdd_user_total.index, title="Points de défis")
        fig.update_traces(textinfo='label+value')
        fig.update_layout(showlegend=False)
        fig.write_image('plot.png')
        await ctx.send(files=interactions.File('plot.png'))
        os.remove('plot.png')

    @interactions.extension_command(name="challenges_profil", description="Profil du compte",
                                    options=[
                                        Option(name="summonername",
                                                    description="Nom du joueur",
                                                    type=interactions.OptionType.STRING,
                                                    required=True)])
    async def challenges_profil(self,
                                ctx: CommandContext,
                                summonername: str):

        session = aiohttp.ClientSession()
        total_user, total_category, total_challenges, total_to_save = await get_data_joueur_challenges(summonername, session)
        
        total_user = total_user[summonername]

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
                f"{argument[0]} : ** {argument[2]} ** points / ** {argument[3]} ** possibles (niveau {argument[1]}) . Seulement **{argument[4]}**% des joueurs font mieux \n"
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
        await ctx.send(f'Le joueur {summonername} a : \n{msg}\n __TOTAL__  : **{total_user["current"]}** / **{total_user["max"]}** (niveau {total_user["level"]}). Seulement **({total_user["percentile"]}%** des joueurs font mieux.)', files=interactions.File('plot.png'))
        await session.close()
        os.remove('plot.png')


    @interactions.extension_command(name="challenges_best", description="Meilleur classement pour les defis",
                                    options=[Option(name="summonername",
                                                    description="Nom du joueur",
                                                    type=interactions.OptionType.STRING,
                                                    required=True)])
    async def challenges_best(self,
                              ctx: CommandContext,
                              summonername: str):

        # tous les summonername sont en minuscule :
        summonername = summonername.lower().replace(' ', '')
        # charge la data
        data = lire_bdd_perso(f'''SELECT "Joueur", value, percentile, level, level_number, position, challenges.* from challenges_data
                                          INNER JOIN challenges ON challenges_data."challengeId" = challenges."challengeId"
                                          where "Joueur" = '{summonername}' ''').transpose()
        # tri sur le joueur
        data = data[data['Joueur'] == summonername]
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
            # index
            data.set_index('name', inplace=True)
            dfi.export(data, 'image.png', max_cols=-1,
                       max_rows=-1, table_conversion="matplotlib")

            await ctx.send(files=interactions.File('image.png'))

            os.remove('image.png')
        else:
            await ctx.send(f"Pas de ranking pour {summonername} :(.")

def setup(bot):
    Challenges(bot)
