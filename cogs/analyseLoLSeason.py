
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, Task, IntervalTrigger, slash_command
import interactions
import pandas as pd
from fonctions.gestion_bdd import lire_bdd_perso, get_tag, autocomplete_riotid
from fonctions.match import emote_champ_discord
import numpy as np
from interactions.ext.paginators import Paginator
import dataframe_image as dfi
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap, BoundaryNorm
import random


saison = int(lire_bdd_perso('select * from settings', format='dict', index_col='parametres')['saison']['value'])

async def export_as_image(df, ctx : SlashContext, content=None):
    dfi.export(df, 'image.png', max_cols=-1,
                       max_rows=-1, table_conversion="matplotlib")

    if content == None:
        await ctx.send(files=interactions.File('image.png'))
    
    else:
        await ctx.send(content=content, files=interactions.File('image.png'))
    

    os.remove('image.png')


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

class AnalyseLoLSeason(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        


    @slash_command(name='lol_analyse_season', description='Stats sur sa saison')
    async def lol_analyse_season(self, ctx: SlashContext):
        pass


    @lol_analyse_season.subcommand("champion",
                            sub_cmd_description="Permet d'afficher des statistiques sur les champions rencontrés dans la saison",
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
                                    name="mode",
                                    description="Mode de jeu",
                                    type=interactions.OptionType.STRING,
                                    required=True,
                                    choices=[SlashCommandChoice(name='RANKED', value='RANKED'),
                                             SlashCommandChoice(name='ARAM', value='ARAM')]),
                                SlashCommandOption(
                                    name="saison",
                                    description="Quelle saison?",
                                    type=interactions.OptionType.INTEGER,
                                    required=False),
                                SlashCommandOption(
                                    name="split",
                                    description="Quelle saison?",
                                    type=interactions.OptionType.INTEGER,
                                    required=False),
                                SlashCommandOption(
                                    name="champion_joue",
                                    description="Champion joué",
                                    type=interactions.OptionType.STRING,
                                    required=False),
                                SlashCommandOption(
                                    name="champion_rencontre",
                                    description="Champion allié ou affronté",
                                    type=interactions.OptionType.STRING,
                                    required=False),
                                SlashCommandOption(
                                    name="role",
                                    description="role",
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    choices=[
                                        SlashCommandChoice(name='top', value='TOP'),
                                        SlashCommandChoice(name='jungle', value='JUNGLE'),
                                        SlashCommandChoice(name='mid', value='MID'),
                                        SlashCommandChoice(name='adc', value='ADC'),
                                        SlashCommandChoice(name='support', value='SUPPORT')]),
                                SlashCommandOption(
                                    name='tri',
                                    description='Quel tri ?',
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    choices=[
                                        SlashCommandChoice(name='Par apparition', value='count'),
                                        SlashCommandChoice(name='Par nom', value='champion')])
                                ])
    async def analyse_champion(self,
                      ctx: SlashContext,
                      riot_id: str,
                      riot_tag:str,
                      mode:str,
                      saison = saison,
                      split = None,
                      champion_joue = None,
                      champion_rencontre = None,
                      role = None,
                      tri = 'count'):
        
        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper() 
        
        await ctx.defer(ephemeral=False)     
        
        df = lire_bdd_perso(f'''SELECT matchs_joueur.*, matchs.champion, matchs.role, matchs.split, matchs.victoire from tracker
        INNER JOIN matchs ON tracker.id_compte = matchs.joueur
        INNER JOIN matchs_joueur ON matchs.match_id = matchs_joueur.match_id
        WHERE tracker.riot_id = '{riot_id}'
        AND tracker.riot_tagline = '{riot_tag}'
        AND matchs.season = {saison}
        AND matchs.mode = '{mode}' ''', index_col='match_id').T

        df['champion'] = df['champion'].str.capitalize()
        
        if champion_joue != None:
            df = df[df['champion'] == champion_joue.replace(' ', '').capitalize()]
        
        if role != None:
            df = df[df['role'] == role]
        
        if split != None:
            df = df[df['split'] == split]
        
        nbgames = df.shape[0]
        
        
        dict_allie = {}
        dict_ennemi = {}

        dict_allie = {}
        dict_ennemi = {}
        victory = []

        for match_id, data in df.iterrows():
            for i in range(1,6):
                name_allie = data[f'allie{i}'].lower()
                name_ennemi = data[f'ennemi{i}'].lower()
                champ_allie = data[f'champ{i}']
                champ_ennemi = data[f'champ{i+5}']
                victory.append(data['victoire'])
                
                if name_allie in dict_allie.keys():
                    name_allie = f'{name_allie} + {match_id} + {random.randint(1,10000)}'
                dict_allie[name_allie] = champ_allie
                if name_ennemi in dict_ennemi.keys():
                    name_ennemi = f'{name_ennemi} + {match_id} + {random.randint(1,10000)}'
                dict_ennemi[name_ennemi] = champ_ennemi

        def count_champion(dict):
            df_champion = pd.DataFrame.from_dict(dict, orient='index', columns=['champion'])
            df_champion['victoire'] = victory
            df_champion['victoire'] = df_champion['victoire'].astype(int)
            df_champion = df_champion[~df_champion.index.str.contains(f'{riot_id}#{riot_tag.lower()}')]
            df_count = df_champion.groupby('champion').agg(count=('champion', 'count'),
                                                        victory=('victoire', 'sum'))

            if tri == 'count':
                ascending = False
            elif tri == 'champion':
                ascending = True                                           
            df_count.sort_values(tri, ascending=ascending, inplace=True)
            df_count.index = df_count.index.str.capitalize()

            if champion_rencontre != None:
                df_count = df_count[df_count.index == champion_rencontre.replace(' ', '').capitalize()]
            df_count['%'] = np.int8((df_count['count'] / df_count['count'].sum())*100)
            df_count['%_victoire'] = np.int8(df_count['victory'] / df_count['count'] * 100)
            
            # return df_champion
            
            return df_count          
        
        df_allie = count_champion(dict_allie)
        df_ennemi = count_champion(dict_ennemi)    
        
        def embedding(df, title, part):
            embed = interactions.Embed(f'{title} ({nbgames} games)')
            txt = ''
            for champion, data in df.iterrows():
                count = data['count']
                pick_percent = data['%']
                victory_percent = data['%_victoire']
                txt += f'{emote_champ_discord.get(champion, champion)} Pick **{count}** fois -> WR : **{victory_percent}%** \n'


            
            embed.add_field(name=f'{mode} PARTIE {part}', value=txt)    
            
            return embed
        
        
        embed_allie_top10 = embedding(df_allie.iloc[:10], 'ALLIE', 1)
        embed_allie_top20 = embedding(df_allie.iloc[10:20], 'ALLIE', 2)
        embed_allie_top30 = embedding(df_allie.iloc[20:30], 'ALLIE', 3)
        embed_ennemi_top10 = embedding(df_ennemi.iloc[:10], 'ENNEMI', 1)
        embed_ennemi_top20 = embedding(df_ennemi.iloc[10:20], 'ENNEMI', 2)
        embed_ennemi_top30 = embedding(df_ennemi.iloc[20:30], 'ENNEMI', 3)

        embeds = []

        for each_embed in [embed_allie_top10, embed_allie_top20, embed_allie_top30, embed_ennemi_top10, embed_ennemi_top20, embed_ennemi_top30]:
            if len(each_embed.fields[0].value) > 20:
                embeds.append(each_embed)
    

        paginator = Paginator.create_from_embeds(
                    self.bot,
                    *embeds)

        paginator.show_select_menu = True
        await paginator.send(ctx)

    @lol_analyse_season.subcommand("ecart_stats",
                            sub_cmd_description="Permet d'afficher des statistiques sur des écarts durant la saison",
                            options=[
                                SlashCommandOption(
                                    name="methode",
                                    description="Methode",
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    choices=[
                                        SlashCommandChoice(name='gold_individuel', value='ecart_gold'),
                                        SlashCommandChoice(name='gold_team', value='ecart_gold_team'),
                                        SlashCommandChoice(name='kills', value='kills'),
                                        SlashCommandChoice(name='morts', value='deaths'),
                                        SlashCommandChoice(name='assists', value='assists'),
                                        SlashCommandChoice(name='dmg', value='dmg'),
                                        SlashCommandChoice(name='tank', value='dmg_tank'),
                                        SlashCommandChoice(name='cs', value='cs'),
                                        SlashCommandChoice(name='vision', value='vision_score'),
                                        SlashCommandChoice(name='afk', value='afk'),
                                        SlashCommandChoice(name='duree', value='time')]),
                                SlashCommandOption(
                                    name="saison",
                                    description="Quelle saison?",
                                    type=interactions.OptionType.INTEGER,
                                    required=False),
                                SlashCommandOption(
                                    name="champion",
                                    description="Quelle champion?",
                                    type=interactions.OptionType.INTEGER,
                                    required=False),
                                SlashCommandOption(
                                    name="calcul",
                                    description="Calcul",
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    choices=[
                                        SlashCommandChoice(name='Somme', value='sum'),
                                        SlashCommandChoice(name='Moyenne', value='mean'),
                                        SlashCommandChoice(name='Mediane', value='median')]),
                                SlashCommandOption(
                                    name="minmax",
                                    description="Inclure min et max?",
                                    type=interactions.OptionType.BOOLEAN,
                                    required=False),
                                SlashCommandOption(
                                    name="role",
                                    description="role",
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    choices=[
                                        SlashCommandChoice(name='top', value='TOP'),
                                        SlashCommandChoice(name='jungle', value='JUNGLE'),
                                        SlashCommandChoice(name='mid', value='MID'),
                                        SlashCommandChoice(name='adc', value='ADC'),
                                        SlashCommandChoice(name='support', value='SUPPORT')])
                                ])
    async def analyse_gold(self,
                      ctx: SlashContext,
                      methode = 'ecart_gold',
                      saison = 0,
                      champion = None,
                      calcul = 'sum',
                      minmax = False,
                      role = None):
        
        
        await ctx.defer(ephemeral=False)     
        
        df = lire_bdd_perso(f'''SELECT tracker.riot_id, matchs.champion, matchs.role, matchs.victoire, matchs.{methode}, matchs.tier, matchs.season from tracker
        INNER JOIN matchs ON tracker.id_compte = matchs.joueur
        AND matchs.mode = 'RANKED'
        and server_id = {int(ctx.guild_id)} ''', index_col=None).T

        if minmax:
            aggfunc = [calcul, 'count', 'min', 'max']
        else:
            aggfunc = [calcul, 'count']

        if champion != None:
            df = df[df['champion'] == champion.replace(' ', '').capitalize()]
        
        if role != None:
            df = df[df['role'] == role]
        
        if saison != 0:
            df = df[df['season'] == saison]

        df['victoire'].replace({False : 'Défaite', True : 'Victoire'}, inplace=True )

        df_pivot = df.pivot_table(index='riot_id',
                                columns=['victoire'],
                                values=methode,
                                aggfunc=aggfunc,
                                fill_value=0)
        
        df_pivot = df_pivot.astype(int)

        nom_total = 'Ecart' if methode in ['ecart_gold', 'ecart_gold_team'] > 0 else 'Total'

        df_pivot[nom_total] = df_pivot[(calcul, 'Défaite')] + df_pivot[(calcul, 'Victoire')]
        df_pivot.sort_values(nom_total, ascending=False, inplace=True)
        
        await export_as_image(df_pivot, ctx)


    @lol_analyse_season.subcommand("lp_par_game",
                            sub_cmd_description="Permet d'afficher des statistiques sur ses LP",
                            options=[
                                SlashCommandOption(
                                    name="riot_id",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True,
                                    autocomplete=True),
                                SlashCommandOption(
                                    name="riot_tag",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=False),
                                SlashCommandOption(    
                                    name="riot_id2",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=False),
                                SlashCommandOption(
                                    name="riot_tag2",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=False),
                                SlashCommandOption(
                                    name="saison",
                                    description="Quelle saison?",
                                    type=interactions.OptionType.INTEGER,
                                    required=False),
                                SlashCommandOption(
                                    name="split",
                                    description="role",
                                    type=interactions.OptionType.INTEGER,
                                    required=False),
                                SlashCommandOption(
                                    name="nbgames",
                                    description="Nombre de games",
                                    type=interactions.OptionType.INTEGER,
                                    required=False),
                                SlashCommandOption(
                                    name="nbjours",
                                    description="Nombre de jours précédents",
                                    type=interactions.OptionType.INTEGER,
                                    required=False)
                                ])
    async def analyse_lp(self,
                      ctx: SlashContext,
                      riot_id: str,
                      riot_tag:str = None,
                      riot_id2: str= None,
                      riot_tag2: str=None,
                    #   mode:str,
                      saison = saison,
                      split = None,
                      nbgames = None,
                      nbjours = None):


        dict_points = {'F': 0,
                                        'B': 400,
                                        'S': 800,
                                        'G': 1200,
                                        'P': 1600,
                                        'E' : 2000,
                                        'D': 2400,
                                        'M': 2800,
                                        'GM': 3200,
                                        'C': 5000,
                                        'I': 300,
                                        'II': 200,
                                        'III': 100,
                                        'IV': 0,
                                        ' ': 0,
                                        '': 0}
        
        dict_color = {'fer' : {'background' : '#252430', 'courbe' : '#7c6f71'},
                        'bronze' : {'background' : '#332a31', 'courbe' : '#785d4f'},
                        'silver' : {'background' : '#323440', 'courbe' : '#727879'},
                        'gold' : {'background' : '#352e31', 'courbe' : '#c88c3d'},
                        'platine' : {'background' : '#213041', 'courbe' : '#43a9d4'},
                        'emeraude' : {'background' : '#1d292b', 'courbe' : '#399a3f'},
                        'diamant' : {'background' : '#332a52', 'courbe' : '#7b3fe8'},
                        'master' : {'background' : '#58363c', 'courbe' : '#9f5c4f'},
                        'gm' : {'background' : '#342631', 'courbe' : '#bb4e45'},
                        'challenger' : {'background' : '#38353a', 'courbe' : '#f0cb78'}}
        
        await ctx.defer(ephemeral=False)

        async def creation_df(riot_id1, riot_tag1, saison1, nbjours1, nbgames1, split1):
            if nbjours == None:
                df = lire_bdd_perso(
                        f'''SELECT matchs.id, tracker.riot_id, tracker.riot_tagline, matchs.role, matchs.champion, matchs.match_id, matchs.mode, matchs.season, matchs.split, 
                        matchs.date, matchs.lp, matchs.tier, matchs.rank, matchs.ecart_lp, matchs.victoire, tracker.discord from matchs
                    INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                    where season = {saison1}
                    ORDER BY match_id DESC ''', index_col='id').transpose()
            
            else:
                df = lire_bdd_perso(
                        f'''SELECT matchs.id, tracker.riot_id, tracker.riot_tagline, matchs.role, matchs.champion, matchs.match_id, matchs.mode, matchs.season, matchs.split, 
                        matchs.date, matchs.lp, matchs.tier, matchs.rank, matchs.ecart_lp, matchs.victoire, tracker.discord from matchs
                    INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                    where season = {saison1}
                    and datetime > '{(datetime.now() - timedelta(days=nbjours1)):%Y-%m-%d}'
                    ORDER BY match_id DESC ''', index_col='id').transpose()




            if riot_tag1 == None:
                try:
                    riot_tag1 = get_tag(riot_id1)
                except ValueError:
                    return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')

            riot_id1 = riot_id1.lower().replace(' ', '')
            riot_tag1 = riot_tag1.upper()
            df = df[(df['riot_id'] == riot_id1) & (df['riot_tagline'] == riot_tag1)]


            df = df[df['mode'] == 'RANKED']

            if split1 != None:
                df = df[df['split'] == split1]

            if nbgames != None:
                df = df.head(nbgames1)


            def transfo_points(x):

                value = x['ladder'].split(' ')[1]
                if x['lp'] > 101 and x['ladder'][0] == 'G':
                        value = 'GM'
                points = dict_points[x['ladder'][0]
                                                ] + dict_points[value] + x['lp']
                return points


            df['ladder'] = df['tier'].str[0] + ' ' + \
                                    df['rank'] + ' / ' + df['lp'].astype('str') + ' LP'

            df['date'] = df['date'].apply(
                                    lambda x: datetime.fromtimestamp(x).strftime('%d/%m/%Y'))
            df['datetime'] = pd.to_datetime(
                                    df['date'], infer_datetime_format=True)

            df.sort_values(['date'], ascending=False, inplace=True)

                    # df['datetime'] = df['datetime'].dt.strftime('%d/%m/%Y')

            df = df.groupby(['match_id', 'datetime', 'ladder'], as_index=False).agg(
                                    {'lp': 'max'}).reset_index()


            df['points'] = df.apply(transfo_points, axis=1)
                    
                    # df = df.groupby(['riot_id', 'riot_tagline', 'datetime'], as_index=False)[['points']].apply(lambda x : x.nlargest(3, 'points'))


            df = df[df['points'] > 50]


            df.sort_values('match_id', inplace=True)

            return df, riot_id1, riot_tag1


        df, riot_id, riot_tag = await creation_df(riot_id, riot_tag, saison, nbjours, nbgames, split)


        nb_games = df.shape[0]

        if riot_id2 != None:
            df2, riot_id2, riot_tag2 = await creation_df(riot_id2, riot_tag2, saison, nbjours, nbgames, split)
            nb_games2 = df2.shape[0]
            gap2 = 50

            if nb_games2 < 50:
                gap2 = 10
            
            elif nb_games2 < 100:
                gap2 = 20

        gap = 50

        if nb_games < 50:
            gap = 10

        elif nb_games < 100:
            gap = 20
            
        def creation_rank(value):
            return [value + 0, value + 100, value + 200, value + 300]
        
        fig, ax = plt.subplots(figsize=(20, 10))
        
        def creation_ligne(df, nb_games, gap, ax):


            # dates =np.linspace(0, 10000, 500)  pd.date_range(start="2023-01-01", end="2023-12-31", periods=500)  # Axe X : de janvier à décembre
            x =  np.arange(gap, nb_games + gap, 1)
            y = np.array(df['points'].tolist())               # Exemple de courbe : y = log(x + 1)



            points = np.array([x, y]).T.reshape(-1, 1, 2)

            segments = np.concatenate([points[:-1], points[1:]], axis=1)

            cmap = ListedColormap([dict_color['fer']['courbe'],
                                    dict_color['bronze']['courbe'],
                                    dict_color['silver']['courbe'],
                                    dict_color['gold']['courbe'],
                                    dict_color['platine']['courbe'],
                                    dict_color['emeraude']['courbe'],
                                    dict_color['diamant']['courbe'],
                                    dict_color['master']['courbe'],
                                    dict_color['gm']['courbe'],
                                    dict_color['challenger']['courbe']])
            
            norm = BoundaryNorm([50, dict_points['B'], dict_points['S'], dict_points['G'], dict_points['P'], dict_points['E'], dict_points['D'], dict_points['M'], dict_points['GM'], dict_points['C'], 12000], cmap.N)
            lc = LineCollection(segments, cmap=cmap, norm=norm)
            lc.set_array(y)
            lc.set_linewidth(2)

            return x, ax, lc
        
        if riot_id2 == None:
            x, ax, lc = creation_ligne(df, nb_games, gap, ax)
        else:
            x, ax, lc = creation_ligne(df, nb_games, max(gap, gap2), ax)

        line = ax.add_collection(lc)

        if riot_id2 != None:
            x2, ax, lc2 = creation_ligne(df2, nb_games2, max(gap, gap2), ax)
            lc2.set_linestyle('dashed')
            line2 = ax.add_collection(lc2)
            nb_games = max(nb_games, nb_games2)
            gap = max(gap, gap2)

            if nb_games2 > nb_games:
                x = x2


        # Personnalisation du graphique
        ax.set_facecolor('#1e1e2f')  # Fond sombre
        ax.spines['bottom'].set_color('#ffffff')
        ax.spines['left'].set_color('#ffffff')
        ax.tick_params(colors='black')

        # Ajouter des lignes horizontales
        y_levels_fer = creation_rank(dict_points['F'])  
        y_levels_bronze = creation_rank(dict_points['B']) 
        y_levels_silver = creation_rank(dict_points['S'])
        y_levels_gold = creation_rank(dict_points['G'])
        y_levels_plat = creation_rank(dict_points['P'])
        y_levels_emeraude = creation_rank(dict_points['E'])
        y_levels_diamant = creation_rank(dict_points['D'])
        y_levels_master = creation_rank(dict_points['M'])
        y_levels_gm = creation_rank(dict_points['GM'])
        y_levels_chal = creation_rank(dict_points['C'])

        liste_order = [4,3,2,1]

        if riot_id2 == None:


            if not df[df['points'].between(50, dict_points['B'])].empty:
            # # Ajout des étiquettes
                for i, level in enumerate(y_levels_fer):
                    ax.axhline(y=level, color=dict_color['fer']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(gap, level, f'F{liste_order[i]}', color=dict_color['fer']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(50, dict_points['B'], facecolor=dict_color['fer']['background'], alpha=0.3)

            if not df[df['points'].between(dict_points['B'], dict_points['S'])].empty:
                for i, level in enumerate(y_levels_bronze):
                    ax.axhline(y=level, color=dict_color['bronze']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(gap, level, f'B{liste_order[i]}', color=dict_color['bronze']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['B'], dict_points['S'], facecolor=dict_color['bronze']['background'], alpha=0.3)

            if not df[df['points'].between(dict_points['S'], dict_points['G'])].empty:
                for i, level in enumerate(y_levels_silver):
                    ax.axhline(y=level, color=dict_color['silver']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(gap, level, f'S{liste_order[i]}', color=dict_color['silver']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['S'], dict_points['G'], facecolor=dict_color['silver']['background'], alpha=0.3)

            if not df[df['points'].between(dict_points['G'], dict_points['P'])].empty:
                for i, level in enumerate(y_levels_gold):
                    ax.axhline(y=level, color=dict_color['gold']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(gap, level, f'G{liste_order[i]}', color=dict_color['gold']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['G'], dict_points['P'], facecolor=dict_color['gold']['background'], alpha=0.3)

            if not df[df['points'].between(dict_points['P'], dict_points['E'])].empty:
                for i, level in enumerate(y_levels_plat):
                    ax.axhline(y=level, color=dict_color['platine']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(gap, level, f'P{liste_order[i]}', color=dict_color['platine']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['P'], dict_points['E'], facecolor=dict_color['platine']['background'], alpha=0.3)

            if not df[df['points'].between(dict_points['E'], dict_points['D'])].empty:

                for i, level in enumerate(y_levels_emeraude):
                    ax.axhline(y=level, color=dict_color['emeraude']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(gap, level, f'E{liste_order[i]}', color=dict_color['emeraude']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['E'], dict_points['D'], facecolor=dict_color['emeraude']['background'], alpha=0.3)

            if not df[df['points'].between(dict_points['D'], dict_points['M'])].empty:

                for i, level in enumerate(y_levels_diamant):
                    ax.axhline(y=level, color=dict_color['diamant']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(gap, level, f'D{liste_order[i]}', color=dict_color['diamant']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['D'], dict_points['M'], facecolor=dict_color['diamant']['background'], alpha=0.3)

            if not df[df['points'].between(dict_points['M'], dict_points['GM'])].empty:

                for i, level in enumerate(y_levels_master):
                    ax.axhline(y=level, color=dict_color['master']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(gap, level, f'M', color=dict_color['master']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['M'], dict_points['GM'], facecolor=dict_color['master']['background'], alpha=0.3)


            if not df[df['points'].between(dict_points['GM'], dict_points['C'])].empty:

                # for i, level in enumerate(y_levels_gm):
                ax.axhline(y=dict_points['GM'], color=dict_color['gm']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                ax.text(gap, dict_points['GM'], f'GM', color=dict_color['gm']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['GM'], dict_points['C'], facecolor=dict_color['gm']['background'], alpha=0.3)

            if not df[df['points'].between(dict_points['C'], 11000)].empty:
                # for i, level in enumerate(y_levels_chal):
                ax.axhline(y=dict_points['C'], color=dict_color['challenger']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                ax.text(gap, dict_points['C'], f'C', color=dict_color['challenger']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['C'], 11000, facecolor=dict_color['challenger']['background'], alpha=0.3)

                for index, data in df[df['points'] > dict_points['M']].iloc[::10].iterrows():

                    plt.annotate(f'{data["lp"]:.0f}', 
                                (index+gap, data['points']), 
                                ha='center', 
                                fontsize=15,
                                color='white')
    
        else:
                    if not (df[df['points'].between(50, dict_points['B'])].empty and df2[df2['points'].between(50, dict_points['B'])].empty):
                    # # Ajout des étiquettes
                        for i, level in enumerate(y_levels_fer):
                            ax.axhline(y=level, color=dict_color['fer']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                            ax.text(gap, level, f'F{liste_order[i]}', color=dict_color['fer']['courbe'], fontsize=20, va='bottom')

                        ax.axhspan(50, dict_points['B'], facecolor=dict_color['fer']['background'], alpha=0.3)

                    if not (df[df['points'].between(dict_points['B'], dict_points['S'])].empty and df2[df2['points'].between(dict_points['B'], dict_points['S'])].empty):
                        for i, level in enumerate(y_levels_bronze):
                            ax.axhline(y=level, color=dict_color['bronze']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                            ax.text(gap, level, f'B{liste_order[i]}', color=dict_color['bronze']['courbe'], fontsize=20, va='bottom')

                        ax.axhspan(dict_points['B'], dict_points['S'], facecolor=dict_color['bronze']['background'], alpha=0.3)

                    if not (df[df['points'].between(dict_points['S'], dict_points['G'])].empty and df2[df2['points'].between(dict_points['S'], dict_points['G'])].empty):
                        for i, level in enumerate(y_levels_silver):
                            ax.axhline(y=level, color=dict_color['silver']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                            ax.text(gap, level, f'S{liste_order[i]}', color=dict_color['silver']['courbe'], fontsize=20, va='bottom')

                        ax.axhspan(dict_points['S'], dict_points['G'], facecolor=dict_color['silver']['background'], alpha=0.3)

                    if not (df[df['points'].between(dict_points['G'], dict_points['P'])].empty and df2[df2['points'].between(dict_points['G'], dict_points['P'])].empty):
                        for i, level in enumerate(y_levels_gold):
                            ax.axhline(y=level, color=dict_color['gold']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                            ax.text(gap, level, f'G{liste_order[i]}', color=dict_color['gold']['courbe'], fontsize=20, va='bottom')

                        ax.axhspan(dict_points['G'], dict_points['P'], facecolor=dict_color['gold']['background'], alpha=0.3)

                    if not (df[df['points'].between(dict_points['P'], dict_points['E'])].empty and df2[df2['points'].between(dict_points['P'], dict_points['E'])].empty):
                        for i, level in enumerate(y_levels_plat):
                            ax.axhline(y=level, color=dict_color['platine']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                            ax.text(gap, level, f'P{liste_order[i]}', color=dict_color['platine']['courbe'], fontsize=20, va='bottom')

                        ax.axhspan(dict_points['P'], dict_points['E'], facecolor=dict_color['platine']['background'], alpha=0.3)

                    if not (df[df['points'].between(dict_points['E'], dict_points['D'])].empty and df2[df2['points'].between(dict_points['E'], dict_points['D'])].empty):

                        for i, level in enumerate(y_levels_emeraude):
                            ax.axhline(y=level, color=dict_color['emeraude']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                            ax.text(gap, level, f'E{liste_order[i]}', color=dict_color['emeraude']['courbe'], fontsize=20, va='bottom')

                        ax.axhspan(dict_points['E'], dict_points['D'], facecolor=dict_color['emeraude']['background'], alpha=0.3)

                    if not (df[df['points'].between(dict_points['D'], dict_points['M'])].empty and df2[df2['points'].between(dict_points['D'], dict_points['M'])].empty):

                        for i, level in enumerate(y_levels_diamant):
                            ax.axhline(y=level, color=dict_color['diamant']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                            ax.text(gap, level, f'D{liste_order[i]}', color=dict_color['diamant']['courbe'], fontsize=20, va='bottom')

                        ax.axhspan(dict_points['D'], dict_points['M'], facecolor=dict_color['diamant']['background'], alpha=0.3)

                    if not (df[df['points'].between(dict_points['M'], dict_points['GM'])].empty and df2[df2['points'].between(dict_points['M'], dict_points['GM'])].empty):

                        for i, level in enumerate(y_levels_master):
                            ax.axhline(y=level, color=dict_color['master']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                            ax.text(gap, level, f'M', color=dict_color['master']['courbe'], fontsize=20, va='bottom')

                        ax.axhspan(dict_points['M'], dict_points['GM'], facecolor=dict_color['master']['background'], alpha=0.3)


                    if not (df[df['points'].between(dict_points['GM'], dict_points['C'])].empty and df2[df2['points'].between(dict_points['GM'], dict_points['C'])].empty):

                        # for i, level in enumerate(y_levels_gm):
                        ax.axhline(y=dict_points['GM'], color=dict_color['gm']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                        ax.text(gap, dict_points['GM'], f'GM', color=dict_color['gm']['courbe'], fontsize=20, va='bottom')

                        ax.axhspan(dict_points['GM'], dict_points['C'], facecolor=dict_color['gm']['background'], alpha=0.3)

                    if not (df[df['points'].between(dict_points['C'], 11000)].empty and df2[df2['points'].between(dict_points['C'], 11000)].empty):
                        # for i, level in enumerate(y_levels_chal):
                        ax.axhline(y=dict_points['C'], color=dict_color['challenger']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                        ax.text(gap, dict_points['C'], f'C', color=dict_color['challenger']['courbe'], fontsize=20, va='bottom')

                        ax.axhspan(dict_points['C'], 11000, facecolor=dict_color['challenger']['background'], alpha=0.3)

                        for index, data in df[df['points'] > dict_points['M']].iloc[::10].iterrows():

                            plt.annotate(f'{data["lp"]:.0f}', 
                                        (index+gap, data['points']), 
                                        ha='center', 
                                        fontsize=15,
                                        color='white')


                        for index2, data2 in df2[df2['points'] > dict_points['M']].iloc[::10].iterrows():

                            plt.annotate(f'{data2["lp"]:.0f}', 
                                        (index2+gap, data2['points']), 
                                        ha='center', 
                                        fontsize=15,
                                        color='white')


        ax.set_xlim([gap, nb_games + gap])

        # Trouver le multiple de 400 le plus proche pour le minimum (vers 0)

        if riot_id2 == None:
            min_multiple_400 = np.floor(df[df['points'] > 50]['points'].min() / 400) * 400
        
        else:
            points1 = df[df['points'] > 50]['points'].min()
            points2 = df2[df2['points'] > 50]['points'].min()
            points = min(points1, points2)
            min_multiple_400 = np.floor(points / 400) * 400


        # Trouver le multiple de 400 le plus proche pour le maximum (vers 12000)
        if riot_id2 == None:
            max_multiple_400 = np.ceil(df['points'].max() / 400) * 400
        else:
            points = max(df['points'].max(), df2['points'].max())
            max_multiple_400 = np.ceil(points / 400) * 400


        ax.set_ylim([min_multiple_400, max_multiple_400])

        # Désactiver les valeurs de l'axe Y
        ax.yaxis.set_ticks([])


        # Ajouter des annotations toutes les 50 valeurs de x
        for i in range(gap, len(x), gap):  # On prend tous les 50 indices
            plt.annotate(f'{x[i]-gap:.0f}', 
                        (x[i], min_multiple_400+10), 
                        ha='center', 
                        fontsize=15,
                        color='white')

        fig.subplots_adjust(bottom = 0)
        fig.subplots_adjust(top = 1)
        fig.subplots_adjust(right = 1)
        fig.subplots_adjust(left = 0)



        fig.savefig('lp.jpg')

        texte = f'{riot_id}#{riot_tag}'

        if riot_id2 != None:
            texte = f'Ligne complète : {riot_id}#{riot_tag} | Pointillés : {riot_id2}#{riot_tag2}'

        await ctx.send(content=texte, file=interactions.File('lp.jpg'))

        os.remove('lp.jpg')



    @analyse_lp.autocomplete("riot_id")
    async def autocomplete(self, ctx: interactions.AutocompleteContext):

        liste_choix = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)

        await ctx.send(choices=liste_choix)



    @lol_analyse_season.subcommand("lp_par_jour",
                            sub_cmd_description="Permet d'afficher des statistiques sur ses LP",
                            options=[
                                SlashCommandOption(
                                    name="riot_id",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True,
                                    autocomplete=True),
                                SlashCommandOption(
                                    name="riot_tag",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=False),
                                SlashCommandOption(    
                                    name="riot_id2",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    autocomplete=True),
                                SlashCommandOption(
                                    name="riot_tag2",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=False),
                                SlashCommandOption(
                                    name="saison",
                                    description="Quelle saison?",
                                    type=interactions.OptionType.INTEGER,
                                    required=False),
                                SlashCommandOption(
                                    name="nbjours",
                                    description="Nombre de jours précédents",
                                    type=interactions.OptionType.INTEGER,
                                    required=False)
                                ])
    async def analyse_lp_par_jour(self,
                      ctx: SlashContext,
                      riot_id: str,
                      riot_tag:str = None,
                      riot_id2: str= None,
                      riot_tag2: str=None,
                    #   mode:str,
                      saison = saison,
                      nbjours = None):

        df = lire_bdd_perso(f'''select suivi_rank.*, tracker.riot_id, tracker.riot_tagline from suivi_rank
                       inner join tracker on suivi_rank.index = tracker.id_compte
                       where saison = {saison} ''', index_col=None).T
        

        if riot_tag == None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')

            riot_id = riot_id.lower().replace(' ', '')
            riot_tag = riot_tag.upper()

        
        if riot_id2 != None and riot_tag2 == None:
            try:
                riot_tag2 = get_tag(riot_id2)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')

            riot_id2 = riot_id2.lower().replace(' ', '')
            riot_tag2 = riot_tag2.upper()             

        df = df[(df['riot_id'].isin([riot_id, riot_id2])) & (df['riot_tagline'].isin([riot_tag, riot_tag2]))]

        df[['index', 'wins', 'losses', 'LP', 'saison']] = df[['index', 'wins', 'losses', 'LP', 'saison']].astype(int)
        df['datetime'] = pd.to_datetime(df['datetime'])

        if nbjours != None:
            df = df[df['datetime'] >= datetime.now() - timedelta(days=nbjours)]

        df = df.sort_values(by='datetime', ascending=True).reset_index(drop=True)

        df['datetime_id'] = pd.factorize(df['datetime'])[0]


        dict_points = {'F': 0,
                                                'B': 400,
                                                'S': 800,
                                                'G': 1200,
                                                'P': 1600,
                                                'E' : 2000,
                                                'D': 2400,
                                                'M': 2800,
                                                'GM': 3200,
                                                'C': 5000,
                                                'I': 300,
                                                'II': 200,
                                                'III': 100,
                                                'IV': 0,
                                                ' ': 0,
                                                '': 0}
                
        dict_color = {'fer' : {'background' : '#252430', 'courbe' : '#7c6f71'},
                                'bronze' : {'background' : '#332a31', 'courbe' : '#785d4f'},
                                'silver' : {'background' : '#323440', 'courbe' : '#727879'},
                                'gold' : {'background' : '#352e31', 'courbe' : '#c88c3d'},
                                'platine' : {'background' : '#213041', 'courbe' : '#43a9d4'},
                                'emeraude' : {'background' : '#1d292b', 'courbe' : '#399a3f'},
                                'diamant' : {'background' : '#332a52', 'courbe' : '#7b3fe8'},
                                'master' : {'background' : '#58363c', 'courbe' : '#9f5c4f'},
                                'gm' : {'background' : '#342631', 'courbe' : '#bb4e45'},
                                'challenger' : {'background' : '#38353a', 'courbe' : '#f0cb78'}}

        def transfo_points(x):

            value = x['ladder'].split(' ')[1]
            if x['LP'] > 101 and x['ladder'][0] == 'G':
                value = 'GM'
            points = dict_points[x['ladder'][0]] + dict_points[value] + x['LP']
            return points


        df['ladder'] = df['tier'].str[0] + ' ' + \
                                            df['rank'] + ' / ' + df['LP'].astype('str') + ' LP'


        df['points'] = df.apply(transfo_points, axis=1)
                        
        df = df[df['points'] > 50] 


        def creation_rank(value):
                    return [value + 0, value + 100, value + 200, value + 300]
                
        fig, ax = plt.subplots(figsize=(20, 10))

        gap = 10

        def creation_ligne(df, ax):


            # dates =np.linspace(0, 10000, 500)  pd.date_range(start="2023-01-01", end="2023-12-31", periods=500)  # Axe X : de janvier à décembre
            # x =  np.arange(gap, nb_games + gap, 1)
            x = np.array(df['datetime_id'].tolist())
            y = np.array(df['points'].tolist())               # Exemple de courbe : y = log(x + 1)



            points = np.array([x, y]).T.reshape(-1, 1, 2)

            segments = np.concatenate([points[:-1], points[1:]], axis=1)

            cmap = ListedColormap([dict_color['fer']['courbe'],
                                    dict_color['bronze']['courbe'],
                                    dict_color['silver']['courbe'],
                                    dict_color['gold']['courbe'],
                                    dict_color['platine']['courbe'],
                                    dict_color['emeraude']['courbe'],
                                    dict_color['diamant']['courbe'],
                                    dict_color['master']['courbe'],
                                    dict_color['gm']['courbe'],
                                    dict_color['challenger']['courbe']])
            
            norm = BoundaryNorm([50, dict_points['B'], dict_points['S'], dict_points['G'], dict_points['P'], dict_points['E'], dict_points['D'], dict_points['M'], dict_points['GM'], dict_points['C'], 12000], cmap.N)
            lc = LineCollection(segments, cmap=cmap, norm=norm)
            lc.set_array(y)
            lc.set_linewidth(2)

            return ax, lc

        x = [0]      
        for i, joueur in enumerate(df['riot_id'].unique()):
            df_filter = df[df['riot_id'] == joueur]
            # df_filter.sort_values(by='datetime_id', ascending=False, inplace=True)
            ax, lc = creation_ligne(df_filter, ax)

            if i == 1:
                lc.set_linestyle('dashed')
            line = ax.add_collection(lc)

        # Personnalisation du graphique
        ax.set_facecolor('#1e1e2f')  # Fond sombre
        ax.spines['bottom'].set_color('#ffffff')
        ax.spines['left'].set_color('#ffffff')
        ax.tick_params(colors='black')

        # Ajouter des lignes horizontales
        y_levels_fer = creation_rank(dict_points['F'])  
        y_levels_bronze = creation_rank(dict_points['B']) 
        y_levels_silver = creation_rank(dict_points['S'])
        y_levels_gold = creation_rank(dict_points['G'])
        y_levels_plat = creation_rank(dict_points['P'])
        y_levels_emeraude = creation_rank(dict_points['E'])
        y_levels_diamant = creation_rank(dict_points['D'])
        y_levels_master = creation_rank(dict_points['M'])
        y_levels_gm = creation_rank(dict_points['GM'])
        y_levels_chal = creation_rank(dict_points['C'])

        liste_order = [4,3,2,1]         

        if not df[df['points'].between(50, dict_points['B'])].empty:
                    # # Ajout des étiquettes
                        for i, level in enumerate(y_levels_fer):
                            ax.axhline(y=level, color=dict_color['fer']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                            ax.text(gap, level, f'F{liste_order[i]}', color=dict_color['fer']['courbe'], fontsize=20, va='bottom')

                        ax.axhspan(50, dict_points['B'], facecolor=dict_color['fer']['background'], alpha=0.3)

        if not df[df['points'].between(dict_points['B'], dict_points['S'])].empty:
                for i, level in enumerate(y_levels_bronze):
                    ax.axhline(y=level, color=dict_color['bronze']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(0, level, f'B{liste_order[i]}', color=dict_color['bronze']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['B'], dict_points['S'], facecolor=dict_color['bronze']['background'], alpha=0.3)

        if not df[df['points'].between(dict_points['S'], dict_points['G'])].empty:
                for i, level in enumerate(y_levels_silver):
                    ax.axhline(y=level, color=dict_color['silver']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(0, level, f'S{liste_order[i]}', color=dict_color['silver']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['S'], dict_points['G'], facecolor=dict_color['silver']['background'], alpha=0.3)

        if not df[df['points'].between(dict_points['G'], dict_points['P'])].empty:
                for i, level in enumerate(y_levels_gold):
                    ax.axhline(y=level, color=dict_color['gold']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(0, level, f'G{liste_order[i]}', color=dict_color['gold']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['G'], dict_points['P'], facecolor=dict_color['gold']['background'], alpha=0.3)

        if not df[df['points'].between(dict_points['P'], dict_points['E'])].empty:
                for i, level in enumerate(y_levels_plat):
                    ax.axhline(y=level, color=dict_color['platine']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(0, level, f'P{liste_order[i]}', color=dict_color['platine']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['P'], dict_points['E'], facecolor=dict_color['platine']['background'], alpha=0.3)

        if not df[df['points'].between(dict_points['E'], dict_points['D'])].empty:
                for i, level in enumerate(y_levels_emeraude):
                    ax.axhline(y=level, color=dict_color['emeraude']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(0, level, f'E{liste_order[i]}', color=dict_color['emeraude']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['E'], dict_points['D'], facecolor=dict_color['emeraude']['background'], alpha=0.3)

        if not df[df['points'].between(dict_points['D'], dict_points['M'])].empty:
                for i, level in enumerate(y_levels_diamant):
                    ax.axhline(y=level, color=dict_color['diamant']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(0, level, f'D{liste_order[i]}', color=dict_color['diamant']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['D'], dict_points['M'], facecolor=dict_color['diamant']['background'], alpha=0.3)

        if not df[df['points'].between(dict_points['M'], dict_points['GM'])].empty:
                for i, level in enumerate(y_levels_master):
                    ax.axhline(y=level, color=dict_color['master']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                    ax.text(0, level, f'M', color=dict_color['master']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['M'], dict_points['GM'], facecolor=dict_color['master']['background'], alpha=0.3)


        if not df[df['points'].between(dict_points['GM'], dict_points['C'])].empty:
                        # for i, level in enumerate(y_levels_gm):
                ax.axhline(y=dict_points['GM'], color=dict_color['gm']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                ax.text(0, dict_points['GM'], f'GM', color=dict_color['gm']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['GM'], dict_points['C'], facecolor=dict_color['gm']['background'], alpha=0.3)

        if not df[df['points'].between(dict_points['C'], 11000)].empty:
                        # for i, level in enumerate(y_levels_chal):
                ax.axhline(y=dict_points['C'], color=dict_color['challenger']['courbe'], linestyle='--', linewidth=0.8)  # Ligne pointillée
                ax.text(0, dict_points['C'], f'C', color=dict_color['challenger']['courbe'], fontsize=20, va='bottom')

                ax.axhspan(dict_points['C'], 11000, facecolor=dict_color['challenger']['background'], alpha=0.3)

        for index, data in df[df['points'] > dict_points['M']].iloc[::10].iterrows():

            ax.annotate(f'{data["LP"]:.0f}', 
                                        (data['datetime_id'], data['points']), 
                                        ha='center', 
                                        fontsize=15,
                                        color='white')    

        ax.set_xlim([0, df['datetime_id'].max() + gap])

        # Trouver le multiple de 400 le plus proche pour le minimum (vers 0)


        min_multiple_400 = np.floor(df[df['points'] > 50]['points'].min() / 400) * 400
                



        max_multiple_400 = np.ceil(df['points'].max() / 400) * 400



        ax.set_ylim([min_multiple_400, max_multiple_400])

                # Désactiver les valeurs de l'axe Y
        ax.yaxis.set_ticks([])

                # Ajouter des annotations toutes les 50 valeurs de x
        for i in range(0, df['datetime_id'].max()+10, 5):  # On prend tous les 50 indices
            ax.annotate(f'{i}', 
                (i, min_multiple_400+10), 
                                ha='center', 
                                fontsize=15,
                                color='white')

        fig.subplots_adjust(bottom = 0)
        fig.subplots_adjust(top = 1)
        fig.subplots_adjust(right = 1)
        fig.subplots_adjust(left = 0)      

        fig.savefig('lp.jpg')

        texte = f'{riot_id}#{riot_tag}'

        if riot_id2 != None:
            texte = f'Ligne complète : {riot_id}#{riot_tag} | Pointillés : {riot_id2}#{riot_tag2}'

        await ctx.send(content=texte, file=interactions.File('lp.jpg'))

        os.remove('lp.jpg')


    @analyse_lp_par_jour.autocomplete("riot_id")

    async def autocomplete_lp_jour(self, ctx: interactions.AutocompleteContext):

        liste_choix = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)

        await ctx.send(choices=liste_choix)


    @analyse_lp_par_jour.autocomplete("riot_id2")

    async def autocomplete_lp_jour2(self, ctx: interactions.AutocompleteContext):

        liste_choix = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)

        await ctx.send(choices=liste_choix)

    @lol_analyse_season.subcommand("gold_max_min",
                            sub_cmd_description="Ecart maximal sur chaque role",
                            options=[
                                SlashCommandOption(
                                    name="riot_id",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True,
                                    autocomplete=True),
                                SlashCommandOption(
                                    name="riot_tag",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=False),
                                SlashCommandOption(
                                    name="saison",
                                    description="Quelle saison?",
                                    type=interactions.OptionType.INTEGER,
                                    required=False)])
    async def gold_max_min(self,
                      ctx: SlashContext,
                      riot_id: str,
                      riot_tag:str = None,
                      saison = saison):

    
        if riot_tag == None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')

        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper()

        req_sql = f'''WITH extremes AS (
        SELECT 
            matchs.match_id, 
            matchs_autres.ecart_gold_top, 
            matchs_autres.ecart_gold_jgl, 
            matchs_autres.ecart_gold_mid, 
            matchs_autres.ecart_gold_adc, 
            matchs_autres.ecart_gold_supp
        FROM 
            matchs_autres
        INNER JOIN 
            matchs 
            ON matchs.match_id = matchs_autres.match_id
        WHERE 
            joueur = (select id_compte from tracker where riot_id = '{riot_id}' and riot_tagline = '{riot_tag}') AND season = {saison} AND mode = 'RANKED'
    ),
    max_values AS (
        SELECT 
            MAX(ecart_gold_top) AS max_top,
            MAX(ecart_gold_jgl) AS max_jgl,
            MAX(ecart_gold_mid) AS max_mid,
            MAX(ecart_gold_adc) AS max_adc,
            MAX(ecart_gold_supp) AS max_supp,
            MIN(ecart_gold_top) AS min_top,
            MIN(ecart_gold_jgl) AS min_jgl,
            MIN(ecart_gold_mid) AS min_mid,
            MIN(ecart_gold_adc) AS min_adc,
            MIN(ecart_gold_supp) AS min_supp
        FROM 
            extremes
    )
    SELECT 
        'ecart_gold_top' AS column_name,
        max_values.max_top AS max_value,
        (SELECT match_id FROM extremes WHERE ecart_gold_top = max_values.max_top LIMIT 1) AS max_match_id,
        (SELECT champ1 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_top = max_values.max_top LIMIT 1)) AS champ_allie_max,
        (SELECT champ6 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_top = max_values.max_top LIMIT 1)) AS champ_ennemi_max,
        max_values.min_top AS min_value,
        (SELECT match_id FROM extremes WHERE ecart_gold_top = max_values.min_top LIMIT 1) AS min_match_id,
        (SELECT champ1 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_top = max_values.min_top LIMIT 1)) AS champ_allie_min,
        (SELECT champ6 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_top = max_values.min_top LIMIT 1)) AS champ_ennemi_min
    FROM 
        max_values
    UNION ALL
    SELECT 
        'ecart_gold_jgl' AS column_name,
        max_values.max_jgl,
        (SELECT match_id FROM extremes WHERE ecart_gold_jgl = max_values.max_jgl LIMIT 1),
        (SELECT champ2 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_jgl = max_values.max_jgl LIMIT 1)) AS champ_allie_max,
        (SELECT champ7 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_jgl = max_values.max_jgl LIMIT 1)) AS champ_ennemi_max,
        max_values.min_jgl,
        (SELECT match_id FROM extremes WHERE ecart_gold_jgl = max_values.min_jgl LIMIT 1),
        (SELECT champ2 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_jgl = max_values.min_jgl LIMIT 1)) AS champ_allie_min,
        (SELECT champ7 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_jgl = max_values.min_jgl LIMIT 1)) AS champ_ennemi_min
    FROM 
        max_values
    UNION ALL
    SELECT 
        'ecart_gold_mid' AS column_name,
        max_values.max_mid,
        (SELECT match_id FROM extremes WHERE ecart_gold_mid = max_values.max_mid LIMIT 1),
        (SELECT champ3 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_mid = max_values.max_mid LIMIT 1)) AS champ_allie_max,
        (SELECT champ8 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_mid = max_values.max_mid LIMIT 1)) AS champ_ennemi_max,
        max_values.min_mid,
        (SELECT match_id FROM extremes WHERE ecart_gold_mid = max_values.min_mid LIMIT 1),
        (SELECT champ3 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_mid = max_values.min_mid LIMIT 1)) AS champ_allie_min,
        (SELECT champ8 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_mid = max_values.min_mid LIMIT 1)) AS champ_ennemi_min
    FROM 
        max_values
    UNION ALL
    SELECT 
        'ecart_gold_adc' AS column_name,
        max_values.max_adc,
        (SELECT match_id FROM extremes WHERE ecart_gold_adc = max_values.max_adc LIMIT 1),
        (SELECT champ4 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_adc = max_values.max_adc LIMIT 1)) AS champ_allie_max,
        (SELECT champ9 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_adc = max_values.max_adc LIMIT 1)) AS champ_ennemi_max,
        max_values.min_adc,
        (SELECT match_id FROM extremes WHERE ecart_gold_adc = max_values.min_adc LIMIT 1),
        (SELECT champ4 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_adc = max_values.min_adc LIMIT 1)) AS champ_allie_min,
        (SELECT champ9 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_adc = max_values.min_adc LIMIT 1)) AS champ_ennemi_min
    FROM 
        max_values
    UNION ALL
    SELECT 
        'ecart_gold_supp' AS column_name,
        max_values.max_supp,
        (SELECT match_id FROM extremes WHERE ecart_gold_supp = max_values.max_supp LIMIT 1),
        (SELECT champ5 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_supp = max_values.max_supp LIMIT 1)) AS champ_allie_max,
        (SELECT champ10 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_supp = max_values.max_supp LIMIT 1)) AS champ_ennemi_max,
        max_values.min_supp,
        (SELECT match_id FROM extremes WHERE ecart_gold_supp = max_values.min_supp LIMIT 1),
        (SELECT champ1 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_supp = max_values.min_supp LIMIT 1)) AS champ_allie_min,
        (SELECT champ6 FROM matchs_joueur where match_id =  (SELECT match_id FROM extremes WHERE ecart_gold_supp = max_values.min_supp LIMIT 1)) AS champ_ennemi_min
    FROM 
        max_values;
        '''

        emote_champ_discord = lire_bdd_perso('SELECT * from data_champion', index_col='nom')\
                                                                                    .T\
                                                                                        .to_dict()\
                                                                                            ['icon_identifiant']
        
        df = lire_bdd_perso(req_sql, index_col=None).T 

        embed = interactions.Embed(title=f'Ecart Min/Max en SoloQ :', color=0x00FF00)

        for index, data in df.iterrows():

            match_id1 = data[2]
            match_id2 = data[6]
    

            url1 = f'https://www.leagueofgraphs.com/fr/match/euw/{match_id1[5:]}#participant3'
            url2 = f'https://www.leagueofgraphs.com/fr/match/euw/{match_id2[5:]}#participant3'


            champ_allie_max = data[3]
            champ_ennemi_max = data[4]

            champ_allie_min = data[7]
            champ_ennemi_min = data[8]

            emote_allie_max = emote_champ_discord.get(champ_allie_max.capitalize(), 'inconnu')
            emote_ennemi_max = emote_champ_discord.get(champ_ennemi_max.capitalize(), 'inconnu')

            emote_allie_min = emote_champ_discord.get(champ_allie_min.capitalize(), 'inconnu')
            emote_ennemi_min = emote_champ_discord.get(champ_ennemi_min.capitalize(), 'inconnu')

            

            embed.add_field(name=f'{data[0]} :', value=f'  - max : {data[1]} ([G]({url1})) {emote_allie_max} vs {emote_ennemi_max}\n- min : {data[5]} ([G]({url2})) {emote_allie_min} vs {emote_ennemi_min}', inline=False)

        await ctx.send(embed=embed)



    
    @gold_max_min.autocomplete("riot_id")
    async def autocomplete_gold_min_max(self, ctx: interactions.AutocompleteContext):

        liste_choix = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)

        await ctx.send(choices=liste_choix)

def setup(bot):
    AnalyseLoLSeason(bot)


   