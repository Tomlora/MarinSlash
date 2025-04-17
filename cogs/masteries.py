import pandas as pd
import aiohttp
from fonctions.match import get_version, get_champ_list, get_champion_masteries, emote_champ_discord
from fonctions.gestion_bdd import lire_bdd_perso, sauvegarde_bdd, get_tag
from fonctions.autocomplete import autocomplete_riotid
from fonctions.channels_discord import get_embed
from time import sleep
import interactions
from interactions import SlashCommandChoice, SlashCommandOption, Extension, SlashContext, slash_command, listen, Task, TimeTrigger
from datetime import datetime
from dateutil import tz
import plotly_express as px
from interactions.ext.paginators import Paginator
import ast

async def champion_unique(riot_id, riot_tag):
    df = lire_bdd_perso(f'''SELECT DISTINCT "champion", mode, datetime from matchs WHERE 
                        joueur = (SELECT id_compte from tracker WHERE riot_id = :riot_id and riot_tagline = :riot_tag)''',
                        index_col=None,
                        params={'riot_id' : riot_id,
                                'riot_tag' : riot_tag.upper(),
                                'chest' : False}).T
    return df

async def champion_lastplay(riot_id, riot_tag):
    
    df = lire_bdd_perso(f'''SELECT "championId", "lastPlayTime" from data_masteries WHERE 
                            id = (SELECT id_compte from tracker WHERE riot_id = :riot_id and riot_tagline = :riot_tag)''',
                            index_col=None,
                            params={'riot_id' : riot_id,
                                    'riot_tag' : riot_tag.upper()}).T
        
    df['jour'] = df['lastPlayTime'].dt.day
    df['mois'] = df['lastPlayTime'].dt.month
    df['annee'] = df['lastPlayTime'].dt.year 
        
    return df


async def extraire_variables_imbriquees(df, colonne):
    df[colonne] = [ast.literal_eval(str(item))
                   for index, item in df[colonne].iteritems()]

    df = pd.concat([df.drop([colonne], axis=1),
                   df[colonne].apply(pd.Series)], axis=1)
    return df



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

                df.drop(columns=['puuid'], inplace=True)

                df['id'] = id_compte
                
            else:
                
                df2 = pd.DataFrame(data)
                
                df2.drop(columns=['puuid'], inplace=True)

                df2['id'] = id_compte
                
                df = pd.concat([df, df2])
                
            sleep(5)
            
        df.reset_index(inplace=True, drop=True)

        # Modification de données
        
        df['lastPlayTime'] = df['lastPlayTime'].apply(lambda x : datetime.fromtimestamp(x / 1000,  tz=timezone))
        
        df['championId'] = df['championId'].str.capitalize()
        df['championId'] = df['championId'].str.replace(' ', '')

        df = await extraire_variables_imbriquees(df, 'nextSeasonMilestone')

        if 'rewardConfig' in df.columns:
            df.drop(columns='rewardConfig', inplace=True)

        df = await extraire_variables_imbriquees(df, 'requireGradeCounts')

        df['update'] = datetime.now(timezone)

        sauvegarde_bdd(df, 'data_masteries', 'replace')
        
        print('Masteries sauvegardés !')


    @slash_command(name='lol_maitrise', description='Points de maitrise League of Legends')
    async def lol_maitrise(self, ctx: SlashContext):
        pass    

    @lol_maitrise.subcommand("champion",
                               sub_cmd_description="Maitrise sur un champion",
                   options=[
                       SlashCommandOption(name="champion",
                                          description="Champion",
                                          type=interactions.OptionType.STRING,
                                          required=True),
                        SlashCommandOption(name="affichage",
                                            description="Affichage",
                                            type=interactions.OptionType.STRING,
                                            required=True,
                                            choices=[SlashCommandChoice(name="Points", value='championPoints'),
                                                           SlashCommandChoice(name="Level", value='championLevel')])])
    async def maitrise_champion(self,
                                ctx: SlashContext,
                                champion: str,
                                affichage:str):
       
        champion = champion.capitalize().replace(' ', '')
        
        await ctx.defer(ephemeral=False)
        
        
        df = lire_bdd_perso(f'''SELECT data_masteries.*, tracker.index as pseudo from data_masteries 
                    INNER JOIN tracker ON data_masteries.id = tracker.id_compte
                    WHERE "championId" = '{champion}' ''', index_col='index').T

        df.sort_values(affichage, ascending=False, inplace=True)
        
        fig = px.histogram(df,
                           x='pseudo',
                           y=affichage,
                           text_auto='.i',
                           color='pseudo',
                           title=f'Points de maitrise sur {champion}')

        fig.update_layout(showlegend=False)
        
        embed, file = get_embed(fig, 'masteries')
        
        await ctx.send(embeds=embed, files=file) 

    @lol_maitrise.subcommand("joueur",
                               sub_cmd_description="Points pour un joueur",
                   options=[
                       SlashCommandOption(name="riot_id",
                                          description="Joueur",
                                          type=interactions.OptionType.STRING,
                                          required=True,
                                          autocomplete=True),

                        SlashCommandOption(name="affichage",
                                            description="Affichage",
                                            type=interactions.OptionType.STRING,
                                            required=True,
                                            choices=[SlashCommandChoice(name="Points", value='championPoints'),
                                                           SlashCommandChoice(name="Level", value='championLevel')]),
                        SlashCommandOption(name="riot_tag",
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
                                riot_id: str,
                                affichage : str,
                                riot_tag: str = None,
                                top:int=20):
       
       
       
        riot_id = riot_id.lower().replace(' ', '')

        if riot_tag == None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')
            
        riot_tag = riot_tag.upper()
        
        await ctx.defer(ephemeral=False)
        df = lire_bdd_perso(f'''SELECT data_masteries.*, tracker.index as pseudo from data_masteries 
                            INNER JOIN tracker ON data_masteries.id = tracker.id_compte
                            WHERE tracker.riot_id = '{riot_id}' and tracker.riot_tagline = '{riot_tag}' ''', index_col='index').T

        df.sort_values(affichage, ascending=False, inplace=True)

        df = df.head(top)
        
        fig = px.histogram(df,
                           x='championId',
                           y=affichage,
                           text_auto='.i',
                           color='championId',
                           title=f'Points de maitrise pour {riot_id} (top {top})')

        fig.update_layout(showlegend=False)
        
        embed, file = get_embed(fig, 'masteries')
        
        await ctx.send(embeds=embed, files=file)

    @maitrise_joueur.autocomplete("riot_id")


    async def autocomplete_maitrise(self, ctx: interactions.AutocompleteContext):

        liste_choix = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)

        await ctx.send(choices=liste_choix)
        
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
                        SlashCommandOption(name="affichage",
                                            description="Affichage",
                                            type=interactions.OptionType.STRING,
                                            required=True,
                                            choices=[SlashCommandChoice(name="Points", value='championPoints'),
                                                           SlashCommandChoice(name="Level", value='championLevel')]),
                       SlashCommandOption(name='top',
                                          description='top combien ?',
                                          type=interactions.OptionType.INTEGER,
                                          required=False,
                                          min_value=3,
                                          max_value=100)])
    async def maitrise_best(self,
                                ctx: SlashContext,
                                methode: str,
                                affichage:str,
                                top:int=20):
              
        await ctx.defer(ephemeral=False)

        df = lire_bdd_perso(f'''SELECT data_masteries.*, tracker.index as pseudo from data_masteries 
                            INNER JOIN tracker ON data_masteries.id = tracker.id_compte''', index_col='index').T

        df[affichage] = df[affichage].astype(int)
        
        if methode == 'top_points':

            df_grp = df.copy()
            df_grp['pseudo'] = df_grp['pseudo'] + "(" + df_grp['championId'] + ")"

            df_grp.sort_values(affichage, ascending=False, inplace=True)

            df_grp = df_grp.head(top)
            
            title = 'Points de maitrise Classement'

        
        elif methode == 'max_personne':

            df_grp = df.groupby('pseudo', as_index=False)[[affichage]].max()

            df_grp = df_grp.merge(df[['pseudo', affichage, 'championId']], how='left', on=['pseudo', affichage])

            df_grp.sort_values(affichage, ascending=False, inplace=True)

            df_grp['pseudo'] = df_grp['pseudo'] + "(" + df_grp['championId'] + ")"
            
            df_grp = df_grp.head(top)
            
            title = 'Points de maitrise : Record par personne'
            

        fig = px.histogram(df_grp,
                           x='pseudo',
                           y=affichage,
                           text_auto='.i',
                           color='pseudo',
                           title=title)

        fig.update_layout(showlegend=False)
        
        embed, file = get_embed(fig, 'masteries')
        
        await ctx.send(embeds=embed, files=file)
        
    @slash_command(name="lol_lastplay",
                   description="Champions les moins joués",
                #    default_member_permissions=interactions.Permissions.MANAGE_GUILD,
                   options=[
                       SlashCommandOption(name="riot_id",
                                          description="Nom du joueur",
                                          type=interactions.OptionType.STRING,
                                            required=True,
                                            autocomplete=True),
                       SlashCommandOption(name="riot_tag",
                                          description="Tag",
                                          type=interactions.OptionType.STRING,
                                            required=False)
                       ]
                   )
    async def lastplay(self,
                   ctx: SlashContext,
                   riot_id: str,
                   riot_tag:str=None):

        await ctx.defer(ephemeral=False)
        
        riot_id = riot_id.lower().replace(' ', '')


        if riot_tag == None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')
            
        riot_tag = riot_tag.upper()

        df = await champion_lastplay(riot_id, riot_tag)
        
        df.sort_values('lastPlayTime', inplace=True)
        
        response = ''

        response = ''
        for index, data in df.iterrows():
            response += f'**{emote_champ_discord.get(data["championId"].capitalize(), data["championId"].capitalize())}** : {data["jour"]}/{data["mois"]}/{data["annee"]} \n' 
        
        paginator = Paginator.create_from_string(self.bot, response, page_size=1500, timeout=60)

        paginator.default_title = f'Dernière game jouée pour {riot_id} #{riot_tag}'
        await paginator.send(ctx)
        
        df_champion_unique = await champion_unique(riot_id, riot_tag)
        
        def count_champion_per_year(df, response, response_count, mode, annee):
            df['annee'] = df['datetime'].dt.year
            df = df[df['annee'] == annee]
            df = df[df['mode'] == mode]
            liste_champ = ', '.join(df['champion'].unique().tolist())
            response += f'{mode} ({annee}) :'
            response += liste_champ + "\n"
            
            response_count += f'**{mode}** ({annee}) : {len(df["champion"].unique().tolist())} \n'
            return response, response_count
        
        response = ''
        response_count = 'Champions joués chaque année : \n'

        for annee in [2023, 2024, 2025]:
            for mode in ['RANKED', 'ARAM']:
                response, response_count = count_champion_per_year(df_champion_unique, response, response_count, mode, annee )
        
        del df, df_champion_unique        
        await ctx.send(response_count)

    @lastplay.autocomplete("riot_id")


    async def autocomplete_lastplay(self, ctx: interactions.AutocompleteContext):

        liste_choix = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)

        await ctx.send(choices=liste_choix)
        


        
        
def setup(bot):
    Masteries(bot)
