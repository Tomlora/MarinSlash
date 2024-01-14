
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, Task, IntervalTrigger, slash_command
import interactions
import pandas as pd
from fonctions.gestion_bdd import lire_bdd_perso
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
        

        df = df[df['tierallie_avg'] != ''] # on supprime les parties sans rank
        df = df[df['mode'] == 'RANKED'] # only SoloQ
        
        # stats qu'on veut
        
        df['vision_avg'] = df[[f'vision{x}' for x in range(1,11)]].mean(axis=1)
        df['pink_avg'] = df[[f'pink{x}' for x in range(1,11)]].mean(axis=1)

        df['vision/min'] = df[[f'vision{x}' for x in range(1,11)]].sum(axis=1) / df['time']
        df['pink/min'] = df[[f'pink{x}' for x in range(1,11)]].sum(axis=1) / df['time']

        df['vision_sans_support'] = df[['vision1', 'vision2', 'vision3', 'vision4', 'vision6', 'vision7', 'vision8', 'vision9']].mean(axis=1)
        df['vision_support'] = df[['vision5', 'vision10']].mean(axis=1)

        df['pink_sans_support'] = df[['pink1', 'pink2', 'pink3', 'pink4', 'pink6', 'pink7', 'pink8', 'pink9']].mean(axis=1)
        df['pink_support'] = df[['pink5', 'pink10']].mean(axis=1)

        df['vision_sans_support/min'] = df[['vision1', 'vision2', 'vision3', 'vision4', 'vision6', 'vision7', 'vision8', 'vision9']].sum(axis=1) / df['time']
        df['vision_support/min'] = df[['vision5', 'vision10']].sum(axis=1) / df['time']

        df['pink_sans_support/min'] = df[['pink1', 'pink2', 'pink3', 'pink4', 'pink6', 'pink7', 'pink8', 'pink9']].sum(axis=1) / df['time']
        df['pink_support/min'] = df[['pink5', 'pink10']].sum(axis=1) / df['time']

        ###############################

        df['vision/min'] = np.round(df['vision/min'].astype(float),2)
        df['pink/min'] = np.round(df['pink/min'].astype(float),2)

        df['vision_sans_support/min'] = np.round(df['vision_sans_support/min'].astype(float),2)
        df['vision_support/min'] = np.round(df['vision_support/min'].astype(float),2)

        df['pink_sans_support/min'] = np.round(df['pink_sans_support/min'].astype(float),2)
        df['pink_support/min'] = np.round(df['pink_support/min'].astype(float),2)

        df['time'] = np.round(df['time'].astype(float),2)


        nbgames = df.groupby('tierallie_avg')['match_id'].count().iloc[:,1]

        df_mean = df.groupby('tierallie_avg')[['vision_avg', 'pink_avg',
                                    'vision/min', 'pink/min', 
                                    'vision_sans_support', 'vision_support',
                                    'pink_sans_support', 'pink_support',
                                    'vision_sans_support/min', 'vision_support/min',
                                    'pink_sans_support/min', 'pink_support/min', 'time']].mean()

        df_mean['nbgames'] = nbgames.values
        
        dfi.export(df_mean, 'image.png', max_cols=-1,
                            max_rows=-1, table_conversion="matplotlib")


        await ctx.send(files=interactions.File('image.png'))

        os.remove('image.png')    
                
def setup(bot):
    AnalyseLoLElo(bot)
