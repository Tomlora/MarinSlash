
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
        

        ### A verifier car changement de table 
        
        df = lire_bdd_perso('''
            SELECT matchs_autres.*, 
                match_participant.team, match_participant.position, 
                match_participant.tierallie_avg, match_participant.tierennemy_avg, 
                match_participant.divallie_avg, match_participant.divennemy_avg,
                matchs.time, matchs.mode
            FROM matchs_autres
            INNER JOIN match_participant ON match_participant.match_id = matchs_autres.match_id
            LEFT JOIN matchs ON matchs_autres.match_id = matchs.match_id
        ''', index_col=None).T

        df.drop_duplicates(subset=['match_id', 'team'], inplace=True)

        # Garde seulement les ranked avec un tier allié
        df = df[(df['tierallie_avg'] != '') & (df['mode'] == 'RANKED')]

        def get_vision(row):
            pos = int(row['position'])
            if row['team'] == 'allie':
                return float(row[f'vision{pos}'])
            else:
                return float(row[f'vision{pos + 5}'])

        def get_pink(row):
            pos = int(row['position'])
            if row['team'] == 'allie':
                return float(row[f'pink{pos}'])
            else:
                return float(row[f'pink{pos + 5}'])

        df['vision'] = df.apply(get_vision, axis=1)
        df['pink'] = df.apply(get_pink, axis=1)
        df['time'] = df['time'].astype(float)

        # Vision/Pink par minute
        df['vision/min'] = df['vision'] / df['time']
        df['pink/min'] = df['pink'] / df['time']

        # Rôle support = position == '5'
        df_support = df[df['position'] == '5']
        df_no_support = df[df['position'] != '5']

        grouped = df.groupby('tierallie_avg')
        grouped_support = df_support.groupby('tierallie_avg')
        grouped_no_support = df_no_support.groupby('tierallie_avg')

        # Moyennes globales par tier
        vision_avg = grouped['vision'].mean()
        pink_avg = grouped['pink'].mean()
        vision_min = grouped['vision/min'].mean()
        pink_min = grouped['pink/min'].mean()
        time_avg = grouped['time'].mean()

        # Moyennes par rôle
        vision_sans_support = grouped_no_support['vision'].mean()
        vision_support = grouped_support['vision'].mean()
        pink_sans_support = grouped_no_support['pink'].mean()
        pink_support = grouped_support['pink'].mean()

        vision_sans_support_min = grouped_no_support['vision/min'].mean()
        vision_support_min = grouped_support['vision/min'].mean()
        pink_sans_support_min = grouped_no_support['pink/min'].mean()
        pink_support_min = grouped_support['pink/min'].mean()

        # Nombre de parties
        nbgames = grouped['match_id'].nunique()

        df_final = pd.DataFrame({
            'V': vision_avg,
            'P': pink_avg,
            'V/m': vision_min,
            'P/m': pink_min,
            'V(Autre)': vision_sans_support,
            'V(Sup)': vision_support,
            'P(Autres)': pink_sans_support,
            'P(Sup)': pink_support,
            'V(Autre)/m': vision_sans_support_min,
            'V(Sup)/m': vision_support_min,
            'P(Autre)/m': pink_sans_support_min,
            'P(Sup)/m': pink_support_min,
            'T': time_avg,
            'Parties': nbgames
        })

        # Optionnel : trier par ordre de tiers
        ordre_tier = ['IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'EMERALD', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']
        df_final = df_final.reindex(ordre_tier)

        df_final = df_final.round(2)
        df_final.index.name = 'Tier'

        import dataframe_image as dfi
        dfi.export(df_final, 'image.png',
                fontsize=9,
                max_cols=-1,
                max_rows=-1,
                table_conversion="matplotlib")

        content = '**V** : Score de Vision | **P** : Pink | **Autres** : Sans support | **m** : Minutes | **T** : Temps'

        await ctx.send(content=content, files=interactions.File('image.png'))
        os.remove('image.png')

                
def setup(bot):
    AnalyseLoLElo(bot)
