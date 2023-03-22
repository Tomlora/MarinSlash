import pandas as pd
import ast
import aiohttp
import os
from fonctions.gestion_bdd import (lire_bdd,
                                   sauvegarde_bdd,
                                   supprimer_bdd)
from fonctions.match import (get_challenges_config,
                             get_summoner_by_name,
                             get_challenges_data_joueur)
import time
import plotly.express as px
import plotly.graph_objects as go
import datetime
import dataframe_image as dfi
import interactions
from interactions import Option, Extension, CommandContext
from interactions.ext.tasks import create_task, IntervalTrigger
from interactions.ext.wait_for import wait_for_component, setup as stp


def extraire_variables_imbriquees(df, colonne):
    df[colonne] = [ast.literal_eval(str(item))
                   for index, item in df[colonne].iteritems()]

    df = pd.concat([df.drop([colonne], axis=1),
                   df[colonne].apply(pd.Series)], axis=1)
    return df


async def get_data_challenges(session):
    data_challenges = await get_challenges_config(session)
    data_challenges = pd.DataFrame(data_challenges)
    data_challenges = extraire_variables_imbriquees(
        data_challenges, 'localizedNames')
    data_challenges = data_challenges[['id', 'state', 'thresholds', 'fr_FR']]
    data_challenges = extraire_variables_imbriquees(data_challenges, 'fr_FR')
    data_challenges = extraire_variables_imbriquees(
        data_challenges, 'thresholds')
    data_challenges = data_challenges[['id', 'state', 'name', 'shortDescription', 'description', 'IRON', 'BRONZE',
                                       'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']]  # on change l'ordre
    return data_challenges


async def get_data_joueur(summonername: str, session):
    me = await get_summoner_by_name(session, summonername)
    data_joueur = await get_challenges_data_joueur(session, me['puuid'])
    data_total_joueur = dict()

    data_total_joueur[summonername] = data_joueur['totalPoints']  # dict

    data_joueur_category = pd.DataFrame(data_joueur['categoryPoints'])

    data_joueur_challenges = pd.DataFrame(data_joueur['challenges'])
    # on ajoute le joueur
    data_joueur_category.insert(0, "Joueur", summonername)
    data_joueur_challenges.insert(0, "Joueur", summonername)

    if data_joueur_challenges.empty:  # si le dataset est vide, on fait rien.
        return 0, 0, 0

    try:  # certains joueurs n'ont pas ces colonnes... impossible de dire pourquoi
        data_joueur_challenges.drop(
            ['playersInLevel', 'achievedTime'], axis=1, inplace=True)
    except KeyError:
        data_joueur_challenges.drop(['achievedTime'], axis=1, inplace=True)

    data_challenges = await get_data_challenges(session)
    # on fusionne en fonction de l'id :
    data_joueur_challenges = data_joueur_challenges.merge(
        data_challenges, left_on="challengeId", right_on='id')
    # on a besoin de savoir ce qui est le mieux dans les levels : on va donc créer une variable chiffrée représentatif de chaque niveau :

    dict_rankid_challenges = {"NONE": 0,
                              "IRON": 1,
                              "BRONZE": 2,
                              "SILVER": 3,
                              "GOLD": 4,
                              "PLATINUM": 5,
                              "DIAMOND": 6,
                              "MASTER": 7,
                              "GRANDMASTER": 8,
                              "CHALLENGER": 9
                              }
    data_joueur_challenges['level_number'] = data_joueur_challenges['level'].map(
        dict_rankid_challenges)

    try:  # si erreur, le joueur n'a aucun classement
        data_joueur_challenges['position'].fillna(0, inplace=True)
    except:
        data_joueur_challenges['position'] = 0

    # on retient ce qu'il nous intéresse
    data_joueur_challenges[['Joueur', 'challengeId', 'name', 'value', 'percentile', 'level', 'level_number', 'state', 'position',
                            'shortDescription', 'description', 'IRON', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']]
    data_joueur_challenges = data_joueur_challenges.reindex(columns=['Joueur', 'challengeId', 'name', 'value', 'percentile', 'level', 'level_number',
                                                            'state',  'position', 'shortDescription', 'description', 'IRON', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER'])
    return data_total_joueur, data_joueur_category, data_joueur_challenges


class Challenges(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self.defis = lire_bdd('challenges_data').transpose(
        ).sort_values(by="name", ascending=True)

        stp(self.bot)

    @interactions.extension_listener
    async def on_start(self):

        self.task1 = create_task(IntervalTrigger(60*60))(self.challenges_maj)
        self.task1.start()

    async def challenges_maj(self):
        '''Chaque jour, à 6h, on actualise les challenges.
        Cette requête est obligatoirement à faire une fois par jour, sur un créneau creux pour éviter de surcharger les requêtes Riot'''

        currentHour = str(datetime.datetime.now().hour)

        if currentHour == str(6):

            session = aiohttp.ClientSession()
            liste_summonername = lire_bdd('tracker', 'dict')

            for table in ['challenges_total', 'challenges_category', 'challenges_data']:
                supprimer_bdd(table)

            for summonername in liste_summonername.keys():

                total, category, challenges = await get_data_joueur(summonername, session)

                # si ce n'est pas un dataframe, la fonction a renvoyée 0, ce qui signifie : pas de données
                if isinstance(challenges, pd.DataFrame):
                    sauvegarde_bdd(total, 'challenges_total', 'append')
                    sauvegarde_bdd(category, 'challenges_category', 'append')
                    sauvegarde_bdd(challenges, 'challenges_data', 'append')

                    time.sleep(3)
                else:
                    print(f'{summonername} : Pas de données')
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

    @interactions.extension_command(name="challenges_liste",
                                    description="Liste des challenges")
    async def challenges_liste(self, ctx: CommandContext):

        em = interactions.Embed(
            title="Challenges", description="Explication des challenges")

        for i in range(0, 24):
            debut = 0 + i*10
            fin = 10 + i*10
            em.add_field(
                name=f"**Challenges part {i}**", value=f"`{self.defis['name'].unique()[debut:fin]}", inline=False)

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
        total_user, total_category, total_challenges = await get_data_joueur(summonername, session)
        
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

    @interactions.extension_command(name="challenges_top",
                                    description="Affiche un classement pour le défi spécifié",
                                    options=[
                                        Option(name="nbpages",
                                                    description="Quel page ? Les challenges sont en ordre alphabétique",
                                                    type=interactions.OptionType.INTEGER,
                                                    required=True)])
    async def challenges_top(self,
                             ctx: CommandContext,
                             nbpages: int):

        # 232 défis

        nbpages = nbpages - 1  # les users ne savent pas que ça commence à 0

        debut_range = 25 * nbpages
        fin_de_range = 25 * (nbpages + 1)

        # si la range de fin est supérieure au dernier de la liste... alors on prend la fin de la liste
        if fin_de_range > len(self.defis):
            fin_de_range = len(self.defis)

        # catégorie
        select = interactions.SelectMenu(
            options=[interactions.SelectOption(label=self.defis['name'].unique()[i], value=self.defis['name'].unique()[i],
                                               description=self.defis[self.defis['name'] == self.defis['name'].unique()[i]]['shortDescription'].to_numpy()[0]) for i in range(debut_range, fin_de_range)],
            placeholder="Choisis le défi")

        channel = ctx.channel

        fait_choix = await ctx.send('Choisis le défi ', components=[interactions.ActionRow(select)])

        def check(m):
            return m.author_id == ctx.author.id and m.origin_message.id == fait_choix.id

        name: interactions.Message = await wait_for_component(self.bot, "on_message_create", components=fait_choix, check=check, timeout=15)

        name_answer = name.values[0]

        bdd_user_challenges = lire_bdd('challenges_data').transpose()
        # on prend les éléments qui nous intéressent
        bdd_user_challenges = bdd_user_challenges[[
            'Joueur', 'name', 'value', 'description']]
        # on trie sur le challenge
        bdd_user_challenges = bdd_user_challenges[bdd_user_challenges['name'] == name_answer]
        # on prend le premier pour la description
        description = bdd_user_challenges['description'].iloc[0]
        # on fait les rank
        bdd_user_challenges['rank'] = bdd_user_challenges['value'].rank(
            method='min', ascending=False)
        # on les range en fonction du rang
        bdd_user_challenges = bdd_user_challenges.sort_values(
            by=['rank'], ascending=True)

        fig = px.histogram(bdd_user_challenges, x="Joueur", y="value",
                           color="Joueur", title=name_answer, text_auto=True)
        fig.write_image('plot.png')

        await name.send(f'Défis : ** {name_answer} **  \nDescription : {description}')
        await channel.send(files=interactions.File('plot.png'))
        os.remove('plot.png')

    @interactions.extension_command(name="challenges_top_name",
                                    description="Affiche un classement pour le défi spécifié (nom du defi)",
                                    options=[
                                        Option(name="defi",
                                                    description="Quel defi ?",
                                                    type=interactions.OptionType.STRING,
                                                    required=True)])
    async def challenges_top_name(self,
                                  ctx: CommandContext,
                                  defi: str):

        bdd_user_challenges = lire_bdd('challenges_data').transpose()
        # on prend les éléments qui nous intéressent
        bdd_user_challenges = bdd_user_challenges[[
            'Joueur', 'name', 'value', 'description']]
        # on trie sur le challenge
        bdd_user_challenges = bdd_user_challenges[bdd_user_challenges['name'] == defi]
        # on prend le premier pour la description
        description = bdd_user_challenges['description'].iloc[0]
        # on fait les rank
        bdd_user_challenges['rank'] = bdd_user_challenges['value'].rank(
            method='min', ascending=False)
        # on les range en fonction du rang
        bdd_user_challenges = bdd_user_challenges.sort_values(
            by=['rank'], ascending=True)

        fig = px.histogram(bdd_user_challenges, x="Joueur",
                           y="value", color="Joueur", title=defi, text_auto=True)
        fig.write_image('plot.png')

        await ctx.send(f'Défis : ** {defi} **  \nDescription : {description}', files=interactions.File("plot.png"))
        os.remove('plot.png')

    @interactions.extension_command(name="challenges_best", description="Meilleur classement pour les defis",
                                    options=[Option(name="summonername",
                                                    description="Nom du joueur (Pas d'espace dans le pseudo !)",
                                                    type=interactions.OptionType.STRING,
                                                    required=True)])
    async def challenges_best(self,
                              ctx: CommandContext,
                              summonername: str):

        # tous les summonername sont en minuscule :
        summonername = summonername.lower()
        # charge la data
        data = lire_bdd('challenges_data').transpose()
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
            await ctx.send(f"Pas de ranking pour {summonername} :(. Pas d'espace dans le pseudo")


def setup(bot):
    Challenges(bot)
