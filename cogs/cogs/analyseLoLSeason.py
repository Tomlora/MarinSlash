
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, Task, IntervalTrigger, slash_command
import interactions
import pandas as pd
from fonctions.gestion_bdd import lire_bdd_perso
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
                                    name="champion",
                                    description="Champion joué",
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
                                        SlashCommandChoice(name='support', value='SUPPORT')])
                                ])
    async def analyse_champion(self,
                      ctx: SlashContext,
                      riot_id: str,
                      riot_tag:str,
                      mode:str,
                      saison = saison,
                      champion = None,
                      role = None):
        
        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper() 
        
        await ctx.defer(ephemeral=False)     
        
        df = lire_bdd_perso(f'''SELECT matchs_joueur.*, matchs.champion, matchs.role, matchs.victoire from tracker
        INNER JOIN matchs ON tracker.id_compte = matchs.joueur
        INNER JOIN matchs_joueur ON matchs.match_id = matchs_joueur.match_id
        WHERE tracker.riot_id = '{riot_id}'
        AND tracker.riot_tagline = '{riot_tag}'
        AND matchs.season = {saison}
        AND matchs.mode = '{mode}' ''', index_col='match_id').T
        
        if champion != None:
            df = df[df['champion'] == champion.replace(' ', '').capitalize()]
        
        if role != None:
            df = df[df['role'] == role]
        
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
                    name_allie = f'{name_allie} + {match_id}'
                dict_allie[name_allie] = champ_allie
                if name_ennemi in dict_ennemi:
                    name_ennemi = f'{name_ennemi} + {match_id}'
                dict_ennemi[name_ennemi] = champ_ennemi

        def count_champion(dict):
            df_champion = pd.DataFrame.from_dict(dict, orient='index', columns=['champion'])
            df_champion['victoire'] = victory
            df_champion['victoire'] = df_champion['victoire'].astype(int)
            df_champion = df_champion[~df_champion.index.str.contains(f'{riot_id}#{riot_tag.lower()}')]
            df_count = df_champion.groupby('champion').agg(count=('champion', 'count'),
                                                        victory=('victoire', 'sum'))
            df_count.sort_values('count', ascending=False, inplace=True)
            df_count.index = df_count.index.str.capitalize()
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
                txt += f'{emote_champ_discord.get(champion, champion)} Pick **{count}** fois ({pick_percent}%) -> WR : **{victory_percent}%** \n'
            
            embed.add_field(name=f'{mode} PARTIE {part}', value=txt)    
            
            return embed
        
        
        embed_allie_top10 = embedding(df_allie.iloc[:10], 'ALLIE', 1)
        embed_allie_top20 = embedding(df_allie.iloc[10:20], 'ALLIE', 2)
        embed_allie_top30 = embedding(df_allie.iloc[20:30], 'ALLIE', 3)
        embed_ennemi_top10 = embedding(df_ennemi.iloc[:10], 'ENNEMI', 1)
        embed_ennemi_top20 = embedding(df_ennemi.iloc[10:20], 'ENNEMI', 2)
        embed_ennemi_top30 = embedding(df_ennemi.iloc[20:30], 'ENNEMI', 3)
        
        embeds = [embed_allie_top10, embed_allie_top20, embed_allie_top30, embed_ennemi_top10, embed_ennemi_top20, embed_ennemi_top30]
    

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


    @lol_analyse_season.subcommand("lp",
                            sub_cmd_description="Permet d'afficher des statistiques sur ses LP",
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
                                # SlashCommandOption(
                                #     name="mode",
                                #     description="Mode de jeu",
                                #     type=interactions.OptionType.STRING,
                                #     required=True,
                                #     choices=[SlashCommandChoice(name='RANKED', value='RANKED'),
                                #              SlashCommandChoice(name='ARAM', value='ARAM')]),
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
                      riot_tag:str,
                    #   mode:str,
                      saison = saison,
                      split = None,
                      nbgames = None,
                      nbjours = None):
        
        
        if nbjours == None:
            df = lire_bdd_perso(
                    f'''SELECT matchs.id, tracker.riot_id, tracker.riot_tagline, matchs.role, matchs.champion, matchs.match_id, matchs.mode, matchs.season, matchs.split, 
                    matchs.date, matchs.lp, matchs.tier, matchs.rank, matchs.ecart_lp, matchs.victoire, tracker.discord from matchs
                INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                where season = {saison}
                ORDER BY match_id DESC ''', index_col='id').transpose()
        
        else:
            df = lire_bdd_perso(
                    f'''SELECT matchs.id, tracker.riot_id, tracker.riot_tagline, matchs.role, matchs.champion, matchs.match_id, matchs.mode, matchs.season, matchs.split, 
                    matchs.date, matchs.lp, matchs.tier, matchs.rank, matchs.ecart_lp, matchs.victoire, tracker.discord from matchs
                INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                where season = {saison}
                and datetime > '{(datetime.now() - timedelta(days=nbjours)):%Y-%m-%d}'
                ORDER BY match_id DESC ''', index_col='id').transpose()

        await ctx.defer(ephemeral=False)



        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper()
        df = df[(df['riot_id'] == riot_id) & (df['riot_tagline'] == riot_tag)]


        df = df[df['mode'] == 'RANKED']

        if split != None:
            df = df[df['split'] == split]

        if nbgames != None:
            df = df.head(nbgames)



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




        nb_games = df.shape[0]

        gap = 50

        if nb_games < 50:
            gap = 10

        elif nb_games < 100:
            gap = 20
            
        def creation_rank(value):
            return [value + 0, value + 100, value + 200, value + 300]

        # dates =np.linspace(0, 10000, 500)  pd.date_range(start="2023-01-01", end="2023-12-31", periods=500)  # Axe X : de janvier à décembre
        x =  np.arange(gap, nb_games + gap, 1)
        y = np.array(df['points'].tolist())               # Exemple de courbe : y = log(x + 1)

        # Création de la figure
        fig, ax = plt.subplots(figsize=(20, 10))

        # Traçage de la courbe en segments colorés
        # Segment 1 : entre 100 et 2000 (orange)

        # def traçage(min_value, max_value, couleur):
        #     x1 = x[(y >= min_value) & (y <= max_value)]
        #     y1 = y[(y >= min_value) & (y <= max_value)]
        #     ax.plot(x1, y1, color=couleur)

        # traçage(50, dict_points['B'], '#6A5054')
        # traçage(dict_points['B'], dict_points['S'], '#D8A797')
        # traçage(dict_points['S'], dict_points['G'], '#CAD5E8')
        # traçage(dict_points['G'], dict_points['P'], '#DEBF8B')
        # traçage(dict_points['P'], dict_points['E'], '#96E1F5')
        # traçage(dict_points['E'], dict_points['D'], '#7EE3AD')
        # traçage(dict_points['D'], dict_points['M'], '#96E1F5')
        # traçage(dict_points['M'], dict_points['GM'], '#ECCFFC')
        # traçage(dict_points['GM'], dict_points['C'], '#EE9460')
        # traçage(dict_points['C'], 12000, '#72AAC8')


        points = np.array([x, y]).T.reshape(-1, 1, 2)

        segments = np.concatenate([points[:-1], points[1:]], axis=1)

        cmap = ListedColormap(['#6A5054', '#D8A797', '#CAD5E8', '#DEBF8B', '#96E1F5', '#7EE3AD', '#A0E1F0', '#ECCFFC', '#EE9460', '#72AAC8'])
        norm = BoundaryNorm([50, dict_points['B'], dict_points['S'], dict_points['G'], dict_points['P'], dict_points['E'], dict_points['D'], dict_points['M'], dict_points['GM'], dict_points['C'], 12000], cmap.N)
        lc = LineCollection(segments, cmap=cmap, norm=norm)
        lc.set_array(y)
        lc.set_linewidth(2)
        line = ax.add_collection(lc)

        # # Segment 2 : entre 2000 et 5000 (cyan)
        # x2 = x[(y > 2000) & (y <= 10000)]
        # y2 = y[(y > 2000) & (y <= 10000)]
        # ax.plot(x2, y2, color='cyan', label='2000 à 5000')


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
                ax.axhline(y=level, color='#6A5054', linestyle='--', linewidth=0.8)  # Ligne pointillée
                ax.text(gap, level, f'F{liste_order[i]}', color='#6A5054', fontsize=20, va='bottom')

            ax.axhspan(50, dict_points['B'], facecolor='#423437', alpha=0.3)

        if not df[df['points'].between(dict_points['B'], dict_points['S'])].empty:
            for i, level in enumerate(y_levels_bronze):
                ax.axhline(y=level, color='#D8A797', linestyle='--', linewidth=0.8)  # Ligne pointillée
                ax.text(gap, level, f'B{liste_order[i]}', color='#D8A797', fontsize=20, va='bottom')

            ax.axhspan(dict_points['B'], dict_points['S'], facecolor='#96685F', alpha=0.3)

        if not df[df['points'].between(dict_points['S'], dict_points['G'])].empty:
            for i, level in enumerate(y_levels_silver):
                ax.axhline(y=level, color='#CAD5E8', linestyle='--', linewidth=0.8)  # Ligne pointillée
                ax.text(gap, level, f'S{liste_order[i]}', color='#CAD5E8', fontsize=20, va='bottom')

            ax.axhspan(dict_points['S'], dict_points['G'], facecolor='#7C98B1', alpha=0.3)

        if not df[df['points'].between(dict_points['G'], dict_points['P'])].empty:
            for i, level in enumerate(y_levels_gold):
                ax.axhline(y=level, color='#DEBF8B', linestyle='--', linewidth=0.8)  # Ligne pointillée
                ax.text(gap, level, f'G{liste_order[i]}', color='#DEBF8B', fontsize=20, va='bottom')

            ax.axhspan(dict_points['G'], dict_points['P'], facecolor='#9C7A58', alpha=0.3)

        if not df[df['points'].between(dict_points['P'], dict_points['E'])].empty:
            for i, level in enumerate(y_levels_plat):
                ax.axhline(y=level, color='#96E1F5', linestyle='--', linewidth=0.8)  # Ligne pointillée
                ax.text(gap, level, f'P{liste_order[i]}', color='#96E1F5', fontsize=20, va='bottom')

            ax.axhspan(dict_points['P'], dict_points['E'], facecolor='#5A8FB4', alpha=0.3)

        if not df[df['points'].between(dict_points['E'], dict_points['D'])].empty:

            for i, level in enumerate(y_levels_emeraude):
                ax.axhline(y=level, color='#7EE3AD', linestyle='--', linewidth=0.8)  # Ligne pointillée
                ax.text(gap, level, f'E{liste_order[i]}', color='#7EE3AD', fontsize=20, va='bottom')

            ax.axhspan(dict_points['E'], dict_points['D'], facecolor='#4B9A7D', alpha=0.3)

        if not df[df['points'].between(dict_points['D'], dict_points['M'])].empty:

            for i, level in enumerate(y_levels_diamant):
                ax.axhline(y=level, color='#A0E1F0', linestyle='--', linewidth=0.8)  # Ligne pointillée
                ax.text(gap, level, f'D{liste_order[i]}', color='#A0E1F0', fontsize=20, va='bottom')

            ax.axhspan(dict_points['D'], dict_points['M'], facecolor='#5A8DB9', alpha=0.3)

        if not df[df['points'].between(dict_points['M'], dict_points['GM'])].empty:

            for i, level in enumerate(y_levels_master):
                ax.axhline(y=level, color='#ECCFFC', linestyle='--', linewidth=0.8)  # Ligne pointillée
                ax.text(gap, level, f'M', color='#ECCFFC', fontsize=20, va='bottom')

            ax.axhspan(dict_points['M'], dict_points['GM'], facecolor='#B39AC6', alpha=0.3)


        if not df[df['points'].between(dict_points['GM'], dict_points['C'])].empty:

            for i, level in enumerate(y_levels_gm):
                ax.axhline(y=level, color='#EE9460', linestyle='--', linewidth=0.8)  # Ligne pointillée
                ax.text(gap, level, f'GM', color='#EE9460', fontsize=20, va='bottom')

            ax.axhspan(dict_points['GM'], dict_points['C'], facecolor='#D2733F', alpha=0.3)

        if not df[df['points'].between(dict_points['C'], 11000)].empty:
            # for i, level in enumerate(y_levels_chal):
            ax.axhline(y=dict_points['C'], color='#72AAC8', linestyle='--', linewidth=0.8)  # Ligne pointillée
            ax.text(gap, dict_points['C'], f'C', color='#72AAC8', fontsize=20, va='bottom')

            ax.axhspan(dict_points['C'], 11000, facecolor='#4E7A97', alpha=0.3)

            for index, data in df[df['points'] > dict_points['M']].iloc[::10].iterrows():

                plt.annotate(f'{data["lp"]:.0f}', 
                            (index+gap, data['points']), 
                            ha='center', 
                            fontsize=15,
                            color='white')


        ax.set_xlim([gap, nb_games + gap])

        # Trouver le multiple de 400 le plus proche pour le minimum (vers 0)
        min_multiple_400 = np.floor(df[df['points'] > 50]['points'].min() / 400) * 400

        # Trouver le multiple de 400 le plus proche pour le maximum (vers 12000)
        max_multiple_400 = np.ceil(df['points'].max() / 400) * 400


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

        await ctx.send(file=interactions.File('lp.jpg'))

        os.remove('lp.jpg')
  
                
def setup(bot):
    AnalyseLoLSeason(bot)


   