import pandas as pd
import aiohttp
from fonctions.match import get_version, get_champ_list, get_champion_masteries
from fonctions.gestion_bdd import lire_bdd_perso, sauvegarde_bdd
from fonctions.channels_discord import get_embed
from time import sleep
import interactions
from interactions import SlashCommandChoice, SlashCommandOption, Extension, SlashContext, slash_command, listen, Task, TimeTrigger
from datetime import datetime
from dateutil import tz
import plotly_express as px

class Masteries(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @listen()
    async def on_startup(self):

        self.masteries_maj.start()

    @Task.create(TimeTrigger(hour=3, minute=30))
    async def masteries_maj(self):
        '''Chaque jour, à 3h, on actualise les masteries.
        Cette requête est obligatoirement à faire une fois par jour, sur un créneau creux pour éviter de surcharger les requêtes Riot'''


        session = aiohttp.ClientSession()
            # Ceux dont les challenges sont activés, sont maj à chaque game
        df_joueur = lire_bdd_perso('''SELECT id_compte, puuid from tracker where activation= True''', index_col='id_compte').T


        version = await get_version(session)
        current_champ_list = await get_champ_list(session, version)

        df = ''
        timezone=tz.gettz('Europe/Paris')

        for id_compte, data in df_joueur.iterrows():

            data = await get_champion_masteries(session, data['puuid'])

            champ_dict = {}
            for key in current_champ_list['data']:
                row = current_champ_list['data'][key]
                champ_dict[row['key']] = row['id']
                
                
            for champ_data in data:
                champ_data['championId'] = champ_dict[str(champ_data['championId'])] 
            
            if not isinstance(df, pd.DataFrame):    
                df = pd.DataFrame(data)    

                df.drop(columns=['puuid', 'summonerId'], inplace=True)

                df['id'] = id_compte
                
            else:
                
                df2 = pd.DataFrame(data)
                
                df2.drop(columns=['puuid', 'summonerId'], inplace=True)

                df2['id'] = id_compte
                
                df = pd.concat([df, df2])
                
            sleep(5)
            
        df.reset_index(inplace=True, drop=True)

        # Modification de données
        
        df['lastPlayTime'] = df['lastPlayTime'].apply(lambda x : datetime.fromtimestamp(x / 1000,  tz=timezone))
        
        df['championId'] = df['championId'].str.capitalize()
        df['championId'] = df['championId'].str.replace(' ', '')

        sauvegarde_bdd(df, 'data_masteries', 'replace')
        
        print('Masteries sauvegardés !')


    @slash_command(name='lol_maitrise', description='Points de maitrise League of Legends')
    async def lol_maitrise(self, ctx: SlashContext):
        pass    

    @lol_maitrise.subcommand("champion",
                               sub_cmd_description="Points sur un champion",
                   options=[
                       SlashCommandOption(name="champion",
                                          description="Champion",
                                          type=interactions.OptionType.STRING,
                                          required=True)])
    async def maitrise_champion(self,
                                ctx: SlashContext,
                                champion: str):
       
        champion = champion.capitalize().replace(' ', '')
        
        await ctx.defer(ephemeral=False)
        
        
        df = lire_bdd_perso(f'''SELECT data_masteries.*, tracker.index as pseudo from data_masteries 
                    INNER JOIN tracker ON data_masteries.id = tracker.id_compte
                    WHERE "championId" = '{champion}' ''', index_col='index').T

        df.sort_values('championPoints', ascending=False, inplace=True)
        
        fig = px.histogram(df,
                           x='pseudo',
                           y='championPoints',
                           text_auto='.i',
                           color='pseudo',
                           title=f'Points de maitrise sur {champion}')

        fig.update_layout(showlegend=False)
        
        embed, file = get_embed(fig, 'masteries')
        
        await ctx.send(embeds=embed, files=file) 

    @lol_maitrise.subcommand("joueur",
                               sub_cmd_description="Points pour un joueur",
                   options=[
                       SlashCommandOption(name="joueur",
                                          description="Joueur",
                                          type=interactions.OptionType.STRING,
                                          required=True),
                       SlashCommandOption(name='top',
                                          description='top combien ?',
                                          type=interactions.OptionType.INTEGER,
                                          required=False,
                                          min_value=3,
                                          max_value=100)])
    async def maitrise_joueur(self,
                                ctx: SlashContext,
                                joueur: str,
                                top:int=20):
       
        joueur = joueur.lower().replace(' ', '')
        
        await ctx.defer(ephemeral=False)
        df = lire_bdd_perso(f'''SELECT data_masteries.*, tracker.index as pseudo from data_masteries 
                            INNER JOIN tracker ON data_masteries.id = tracker.id_compte
                            WHERE tracker.index = '{joueur}' ''', index_col='index').T

        df.sort_values('championPoints', ascending=False, inplace=True)

        df = df.head(top)
        
        fig = px.histogram(df,
                           x='championId',
                           y='championPoints',
                           text_auto='.i',
                           color='championId',
                           title=f'Points de maitrise pour {joueur} (top {top})')

        fig.update_layout(showlegend=False)
        
        embed, file = get_embed(fig, 'masteries')
        
        await ctx.send(embeds=embed, files=file)
        
    @lol_maitrise.subcommand("best",
                               sub_cmd_description="Best pour un joueur",
                   options=[
                       SlashCommandOption(name="methode",
                                          description="Methode",
                                          type=interactions.OptionType.STRING,
                                          required=True,
                                          choices=[
                                                SlashCommandChoice(name='top_points', value='top_points'),
                                                SlashCommandChoice(name='max par personne', value='max_personne')
                                            ]),
                       SlashCommandOption(name='top',
                                          description='top combien ?',
                                          type=interactions.OptionType.INTEGER,
                                          required=False,
                                          min_value=3,
                                          max_value=100)])
    async def maitrise_best(self,
                                ctx: SlashContext,
                                methode: str,
                                top:int=20):
              
        await ctx.defer(ephemeral=False)

        df = lire_bdd_perso(f'''SELECT data_masteries.*, tracker.index as pseudo from data_masteries 
                            INNER JOIN tracker ON data_masteries.id = tracker.id_compte''', index_col='index').T

        df['championPoints'] = df['championPoints'].astype(int)
        
        if methode == 'top_points':

            df_grp = df.copy()
            df_grp['pseudo'] = df_grp['pseudo'] + "(" + df_grp['championId'] + ")"

            df_grp.sort_values('championPoints', ascending=False, inplace=True)

            df_grp = df_grp.head(top)
            
            title = 'Points de maitrise Classement'

        
        elif methode == 'max_personne':

            df_grp = df.groupby('pseudo', as_index=False)[['championPoints']].max()

            df_grp = df_grp.merge(df[['pseudo', 'championPoints', 'championId']], how='left', on=['pseudo', 'championPoints'])

            df_grp.sort_values('championPoints', ascending=False, inplace=True)

            df_grp['pseudo'] = df_grp['pseudo'] + "(" + df_grp['championId'] + ")"
            
            df_grp = df_grp.head(top)
            
            title = 'Points de maitrise : Record par personne'
            

        fig = px.histogram(df_grp,
                           x='pseudo',
                           y='championPoints',
                           text_auto='.i',
                           color='pseudo',
                           title=title)

        fig.update_layout(showlegend=False)
        
        embed, file = get_embed(fig, 'masteries')
        
        await ctx.send(embeds=embed, files=file)

def setup(bot):
    Masteries(bot)
