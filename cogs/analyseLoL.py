import interactions
from interactions import Choice, Option, Extension, CommandContext
import pandas as pd
import os
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import warnings
from skimage import io
from skimage.transform import resize
import asyncio
from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap, BoundaryNorm
import aiohttp
import json
from datetime import datetime

from fonctions.match import (match_by_puuid,
                             get_summoner_by_puuid,
                             get_version,
                             get_champ_list,
                             get_match_timeline,
                             label_ward)
from fonctions.channels_discord import get_embed
from fonctions.gestion_bdd import lire_bdd_perso
from fonctions.params import saison


choice_var = [Choice(name="dmg", value="dmg"),
              Choice(name="gold", value="gold"),
              Choice(name="vision", value="vision"),
              Choice(name="tank", value="tank"),
              Choice(name="heal alliés", value="heal_allies"),
              Choice(name="solokills", value="solokills")]


choice_analyse = [Choice(name="gold", value="gold"),
                  Choice(name='gold_team', value='gold_team'),
                  Choice(name='vision', value='vision'),
                  Choice(name='position', value='position')]

parameters_commun_stats_lol = [
    Option(
        name='season',
        description='saison lol',
        type=interactions.OptionType.INTEGER,
        required=False),
    Option(
        name='joueur',
        description='se focaliser sur un joueur ?',
        type=interactions.OptionType.STRING,
        required=False),
    Option(
        name='champion',
        description='se focaliser sur un champion ?',
        type=interactions.OptionType.STRING,
        required=False),
    Option(
        name='mode_de_jeu',
        description='se focaliser sur un mode de jeu ?',
        type=interactions.OptionType.STRING,
        required=False,
        choices=[
            Choice(name='soloq',
                   value='RANKED'),
            Choice(name='aram', value='ARAM')]),
    Option(
        name='top',
        description='top x ?',
        type=interactions.OptionType.INTEGER,
        required=False,
        choices=[
            Choice(name='3', value=3),
            Choice(name='5', value=5),
            Choice(name='7', value=7),
            Choice(name='10', value=10),
            Choice(name='15', value=15),
            Choice(name='20', value=20)]
    )]


def option_stats_lol(name,
                     choices: list,
                     parameters_commun_stats_lol,
                     description='type de recherche'):
    option = Option(
        name=name,
        description=description,
        type=interactions.OptionType.SUB_COMMAND,
        options=[
            Option(
                name='calcul',
                description='quel type de calcul ?',
                type=interactions.OptionType.STRING,
                required=True,
                choices=choices)] + parameters_commun_stats_lol)
    return option


def get_data_matchs(columns, season):
    df = lire_bdd_perso(
        f'SELECT id, joueur, champion, match_id, mode, season, {columns} from matchs where season = {season}', index_col='id').transpose()
    return df


def transformation_top(df,
                       value,
                       title,
                       top,
                       showlegend=False):

    # On retire les données sans item
    df_item = df[df[value] != 0]
    # On compte le nombre d'occurences
    df_group = df_item.groupby(value).count().reset_index()
    # On trie du plus grand au plus petit
    df_group = df_group.sort_values('joueur', ascending=False)
    # On retient le top x
    df_group = df_group.head(top)
    # On fait le graphique
    fig = px.histogram(df_group, value, 'joueur', color=value, title=title,
                       text_auto=".i").update_xaxes(categoryorder='total descending')
    # On enlève la légende et l'axe y
    fig.update_layout(showlegend=showlegend)
    fig.update_yaxes(visible=False)
    # On enregistre et transpose l'img aui format discord

    return fig


def dict_data(thisId: int,
              match_detail,
              info):
    try:
        if thisId > 4:
            infos1 = match_detail['info']['participants'][5][info]
            infos2 = match_detail['info']['participants'][6][info]
            infos3 = match_detail['info']['participants'][7][info]
            infos4 = match_detail['info']['participants'][8][info]
            infos5 = match_detail['info']['participants'][9][info]
            infos6 = match_detail['info']['participants'][0][info]
            infos7 = match_detail['info']['participants'][1][info]
            infos8 = match_detail['info']['participants'][2][info]
            infos9 = match_detail['info']['participants'][3][info]
            infos10 = match_detail['info']['participants'][4][info]
        else:
            infos1 = match_detail['info']['participants'][0][info]
            infos2 = match_detail['info']['participants'][1][info]
            infos3 = match_detail['info']['participants'][2][info]
            infos4 = match_detail['info']['participants'][3][info]
            infos5 = match_detail['info']['participants'][4][info]
            infos6 = match_detail['info']['participants'][5][info]
            infos7 = match_detail['info']['participants'][6][info]
            infos8 = match_detail['info']['participants'][7][info]
            infos9 = match_detail['info']['participants'][8][info]
            infos10 = match_detail['info']['participants'][9][info]
    except:
        if thisId > 4:
            infos1 = match_detail['info']['participants'][5]['challenges'][info]
            infos2 = match_detail['info']['participants'][6]['challenges'][info]
            infos3 = match_detail['info']['participants'][7]['challenges'][info]
            infos4 = match_detail['info']['participants'][8]['challenges'][info]
            infos5 = match_detail['info']['participants'][9]['challenges'][info]
            infos6 = match_detail['info']['participants'][0]['challenges'][info]
            infos7 = match_detail['info']['participants'][1]['challenges'][info]
            infos8 = match_detail['info']['participants'][2]['challenges'][info]
            infos9 = match_detail['info']['participants'][3]['challenges'][info]
            infos10 = match_detail['info']['participants'][4]['challenges'][info]
        else:
            infos1 = match_detail['info']['participants'][0]['challenges'][info]
            infos2 = match_detail['info']['participants'][1]['challenges'][info]
            infos3 = match_detail['info']['participants'][2]['challenges'][info]
            infos4 = match_detail['info']['participants'][3]['challenges'][info]
            infos5 = match_detail['info']['participants'][4]['challenges'][info]
            infos6 = match_detail['info']['participants'][5]['challenges'][info]
            infos7 = match_detail['info']['participants'][6]['challenges'][info]
            infos8 = match_detail['info']['participants'][7]['challenges'][info]
            infos9 = match_detail['info']['participants'][8]['challenges'][info]
            infos10 = match_detail['info']['participants'][9]['challenges'][info]

    liste = [infos1, infos2, infos3, infos4, infos5,
             infos6, infos7, infos8, infos9, infos10]

    return liste


class analyseLoL(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @interactions.extension_command(name="analyse_durant_la_game",
                                    description="Permet d'afficher des statistiques durant la game",
                                    options=[
                                        Option(
                                            name="summonername",
                                            description="Nom du joueur",
                                            type=interactions.OptionType.STRING,
                                            required=True),
                                        Option(
                                            name="stat",
                                            description="Quel stat ?",
                                            type=interactions.OptionType.STRING,
                                            required=True,
                                            choices=choice_analyse),
                                        Option(name="stat2",
                                               description="Quel stat ?",
                                               type=interactions.OptionType.STRING,
                                               required=False,
                                               choices=choice_analyse),
                                        Option(
                                            name="game",
                                            description="Numero Game",
                                            type=interactions.OptionType.INTEGER,
                                            required=False,
                                            min_value=0,
                                            max_value=10)])
    async def analyse(self,
                      ctx: CommandContext,
                      summonername: str,
                      stat: str,
                      stat2: str = "no",
                      game: int = 0):

        stat = [stat, stat2]
        liste_graph = list()
        liste_delete = list()
        
        summonername = summonername.lower()

        def graphique(fig, name):
            fig.write_image(name)
            liste_delete.append(name)
            liste_graph.append(interactions.File(name))

        await ctx.defer(ephemeral=False)

        global thisId, team
        # supprime les FutureWarnings dû à l'utilisation de pandas (.append/.drop)
        warnings.simplefilter(action='ignore', category=FutureWarning)
        pd.options.mode.chained_assignment = None  # default='warn'
        session = aiohttp.ClientSession()
        last_match, match_detail, me = await match_by_puuid(summonername, game, session)
        timeline = await get_match_timeline(session, last_match)

        # timestamp à diviser par 60000

        dict_joueur = []
        for i in range(0, 10):
            summoner = await get_summoner_by_puuid(session, timeline['metadata']['participants'][i])
            dict_joueur.append(summoner['name'].lower())

        await session.close()
        
        if summonername in dict_joueur:
            thisId = list(dict_joueur).index(summonername)

        if thisId <= 4:
            team = ['Team alliée', 'Team adverse']
        elif thisId >= 5:
            team = ['Team adverse', 'Team alliée']

        if "vision" in stat:

            df_timeline = pd.DataFrame(timeline['info']['frames'][1]['events'])

            minute = len(timeline['info']['frames']) - 1

            for i in range(2, minute):
                df_timeline2 = pd.DataFrame(
                    timeline['info']['frames'][i]['events'])
                df_timeline = df_timeline.append(df_timeline2)

            df_timeline['timestamp'] = df_timeline['timestamp'] / \
                60000  # arrondir à l'inférieur ou au supérieur ?

            pd.set_option('display.max_columns', None)

            df_ward = df_timeline[(df_timeline['type'] == 'WARD_PLACED') | (
                df_timeline['type'] == 'WARD_KILL')]

            df_ward['creatorId'].fillna(0, inplace=True)
            df_ward['killerId'].fillna(0, inplace=True)
            df_ward = df_ward.astype(
                {"creatorId": 'int32', "killerId": 'int32'})

            df_ward['joueur'] = df_ward['creatorId']

            df_ward['joueur'] = np.where(
                df_ward.joueur == 0, df_ward.killerId, df_ward.joueur)

            df_ward = df_ward.astype({"joueur": 'string'})

            df_ward['joueur'] = df_ward['joueur'].map({'1': dict_joueur[0],
                                                       '2': dict_joueur[1],
                                                       '3': dict_joueur[2],
                                                       '4': dict_joueur[3],
                                                       '5': dict_joueur[4],
                                                       '6': dict_joueur[5],
                                                       '7': dict_joueur[6],
                                                       '8': dict_joueur[7],
                                                       '9': dict_joueur[8],
                                                       '10': dict_joueur[9]})

            
            df_ward['points'] = df_ward['wardType'].map(label_ward).fillna(1)

            df_ward['size'] = 4

            df_ward['type'] = df_ward['type'].map({'WARD_PLACED': 'POSEES',
                                                   'WARD_KILL': 'DETRUITES'})

            df_ward['wardType'] = df_ward['wardType'].map({'YELLOW_TRINKET': 'Trinket jaune',
                                                           'UNDEFINED': 'Balise Zombie',
                                                           'CONTROL_WARD': 'Pink',
                                                           'SIGHT_WARD': 'Ward support',
                                                           'BLUE_TRINKET': 'Trinket bleu'
                                                           })

            df_ward = df_ward[df_ward['joueur'] == summonername]

            illustrative_var = np.array(df_ward['wardType'])
            illustrative_type = np.array(df_ward['type'])

            fig = px.scatter(x=df_ward['timestamp'], y=df_ward['points'], color=illustrative_var, range_y=[0, 6],
                             size=df_ward['size'], symbol=illustrative_type, title='Warding', width=1600,
                             height=800)
            fig.update_yaxes(showticklabels=False)
            fig.update_layout(xaxis_title='Temps',
                              font_size=18)

            graphique(fig, 'vision.png')

        if 'gold' in stat:

            df_timeline = pd.DataFrame(
                timeline['info']['frames'][1]['participantFrames'])
            df_timeline = df_timeline.transpose()
            df_timeline['timestamp'] = 0

            minute = len(timeline['info']['frames']) - 1

            for i in range(2, minute):
                df_timeline2 = pd.DataFrame(
                    timeline['info']['frames'][i]['participantFrames'])
                df_timeline2 = df_timeline2.transpose()
                df_timeline2['timestamp'] = i
                df_timeline = df_timeline.append(df_timeline2)

            df_timeline['joueur'] = df_timeline['participantId']

            df_timeline = df_timeline.astype({"joueur": 'string'})

            df_timeline['joueur'] = df_timeline['joueur'].map({'1': dict_joueur[0],
                                                               '2': dict_joueur[1],
                                                               '3': dict_joueur[2],
                                                               '4': dict_joueur[3],
                                                               '5': dict_joueur[4],
                                                               '6': dict_joueur[5],
                                                               '7': dict_joueur[6],
                                                               '8': dict_joueur[7],
                                                               '9': dict_joueur[8],
                                                               '10': dict_joueur[9]})

            fig = px.line(df_timeline, x='timestamp', y='totalGold', color='joueur', markers=True, title='Gold',
                          height=1000, width=1800)
            fig.update_layout(xaxis_title='Temps',
                              font_size=18)

            graphique(fig, 'gold.png')

        if 'gold_team' in stat:

            df_timeline = pd.DataFrame(
                timeline['info']['frames'][1]['participantFrames'])
            df_timeline = df_timeline.transpose()
            df_timeline['timestamp'] = 0

            minute = len(timeline['info']['frames']) - 1

            for i in range(2, minute):
                df_timeline2 = pd.DataFrame(
                    timeline['info']['frames'][i]['participantFrames'])
                df_timeline2 = df_timeline2.transpose()
                df_timeline2['timestamp'] = i
                df_timeline = df_timeline.append(df_timeline2)

            df_timeline['joueur'] = df_timeline['participantId']

            df_timeline['team'] = np.where(df_timeline.joueur <= 5, team[0], team[1])

            df_timeline = df_timeline.groupby(['team', 'timestamp'], as_index=False)[
                'totalGold'].sum()

            df_timeline_adverse = df_timeline[df_timeline['team'] == 'Team adverse'].reset_index(
                drop=True)
            df_timeline_alliee = df_timeline[df_timeline['team'] == 'Team alliée'].reset_index(
                drop=True)

            df_timeline_diff = pd.DataFrame(columns=['timestamp', 'ecart'])

            df_timeline_diff['timestamp'] = df_timeline['timestamp']

            df_timeline_diff['ecart'] = df_timeline_alliee['totalGold'] - \
                (df_timeline_adverse['totalGold'])

            # Cela applique deux fois le timestamp (un pour les adversaires, un pour les alliés...) On supprime la moitié :

            df_timeline_diff.dropna(axis=0, inplace=True)

            df_timeline_diff['signe'] = np.where(df_timeline_diff.ecart < 0, 'negatif', 'positif')

            # Graphique
            # Src : https://matplotlib.org/stable/gallery/lines_bars_and_markers/multicolored_line.html

            val_min = df_timeline_diff['ecart'].min()
            val_max = df_timeline_diff['ecart'].max()

            x = df_timeline_diff['timestamp']
            y = df_timeline_diff['ecart']

            points = np.array([x, y]).T.reshape(-1, 1, 2)

            segments = np.concatenate([points[:-1], points[1:]], axis=1)

            fig, ax = plt.figure(figsize=(25, 10)), plt.axes()

            df_timeline_diff.iloc[0, 2] = df_timeline_diff.iloc[1, 2]

            plt.title('Ecart gold')

            cmap = ListedColormap(['r', 'b'])
            norm = BoundaryNorm([val_min, 0, val_max], cmap.N)
            lc = LineCollection(segments, cmap=cmap, norm=norm)
            lc.set_array(y)
            lc.set_linewidth(2)
            line = ax.add_collection(lc)

            def add_value_label(x_list, y_list):
                for i in range(1, len(x_list)+1):
                    plt.text(i, y_list[i-1], y_list[i-1])

            add_value_label(x, y)
            ax.set_xlim(x.min(), x.max())
            ax.set_ylim(y.min(), y.max())

            plt.savefig('gold_team.png')
            liste_delete.append('gold_team.png')
            liste_graph.append(interactions.File('gold_team.png'))

        if 'position' in stat:

            df_timeline = pd.DataFrame(
                timeline['info']['frames'][1]['participantFrames'])
            df_timeline = df_timeline.transpose()
            df_timeline['timestamp'] = 0

            minute = len(timeline['info']['frames']) - 1

            for i in range(2, minute):
                df_timeline2 = pd.DataFrame(
                    timeline['info']['frames'][i]['participantFrames'])
                df_timeline2 = df_timeline2.transpose()
                df_timeline2['timestamp'] = i
                df_timeline = df_timeline.append(df_timeline2)

            df_timeline['joueur'] = df_timeline['participantId']

            df_timeline = df_timeline.astype({"joueur": 'string'})

            df_timeline['joueur'] = df_timeline['joueur'].map({'1': dict_joueur[0],
                                                               '2': dict_joueur[1],
                                                               '3': dict_joueur[2],
                                                               '4': dict_joueur[3],
                                                               '5': dict_joueur[4],
                                                               '6': dict_joueur[5],
                                                               '7': dict_joueur[6],
                                                               '8': dict_joueur[7],
                                                               '9': dict_joueur[8],
                                                               '10': dict_joueur[9]})

            df_timeline = df_timeline[df_timeline['joueur'] == summonername]

            img = io.imread('https://map.riftkit.net/img/rift/normal.jpg')

            # 3750 taille optimale et 4 en diviseur
            x_pos = 468.75
            y_pos = 468.75
            diviseur = 32

            img = resize(img, (x_pos, y_pos), anti_aliasing=False)

            fig = px.imshow(img)

            for i in range(0, minute - 1):
                x = [df_timeline['position'][i]['x'] / diviseur]
                y = [y_pos - (df_timeline['position'][i]['y'] / diviseur)]

                if i < 10:
                    color = 'red'
                elif 10 <= i < 20:
                    color = 'cyan'
                elif 20 <= i < 30:
                    color = 'lightgreen'
                else:
                    color = 'goldenrod'

                fig.add_trace(
                    go.Scatter(x=x, y=y, mode="markers+text", text=str(i + 1), marker=dict(color=color, size=20),
                               textposition='top center', textfont=dict(size=35, color=color)))

            fig.update_layout(width=1200, height=1200)
            fig.update_layout(coloraxis_showscale=False, showlegend=False)

            fig.update_xaxes(showticklabels=False)
            fig.update_yaxes(showticklabels=False)
            fig.update_yaxes(automargin=True)
            fig.update_xaxes(automargin=True)

            graphique(fig, 'position.png')

        await ctx.send(files=liste_graph)

        for graph in liste_delete:
            os.remove(graph)

    @interactions.extension_command(name="analyse_fin_de_game",
                                    description="Voir des stats de fin de game",
                                    options=[
                                        Option(
                                            name="summonername",
                                            description="Nom du joueur",
                                            type=interactions.OptionType.STRING,
                                            required=True),
                                        Option(
                                            name="stat",
                                            description="Quel stat ?",
                                            type=interactions.OptionType.STRING,
                                            required=True,
                                            choices=choice_var),
                                        Option(
                                            name="stat2",
                                            description="Quel stat ?",
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=choice_var),
                                        Option(
                                            name="stat3",
                                            description="Quel stat ?",
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=choice_var),
                                        Option(
                                            name="game",
                                            description="Game de 0 à 10 (0 étant la dernière)",
                                            type=interactions.OptionType.INTEGER,
                                            required=False,
                                            min_value=0,
                                            max_value=10)])
    async def var(self,
                  ctx: CommandContext,
                  summonername, stat: str,
                  stat2: str = 'no',
                  stat3: str = 'no',
                  game: int = 0):

        stat = [stat, stat2, stat3]

        await ctx.defer(ephemeral=False)

        liste_delete = list()
        liste_graph = list()

        def graphique(fig, name):
            fig.write_image(name)
            liste_delete.append(name)
            liste_graph.append(interactions.File(name))

        session = aiohttp.ClientSession()

        last_match, match_detail_stats, me = await match_by_puuid(summonername, game, session)

        match_detail = pd.DataFrame(match_detail_stats)

        version = await get_version(session)

        current_champ_list = await get_champ_list(session, version)

        await session.close()

        champ_dict = {}
        for key in current_champ_list['data']:
            row = current_champ_list['data'][key]
            champ_dict[row['key']] = row['id']

        dic = {
            (match_detail['info']['participants'][0]['summonerName']).lower().replace(" ", ""): 0,
            (match_detail['info']['participants'][1]['summonerName']).lower().replace(" ", ""): 1,
            (match_detail['info']['participants'][2]['summonerName']).lower().replace(" ", ""): 2,
            (match_detail['info']['participants'][3]['summonerName']).lower().replace(" ", ""): 3,
            (match_detail['info']['participants'][4]['summonerName']).lower().replace(" ", ""): 4,
            (match_detail['info']['participants'][5]['summonerName']).lower().replace(" ", ""): 5,
            (match_detail['info']['participants'][6]['summonerName']).lower().replace(" ", ""): 6,
            (match_detail['info']['participants'][7]['summonerName']).lower().replace(" ", ""): 7,
            (match_detail['info']['participants'][8]['summonerName']).lower().replace(" ", ""): 8,
            (match_detail['info']['participants'][9]['summonerName']).lower().replace(" ", ""): 9
        }

        thisId = dic[
            summonername.lower().replace(" ", "")]  # cherche le pseudo dans le dico et renvoie le nombre entre 0 et 9

        pseudo = dict_data(thisId, match_detail, 'summonerName')
        thisChamp = dict_data(thisId, match_detail, 'championId')

        champ_names = []
        for i in range(len(thisChamp)):
            champ_names.append(champ_dict[str(thisChamp[i])])


        try:
            if "dmg" in stat:

                thisStats = dict_data(
                    thisId, match_detail, 'totalDamageDealtToChampions')

                dict_score = {pseudo[i] + "(" + champ_names[i] + ")": thisStats[i] for i in range(len(pseudo))}

                df = pd.DataFrame.from_dict(dict_score, orient='index')
                df = df.reset_index()
                df = df.rename(columns={"index": "pseudo", 0: 'dmg'})

                fig = px.histogram(
                    df, y="pseudo", x="dmg", color="pseudo", title="Total DMG", text_auto=True)
                fig.update_layout(showlegend=False)

                graphique(fig, 'dmg.png')

            if "gold" in stat:

                thisStats = dict_data(thisId, match_detail, 'goldEarned')

                dict_score = {pseudo[i] + "(" + champ_names[i] + ")": thisStats[i] for i in range(len(pseudo))}

                # print(dict_score)
                df = pd.DataFrame.from_dict(dict_score, orient='index')
                df = df.reset_index()
                df = df.rename(columns={"index": "pseudo", 0: 'gold'})

                fig = px.histogram(
                    df, y="pseudo", x="gold", color="pseudo", title="Total Gold", text_auto=True)
                fig.update_layout(showlegend=False)

                graphique(fig, 'gold.png')

            if "vision" in stat:

                thisStats = dict_data(thisId, match_detail, 'visionScore')

                dict_score = {pseudo[i] + "(" + champ_names[i] + ")": thisStats[i] for i in range(len(pseudo))}

                df = pd.DataFrame.from_dict(dict_score, orient='index')
                df = df.reset_index()
                df = df.rename(columns={"index": "pseudo", 0: 'vision'})

                fig = px.histogram(
                    df, y="pseudo", x="vision", color="pseudo", title="Total Vision", text_auto=True)
                fig.update_layout(showlegend=False)

                graphique(fig, 'vision.png')

            if "tank" in stat:

                totalDamageTaken = dict_data(
                    thisId, match_detail, 'totalDamageTaken')
                damageSelfMitigated = dict_data(
                    thisId, match_detail, 'damageSelfMitigated')

                dict_score = {pseudo[i] + "(" + champ_names[i] + ")": thisStats[i] for i in range(len(pseudo))}

                # print(dict_score)
                df = pd.DataFrame.from_dict(dict_score, orient='index')
                df = df.reset_index()
                df = df.rename(
                    columns={"index": "pseudo", 0: 'dmg_tank', 1: 'dmg_reduits'})

                fig = go.Figure()
                fig.add_trace(go.Bar(y=df['dmg_reduits'].values, x=df['pseudo'].values, text=df['dmg_reduits'].values,
                                     marker_color='rgb(55,83,109)', name="Dmg reduits"))
                fig.add_trace(go.Bar(y=df['dmg_tank'].values, x=df['pseudo'].values, text=df['dmg_tank'].values,
                                     marker_color='rgb(26,118,255)', name='Dmg tank'))

                fig.update_traces(
                    texttemplate='%{text:.2s}', textposition='auto')
                fig.update_layout(title='Dmg encaissés',
                                  uniformtext_minsize=8, uniformtext_mode='hide')
                fig.update_layout(barmode='stack')

                graphique(fig, 'tank.png')

            if "heal_allies" in stat:

                thisStats = dict_data(
                    thisId, match_detail, 'totalHealsOnTeammates')

                dict_score = {pseudo[i] + "(" + champ_names[i] + ")": thisStats[i] for i in range(len(pseudo))}

                # print(dict_score)
                df = pd.DataFrame.from_dict(dict_score, orient='index')
                df = df.reset_index()
                df = df.rename(columns={"index": "pseudo", 0: 'heal_allies'})

                fig = px.histogram(df, y="pseudo", x="heal_allies", color="pseudo", title="Total Heal allies",
                                   text_auto=True)
                fig.update_layout(showlegend=False)

                graphique(fig, 'heal_allies.png')

            if "solokills" in stat:

                thisStats = dict_data(thisId, match_detail, 'soloKills')

                dict_score = {pseudo[i] + "(" + champ_names[i] + ")": thisStats[i] for i in range(len(pseudo))}

                df = pd.DataFrame.from_dict(dict_score, orient='index')
                df = df.reset_index()
                df = df.rename(columns={"index": "pseudo", 0: 'SoloKills'})

                fig = px.histogram(df, y="pseudo", x="SoloKills", color="pseudo", title="Total SoloKills",
                                   text_auto=True)
                fig.update_layout(showlegend=False)

                graphique(fig, 'solokills.png')

            await ctx.send(files=liste_graph)

            for graph in liste_delete:
                os.remove(graph)

        except asyncio.TimeoutError:
            await stat.delete()
            await ctx.send("Annulé")

    choice_comptage = Choice(name='comptage', value='count')
    choice_winrate = Choice(name='winrate', value='winrate')
    choice_avg = Choice(name='avg', value='avg')
    choice_progression = Choice(name='progression', value='progression')

    @interactions.extension_command(name="stats_lol",
                                    description="Historique de game",
                                    options=[
                                        option_stats_lol(name='items',
                                                              choices=[
                                                                  choice_comptage, choice_winrate],
                                                              parameters_commun_stats_lol=parameters_commun_stats_lol,
                                                              description='stats sur les items'),
                                        option_stats_lol(name='champion',
                                                              choices=[
                                                                  choice_comptage, choice_winrate],
                                                              parameters_commun_stats_lol=parameters_commun_stats_lol,
                                                              description='stats sur les champions'),
                                        option_stats_lol(name='dommage',
                                                              choices=[
                                                                  choice_avg],
                                                              parameters_commun_stats_lol=parameters_commun_stats_lol,
                                                              description='stats sur les dégats'),
                                        option_stats_lol(name='tank',
                                                              choices=[
                                                                  choice_avg],
                                                              parameters_commun_stats_lol=parameters_commun_stats_lol,
                                                              description='stats sur le tanking'),
                                        option_stats_lol(name='kda',
                                                              choices=[
                                                                  choice_avg],
                                                              parameters_commun_stats_lol=parameters_commun_stats_lol,
                                                              description='stats sur le kda'),
                                        option_stats_lol(name='lp',
                                                              choices=[
                                                                  choice_progression],
                                                              parameters_commun_stats_lol=parameters_commun_stats_lol,
                                                              description='stats sur les lp'),
                                        option_stats_lol(name='games',
                                                              choices=[
                                                                  choice_comptage],
                                                              parameters_commun_stats_lol=parameters_commun_stats_lol,
                                                              description='stats sur les games')
                                    ])
    async def historique_lol(self,
                             ctx: CommandContext,
                             sub_command: str,
                             calcul: str,
                             season: int = saison,
                             joueur: str = None,
                             champion: str = None,
                             mode_de_jeu: str = None,
                             top: int = 20):

        dict_type = {
            'dommage': 'dmg, dmg_ad, dmg_ap, dmg_true',
            'tank': 'dmg_reduit, dmg_tank',
            'champion': 'victoire',
            'kda': 'kills, assists, deaths',
            'type': sub_command,
            'lp': 'date, lp, tier, rank',
            'games': 'victoire'
        }

        await ctx.defer(ephemeral=False)

        if sub_command == 'items':
            column = 'item1, item2, item3, item4, item5, item6, victoire'
            column_list = ['item1', 'item2',
                           'item3', 'item4', 'item5', 'item6']
            df = get_data_matchs(column, saison)
            with open('./obj/item.json', encoding='utf-8') as mon_fichier:
                data = json.load(mon_fichier)
            for column_item in column_list:
                df[column_item] = df[column_item].apply(
                    lambda x: 0 if x == 0 else data['data'][str(x)]['name'])

        else:

            df = get_data_matchs(dict_type[sub_command], saison)

        title = f'{sub_command}'

        df[df['season'] == season]

        if joueur != None:
            joueur = joueur.lower()
            df = df[df['joueur'] == joueur]
            title += f' pour {joueur}'

        if champion != None:
            df = df[df['champion'] == champion]
            title += f' sur {champion}'

        if mode_de_jeu != None:
            df = df[df['mode'] == mode_de_jeu]
            title += f' en {mode_de_jeu}'

        title += f' ({calcul})'

        # if calcul == 'count':

        if sub_command == 'items':

            select = interactions.SelectMenu(
                options=[
                    interactions.SelectOption(
                        label="item1", value="item1", emoji=interactions.Emoji(name='1️⃣')),
                    interactions.SelectOption(
                        label="item2", value="item2", emoji=interactions.Emoji(name='2️⃣')),
                    interactions.SelectOption(
                        label="item3", value="item3", emoji=interactions.Emoji(name='3️⃣')),
                    interactions.SelectOption(
                        label="item4", value="item4", emoji=interactions.Emoji(name='4️⃣')),
                    interactions.SelectOption(
                        label="item5", value="item5", emoji=interactions.Emoji(name='5️⃣')),
                    interactions.SelectOption(
                        label="item6", value="item6", emoji=interactions.Emoji(name='6️⃣'))
                ],
                custom_id='items',
                placeholder="Ordre d'item",
                min_values=1,
                max_values=1
            )

            title += f' | Top {top}'

            await ctx.send("Pour quel slot d'item ?",
                           components=select)

            async def check(button_ctx):
                if int(button_ctx.author.user.id) == int(ctx.author.user.id):
                    return True
                await ctx.send("I wasn't asking you!", ephemeral=True)
                return False

            if calcul == 'count':
                while True:
                    try:
                        button_ctx: interactions.ComponentContext = await self.bot.wait_for_component(
                            components=select, check=check, timeout=30
                        )
                        fig = transformation_top(
                            df, button_ctx.data.values[0], title, top)
                        embed, file = get_embed(fig, 'stats')
                        # On envoie

                        await ctx.edit(embeds=embed, files=file)

                    except asyncio.TimeoutError:
                        # When it times out, edit the original message and remove the button(s)
                        return await ctx.edit(components=[])

            elif calcul == 'winrate':
                while True:
                    try:
                        button_ctx: interactions.ComponentContext = await self.bot.wait_for_component(
                            components=select, check=check, timeout=30
                        )
                        df['victoire'] = df['victoire'].replace(
                            {True: 'Victoire', False: 'Defaite'})

                        df_item = df[df[button_ctx.data.values[0]] != 0]

                        df_item = df_item[[
                            'joueur', button_ctx.data.values[0], 'victoire']]
                        # On compte le nombre d'occurences
                        df_group = df_item.groupby(['joueur', button_ctx.data.values[0]]).agg([
                            'count']).reset_index()
                        df_group = df_group.droplevel(1, axis=1)
                        df_group.rename(
                            columns={'victoire': 'count'}, inplace=True)
                        df_item = df_item.merge(df_group, how='left', on=[
                                                'joueur', button_ctx.data.values[0]])
                        # df_item.drop_duplicates(inplace=True)
                        df_item = df_item.sort_values(
                            ['count'], ascending=False)
                        df_item = df_item.head(top)
                        # On fait le graphique
                        fig = px.histogram(df_item, button_ctx.data.values[0], 'victoire', pattern_shape='victoire', color=button_ctx.data.values[
                                           0], title=title, text_auto=True, histfunc='count').update_xaxes(categoryorder='total descending')
                        # On enlève la légende et l'axe y
                        fig.update_layout(showlegend=False)
                        fig.update_yaxes(visible=False)
                        embed, file = get_embed(fig, 'stats')

                        embed.add_field(
                            name='description', value='Non-grisé : Victoire | Grisé : Défaite')
                        # On envoie
                        await ctx.edit(embeds=embed, files=file)
                    except asyncio.TimeoutError:
                        # When it times out, edit the original message and remove the button(s)
                        return await ctx.edit(components=[])

        elif sub_command == 'champion':
            if calcul == 'count':
                if joueur != None:
                    showlegend = True
                else:
                    showlegend = False
                fig = transformation_top(
                    df, 'champion', title, top, showlegend=showlegend)
                embed, files = get_embed(fig, 'champion')
                await ctx.send(embeds=embed, files=files)

            elif type == 'winrate':

                df['victoire'] = df['victoire'].map({True: 'Victoire',
                                                     False: 'Défaite'})

                values = df['victoire'].value_counts()
                fig = go.Figure(
                    data=[go.Pie(labels=values.index, values=values)])
                fig.update_layout(title=title)

                embed, files = get_embed(fig, 'wr')

                await ctx.send(embeds=embed, files=files)

            else:
                await ctx.send('Non disponible')
                pass

        elif sub_command in ['dommage', 'tank', 'kda']:
            if calcul == 'avg':

                dict_stats = {'dommage': {'dmg': 'total', 'dmg_ad': 'ad', 'dmg_ap': 'ap', 'dmg_true': 'true'},
                              'tank': {'dmg_tank': 'tank', 'dmg_reduit': 'reduit'},
                              'kda': {'kills': 'K', 'deaths': 'D', 'assists': 'A'}}

                dict_stats_choose = dict_stats[sub_command]

                fig = go.Figure()
                fig.update_layout(title=title)

                for column, name in dict_stats_choose.items():

                    fig.add_trace(go.Histogram(x=df['joueur'], y=df[column], histfunc='avg', name=name,
                                               texttemplate="%{y:.0f}")).update_xaxes(categoryorder='total descending')

                fig.update_yaxes(visible=False)

                embed, files = get_embed(fig, 'stats')

                await ctx.send(embeds=embed, files=files)

        if sub_command == 'lp':
            if calcul == 'progression':
                if mode_de_jeu != None:  # on impose un mode de jeu, sinon les lp vont s'entremeler, ce qui n'a aucun sens
                    
                    dict_points = {'F' : 0,
                                    'B' : 1000,
                                    'S' : 2000,
                                    'G' : 3000,
                                    'P' : 4000,
                                    'D' : 5000,
                                    'M' : 6000,
                                    'G' : 7000,
                                    'C' : 8000,
                                    'I' : 100,
                                    'II' : 200,
                                    'III' : 300,
                                    'IV' : 400,
                                    ' ' : 0,
                                    '' : 0}
                    
                    def transfo_points(x, mode):
                        if mode == 'RANKED':
                            value = x['ladder'].split(' ')[1]
                            points = dict_points[x['ladder'][0]] + dict_points[value] + x['lp']
                        elif mode == 'ARAM':
                            points = dict_points[x['tier'][0]] + x['lp']
                        return points
                    
                    
                    
                    if mode_de_jeu == 'RANKED':
                        df['ladder'] = df['tier'].str[0] + ' ' + df['rank'] + ' / ' + df['lp'].astype('str') + ' LP'

                        df['date'] = df['date'].apply(
                            lambda x: datetime.fromtimestamp(x).strftime('%d/%m/%Y'))
                        df['datetime'] = pd.to_datetime(
                            df['date'], infer_datetime_format=True)
                        
                        df.sort_values(['date'], ascending=False, inplace=True)

                        df['date'] = df['datetime'].dt.strftime('%d %m')
                        
                        df = df.groupby(['joueur', 'date', 'ladder']).agg({'lp' : 'max'}).reset_index()
                        
                        df['jour'] = df['date'].astype('str').str[:2]
                        df['mois'] = df['date'].astype('str').str[3:]

                        df.sort_values(['mois', 'jour'], ascending=[True, True], inplace=True)
                        
                        df['points'] = df.apply(transfo_points, axis=1, mode='RANKED')
                        
                        
                        fig = px.line(df, x='date', y='points',
                                      color='joueur', text='ladder', title=title)
                        
                        fig.update_yaxes(visible=False)
                        
                        # on ré-order l'axe des dates. 
                        fig.update_xaxes(categoryorder='array', categoryarray=df['date'].to_xarray().values)
                    
                    elif mode_de_jeu == 'ARAM':
                        df['date'] = df['date'].apply(
                            lambda x: datetime.fromtimestamp(x).strftime('%d/%m/%Y'))
                        df['datetime'] = pd.to_datetime(
                            df['date'], infer_datetime_format=True)
                        df.sort_values(['datetime'], ascending=True, inplace=True)

                        df['date'] = df['datetime'].dt.strftime('%d %m')
                        
                        df['ladder'] = df['tier'].str[0] + ' / ' + df['lp'].astype('str') + ' LP'
                        
                        df = df.groupby(['joueur', 'date', 'tier']).agg({'lp' : 'max'}).reset_index()
                        
                        df['jour'] = df['date'].astype('str').str[:2]
                        df['mois'] = df['date'].astype('str').str[3:]

                        df.sort_values(['mois', 'jour'], ascending=[True, True], inplace=True)
                        
                        df['points'] = df.apply(transfo_points, axis=1, mode='ARAM')
                        
                        
                        fig = px.line(df, x='date', y='points',
                                  color='joueur', text='tier', title=title)
                        
                        fig.update_yaxes(visible=False)
                        
                        # on ré-order l'axe des dates.
                        fig.update_xaxes(categoryorder='array', categoryarray=df['date'].to_xarray().values)
                        

                    embed, files = get_embed(fig, 'evo')

                    await ctx.send(embeds=embed, files=files)
                else:
                    await ctx.send('Tu dois selectionner un mode de jeu pour cette analyse.')

        if sub_command == 'games':
            if calcul == 'count':
                df = df.groupby('joueur').count()
                fig = px.histogram(x=df.index, y=df['victoire'], color=df.index, text_auto=True, title=title).update_xaxes(
                    categoryorder="total descending")
                fig.update_layout(showlegend=False)
                embed, files = get_embed(fig, 'games')

                await ctx.send(embeds=embed, files=files)


def setup(bot):
    analyseLoL(bot)
