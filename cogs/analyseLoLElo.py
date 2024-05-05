
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, Task, IntervalTrigger, slash_command
import interactions
import pandas as pd
from fonctions.gestion_bdd import lire_bdd_perso
from fonctions.match import fix_temps
import numpy as np
import dataframe_image as dfi
import os

class AnalyseLoLElo(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot


    @slash_command(name='lol_analyse_elo', description='Stats sur des elos')
    async def lol_analyse_elo(self, ctx: SlashContext):
        pass


    @lol_analyse_elo.subcommand("vision",
                           sub_cmd_description="Stats Vision par Elo")
    async def analyse_vision(self,
                     ctx: SlashContext):
        
        df = lire_bdd_perso('''SELECT matchs_autres.*, matchs_joueur.*, matchs.time, matchs.mode from matchs_autres
                            INNER JOIN matchs_joueur on matchs_joueur.match_id = matchs_autres.match_id
                            LEFT JOIN matchs on matchs_autres.match_id = matchs.match_id''', 
                            index_col=None).T   
        
        await ctx.defer(ephemeral=False)     
        

        df = df[(df['tierallie_avg'] != '') & (df['mode'] == 'RANKED')] # on supprime les parties sans rank et on veut only soloq
        
        # stats qu'on veut
        
        df['vision_avg'] = np.round(df[[f'vision{x}' for x in range(1,11)]].mean(axis=1),1)
        df['pink_avg'] = np.round(df[[f'pink{x}' for x in range(1,11)]].mean(axis=1),1)

        df['vision/min'] = df[[f'vision{x}' for x in range(1,11)]].sum(axis=1) / df['time']
        df['pink/min'] = df[[f'pink{x}' for x in range(1,11)]].sum(axis=1) / df['time']

        df['vision_sans_support'] = np.round(df[['vision1', 'vision2', 'vision3', 'vision4', 'vision6', 'vision7', 'vision8', 'vision9']].mean(axis=1),1)
        df['vision_support'] = np.round(df[['vision5', 'vision10']].mean(axis=1),1)

        df['pink_sans_support'] = np.round(df[['pink1', 'pink2', 'pink3', 'pink4', 'pink6', 'pink7', 'pink8', 'pink9']].mean(axis=1),1)
        df['pink_support'] = np.round(df[['pink5', 'pink10']].mean(axis=1),1)

        df['vision_sans_support/min'] = df[['vision1', 'vision2', 'vision3', 'vision4', 'vision6', 'vision7', 'vision8', 'vision9']].sum(axis=1) / df['time']
        df['vision_support/min'] = df[['vision5', 'vision10']].sum(axis=1) / df['time']

        df['pink_sans_support/min'] = df[['pink1', 'pink2', 'pink3', 'pink4', 'pink6', 'pink7', 'pink8', 'pink9']].sum(axis=1) / df['time']
        df['pink_support/min'] = df[['pink5', 'pink10']].sum(axis=1) / df['time']

        ###############################

        df['vision/min'] = np.round(df['vision/min'].astype(float),1)
        df['pink/min'] = np.round(df['pink/min'].astype(float),1)

        df['vision_sans_support/min'] = np.round(df['vision_sans_support/min'].astype(float),1)
        df['vision_support/min'] = np.round(df['vision_support/min'].astype(float),1)

        df['pink_sans_support/min'] = np.round(df['pink_sans_support/min'].astype(float),1)
        df['pink_support/min'] = np.round(df['pink_support/min'].astype(float),1)

        df['time'] = np.round(df['time'].astype(float),2)


        nbgames = df.groupby('tierallie_avg')['match_id'].count().iloc[:,1]

        df_mean = df.groupby('tierallie_avg')[['vision_avg', 'pink_avg',
                                    'vision/min', 'pink/min', 
                                    'vision_sans_support', 'vision_support',
                                    'pink_sans_support', 'pink_support',
                                    'vision_sans_support/min', 'vision_support/min',
                                    'pink_sans_support/min', 'pink_support/min', 'time']].mean()
        
        df_mean['time'] = np.round(df_mean['time'].apply(fix_temps),2)
        df_mean['time'] = np.round(df_mean['time'], 2)
        df_mean['nbgames'] = nbgames.values
        
        columns = ['V', 'P', 'V/m', 'P/m', 'V(Autre)', 'V(Sup)', 'P(Autres)', 'P(Sup)', 'V(Autre)/m', 'V(Sup)/m', 'P(Autre)/m', 'P(Sup)/m', 'T', 'Parties']

        df_mean.columns = columns

        df_mean[columns] = np.round(df_mean[columns], 2)
        df_mean.index.name = 'Tier'
        
        df_mean = df_mean.reindex(['IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'EMERALD', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER'])
        
        dfi.export(df_mean, 'image.png',
                   fontsize=9,
                   max_cols=-1,
                    max_rows=-1,
                    table_conversion="matplotlib")


        content = '**V** : Score de Vision | **P** : Pink | **Autres** : Sans support | **m** : Minutes | **T** : Temps'
        
        await ctx.send(content=content,
                       files=interactions.File('image.png'))

        os.remove('image.png')    
                
def setup(bot):
    AnalyseLoLElo(bot)
