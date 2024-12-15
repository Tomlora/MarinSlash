import interactions
from interactions import Extension, SlashContext, SlashCommandChoice, SlashCommandOption, slash_command
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
from datetime import datetime
from interactions.ext.paginators import Paginator
import dataframe_image as dfi

from fonctions.match import (get_summoner_by_puuid,
                             get_version,
                             get_champ_list,
                             get_match_timeline,
                             label_ward,
                             emote_champ_discord,
                             match_by_puuid_with_puuid,
                             emote_rank_discord,
                             get_summoner_by_riot_id)
from fonctions.channels_discord import get_embed
from fonctions.gestion_bdd import lire_bdd_perso


saison = int(lire_bdd_perso('select * from settings', format='dict', index_col='parametres')['saison']['value'])


choice_var = [SlashCommandChoice(name="dmg", value="dmg"),
              SlashCommandChoice(name="gold", value="gold"),
              SlashCommandChoice(name="vision", value="vision"),
              SlashCommandChoice(name="tank", value="tank"),
              SlashCommandChoice(name="heal alliés", value="heal_allies"),
              SlashCommandChoice(name="solokills", value="solokills")]


choice_analyse = [SlashCommandChoice(name="gold", value="gold"),
                  SlashCommandChoice(name='gold_team', value='gold_team'),
                  SlashCommandChoice(name='cs', value='cs'),
                  SlashCommandChoice(name='level', value='level'),
                  SlashCommandChoice(name='vision', value='vision'),
                  SlashCommandChoice(name='position', value='position')]

parameters_commun_stats_lol = [
    SlashCommandOption(
        name='season',
        description='saison lol',
        type=interactions.OptionType.INTEGER,
        min_value=12,
        max_value=saison,
        required=False),
    SlashCommandOption(
        name='riot_id',
        description='se focaliser sur un joueur ? Incompatible avec grouper par personne',
        type=interactions.OptionType.STRING,
        required=False),
    SlashCommandOption(
        name='riot_tag',
        description='se focaliser sur un joueur ? Incompatible avec grouper par personne',
        type=interactions.OptionType.STRING,
        required=False),
    SlashCommandOption(
        name='role',
        description='Role LoL. Remplir ce role retire les stats aram',
        type=interactions.OptionType.STRING,
        required=False,
        choices=[
            SlashCommandChoice(name='top', value='TOP'),
            SlashCommandChoice(name='jungle', value='JUNGLE'),
            SlashCommandChoice(name='mid', value='MID'),
            SlashCommandChoice(name='adc', value='ADC'),
            SlashCommandChoice(name='support', value='SUPPORT')]),
    SlashCommandOption(
        name='champion',
        description='se focaliser sur un champion ?',
        type=interactions.OptionType.STRING,
        required=False),
    SlashCommandOption(
        name='mode_de_jeu',
        description='se focaliser sur un mode de jeu ?',
        type=interactions.OptionType.STRING,
        required=False,
        choices=[
            SlashCommandChoice(name='soloq',
                               value='RANKED'),
            SlashCommandChoice(name='aram', value='ARAM')]),
    SlashCommandOption(
        name='top',
        description='top x ?',
        type=interactions.OptionType.INTEGER,
        required=False,
        choices=[
            SlashCommandChoice(name='3', value=3),
            SlashCommandChoice(name='5', value=5),
            SlashCommandChoice(name='7', value=7),
            SlashCommandChoice(name='10', value=10),
            SlashCommandChoice(name='15', value=15),
            SlashCommandChoice(name='20', value=20)]),
    SlashCommandOption(
        name='view',
        description='global ou par serveur ?',
        type=interactions.OptionType.STRING,
        required=False,
        choices=[
            SlashCommandChoice(name='global', value='global'),
            SlashCommandChoice(name='serveur', value='serveur')
        ]
    )
]

parameters_nbgames = [
    SlashCommandOption(
        name='season',
        description='saison lol',
        type=interactions.OptionType.INTEGER,
        required=False),
    SlashCommandOption(
        name='joueur',
        description='se focaliser sur un joueur ? Incompatible avec grouper par personne',
        type=interactions.OptionType.STRING,
        required=False),
    SlashCommandOption(
        name='champion',
        description='se focaliser sur un champion ?',
        type=interactions.OptionType.STRING,
        required=False),
    SlashCommandOption(
        name='mode_de_jeu',
        description='se focaliser sur un mode de jeu ?',
        type=interactions.OptionType.STRING,
        required=False,
        choices=[
            SlashCommandChoice(name='soloq',
                               value='RANKED'),
            SlashCommandChoice(name='aram', value='ARAM')]),
    SlashCommandOption(
        name='top',
        description='top x ?',
        type=interactions.OptionType.INTEGER,
        required=False,
        choices=[
            SlashCommandChoice(name='3', value=3),
            SlashCommandChoice(name='5', value=5),
            SlashCommandChoice(name='7', value=7),
            SlashCommandChoice(name='10', value=10),
            SlashCommandChoice(name='15', value=15),
            SlashCommandChoice(name='20', value=20)]),
    SlashCommandOption(
        name='grouper',
        description='Grouper par joueur ou personne ? (Fonctionne uniquement avec games)',
        type=interactions.OptionType.STRING,
        required=False,
        choices=[
            SlashCommandChoice(name='compte', value='joueur'),
            SlashCommandChoice(name='personne', value='discord')
        ]),
    SlashCommandOption(
        name='view',
        description='global ou par serveur ?',
        type=interactions.OptionType.STRING,
        required=False,
        choices=[
            SlashCommandChoice(name='global', value='global'),
            SlashCommandChoice(name='serveur', value='serveur')
        ]
    )
]


def fix_temps(duree):
    '''Convertit le temps en secondes en minutes et secondes'''
    minutes = int(duree)
    secondes = int((duree - minutes) * 60)/100
    
    return minutes + secondes


def get_data_matchs(columns, season, server_id, view='global', datetime=None):

    if datetime == None:
        if view == 'global':
            df = lire_bdd_perso(
                f'''SELECT matchs.id, tracker.riot_id, tracker.riot_tagline, matchs.role, matchs.champion, matchs.match_id, matchs.mode, matchs.season, matchs.split, {columns}, tracker.discord from matchs
            INNER JOIN tracker ON tracker.id_compte = matchs.joueur
            where season = {season}''', index_col='id').transpose()
        else:
            df = lire_bdd_perso(
                f'''SELECT matchs.id, tracker.riot_id, tracker.riot_tagline, matchs.role, matchs.champion, matchs.match_id, matchs.mode, matchs.season, matchs.split, {columns}, tracker.discord from matchs
                INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                where season = {season}
                AND server_id = {server_id}''', index_col='id').transpose()
    else:
        if view == 'global':
            df = lire_bdd_perso(
                f'''SELECT matchs.id, tracker.riot_id, tracker.riot_tagline, matchs.role, matchs.champion, matchs.match_id, matchs.mode, matchs.season, matchs.split, {columns}, matchs.datetime tracker.discord from matchs
            INNER JOIN tracker ON tracker.id_compte = matchs.joueur
            where season = {season}
            and datetime >= :date''', index_col='id').transpose()
        else:
            df = lire_bdd_perso(
                f'''SELECT matchs.id, tracker.riot_id, tracker.riot_tagline, matchs.role, matchs.champion, matchs.match_id, matchs.mode, matchs.season, matchs.split, {columns}, matchs.datetime tracker.discord from matchs
                INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                where season = {season}
                AND server_id = {server_id}
                AND datetime >= :date''', index_col='id').transpose()
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
    df_group = df_group.sort_values('riot_id', ascending=False)
    # On retient le top x
    df_group = df_group.head(top)
    # On fait le graphique
    fig = px.histogram(df_group, value, 'riot_id', color=value, title=title,
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

def mapping_joueur(df, colonne, dict_joueur):
    df = df.astype({colonne: 'string'})

    df[colonne] = df[colonne].map({'1': dict_joueur[0],
                                                        '2': dict_joueur[1],
                                                        '3': dict_joueur[2],
                                                        '4': dict_joueur[3],
                                                        '5': dict_joueur[4],
                                                        '6': dict_joueur[5],
                                                        '7': dict_joueur[6],
                                                        '8': dict_joueur[7],
                                                        '9': dict_joueur[8],
                                                        '10': dict_joueur[9]})
    return df

def tri_riot_id(df, riot_id, riot_tag, title):
    riot_id = riot_id.lower().replace(' ', '')
    riot_tag = riot_tag.upper()
    df = df[(df['riot_id'] == riot_id) & (df['riot_tagline'] == riot_tag)]
    title += f' pour {riot_id}'
    return riot_id, riot_tag, df, title

def tri_champion(champion, df, title):
    champion = champion.capitalize()
    df = df[df['champion'] == champion]
    title += f' sur {champion}'
    return champion, df, title

def tri_occurence(df, colonne, nb_parties):
    occurences = df[colonne].value_counts()

    mask = df[colonne].isin(occurences.index[occurences >= nb_parties])

    df = df[mask]
            
    return df 

def load_timeline(timeline):
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

    df_timeline['riot_id'] = df_timeline['participantId']
            
    return df_timeline, minute

def format_graph_var(thisId, match_detail, info : str, pseudo : list, champ_names:list, rename_x, title_graph):

    thisStats = dict_data(thisId, match_detail, info)

    dict_score = {
                pseudo[i] + "(" + champ_names[i] + ")": thisStats[i] for i in range(len(pseudo))}

    df = pd.DataFrame.from_dict(dict_score, orient='index')
    df = df.reset_index()
    df = df.rename(columns={"index": "pseudo", 0: rename_x})

    fig = px.histogram(df, y="pseudo", x=rename_x, color="pseudo", title=title_graph, text_auto=True)
    fig.update_layout(showlegend=False)
                    
    return fig 


def graphique(fig, name, liste_delete, liste_graph):
    fig.write_image(name)
    liste_delete.append(name)
    liste_graph.append(interactions.File(name))

    return liste_delete, liste_graph

class analyseLoL(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @slash_command(name='lol_analyse_durant_la_game', description='analyse lol')
    async def analyse_lol(self, ctx: SlashContext):
        pass

    @analyse_lol.subcommand("position",
                            sub_cmd_description="Permet d'afficher des statistiques durant la game",
                            options=[
                                SlashCommandOption(
                                    name="riot_id",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True),
                                SlashCommandOption(
                                    name="riot_tag",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True),
                                SlashCommandOption(
                                    name='detail',
                                    description="Ajout d'actions durant la game",
                                    type=interactions.OptionType.BOOLEAN,
                                    required=False),
                                SlashCommandOption(
                                    name="game",
                                    description="Numero Game",
                                    type=interactions.OptionType.INTEGER,
                                    required=False,
                                    min_value=0,
                                    max_value=10),
                                SlashCommandOption(
                                    name='id_game',
                                    description='Identifiant de la game',
                                    type=interactions.OptionType.STRING,
                                    required=False
                                )])
    async def analyse_position(self,
                      ctx: SlashContext,
                      riot_id: str,
                      riot_tag:str,
                      detail : bool = False,
                      game: int = 0,
                      id_game : str = None):

        liste_graph = list()
        liste_delete = list()

        riot_id_origin = riot_id.lower()
        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper()

        await ctx.defer(ephemeral=False)

        global thisId, team
        # supprime les FutureWarnings dû à l'utilisation de pandas (.append/.drop)
        warnings.simplefilter(action='ignore', category=FutureWarning)
        pd.options.mode.chained_assignment = None  # default='warn'
        session = aiohttp.ClientSession()
        
        try:
            puuid = lire_bdd_perso('''SELECT index, puuid from tracker where riot_id = :riot_id and riot_tagline = :riot_tag''',
                                        params={'riot_id' : riot_id,
                                                'riot_tag' : riot_tag})\
                                                    .T\
                                                        .loc[riot_id, 'puuid']
        except KeyError:
            me = await get_summoner_by_riot_id(session, riot_id, riot_tag)
            puuid = me['puuid']

        


        if id_game == None:                                                  
            last_match, match_detail = await match_by_puuid_with_puuid(puuid, game, session)
        else:
            last_match = str(id_game)
            if 'EUW' not in last_match:
                last_match = f'EUW1_{last_match}'   

        timeline = await get_match_timeline(session, last_match)

        # timestamp à diviser par 60000

        dict_joueur = []
        for i in range(0, 10):
            attempt = 0

            while attempt < 5:
                try:
                    summoner = await get_summoner_by_puuid(timeline['metadata']['participants'][i], session)
                    dict_joueur.append(summoner['gameName'].lower())
                    break
                except:
                    attempt += 1

                    if attempt >= 5:
                        msg = await ctx.send(f'Trop de demandes à Riot Games... Réessai dans 10 secondes. Tentative {attempt}/5 ')
                        await asyncio.sleep(10)
                        await msg.delete()


        await session.close()

        if riot_id_origin in dict_joueur:
            thisId = list(dict_joueur).index(riot_id_origin)
        else:
            return await ctx.send(f'Erreur. Joueur introuvable parmi **{dict_joueur}**')

        if thisId <= 4:
            team = ['Team alliée', 'Team adverse']
        elif thisId >= 5:
            team = ['Team adverse', 'Team alliée']



        df_timeline, minute = load_timeline(timeline)

        df_timeline = mapping_joueur(df_timeline, 'riot_id', dict_joueur)
           
        df_timeline = df_timeline[(df_timeline['riot_id'] == riot_id)]

        df_timeline['type'] = 'position'

        if detail:
            df_events = pd.DataFrame(timeline['info']['frames'][1]['events'])
            minute = len(timeline['info']['frames']) - 1

            index_timeline = df_timeline['participantId'][0]

            for i in range(1, minute):
                        df_timeline2 = pd.DataFrame(
                            timeline['info']['frames'][i]['events'])
                        df_events = df_events.append(df_timeline2)


            df_events_joueur = df_events[(df_events['participantId'] == index_timeline) |
                                                    (df_events['creatorId'] == index_timeline) |
                                                    (df_events['killerId'] == index_timeline) |
                                                    (df_events['victimId'] == index_timeline) |
                                                    df_events['assistingParticipantIds'].apply(lambda x: isinstance(x, list) and index_timeline in x)]

            df_events_joueur.dropna(subset=['position'], inplace=True)

            df_events_joueur = df_events_joueur[['timestamp', 'type', 'position', 'killerId', 'victimId', 'assistingParticipantIds']]

            df_events_joueur[['killerId', 'victimId']] = df_events_joueur[['killerId', 'victimId']].astype(int, errors='ignore')

            df_events_joueur['timestamp'] = np.round(df_events_joueur['timestamp'] / 60000,2)
                        
            df_events_joueur['timestamp'] = df_events_joueur['timestamp'].apply(fix_temps)

            df_events_joueur.drop_duplicates(subset=['timestamp'], inplace=True, keep='first')

            df_timeline = pd.concat([df_timeline, df_events_joueur]).sort_values('timestamp').reset_index(drop=True)

        img = io.imread('./img/map2.jpg')

        # 3750 taille optimale et 4 en diviseur
        x_pos = 468.75
        y_pos = 468.75
        diviseur = 32

        img = resize(img, (x_pos, y_pos), anti_aliasing=False)

        fig = px.imshow(img)

        for i in range(0, df_timeline.shape[0]):
                x = [df_timeline['position'][i]['x'] / diviseur]
                y = [y_pos - (df_timeline['position'][i]['y'] / diviseur)]
                timestamp = df_timeline['timestamp'][i]
                type = df_timeline['type'][i]

                if type == 'position':

                    timestamp = int(timestamp)

                    if timestamp < 10:
                        color = 'red'
                    elif 10 <= timestamp < 20:
                        color = 'cyan'
                    elif 20 <= timestamp < 30:
                        color = 'lightgreen'
                    else:
                        color = 'goldenrod'


                elif type == 'CHAMPION_KILL':
                    color = 'violet'
                    if df_timeline['victimId'][i] == index_timeline:
                        timestamp = f'{timestamp}(D)'
                    
                    elif df_timeline['killerId'][i] == index_timeline:
                        timestamp = f'{timestamp}(K)'
                    
                    else:
                         timestamp = f'{timestamp}(A)'
                
                elif type == 'BUILDING_KILL':
                      color = 'yellow'
                      timestamp = f'{timestamp}(B)'
                    
                elif type == 'ELITE_MONSTER_KILL':
                      color = 'orange'
                      timestamp = f'{timestamp}(M)'

                fig.add_trace(
                    go.Scatter(x=x, y=y, mode="markers+text", text=str(timestamp), marker=dict(color=color, size=20),
                               textposition='top center', textfont=dict(size=35, color=color)))

        fig.update_layout(width=1200,
                              height=1200,
                              coloraxis_showscale=False,
                              showlegend=False)

        fig.update_xaxes(showticklabels=False,
                             automargin=True)
        fig.update_yaxes(showticklabels=False,
                             automargin=True)

        liste_delete, liste_graph = graphique(fig, 'position.png', liste_delete, liste_graph)

        await ctx.send(files=liste_graph)

        for graph in liste_delete:
            os.remove(graph)

    @analyse_lol.subcommand("vision",
                            sub_cmd_description="Permet d'afficher des statistiques durant la game",
                            options=[
                                SlashCommandOption(
                                    name="riot_id",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True),
                                SlashCommandOption(
                                    name="riot_tag",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True),
                                SlashCommandOption(
                                    name="game",
                                    description="Numero Game",
                                    type=interactions.OptionType.INTEGER,
                                    required=False,
                                    min_value=0,
                                    max_value=10),
                                SlashCommandOption(
                                    name='id_game',
                                    description='Identifiant de la game',
                                    type=interactions.OptionType.STRING,
                                    required=False
                                )])
    async def analyse_vision(self,
                      ctx: SlashContext,
                      riot_id: str,
                      riot_tag:str,
                      game: int = 0,
                      id_game : str = None):

        liste_graph = list()
        liste_delete = list()

        riot_id_origin = riot_id.lower()
        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper()

        await ctx.defer(ephemeral=False)

        global thisId, team
        # supprime les FutureWarnings dû à l'utilisation de pandas (.append/.drop)
        warnings.simplefilter(action='ignore', category=FutureWarning)
        pd.options.mode.chained_assignment = None  # default='warn'
        session = aiohttp.ClientSession()
        
        try:
            puuid = lire_bdd_perso('''SELECT index, puuid from tracker where riot_id = :riot_id and riot_tagline = :riot_tag''',
                                        params={'riot_id' : riot_id,
                                                'riot_tag' : riot_tag})\
                                                    .T\
                                                        .loc[riot_id, 'puuid']
        except KeyError:
            me = await get_summoner_by_riot_id(session, riot_id, riot_tag)
            puuid = me['puuid']

        


        if id_game == None:                                                  
            last_match, match_detail = await match_by_puuid_with_puuid(puuid, game, session)
        else:
            last_match = str(id_game)
            if 'EUW' not in last_match:
                last_match = f'EUW1_{last_match}'   

        timeline = await get_match_timeline(session, last_match)

        # timestamp à diviser par 60000

        dict_joueur = []
        for i in range(0, 10):
            attempt = 0

            while attempt < 5:
                try:
                    summoner = await get_summoner_by_puuid(timeline['metadata']['participants'][i], session)
                    dict_joueur.append(summoner['gameName'].lower())
                    break
                except:
                    attempt += 1

                    if attempt >= 5:
                        msg = await ctx.send(f'Trop de demandes à Riot Games... Réessai dans 10 secondes. Tentative {attempt}/5 ')
                        await asyncio.sleep(10)
                        await msg.delete()


        await session.close()

        if riot_id_origin in dict_joueur:
            thisId = list(dict_joueur).index(riot_id_origin)
        else:
            return await ctx.send(f'Erreur. Joueur introuvable parmi **{dict_joueur}**')

        if thisId <= 4:
            team = ['Team alliée', 'Team adverse']
        elif thisId >= 5:
            team = ['Team adverse', 'Team alliée']



        df_timeline = pd.DataFrame(timeline['info']['frames'][1]['events'])

        minute = len(timeline['info']['frames']) - 1

        for i in range(2, minute):
            df_timeline2 = pd.DataFrame(
                    timeline['info']['frames'][i]['events'])
            df_timeline = df_timeline.append(df_timeline2)

        df_timeline['timestamp'] = df_timeline['timestamp'] / \
                60000  # arrondir à l'inférieur ou au supérieur ?

        df_ward = df_timeline[(df_timeline['type'] == 'WARD_PLACED') | (
                df_timeline['type'] == 'WARD_KILL')]

        df_ward['creatorId'].fillna(0, inplace=True)
        df_ward['killerId'].fillna(0, inplace=True)
        df_ward = df_ward.astype(
                {"creatorId": 'int32', "killerId": 'int32'})

        df_ward['riot_id'] = df_ward['creatorId']

        df_ward['riot_id'] = np.where(
                df_ward['riot_id'] == 0, df_ward.killerId, df_ward['riot_id'])
            
        df_ward = mapping_joueur(df_ward, 'riot_id', dict_joueur)

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


            
        df_ward = df_ward[(df_ward['riot_id'] == riot_id)]

        illustrative_var = np.array(df_ward['wardType'])
        illustrative_type = np.array(df_ward['type'])

        fig = px.scatter(x=df_ward['timestamp'], y=df_ward['points'], color=illustrative_var, range_y=[0, 6],
                             size=df_ward['size'], symbol=illustrative_type, title='Warding', width=1600,
                             height=800)
        fig.update_yaxes(showticklabels=False)
        fig.update_layout(xaxis_title='Temps',
                              font_size=18)

        liste_delete, liste_graph = graphique(fig, 'vision.png', liste_delete, liste_graph)

        


        await ctx.send(files=liste_graph)

        for graph in liste_delete:
            os.remove(graph)


    @analyse_lol.subcommand("gold_team",
                            sub_cmd_description="Permet d'afficher des statistiques durant la game",
                            options=[
                                SlashCommandOption(
                                    name="riot_id",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True),
                                SlashCommandOption(
                                    name="riot_tag",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True),
                                SlashCommandOption(
                                    name="game",
                                    description="Numero Game",
                                    type=interactions.OptionType.INTEGER,
                                    required=False,
                                    min_value=0,
                                    max_value=10),
                                SlashCommandOption(
                                    name='id_game',
                                    description='Identifiant de la game',
                                    type=interactions.OptionType.STRING,
                                    required=False
                                )])
    async def analyse_gold_team(self,
                      ctx: SlashContext,
                      riot_id: str,
                      riot_tag:str,
                      game: int = 0,
                      id_game : str = None):

        liste_graph = list()
        liste_delete = list()

        riot_id_origin = riot_id.lower()
        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper()

        await ctx.defer(ephemeral=False)

        global thisId, team
        # supprime les FutureWarnings dû à l'utilisation de pandas (.append/.drop)
        warnings.simplefilter(action='ignore', category=FutureWarning)
        pd.options.mode.chained_assignment = None  # default='warn'
        session = aiohttp.ClientSession()
        
        try:
            puuid = lire_bdd_perso('''SELECT index, puuid from tracker where riot_id = :riot_id and riot_tagline = :riot_tag''',
                                        params={'riot_id' : riot_id,
                                                'riot_tag' : riot_tag})\
                                                    .T\
                                                        .loc[riot_id, 'puuid']
        except KeyError:
            me = await get_summoner_by_riot_id(session, riot_id, riot_tag)
            puuid = me['puuid']

        


        if id_game == None:                                                  
            last_match, match_detail = await match_by_puuid_with_puuid(puuid, game, session)
        else:
            last_match = str(id_game)
            if 'EUW' not in last_match:
                last_match = f'EUW1_{last_match}'   

        timeline = await get_match_timeline(session, last_match)

        # timestamp à diviser par 60000

        dict_joueur = []
        for i in range(0, 10):
            attempt = 0

            while attempt < 5:
                try:
                    summoner = await get_summoner_by_puuid(timeline['metadata']['participants'][i], session)
                    dict_joueur.append(summoner['gameName'].lower())
                    break
                except:
                    attempt += 1

                    if attempt >= 5:
                        msg = await ctx.send(f'Trop de demandes à Riot Games... Réessai dans 10 secondes. Tentative {attempt}/5 ')
                        await asyncio.sleep(10)
                        await msg.delete()


        await session.close()

        if riot_id_origin in dict_joueur:
            thisId = list(dict_joueur).index(riot_id_origin)
        else:
            return await ctx.send(f'Erreur. Joueur introuvable parmi **{dict_joueur}**')

        if thisId <= 4:
            team = ['Team alliée', 'Team adverse']
        elif thisId >= 5:
            team = ['Team adverse', 'Team alliée']

       



        df_timeline, minute = load_timeline(timeline)

        df_timeline['riot_id'] = df_timeline['participantId']

        df_timeline['team'] = np.where(
                df_timeline['riot_id'] <= 5, team[0], team[1])

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

        df_timeline_diff['signe'] = np.where(
                df_timeline_diff.ecart < 0, 'negatif', 'positif')

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

        plt.title(f'Ecart gold {riot_id}')

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


        await ctx.send(files=liste_graph)

        for graph in liste_delete:
            os.remove(graph)


    @analyse_lol.subcommand("gold",
                            sub_cmd_description="Permet d'afficher des statistiques durant la game",
                            options=[
                                SlashCommandOption(
                                    name="riot_id",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True),
                                SlashCommandOption(
                                    name="riot_tag",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True),
                                SlashCommandOption(
                                    name="game",
                                    description="Numero Game",
                                    type=interactions.OptionType.INTEGER,
                                    required=False,
                                    min_value=0,
                                    max_value=10),
                                SlashCommandOption(
                                    name='id_game',
                                    description='Identifiant de la game',
                                    type=interactions.OptionType.STRING,
                                    required=False
                                )])
    async def analyse(self,
                      ctx: SlashContext,
                      riot_id: str,
                      riot_tag:str,
                      game: int = 0,
                      id_game : str = None):

        liste_graph = list()
        liste_delete = list()

        riot_id_origin = riot_id.lower()
        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper()


        await ctx.defer(ephemeral=False)

        global thisId, team
        # supprime les FutureWarnings dû à l'utilisation de pandas (.append/.drop)
        warnings.simplefilter(action='ignore', category=FutureWarning)
        pd.options.mode.chained_assignment = None  # default='warn'
        session = aiohttp.ClientSession()
        
        try:
            puuid = lire_bdd_perso('''SELECT index, puuid from tracker where riot_id = :riot_id and riot_tagline = :riot_tag''',
                                        params={'riot_id' : riot_id,
                                                'riot_tag' : riot_tag})\
                                                    .T\
                                                        .loc[riot_id, 'puuid']
        except KeyError:
            me = await get_summoner_by_riot_id(session, riot_id, riot_tag)
            puuid = me['puuid']

        


        if id_game == None:                                                  
            last_match, match_detail = await match_by_puuid_with_puuid(puuid, game, session)
        else:
            last_match = str(id_game)
            if 'EUW' not in last_match:
                last_match = f'EUW1_{last_match}'   

        timeline = await get_match_timeline(session, last_match)

        # timestamp à diviser par 60000

        dict_joueur = []
        for i in range(0, 10):
            attempt = 0

            while attempt < 5:
                try:
                    summoner = await get_summoner_by_puuid(timeline['metadata']['participants'][i], session)
                    dict_joueur.append(summoner['gameName'].lower())
                    break
                except:
                    attempt += 1

                    if attempt >= 5:
                        msg = await ctx.send(f'Trop de demandes à Riot Games... Réessai dans 10 secondes. Tentative {attempt}/5 ')
                        await asyncio.sleep(10)
                        await msg.delete()


        await session.close()

        if riot_id_origin in dict_joueur:
            thisId = list(dict_joueur).index(riot_id_origin)
        else:
            return await ctx.send(f'Erreur. Joueur introuvable parmi **{dict_joueur}**')

        if thisId <= 4:
            team = ['Team alliée', 'Team adverse']
        elif thisId >= 5:
            team = ['Team adverse', 'Team alliée']
            
        df_timeline, minute = load_timeline(timeline)

        df_timeline = mapping_joueur(df_timeline, 'riot_id', dict_joueur)

        fig = px.line(df_timeline, x='timestamp', y='totalGold', color='riot_id', markers=True, title='Gold',
                          height=1000, width=1800)
        fig.update_layout(xaxis_title='Temps',
                              font_size=18)

        liste_delete, liste_graph = graphique(fig, 'gold.png', liste_delete, liste_graph)
            

        await ctx.send(files=liste_graph)

        for graph in liste_delete:
            os.remove(graph)

    choice_comptage = SlashCommandChoice(name='comptage', value='count')
    choice_time_joue = SlashCommandChoice(name='temps_joué', value='time')
    choice_winrate = SlashCommandChoice(name='winrate', value='winrate')
    choice_avg = SlashCommandChoice(name='avg', value='avg')
    choice_progression = SlashCommandChoice(
        name='progression', value='progression')
    choice_ecart = SlashCommandChoice(name='ecart', value='ecart')


    @slash_command(name="lol_stats",
                   description="Historique de game")
    async def stats_lol(self, ctx: SlashContext):
        pass


    @stats_lol.subcommand('champions',
                          sub_cmd_description='Statistiques sur les champions',
                          options=[SlashCommandOption(
                              name='calcul',
                              description='quel type de calcul ?',
                              type=interactions.OptionType.STRING,
                              required=True,
                              choices=[choice_comptage, choice_winrate]),
                              SlashCommandOption(
                              name='nb_parties',
                              description='Combien de parties minimum ? (Debloque un graph détaillé pour winrate si supérieur à 1)',
                              required=False,
                              type=interactions.OptionType.INTEGER,
                              min_value=1
                          )
                          ] + parameters_commun_stats_lol)
    async def stats_lol_champions(self,
                                  ctx: SlashContext,
                                  calcul: str,
                                  season: int = saison,
                                  riot_id: str = None,
                                  riot_tag: str = None,
                                  role: str = None,
                                  champion: str = None,
                                  mode_de_jeu: str = None,
                                  nb_parties: int = 1,
                                  top: int = 20,
                                  view: str = 'global'
                                  ):

        await ctx.defer(ephemeral=False)

        df = get_data_matchs('matchs.victoire', saison,
                             int(ctx.guild_id), view)

        title = f'Champion'

        df[df['season'] == season]

        if riot_id != None and riot_tag != None:
            riot_id, riot_tag, df, title = tri_riot_id(df, riot_id, riot_tag, title)

        if champion != None:
            champion, df, title = tri_champion(champion, df, title)


        if mode_de_jeu != None:
            df = df[df['mode'] == mode_de_jeu]
            title += f' en {mode_de_jeu}'


        if role != None:
            df = df[df['role'] == role]
            title += f' ({role})'

        df = tri_occurence(df, 'champion', nb_parties)
                
        title += f' ({calcul})'

        if calcul == 'count':
            if riot_id != None:
                showlegend = True
            else:
                showlegend = False
            fig = transformation_top(
                df, 'champion', title, top, showlegend=showlegend)
            embed, files = get_embed(fig, 'champion')
            await ctx.send(embeds=embed, files=files)

        elif calcul == 'winrate':

            df['victoire_int'] = df['victoire'].astype(int)
            df['victoire'] = df['victoire'].map({True: 'Victoire',
                                                 False: 'Défaite'})

            values = df['victoire'].value_counts()
            fig = go.Figure(
                data=[go.Pie(labels=values.index, values=values)])
            fig.update_layout(title=title)

            embed, files = get_embed(fig, 'wr')

            await ctx.send(embeds=embed, files=files)
            
            if nb_parties > 1: # on fait le détail de winrate par champ si ce champ est renseigné
                df_grp = df.groupby('champion').agg(victoire_sum=('victoire_int', 'sum'),
                                                    nb_games=('victoire', 'count'))
                df_grp['winrate'] = np.round((df_grp['victoire_sum'] / df_grp['nb_games']) * 100,1)
                
                df_grp['champion_joues'] = df_grp.index + '(' + df_grp['nb_games'].astype(str) + ')'
                
                fig = px.histogram(df_grp, x='champion_joues',
                                   y='winrate',
                                   color='champion_joues',
                                   text_auto=".i").update_xaxes(categoryorder='total descending')
                
                fig.update_layout(title=f'Winrate par champion ({nb_parties} parties minimum)',
                                  showlegend=False)
                
                embed, files = get_embed(fig, 'wr')
                
                await ctx.send(embeds=embed, files=files)

        else:
            await ctx.send('Non disponible')
            pass

    @stats_lol.subcommand('kills',
                          sub_cmd_description='Statistiques sur les kills',
                          options=[SlashCommandOption(
                              name='calcul',
                              description='quel type de calcul ?',
                              type=interactions.OptionType.STRING,
                              required=True,
                              choices=[choice_comptage]),
                              SlashCommandOption(
                              name='nb_parties',
                              description='Combien de parties minimum ?',
                              type=interactions.OptionType.INTEGER,
                              required=False,
                              min_value=1
                          )
                          ] + parameters_commun_stats_lol)
    async def stats_lol_kills(self,
                              ctx: SlashContext,
                              calcul: str,
                              season: int = saison,
                              riot_id: str = None,
                              riot_tag : str = None,
                              role: str = None,
                              champion: str = None,
                              mode_de_jeu: str = None,
                              nb_parties: int = 1,
                              top: int = 20,
                              view: str = 'global'
                              ):

        await ctx.defer(ephemeral=False)

        df = get_data_matchs(
            'matchs.kills, matchs.double, matchs.triple, matchs.quadra, matchs.penta, matchs.solokills', saison, int(ctx.guild_id), view)

        title = f'Kills'

        df[df['season'] == season]

        if riot_id != None and riot_tag != None:
            riot_id, riot_tag, df, title = tri_riot_id(df, riot_id, riot_tag, title)

        if champion != None:
            champion, df, title = tri_champion(champion, df, title)

        if mode_de_jeu != None:
            df = df[df['mode'] == mode_de_jeu]
            title += f' en {mode_de_jeu}'

        if role != None:
            df = df[df['role'] == role]
            title += f' ({role})'

        df = tri_occurence(df, 'champion', nb_parties)

        title += f' ({calcul})'

        if calcul == 'count':

            df.drop('discord', axis=1, inplace=True)

            df = df.groupby('riot_id').agg(
                {'double': ['sum', 'count'], 'triple': 'sum', 'quadra': 'sum', 'penta': 'sum', 'solokills' : 'sum'})
            df.columns = pd.Index([e[0] + "_" + e[1].upper()
                                  for e in df.columns.tolist()])
            df.rename(columns={'double_SUM': 'double', 'double_COUNT': 'nbgames', 'triple_SUM': 'triple',
                      'quadra_SUM': 'quadra', 'penta_SUM': 'penta', 'solokills_SUM' : 'solokills'}, inplace=True)  # doubleCount sert à compter le nombre de games

            df.sort_values(['penta', 'quadra', 'triple', 'double', 'solokills'], ascending=[
                           False, False, False, False, False], inplace=True)

            if riot_id == None:

                txt = f'{title} :'

                for joueur, data in df.iterrows():
                    txt += f'\n**{joueur}** : **{data["penta"]}** penta, **{data["quadra"]}** quadra, **{data["triple"]}** triple, **{data["double"]}** double | **{data["solokills"]}** solokills | **{data["nbgames"]}** games'

                await ctx.send(txt)

            else:
                
                def format_data_graph(df, colonne: str):
                    trace = go.Bar(
                        x=df.index,
                        y=df[colonne],
                        name=colonne.capitalize(),
                        orientation='v',
                        text=df[colonne],
                        textposition='inside',
                        insidetextanchor='middle',
                        textfont=dict(color='white')
                    )
                    return trace

                data = [format_data_graph(df, 'double'),
                        format_data_graph(df, 'triple'),
                        format_data_graph(df, 'quadra'),
                        format_data_graph(df, 'penta')]

                layout = go.Layout(
                    title='Graphique',
                    xaxis=dict(title='Valeurs'),
                    yaxis=dict(showticklabels=False)
                )

                fig = go.Figure(data=data, layout=layout)

                embed, files = get_embed(fig, 'kills')

                await ctx.send(embeds=embed, files=files)

    @stats_lol.subcommand('dmg_tank_kda',
                          sub_cmd_description='Statistiques sur les dégats, tanking et les kda',
                          options=[SlashCommandOption(
                              name='type',
                              description='Quel type ?',
                              type=interactions.OptionType.STRING,
                              required=True,
                              choices=[SlashCommandChoice(name='dmg', value='dmg'),
                                       SlashCommandChoice(
                                           name='tank', value='tank'),
                                       SlashCommandChoice(name='kda', value='kda')]),
                                   SlashCommandOption(
                              name='calcul',
                              description='quel type de calcul ?',
                              type=interactions.OptionType.STRING,
                              required=True,
                              choices=[choice_avg]),
                              SlashCommandOption(
                                  name='group_par_champion',
                                  description='montrer un total global ou par champion ?',
                                  type=interactions.OptionType.BOOLEAN,
                                  required=False
                          ),
                              SlashCommandOption(
                                  name='nb_parties',
                                  description='combien de parties minimum ?',
                                  type=interactions.OptionType.INTEGER,
                                  required=False,
                                  min_value=1
                          )
                          ] + parameters_commun_stats_lol,)
    async def stats_lol_dmg(self,
                            ctx: SlashContext,
                            type: str,
                            calcul: str,
                            season: int = saison,
                            riot_id: str = None,
                            riot_tag: str = None,
                            role: str = None,
                            champion: str = None,
                            mode_de_jeu: str = None,
                            group_par_champion: bool = False,
                            nb_parties: int = 1,
                            view: str = 'global'
                            ):

        await ctx.defer(ephemeral=False)

        dict_type = {
            'dmg': 'matchs.dmg, matchs.dmg_ad, matchs.dmg_ap, matchs.dmg_true, matchs.dmg_min',
            'tank': 'matchs.dmg_reduit, matchs.dmg_tank',
            'kda': 'matchs.kills, matchs.assists, matchs.deaths',
        }

        df = get_data_matchs(dict_type[type], saison, int(ctx.guild_id), view)

        title = f'{type.upper()}'

        df[df['season'] == season]

        if riot_id != None and riot_tag != None:
            riot_id, riot_tag, df, title = tri_riot_id(df, riot_id, riot_tag, title)

        if champion != None:
            champion, df, title = tri_champion(champion, df, title)

        if mode_de_jeu != None:
            df = df[df['mode'] == mode_de_jeu]
            title += f' en {mode_de_jeu}'

        if role != None:
            df = df[df['role'] == role]
            title += f' ({role})'

        df = tri_occurence(df, 'champion', nb_parties)

        title += f' ({calcul})'

        if calcul == 'avg':

            dict_stats = {'dmg': {'dmg': 'total', 'dmg_ad': 'ad', 'dmg_ap': 'ap', 'dmg_true': 'true', 'dmg_min': 'dmg_min'},
                          'tank': {'dmg_tank': 'tank', 'dmg_reduit': 'reduit'},
                          'kda': {'kills': 'K', 'deaths': 'D', 'assists': 'A'}}

            dict_stats_choose = dict_stats[type]

            fig = go.Figure()
            fig.update_layout(title=title)

            nb_games = df.shape[0]

            if group_par_champion:
                dict_stat = {'dmg': 'dmg',
                             'tank': 'dmg_tank',
                             'kda': 'kills'}
                df = df.groupby('champion', as_index=False).mean().sort_values(
                    by=dict_stat[type], ascending=False).head(10)
                fig.add_trace(go.Histogram(x=df['champion'], y=df[dict_stat[type]], name=dict_stat[type], histfunc='avg',
                                           texttemplate="%{y:.0f}")).update_xaxes(categoryorder='total descending')

            else:
                for column, name in dict_stats_choose.items():

                    fig.add_trace(go.Histogram(x=df['riot_id'], y=df[column], histfunc='avg', name=name,
                                               texttemplate="%{y:.0f}")).update_xaxes(categoryorder='total descending')

            fig.update_yaxes(visible=False)

            embed, files = get_embed(fig, 'stats')

            embed.set_footer(text=f'Calculé sur {nb_games} matchs')

            await ctx.send(embeds=embed, files=files)


    @stats_lol.subcommand('games',
                          sub_cmd_description='Analyse des games',
                          options=[SlashCommandOption(
                              name='calcul',
                              description='quel type de calcul ?',
                              type=interactions.OptionType.STRING,
                              required=True,
                              choices=[choice_progression, choice_ecart]),
                          ] + parameters_nbgames)
    async def stats_lol_games(self,
                              ctx: SlashContext,
                              calcul: str,
                              season: int = saison,
                              riot_id: str = None,
                              riot_tag: str = None,
                              role: str = None,
                              champion: str = None,
                              mode_de_jeu: str = None,
                              grouper: str = 'joueur',
                              top: int = 20,
                              view: str = 'global'
                              ):

        await ctx.defer(ephemeral=False)

        df = get_data_matchs('matchs.victoire, matchs.time',
                             saison, int(ctx.guild_id), view)

        title = f'Games'

        df[df['season'] == season]

        if riot_id != None and riot_tag != None:
            riot_id, riot_tag, df, title = tri_riot_id(df, riot_id, riot_tag, title)

        if champion != None:            
            champion, df, title = tri_champion(champion, df, title)

        if mode_de_jeu != None:
            df = df[df['mode'] == mode_de_jeu]
            title += f' en {mode_de_jeu}'

        if role != None:
            df = df[df['role'] == role]
            title += f' ({role})'

        title += f' ({calcul})'

        if calcul == 'count':
            df = df.groupby('riot_id').count()
            fig = px.histogram(x=df.index, y=df['victoire'], color=df.index, text_auto=True, title=title).update_xaxes(
                categoryorder="total descending")
            fig.update_layout(showlegend=False)
            embed, files = get_embed(fig, 'games')

            await ctx.send(embeds=embed, files=files)

        elif calcul == 'time':
            if grouper == 'discord':
                df = df.groupby('discord').agg(
                    {'time': 'sum', 'champion': 'count', 'riot_id': 'max'})
                df.set_index('riot_id', inplace=True)
            else:
                df = df.groupby('riot_id').agg(
                    {'time': 'sum', 'champion': 'count'})
            df.rename(columns={'champion': 'nbgames'}, inplace=True)

            df.sort_values(by='time', ascending=False, inplace=True)
            df['jour'] = df['time'] // 1440
            df['heure'] = (df['time'] % 1440) // 60
            df['minute'] = (df['time'] % 1440) % 60

            txt = f'{title} : '

            for joueur, data in df.iterrows():
                txt += f'\n**{joueur}** : **{int(data["jour"])}** jours, **{int(data["heure"])}** heures, **{int(data["minute"])}** minutes, **{int(data["nbgames"])}** parties.'

            options = [
                interactions.StringSelectOption(
                    label="Nombre de games", value="nbgames", emoji=interactions.PartialEmoji(name='1️⃣')),
                interactions.StringSelectOption(
                    label="Temps joué", value="time", emoji=interactions.PartialEmoji(name='2️⃣')),
            ],

            select = interactions.StringSelectMenu(
                *options,
                custom_id='selection',
                placeholder="Choix de la statistique",
                min_values=1,
                max_values=1)

            message = await ctx.send("Quel stat ?",
                                     components=select)

            async def check(button_ctx):
                if int(button_ctx.ctx.author_id) == int(ctx.author.user.id):
                    return True
                await ctx.send("I wasn't asking you!", ephemeral=True)
                return False

            while True:
                try:
                    button_ctx: interactions.ComponentContext = await self.bot.wait_for_component(
                        components=select, check=check, timeout=30
                    )

                    if button_ctx.ctx.values[0] == 'nbgames':
                        fig = px.histogram(
                            df, x=df.index, y='nbgames', title='Nombre de parties jouées', color=df.index, text_auto=True)

                    elif button_ctx.ctx.values[0] == 'time':
                        fig = px.histogram(
                            df, x=df.index, y='time', title='Temps de jeu', color=df.index)

                    fig.update_xaxes(categoryorder="total descending")
                    fig.update_layout(showlegend=False)
                    embed, file = get_embed(fig, button_ctx.ctx.values[0])
                    # On envoie

                    await ctx.edit(content=txt, embeds=embed, files=file)

                except asyncio.TimeoutError:
                    # When it times out, edit the original message and remove the button(s)
                    return await ctx.edit(components=[])

        
    @stats_lol.subcommand('ecart_gold',
                          sub_cmd_description='Statistiques sur les Ecart gold',
                          options=[SlashCommandOption(
                              name='riot_id',
                              description='Pseudo LoL',
                              type=interactions.OptionType.STRING,
                              required=True),
                              SlashCommandOption(
                                  name='riot_tag',
                                  description='tag',
                                  type=interactions.OptionType.STRING,
                                  required=True),
                              SlashCommandOption(
                              name='nb_parties',
                              description='Combien de parties minimum ?',
                              type=interactions.OptionType.INTEGER,
                              required=False,
                              min_value=5
                          ),
                              SlashCommandOption(
                              name='season',
                              description='saison lol',
                              type=interactions.OptionType.INTEGER,
                              min_value=12,
                              max_value=saison,
                              required=False),
                              SlashCommandOption(
                              name='role',
                              description='Role LoL. Remplir ce role retire les stats par role',
                              type=interactions.OptionType.STRING,
                              required=False,
                              choices=[
                                  SlashCommandChoice(name='top', value='TOP'),
                                  SlashCommandChoice(
                                      name='jungle', value='JUNGLE'),
                                  SlashCommandChoice(name='mid', value='MID'),
                                  SlashCommandChoice(name='adc', value='ADC'),
                                  SlashCommandChoice(name='support', value='SUPPORT')]),
                              SlashCommandOption(
                              name='mode_de_jeu',
                              description='se focaliser sur un mode de jeu ?',
                              type=interactions.OptionType.STRING,
                              required=False,
                              choices=[
                                  SlashCommandChoice(name='soloq',
                                                     value='RANKED'),
                                  SlashCommandChoice(name='flex', value='FLEX')]),
                              SlashCommandOption(
                                  name='tier',
                                  description='se focaliser sur un tier ?',
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    choices=[
                                        SlashCommandChoice(name='fer', value='IRON'),
                                        SlashCommandChoice(name='bronze', value='BRONZE'),
                                        SlashCommandChoice(name='argent', value='SILVER'),
                                        SlashCommandChoice(name='or', value='GOLD'),
                                        SlashCommandChoice(name='platine', value='PLATINUM'),
                                        SlashCommandChoice(name='emeraude', value='EMERALD'),
                                        SlashCommandChoice(name='diamant', value='DIAMOND'),
                                        SlashCommandChoice(name='master', value='MASTER'),
                                        SlashCommandChoice(name='grandmaster', value='GRANDMASTER'),
                                        SlashCommandChoice(name='challenger', value='CHALLENGER')]),
                              SlashCommandOption(
                                  name='resultat_partie',
                                    description='se focaliser sur un type de partie ?',
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    choices=[
                                        SlashCommandChoice(name='victoire', value='True'), 
                                        SlashCommandChoice(name='défaite', value='False')
                                    ])
                          ])
    async def stats_lol_ecart_gold(self,
                                   ctx: SlashContext,
                                   season: int = saison,
                                   riot_id: str = None,
                                   riot_tag:str = None,
                                   role: str = None,
                                   mode_de_jeu: str = 'RANKED',
                                   nb_parties: int = 5,
                                   tier : str = None,
                                   resultat_partie:str = None,
                                   ):

        await ctx.defer(ephemeral=False)

        df = get_data_matchs(
            'matchs.ecart_gold, matchs.victoire, matchs.tier, matchs.rank, matchs.ecart_gold_min', saison, int(ctx.guild_id))
        
        title = f'Ecart gold moyen'

        df[df['season'] == season]

        if riot_id != None and riot_tag != None:
            riot_id, riot_tag, df, title = tri_riot_id(df, riot_id, riot_tag, title)

        if mode_de_jeu != None:
            df = df[df['mode'] == mode_de_jeu]
            title += f' en {mode_de_jeu}'

        if role != None:
            df = df[df['role'] == role]
            title += f' ({role})'
        
        if tier != None:
            df = df[df['tier'] == tier]
            title += f' ({tier})'
            
            
        if resultat_partie == 'True':
            df = df[df['victoire'] == True]
            title += f' | victoire only |'
        elif resultat_partie == 'False':
            df = df[df['victoire'] == False]
            title += f'  | défaite only |'

           
        df_grp = df.groupby('champion').agg({'ecart_gold': 'mean', 'ecart_gold_min' : 'mean', 'riot_id': 'count'})
        
        df_grp = df_grp[df_grp['riot_id'] >= nb_parties]
        
        df_grp.sort_values('ecart_gold', ascending=False, inplace=True)
        
        title += f' ({nb_parties} parties minimum)'
        
        
        txt = ''
        embeds = []
        for champion, data in df_grp.iterrows():
            txt += f'\n{emote_champ_discord[champion.capitalize()]} : Moyenne : **{int(data["ecart_gold"])}** | **{int(data["ecart_gold_min"])}** / min | ({int(data["riot_id"])} games) \n'
        
        try:    
            embed1 = interactions.Embed(title=title, color=interactions.Color.random())
            embed1.add_field(name=f'Champion', value=txt, inline=False)
        
        except ValueError:
            return await ctx.send(f'Tu as trop de champions, tu dois augmenter la limite de parties minimum (Actuellement {nb_parties} )')
                    
        embeds.append(embed1)
        
        if role == None:
            df_role = df.groupby('role').agg({'ecart_gold': 'mean', 'ecart_gold_min' : 'mean', 'riot_id': 'count'})
            
            df_role = df_role[df_role['riot_id'] >= nb_parties]
            df_role.sort_values('ecart_gold', ascending=False, inplace=True)
            
            txt_role = ''
            for role, data in df_role.iterrows():
                
                txt_role += f'\n{role} : Moyenne : **{int(data["ecart_gold"])}** | **{int(data["ecart_gold_min"])}** / min | ({int(data["riot_id"])} games) \n'
            

                embed4 = interactions.Embed(title=title, color=interactions.Color.random())
            embed4.add_field(name='Role', value=txt_role, inline=False)
                
            embeds.append(embed4)
        
        
        if tier == None:
            txt_tier = ''
            df_tier = df.groupby('tier').agg({'ecart_gold': 'mean', 'ecart_gold_min' : 'mean', 'riot_id': 'count'})
            
            df_tier = df_tier[df_tier['riot_id'] >= nb_parties]
            df_tier.sort_values('ecart_gold', ascending=False, inplace=True)
            
            for tier, data in df_tier.iterrows():
                
                txt_tier += f'\n{emote_rank_discord[tier]} : Moyenne : **{int(data["ecart_gold"])}** | **{int(data["ecart_gold_min"])}** / min | ({int(data["riot_id"])} games) \n'
                
            embed2 = interactions.Embed(title=title, color=interactions.Color.random())
            embed2.add_field(name=f'Tier', value=txt_tier, inline=False)
            
            embeds.append(embed2)
                
            df_rank = df.groupby(['tier', 'rank']).agg({'ecart_gold': 'mean', 'ecart_gold_min' : 'mean', 'riot_id': 'count'})
            
            df_rank = df_rank[df_rank['riot_id'] >= nb_parties]
            df_rank.sort_values('ecart_gold', ascending=False, inplace=True)
            
            txt_rank = ''
            for (tier, rank), data in df_rank.iterrows():
                    
                txt_rank += f'\n{emote_rank_discord[tier]} {rank} : Moyenne : **{int(data["ecart_gold"])}** | **{int(data["ecart_gold_min"])}** / min | ({int(data["riot_id"])} games) \n'
                    
            embed3 = interactions.Embed(title=title, color=interactions.Color.random())
            embed3.add_field(name=f'Tier/Rank', value=txt_rank, inline=False)
            
            embeds.append(embed3)
            
            
            
        
            paginator = Paginator.create_from_embeds(
                    self.bot,
                    *embeds)

            paginator.show_select_menu = True
            await paginator.send(ctx)
            
    @stats_lol.subcommand('elo',
                          sub_cmd_description='Statistiques sur ton elo',
                          options=[SlashCommandOption(
                              name='riot_id',
                              description='Pseudo LoL',
                              type=interactions.OptionType.STRING,
                              required=True),
                              SlashCommandOption(
                                  name='riot_tag',
                                  description='tag',
                                  type=interactions.OptionType.STRING,
                                  required=True),
                              SlashCommandOption(
                              name='season',
                              description='saison lol',
                              type=interactions.OptionType.INTEGER,
                              min_value=12,
                              max_value=saison,
                              required=False),
                            #   SlashCommandOption(
                            #   name='role',
                            #   description='Role LoL. Remplir ce role retire les stats par role',
                            #   type=interactions.OptionType.STRING,
                            #   required=False,
                            #   choices=[
                            #       SlashCommandChoice(name='top', value='TOP'),
                            #       SlashCommandChoice(
                            #           name='jungle', value='JUNGLE'),
                            #       SlashCommandChoice(name='mid', value='MID'),
                            #       SlashCommandChoice(name='adc', value='ADC'),
                            #       SlashCommandChoice(name='support', value='SUPPORT')]),
                              SlashCommandOption(
                              name='mode_de_jeu',
                              description='se focaliser sur un mode de jeu ?',
                              type=interactions.OptionType.STRING,
                              required=False,
                              choices=[
                                  SlashCommandChoice(name='soloq',
                                                     value='RANKED'),
                                  SlashCommandChoice(name='flex', value='FLEX')]),
                          ])
    async def stats_lol_elo(self,
                                   ctx: SlashContext,
                                   season: int = saison,
                                   riot_id: str = None,
                                   riot_tag:str = None,
                                #    role: str = None,
                                   mode_de_jeu: str = 'RANKED',
                                   ):

        await ctx.defer(ephemeral=False)
        
        riot_id = riot_id.replace(' ', '').lower()
        riot_tag = riot_tag.upper()
        
        df = lire_bdd_perso(f''' SELECT matchs.tier,
            matchs.rank,
            matchs.victoire,
            round(avg(matchs.mvp)) AS "Moyenne_MVP",
            count(matchs.mvp) AS count,
            round(avg(matchs.kp)) AS kp,
            round(avg(matchs.kda)) AS kda,
            round(avg(matchs.ecart_gold)) AS ecart_gold
        FROM matchs
        WHERE matchs.joueur = (( SELECT tracker.id_compte
                FROM tracker
                WHERE tracker.riot_id = '{riot_id}' AND tracker.riot_tagline = '{riot_tag}')) AND matchs.season = {season} AND matchs.mode = '{mode_de_jeu}'
        GROUP BY matchs.joueur, matchs.tier, matchs.rank, matchs.victoire
        ORDER BY tier ASC, rank DESC, victoire ASC;''' , index_col=['tier', 'rank', 'victoire']).T
        
        dfi.export(df, 'image.png', max_cols=-1,
                            max_rows=-1, table_conversion="matplotlib")

        await ctx.send(files=interactions.File('image.png'))

        os.remove('image.png')
        






def setup(bot):
    analyseLoL(bot)
