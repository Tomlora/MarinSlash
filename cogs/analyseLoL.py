from turtle import st
from discord.ext import commands

from riotwatcher import LolWatcher
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
import cogs.leagueoflegends as league
from discord_slash import cog_ext, SlashContext



from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice


api_key_lol = os.environ.get('API_LOL')  # https://www.youtube.com/watch?v=IolxqkL7cD8

lol_watcher = LolWatcher(api_key_lol)
my_region = 'euw1'
region = "EUROPE"

# Paramètres LoL
version = lol_watcher.data_dragon.versions_for_region(my_region)
champions_versions = version['n']['champion']


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

class analyseLoL(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # commands.command(brief="Permet d'afficher des statistiques durantla game")
    @cog_ext.cog_slash(name="analyse",
                       description="Permet d'afficher des statistiques durant la game",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True),
                                create_option(name="stat", description="Quel stat ?", option_type=3, required=True, choices=[
                                    create_choice(name="gold", value="gold"),
                                    create_choice(name='gold_team', value='gold_team'),
                                    create_choice(name='vision', value='vision'),
                                    create_choice(name='position', value='position')]),
                                create_option(name="stat2", description="Quel stat ?", option_type=3, required=False, choices=[
                                    create_choice(name="gold", value="gold"),
                                    create_choice(name='gold_team', value='gold_team'),
                                    create_choice(name='vision', value='vision'),
                                    create_choice(name='position', value='position')])]
                       )
    @commands.cooldown(1,30, commands.BucketType.guild)
    # async def analyse(self, ctx: SlashContext, summonerName):
    async def analyse(self, ctx:SlashContext, summonername:str, stat:str, stat2:str = "no"):
        
        stat = [stat, stat2]
        

        await ctx.defer(hidden=False)
        global id, team
        warnings.simplefilter(action='ignore', category=FutureWarning)  # supprime les FutureWarnings dû à l'utilisation de pandas (.append/.drop)
        pd.options.mode.chained_assignment = None  # default='warn'
        last_match, match_detail, me = league.match_by_puuid(summonername, 0)
        timeline = lol_watcher.match.timeline_by_match(region, last_match)

        # timestamp à diviser par 60000

        dict_joueur = [lol_watcher.summoner.by_puuid(my_region, timeline['metadata']['participants'][i])['name'] for i
                       in range(0, 10)]  # liste en compréhension
        
        
        if summonername in dict_joueur:
            id = list(dict_joueur).index(summonername)
            

        if id <= 4:
            team = ['Team alliée', 'Team adverse']
        elif id >= 5:
            team = ['Team adverse', 'Team alliée']
  

        try:
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

                # df_ward = df_ward.astype({"killerId": 'int32'})
                df_ward['joueur'] = df_ward['creatorId']
                # df_ward.loc[df_ward['joueur'] == 0, 'joueur'] = df_ward['killerId']
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

                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

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
                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

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

                df_timeline_diff.iloc[0, 2] = df_timeline_diff.iloc[1, 2]

                if df_timeline_diff.iloc[0, 2] == "negatif":
                    color_sequence = ['red', 'blue']
                else:
                    color_sequence = ['blue', 'red']

                fig = px.line(df_timeline_diff, x='timestamp', y='ecart', color='signe', markers=True,
                              title='Ecart gold',
                              height=1000, width=1800, color_discrete_sequence=color_sequence)
                fig.update_layout(xaxis_title='Temps',
                                  font_size=18,
                                  showlegend=False)
                fig.update_traces(textposition="bottom center")
                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

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

                img = resize(img, (3750, 3750), anti_aliasing=False)

                fig = px.imshow(img)

                for i in range(0, minute - 1):
                    x = [df_timeline['position'][i]['x'] / 4]
                    y = [3750 - (df_timeline['position'][i]['y'] / 4)]

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
                fig.write_image('plot.png')
                await ctx.send(content=f'pour le joueur {summonername}', file=discord.File('plot.png'))
                os.remove('plot.png')

        except asyncio.TimeoutError:
            await ctx.send("Annulé")
            
    @analyse.error
    async def analyse_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(title='Cooldown', description=f'Description: \n `{error}`',
                              timestamp=ctx.created_at, color=242424)
            await ctx.send(embed=embed)

    @cog_ext.cog_slash(name="var",
                       description="Voir des stats de fin de game",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True),
                                create_option(name="stat", description="Quel stat ?", option_type=3, required=True, choices=[
                                    create_choice(name="dmg", value="dmg"),
                                    create_choice(name="gold", value="gold"),
                                    create_choice(name="gold role", value="gold_role"),
                                    create_choice(name="vision", value="vision"),
                                    create_choice(name="vision role", value="vision_role"),
                                    create_choice(name="tank", value="tank"),
                                    create_choice(name="heal alliés", value="heal_allies"),
                                    create_choice(name="solokills", value="solokills")]),
                                create_option(name="stat2", description="Quel stat ?", option_type=3, required=False, choices=[
                                    create_choice(name="dmg", value="dmg"),
                                    create_choice(name="gold", value="gold"),
                                    create_choice(name="gold role", value="gold_role"),
                                    create_choice(name="vision", value="vision"),
                                    create_choice(name="vision role", value="vision_role"),
                                    create_choice(name="tank", value="tank"),
                                    create_choice(name="heal alliés", value="heal_allies"),
                                    create_choice(name="solokills", value="solokills")]),
                                create_option(name="stat3", description="Quel stat ?", option_type=3, required=False, choices=[
                                    create_choice(name="dmg", value="dmg"),
                                    create_choice(name="gold", value="gold"),
                                    create_choice(name="gold role", value="gold_role"),
                                    create_choice(name="vision", value="vision"),
                                    create_choice(name="vision role", value="vision_role"),
                                    create_choice(name="tank", value="tank"),
                                    create_choice(name="heal alliés", value="heal_allies"),
                                    create_choice(name="solokills", value="solokills")
                                ])])
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def var(self, ctx:SlashContext, summonername, stat:str, stat2:str='no', stat3:str='no'):
        
        await ctx.defer(hidden=False)
        stat = [stat, stat2, stat3]
        

        last_match, match_detail_stats, me = league.match_by_puuid(summonername, 0)

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

                # print(dict_score)
                df = pd.DataFrame.from_dict(dict_score, orient='index')
                df = df.reset_index()
                df = df.rename(columns={"index": "pseudo", 0: 'dmg'})

                # print(df)
                # print(df.values)

                fig = px.histogram(df, y="pseudo", x="dmg", color="pseudo", title="Total DMG", text_auto=True)
                fig.update_layout(showlegend=False)

                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

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

                # print(df)
                # print(df.values)

                fig = px.histogram(df, y="pseudo", x="gold", color="pseudo", title="Total Gold", text_auto=True)
                fig.update_layout(showlegend=False)

                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')
            
            if "gold_role" in stat:

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
                
                role = ['SUPPORT', 'ADC', 'MID', 'JGL', 'TOP']

                if thisId <= 4:
                    liste_ecart = [df['gold'].loc[i] - df['gold'].loc[i+5] for i in range(4,-1,-1)] # on fait à l'envers car le graphique commence par les valeurs à droite
                    role[4-thisId] = role[4-thisId] + " (toi)"
                else:
                    liste_ecart = [df['gold'].loc[i+5] - df['gold'].loc[i] for i in range(4,-1,-1)]
                    role[9-thisId] = role[9-thisId] + " (toi)"
                
                df_ecart = pd.DataFrame(data=liste_ecart, columns=['gold'], index=role)

                fig = px.histogram(df_ecart, y=df_ecart.index.values, x="gold", color=df_ecart.index.values, title="Ecart gold par role", text_auto=True)
                fig.update_layout(showlegend=False)

                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

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

                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')
                
            if "vision_role" in stat:

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

                # print(dict_score)
                df = pd.DataFrame.from_dict(dict_score, orient='index')
                df = df.reset_index()
                df = df.rename(columns={"index": "pseudo", 0: 'vision'})
                
                role = ['SUPPORT', 'ADC', 'MID', 'JGL', 'TOP']

                if thisId <= 4:
                    liste_ecart = [df['vision'].loc[i] - df['vision'].loc[i+5] for i in range(4,-1,-1)] # on fait à l'envers car le graphique commence par les valeurs à droite
                    role[4-thisId] = role[4-thisId] + " (toi)"
                else:
                    liste_ecart = [df['vision'].loc[i+5] - df['vision'].loc[i] for i in range(4,-1,-1)]
                    role[9-thisId] = role[9-thisId] + " (toi)"
                
                df_ecart = pd.DataFrame(data=liste_ecart, columns=['vision'], index=role)

                fig = px.histogram(df_ecart, y=df_ecart.index.values, x="vision", color=df_ecart.index.values, title="Ecart vision par role", text_auto=True)
                fig.update_layout(showlegend=False)

                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

            if "tank" in stat:

                # thisStatsTaken = int(match_detail['info']['participants'][thisId]['totalDamageTaken'])
                # thisStatsSelfMitigated = match_detail['info']['participants'][thisId]['damageSelfMitigated']

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

                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

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

                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

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

                # print(dict_score)
                df = pd.DataFrame.from_dict(dict_score, orient='index')
                df = df.reset_index()
                df = df.rename(columns={"index": "pseudo", 0: 'SoloKills'})

                fig = px.histogram(df, y="pseudo", x="SoloKills", color="pseudo", title="Total SoloKills",
                                   text_auto=True)
                fig.update_layout(showlegend=False)

                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

        except asyncio.TimeoutError:
            await stat.delete()
            await ctx.send("Annulé")
    
    @var.error
    async def var_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(title='Cooldown', description=f'Description: \n `{error}`',
                              timestamp=ctx.created_at, color=242424)
            await ctx.send(embed=embed)

    @cog_ext.cog_slash(name="var_10games",
                       description="Voir des stats de fin de game sur 10 games",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True),
                                create_option(name="stat", description = "Quel stat ?", option_type=3, required=True, choices=[
                                    create_choice(name="vision", value="vision")
                                ])])
    async def var_10games(self, ctx, summonername, stat):

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
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')


        except asyncio.TimeoutError:
            await stat.delete()
            await ctx.send("Annulé")


def setup(bot):
    bot.add_cog(analyseLoL(bot))
