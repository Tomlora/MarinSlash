
import interactions
from interactions import Extension, listen, Task, IntervalTrigger, slash_command, SlashCommandOption, SlashCommandChoice, SlashContext
from fonctions.gestion_bdd import sauvegarde_bdd, lire_bdd_perso
from aiohttp import ClientSession
import pandas as pd


class LolPronostic(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self.url_api = "https://lol.fandom.com/api.php"

## Choisir 2 compet début d'année et ne peut plus changer

    @slash_command(name='config_competition_lol',
                   description='Competition lol',
                   default_member_permissions=interactions.Permissions.ADMINISTRATOR)
    async def config_competition_lol(self, ctx: SlashContext):
        pass    

    @config_competition_lol.subcommand("maj",
                               sub_cmd_description="Met à jour le calendrier des matchs")
    
    async def maitrise_champion(self,
                                ctx: SlashContext):
        
        session = ClientSession()
        
        await ctx.defer()

        liste_matchs = []

        liste_championnat = ['LoL EMEA Championship', 'La Ligue Française', 'League of Legends Championship Series', 'LTA North', 'LTA South']

        for championnat in liste_championnat:

            params = {
                'action' : "cargoquery",
                'tables' : "MatchSchedule, Tournaments",
                'fields' : "Tournaments.Name, MatchSchedule.DateTime_UTC, MatchSchedule.Team1, MatchSchedule.Team2, MatchSchedule.Winner",
                'where' : f"MatchSchedule.DateTime_UTC >= '2024-01-01 00:00:00' and Tournaments.League in ('{championnat}')",  # Results after Aug 1, 2019
                'join_on' : "MatchSchedule.OverviewPage=Tournaments.OverviewPage",
                'format' : "json",
                'limit' : "2000"}   

            response = await session.get(self.url, params=params)
            data = await response.json()

            data = data['cargoquery']

            # Transformation des données pour obtenir une liste de dictionnaires
            cleaned_data = [entry['title'] for entry in data]

            # Création du DataFrame à partir des données nettoyées
            df = pd.DataFrame(cleaned_data)

            # Optionnel : Renommer les colonnes pour un meilleur affichage
            # df.columns = ['Joueur', 'Nom', 'Pays', 'Rôle', 'Ligue', 'Équipe']

            liste_matchs.append(df)


        df_matchs = pd.concat(liste_matchs)

        if 'DateTime UTC__precision' in df_matchs.columns:
            df_matchs.drop(columns=['DateTime UTC__precision'], inplace=True)

        df_matchs.rename(columns={'Name' : 'Competition'}, inplace=True)

        def detection_championnat(x):

            if 'LEC' in x:
                return 'LEC'
            elif 'LFL' in x:
                return 'LFL'
            elif 'LTA' in x:
                return 'LTA'
            elif 'LCS' in x:
                return 'LCS'
            else:
                return None
            

        df_matchs['Ligue'] = df_matchs['Competition'].apply(detection_championnat)

        df_matchs.reset_index(inplace=True, drop=True)

        sauvegarde_bdd(df_matchs, 'calendrier_pro_lol', index=False)


        await ctx.send(f'Calendrier des matchs à jour pour {liste_championnat}')

    @slash_command(name='competition_lol',
                   description='Competition lol')
    async def competition_lol(self, ctx: SlashContext):
        pass    
    

    @competition_lol.subcommand("calendrier",
                               sub_cmd_description="Prochaine semaine de compétition")
    
    async def maitrise_champion(self,
                                ctx: SlashContext):
        
        df = lire_bdd_perso('''SELECT * from calendrier_pro_lol
                            WHERE "DateTime UTC" >= '2025-01-01'
                            and "Winner" is null ''', index_col=None).T       

        await ctx.defer()

        df['DateTime UTC'] = pd.to_datetime(df['DateTime UTC'])

        df['Semaine'] = df['DateTime UTC'].dt.isocalendar().week

        df = df[df['Semaine'] == df['Semaine'].min()]

        txt = ''

        for competition in df['Competition'].unique():
            df_filter = df[df['Competition'] == competition]

            txt += f'{df_filter.iloc[0]["Ligue"]} \n :'

            for index, data in df_filter.iterrows():
                team1 = data['Team1']
                team2 = data['Team2']
                date_match = data['DateTime UTC']
                txt += f'{date_match} - {team1} vs {team2}' 

        await ctx.send(txt)
def setup(bot):
    LolPronostic(bot)
