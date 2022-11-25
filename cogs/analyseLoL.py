import interactions
from interactions import Choice, Option
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
import seaborn as sns


from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap, BoundaryNorm

from fonctions.match import (match_by_puuid,
                             lol_watcher,
                             my_region,
                             region)

# Paramètres LoL
version = lol_watcher.data_dragon.versions_for_region(my_region)
champions_versions = version['n']['champion']


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


def dict_data(thisId: int, match_detail, info):
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

    liste = [infos1, infos2, infos3, infos4, infos5, infos6, infos7, infos8, infos9, infos10]

    return liste




class analyseLoL(interactions.Extension):
    def __init__(self, bot):
        self.bot : interactions.Client = bot

    @interactions.extension_command(name="analyse",
                       description="Permet d'afficher des statistiques durant la game",
                       options=[Option(
                                    name="summonername",
                                    description = "Nom du joueur",
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
    async def analyse(self, ctx:interactions.CommandContext, summonername:str, stat:str, stat2:str = "no", game:int=0):
    
        
        stat = [stat, stat2]
        liste_graph = list()
        liste_delete = list()
        

        
        def graphique(fig, name):
            fig.write_image(name)
            liste_delete.append(name)
            liste_graph.append(interactions.File(name))
        

        await ctx.defer(ephemeral=False)
        

        
        global thisId, team
        warnings.simplefilter(action='ignore', category=FutureWarning)  # supprime les FutureWarnings dû à l'utilisation de pandas (.append/.drop)
        pd.options.mode.chained_assignment = None  # default='warn'
        last_match, match_detail, me = match_by_puuid(summonername, game)
        timeline = lol_watcher.match.timeline_by_match(region, last_match)
        

            

        # timestamp à diviser par 60000

        dict_joueur = [lol_watcher.summoner.by_puuid(my_region, timeline['metadata']['participants'][i])['name'] for i
                       in range(0, 10)]  # liste en compréhension
        

        
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
                df_timeline2 = pd.DataFrame(timeline['info']['frames'][i]['events'])
                df_timeline = df_timeline.append(df_timeline2)

            df_timeline['timestamp'] = df_timeline['timestamp'] / 60000  # arrondir à l'inférieur ou au supérieur ?

            pd.set_option('display.max_columns', None)

            df_ward = df_timeline[(df_timeline['type'] == 'WARD_PLACED') | (df_timeline['type'] == 'WARD_KILL')]

            df_ward['creatorId'].fillna(0, inplace=True)
            df_ward['killerId'].fillna(0, inplace=True)
            df_ward = df_ward.astype({"creatorId": 'int32', "killerId": 'int32'})

            df_ward['joueur'] = df_ward['creatorId']

            df_ward['joueur'] = np.where(df_ward.joueur == 0, df_ward.killerId, df_ward.joueur)

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
            df_ward['points'] = 1
            df_ward['points'] = np.where(df_ward.wardType == 'YELLOW TRINKET', 1, df_ward.points)
            df_ward['points'] = np.where(df_ward.wardType == 'UNDEFINED', 2, df_ward.points)
            df_ward['points'] = np.where(df_ward.wardType == 'CONTROL_WARD', 3, df_ward.points)
            df_ward['points'] = np.where(df_ward.wardType == 'SIGHT_WARD', 4, df_ward.points)
            df_ward['points'] = np.where(df_ward.wardType == 'BLUE_TRINKET', 5, df_ward.points)

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

            df_timeline = pd.DataFrame(timeline['info']['frames'][1]['participantFrames'])
            df_timeline = df_timeline.transpose()
            df_timeline['timestamp'] = 0

            minute = len(timeline['info']['frames']) - 1

            for i in range(2, minute):
                df_timeline2 = pd.DataFrame(timeline['info']['frames'][i]['participantFrames'])
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
                


            df_timeline = pd.DataFrame(timeline['info']['frames'][1]['participantFrames'])
            df_timeline = df_timeline.transpose()
            df_timeline['timestamp'] = 0

            minute = len(timeline['info']['frames']) - 1

            for i in range(2, minute):
                df_timeline2 = pd.DataFrame(timeline['info']['frames'][i]['participantFrames'])
                df_timeline2 = df_timeline2.transpose()
                df_timeline2['timestamp'] = i
                df_timeline = df_timeline.append(df_timeline2)

            df_timeline['joueur'] = df_timeline['participantId']

            df_timeline['team'] = "a"
            df_timeline['team'] = np.where(df_timeline.joueur <= 5, team[0], df_timeline.team)
            df_timeline['team'] = np.where(df_timeline.joueur >= 6, team[1], df_timeline.team)

            df_timeline = df_timeline.groupby(['team', 'timestamp'], as_index=False)['totalGold'].sum()

            df_timeline_adverse = df_timeline[df_timeline['team'] == 'Team adverse'].reset_index(drop=True)
            df_timeline_alliee = df_timeline[df_timeline['team'] == 'Team alliée'].reset_index(drop=True)
                        


            df_timeline_diff = pd.DataFrame(columns=['timestamp', 'ecart'])

            df_timeline_diff['timestamp'] = df_timeline['timestamp']

            df_timeline_diff['ecart'] = df_timeline_alliee['totalGold'] - (df_timeline_adverse['totalGold'])

            # Cela applique deux fois le timestamp (un pour les adversaires, un pour les alliés...) On supprime la moitié :

            df_timeline_diff.dropna(axis=0, inplace=True)

            df_timeline_diff['signe'] = "a"
            df_timeline_diff['signe'] = np.where(df_timeline_diff.ecart < 0, "negatif", df_timeline_diff.signe)
            df_timeline_diff['signe'] = np.where(df_timeline_diff.ecart > 0, "positif", df_timeline_diff.signe)
            
            # Graphique
            # Src : https://matplotlib.org/stable/gallery/lines_bars_and_markers/multicolored_line.html
            
            val_min = df_timeline_diff['ecart'].min()
            val_max = df_timeline_diff['ecart'].max()
            
            x = df_timeline_diff['timestamp']
            y = df_timeline_diff['ecart']
                        
            points = np.array([x, y]).T.reshape(-1, 1, 2)
            
            segments = np.concatenate([points[:-1], points[1:]], axis=1)
                        
            fig, ax = plt.figure(figsize=(25,10)), plt.axes()

            df_timeline_diff.iloc[0, 2] = df_timeline_diff.iloc[1, 2]
            
            
            plt.title('Ecart gold')
            
            cmap = ListedColormap(['r', 'b'])
            norm = BoundaryNorm([val_min, 0, val_max], cmap.N)
            lc = LineCollection(segments, cmap=cmap, norm=norm)
            lc.set_array(y)
            lc.set_linewidth(2)
            line = ax.add_collection(lc)
            
            def add_value_label(x_list,y_list):
                for i in range(1, len(x_list)+1):
                    plt.text(i,y_list[i-1],y_list[i-1])
    
            add_value_label(x, y)
            ax.set_xlim(x.min(), x.max())
            ax.set_ylim(y.min(), y.max())
            
            plt.savefig('gold_team.png')
            liste_delete.append('gold_team.png')
            liste_graph.append(interactions.File('gold_team.png'))

        if 'position' in stat:

            df_timeline = pd.DataFrame(timeline['info']['frames'][1]['participantFrames'])
            df_timeline = df_timeline.transpose()
            df_timeline['timestamp'] = 0

            minute = len(timeline['info']['frames']) - 1

            for i in range(2, minute):
                df_timeline2 = pd.DataFrame(timeline['info']['frames'][i]['participantFrames'])
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

    interactions.CommandContext.send
    @interactions.extension_command(name="var",
                       description="Voir des stats de fin de game",
                       options=[Option(
                                    name="summonername",
                                    description = "Nom du joueur",
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
    async def var(self, ctx:interactions.CommandContext, summonername, stat:str, stat2:str='no', stat3:str='no', game:int=0):
        
        
        
        stat = [stat, stat2, stat3]
        
        await ctx.defer(ephemeral=False)
        
        liste_delete = list()
        liste_graph = list()
        
        def graphique(fig, name):
            fig.write_image(name)
            liste_delete.append(name)
            liste_graph.append(interactions.File(name))
        

        last_match, match_detail_stats, me = match_by_puuid(summonername, game)

        match_detail = pd.DataFrame(match_detail_stats)

        current_champ_list = lol_watcher.data_dragon.champions(champions_versions, False, 'fr_FR')

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

        thisChampName1 = champ_dict[str(thisChamp[0])]
        thisChampName2 = champ_dict[str(thisChamp[1])]
        thisChampName3 = champ_dict[str(thisChamp[2])]
        thisChampName4 = champ_dict[str(thisChamp[3])]
        thisChampName5 = champ_dict[str(thisChamp[4])]
        thisChampName6 = champ_dict[str(thisChamp[5])]
        thisChampName7 = champ_dict[str(thisChamp[6])]
        thisChampName8 = champ_dict[str(thisChamp[7])]
        thisChampName9 = champ_dict[str(thisChamp[8])]
        thisChampName10 = champ_dict[str(thisChamp[9])]

        try:
            if "dmg" in stat:

                thisStats = dict_data(thisId, match_detail, 'totalDamageDealtToChampions')

                dict_score = {
                    pseudo[0] + "(" + thisChampName1 + ")": thisStats[0],
                    pseudo[1] + "(" + thisChampName2 + ")": thisStats[1],
                    pseudo[2] + "(" + thisChampName3 + ")": thisStats[2],
                    pseudo[3] + "(" + thisChampName4 + ")": thisStats[3],
                    pseudo[4] + "(" + thisChampName5 + ")": thisStats[4],
                    pseudo[5] + "(" + thisChampName6 + ")": thisStats[5],
                    pseudo[6] + "(" + thisChampName7 + ")": thisStats[6],
                    pseudo[7] + "(" + thisChampName8 + ")": thisStats[7],
                    pseudo[8] + "(" + thisChampName9 + ")": thisStats[8],
                    pseudo[9] + "(" + thisChampName10 + ")": thisStats[9],
                }

                df = pd.DataFrame.from_dict(dict_score, orient='index')
                df = df.reset_index()
                df = df.rename(columns={"index": "pseudo", 0: 'dmg'})


                fig = px.histogram(df, y="pseudo", x="dmg", color="pseudo", title="Total DMG", text_auto=True)
                fig.update_layout(showlegend=False)

                graphique(fig, 'dmg.png')

            if "gold" in stat:

                thisStats = dict_data(thisId, match_detail, 'goldEarned')

                dict_score = {
                    pseudo[0] + "(" + thisChampName1 + ")": thisStats[0],
                    pseudo[1] + "(" + thisChampName2 + ")": thisStats[1],
                    pseudo[2] + "(" + thisChampName3 + ")": thisStats[2],
                    pseudo[3] + "(" + thisChampName4 + ")": thisStats[3],
                    pseudo[4] + "(" + thisChampName5 + ")": thisStats[4],
                    pseudo[5] + "(" + thisChampName6 + ")": thisStats[5],
                    pseudo[6] + "(" + thisChampName7 + ")": thisStats[6],
                    pseudo[7] + "(" + thisChampName8 + ")": thisStats[7],
                    pseudo[8] + "(" + thisChampName9 + ")": thisStats[8],
                    pseudo[9] + "(" + thisChampName10 + ")": thisStats[9],
                }

                # print(dict_score)
                df = pd.DataFrame.from_dict(dict_score, orient='index')
                df = df.reset_index()
                df = df.rename(columns={"index": "pseudo", 0: 'gold'})


                fig = px.histogram(df, y="pseudo", x="gold", color="pseudo", title="Total Gold", text_auto=True)
                fig.update_layout(showlegend=False)

                graphique(fig, 'gold.png')
            

            if "vision" in stat:

                thisStats = dict_data(thisId, match_detail, 'visionScore')

                dict_score = {
                    pseudo[0] + "(" + thisChampName1 + ")": thisStats[0],
                    pseudo[1] + "(" + thisChampName2 + ")": thisStats[1],
                    pseudo[2] + "(" + thisChampName3 + ")": thisStats[2],
                    pseudo[3] + "(" + thisChampName4 + ")": thisStats[3],
                    pseudo[4] + "(" + thisChampName5 + ")": thisStats[4],
                    pseudo[5] + "(" + thisChampName6 + ")": thisStats[5],
                    pseudo[6] + "(" + thisChampName7 + ")": thisStats[6],
                    pseudo[7] + "(" + thisChampName8 + ")": thisStats[7],
                    pseudo[8] + "(" + thisChampName9 + ")": thisStats[8],
                    pseudo[9] + "(" + thisChampName10 + ")": thisStats[9],
                }

                df = pd.DataFrame.from_dict(dict_score, orient='index')
                df = df.reset_index()
                df = df.rename(columns={"index": "pseudo", 0: 'vision'})

                fig = px.histogram(df, y="pseudo", x="vision", color="pseudo", title="Total Vision", text_auto=True)
                fig.update_layout(showlegend=False)

                graphique(fig, 'vision.png')

            if "tank" in stat:

                totalDamageTaken = dict_data(thisId, match_detail, 'totalDamageTaken')
                damageSelfMitigated = dict_data(thisId, match_detail, 'damageSelfMitigated')

                dict_score = {
                    pseudo[0] + "(" + thisChampName1 + ")": [totalDamageTaken[0], damageSelfMitigated[0]],
                    pseudo[1] + "(" + thisChampName2 + ")": [totalDamageTaken[1], damageSelfMitigated[1]],
                    pseudo[2] + "(" + thisChampName3 + ")": [totalDamageTaken[2], damageSelfMitigated[2]],
                    pseudo[3] + "(" + thisChampName4 + ")": [totalDamageTaken[3], damageSelfMitigated[3]],
                    pseudo[4] + "(" + thisChampName5 + ")": [totalDamageTaken[4], damageSelfMitigated[4]],
                    pseudo[5] + "(" + thisChampName6 + ")": [totalDamageTaken[5], damageSelfMitigated[5]],
                    pseudo[6] + "(" + thisChampName7 + ")": [totalDamageTaken[6], damageSelfMitigated[6]],
                    pseudo[7] + "(" + thisChampName8 + ")": [totalDamageTaken[7], damageSelfMitigated[7]],
                    pseudo[8] + "(" + thisChampName9 + ")": [totalDamageTaken[8], damageSelfMitigated[8]],
                    pseudo[9] + "(" + thisChampName10 + ")": [totalDamageTaken[9], damageSelfMitigated[9]],
                }

                # print(dict_score)
                df = pd.DataFrame.from_dict(dict_score, orient='index')
                df = df.reset_index()
                df = df.rename(columns={"index": "pseudo", 0: 'dmg_tank', 1: 'dmg_reduits'})

                fig = go.Figure()
                fig.add_trace(go.Bar(y=df['dmg_reduits'].values, x=df['pseudo'].values, text=df['dmg_reduits'].values,
                                     marker_color='rgb(55,83,109)', name="Dmg reduits"))
                fig.add_trace(go.Bar(y=df['dmg_tank'].values, x=df['pseudo'].values, text=df['dmg_tank'].values,
                                     marker_color='rgb(26,118,255)', name='Dmg tank'))

                fig.update_traces(texttemplate='%{text:.2s}', textposition='auto')
                fig.update_layout(title='Dmg encaissés', uniformtext_minsize=8, uniformtext_mode='hide')
                fig.update_layout(barmode='stack')

                graphique(fig, 'tank.png')

            if "heal_allies" in stat:

                thisStats = dict_data(thisId, match_detail, 'totalHealsOnTeammates')

                dict_score = {
                    pseudo[0] + "(" + thisChampName1 + ")": thisStats[0],
                    pseudo[1] + "(" + thisChampName2 + ")": thisStats[1],
                    pseudo[2] + "(" + thisChampName3 + ")": thisStats[2],
                    pseudo[3] + "(" + thisChampName4 + ")": thisStats[3],
                    pseudo[4] + "(" + thisChampName5 + ")": thisStats[4],
                    pseudo[5] + "(" + thisChampName6 + ")": thisStats[5],
                    pseudo[6] + "(" + thisChampName7 + ")": thisStats[6],
                    pseudo[7] + "(" + thisChampName8 + ")": thisStats[7],
                    pseudo[8] + "(" + thisChampName9 + ")": thisStats[8],
                    pseudo[9] + "(" + thisChampName10 + ")": thisStats[9],
                }

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

                dict_score = {
                    pseudo[0] + "(" + thisChampName1 + ")": thisStats[0],
                    pseudo[1] + "(" + thisChampName2 + ")": thisStats[1],
                    pseudo[2] + "(" + thisChampName3 + ")": thisStats[2],
                    pseudo[3] + "(" + thisChampName4 + ")": thisStats[3],
                    pseudo[4] + "(" + thisChampName5 + ")": thisStats[4],
                    pseudo[5] + "(" + thisChampName6 + ")": thisStats[5],
                    pseudo[6] + "(" + thisChampName7 + ")": thisStats[6],
                    pseudo[7] + "(" + thisChampName8 + ")": thisStats[7],
                    pseudo[8] + "(" + thisChampName9 + ")": thisStats[8],
                    pseudo[9] + "(" + thisChampName10 + ")": thisStats[9],
                }

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
    
    @interactions.extension_command(name="var_10games",
                       description="Voir des stats de fin de game sur 10 games",
                       options=[Option(
                                    name="summonername",
                                    description = "Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True),
                                Option(
                                    name="stat",
                                    description = "Quel stat ?",
                                    type=interactions.OptionType.STRING,
                                    required=True,
                                    choices=[
                                    Choice(name="vision", value="vision")
                                ])])
    async def var_10games(self, ctx:interactions.CommandContext, summonername, stat):

        me = lol_watcher.summoner.by_name(my_region, summonername)
        my_matches = lol_watcher.match.matchlist_by_puuid(region, me['puuid'])

        match = [lol_watcher.match.by_id(region, my_matches[i]) for i in
                 range(0, 10)]  # liste en compréhension des 10 matchs

        match_detail = match[0]

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

        # stats
        thisId = dic[
            summonername.lower().replace(" ", "")]  # cherche le pseudo dans le dico et renvoie le nombre entre 0 et 9

        df = pd.DataFrame(match)


        try:
            if stat == "vision":

                dict_score = {}

                for i in range(0, 10): #i = la game
                    dict_score['M' + str(i)] = df['info'][i]['participants'][thisId]['visionScore']

                stats = sns.lineplot(x=dict_score.keys(), y=dict_score.values(), linewidth=2.5)
                stats.set_title('Score Vision sur les 10 dernières games')
                stats.set_xlabel('Match', fontsize=10)
                stats.set_ylabel('Vision', fontsize=10)
                plt.legend(title='Joueur', labels=[summonername])
                plt.savefig(fname='plot')
                plt.clf()
                await ctx.send(file=interactions.File('plot.png'))
                os.remove('plot.png')


        except asyncio.TimeoutError:
            await stat.delete()
            await ctx.send("Annulé")


def setup(bot):
    analyseLoL(bot)
