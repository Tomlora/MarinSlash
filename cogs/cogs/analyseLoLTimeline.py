
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, Task, IntervalTrigger, slash_command
import interactions
import pandas as pd
from fonctions.gestion_bdd import lire_bdd_perso, get_tag
from fonctions.match import fix_temps
import numpy as np
import dataframe_image as dfi
import os


def fix_temps(duree):
    '''Convertit le temps en secondes en minutes et secondes'''
    minutes = int(duree)
    secondes = int((duree - minutes) * 60)/100
    
    return minutes + secondes



class AnalyseLoLTimeline(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot


    @slash_command(name='lol_analyse_timeline', description='Stats sur des elos')
    async def lol_analyse_timeline(self, ctx: SlashContext):
        pass



    @lol_analyse_timeline.subcommand("morts",
                            sub_cmd_description="Permet d'afficher les timing de la premiere mort",
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
                                            SlashCommandChoice(name='support', value='SUPPORT')])])  
    
    async def analyse_timeline_mort(self, 
                                    ctx : SlashContext,
                                    riot_id,
                                    riot_tag = None,
                                    role='None'):

        riot_id = riot_id.replace(' ', '').lower()

        if riot_tag == None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')
        riot_tag = riot_tag.upper()

        await ctx.defer(ephemeral=False)          

        req = f'''select public.data_timeline_events.match_id, datetime, matchs.role, timestamp from public.data_timeline_events
        INNER JOIN matchs on matchs.match_id = public.data_timeline_events.match_id and matchs.joueur = public.data_timeline_events.riot_id
        INNER JOIN tracker on matchs.joueur = tracker.id_compte
        where tracker.riot_id = '{riot_id}' and tracker.riot_tagline = '{riot_tag}'
          and type = 'DEATHS' 
        and mode = 'RANKED' '''    

        df = lire_bdd_perso(req, index_col=None).T

        if df.empty:
            return await ctx.send('Joueur introuvable ou pas de données')
        
        if role != 'None':
            df = df[df['role'] == role]


        df.sort_values('timestamp', inplace=True)

        df.drop_duplicates('match_id', keep='first', inplace=True)

        # Définir les intervalles (bins)
        bins = [0, 2, 5, 8, 10, 12, 15, 18, 20, float('inf')]

        # Définir les labels pour chaque intervalle
        labels = ['0-2', '2-5', '5-8', '8-10', '10-12', '12-15', '15-18', '18-20', '>20']

        # Ajouter la colonne 'bins' au DataFrame
        df['bins'] = pd.cut(df['timestamp'], bins=bins, labels=labels, right=False)


        moyenne = fix_temps(df['timestamp'].mean())

        palier = df['bins'].value_counts()

        txt = f'Joueur : {riot_id}#{riot_tag} \nMoyenne : {moyenne}\n'
        percent_total = 0

        for index, value in palier.items():
            percent = int((value / palier.sum()) * 100)
            percent_total += percent
            # txt += f'**{index}m** : {value} ({percent}%) | Cumulé : ({percent_total}%)\n'
            txt += f'**{index}m** : {value} ({percent}%) \n'


        await ctx.send(txt)







def setup(bot):
    AnalyseLoLTimeline(bot)
