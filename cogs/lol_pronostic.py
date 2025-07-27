
import interactions
from interactions import Extension, listen, Task, IntervalTrigger, slash_command, SlashCommandOption, SlashCommandChoice, SlashContext, ModalContext, modal_callback
from fonctions.gestion_bdd import sauvegarde_bdd, lire_bdd_perso, requete_perso_bdd
from aiohttp import ClientSession
import pandas as pd

async def generation_modal_pronostic(ctx : SlashContext):

        df = lire_bdd_perso(f'''
                             With info_joueur as (select championnat1, championnat2 from pronostic_joueurs where joueur = {int(ctx.author_id)} )
                            
                            
                            SELECT * from calendrier_pro_lol
                            WHERE "DateTime UTC" >= '2025-01-01'
                            and "Winner" is null
                            and ("Ligue" in (select championnat1 from info_joueur)
                                or "Ligue" in (select championnat2 from info_joueur)) ''', index_col=None).T       

        # await ctx.defer()

        df['DateTime UTC'] = pd.to_datetime(df['DateTime UTC'])



        df['Semaine'] = df['DateTime UTC'].dt.isocalendar().week

        df = df[df['Semaine'] == df['Semaine'].min()]

        dict_replace = {'Rogue (European Team)' : 'Rogue',
                        'Team Heretics' : 'Heretics',
                        'Team Vitality' : 'Vitality',
                        'SK Gaming' : 'SK G',
                        'G2 Esports' : 'G2',
                        'Fnatic' : 'FNC',
                        'Karmine Corp' : 'KC'}




        df['Team1'] = df['Team1'].replace(dict_replace)

        df['Team2'] = df['Team2'].replace(dict_replace)

        modals = []

        # Créer les modals par lots de 5 add_components
        for batch_index in range(0, len(df), 5):
            my_modal = interactions.Modal(
                title=f"My Modal {batch_index // 5 + 1}",  # Titre pour identifier chaque modal
                custom_id=f"modal_pronostic{batch_index // 5}"
            )

            # print(f"modal_pronostic{batch_index // 5}")

            for i, (team1, team2, date) in enumerate(
                    zip(df['Team1'][batch_index:batch_index + 5],
                        df['Team2'][batch_index:batch_index + 5],
                        df['DateTime UTC'][batch_index:batch_index + 5])):
                
                jour = date.day_name()
                label = f"{team1} vs {team2} ({jour})"
                custom_id = f"text_pronostic{batch_index + i}"

                # print(custom_id)
                my_modal.add_components(
                    interactions.ShortText(label=label, custom_id=custom_id)
                )

            modals.append(my_modal)

        return modals

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
    
    async def maj(self,
                ctx: SlashContext):
        
        session = ClientSession()
        
        await ctx.defer()

        liste_matchs = []

        liste_championnat = ['LoL EMEA Championship', 'La Ligue Française', 'League of Legends Championship Series', 'LTA North', 'LTA South', 'LoL Champions Korea'] #https://lol.fandom.com/wiki/Metadata:Leagues

        for championnat in liste_championnat:

            params = {
                'action' : "cargoquery",
                'tables' : "MatchSchedule, Tournaments",
                'fields' : "Tournaments.Name, MatchSchedule.DateTime_UTC, MatchSchedule.Team1, MatchSchedule.Team2, MatchSchedule.Winner",
                'where' : f"MatchSchedule.DateTime_UTC >= '2024-01-01 00:00:00' and Tournaments.League in ('{championnat}')",  # Results after Aug 1, 2019
                'join_on' : "MatchSchedule.OverviewPage=Tournaments.OverviewPage",
                'format' : "json",
                'limit' : "2000"}   

            response = await session.get(self.url_api, params=params)
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
            elif 'LCK' in x:
                return 'LCK'
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

            # df_filter = df_filter[df_filter['Semaine'] == df_filter['Semaine'].min()]

            txt += f'{df_filter.iloc[0]["Ligue"]} : \n '

            for index, data in df_filter.iterrows():
                team1 = data['Team1']
                team2 = data['Team2']
                date_match = data['DateTime UTC']
                txt += f'{date_match} - {team1} vs {team2}\n' 

        await ctx.send(txt)


    @competition_lol.subcommand('inscription',
                                sub_cmd_description='inscription aux pronostics',
                                options=[
        SlashCommandOption(
            name="championnat1",
            description="Premier championnat à parier",
            type=interactions.OptionType.STRING,
            required=True, choices=[
                SlashCommandChoice(name='LFL', value='LFL'),
                SlashCommandChoice(name='LEC', value='LEC'),
                SlashCommandChoice(name='LTA', value='LTA')]),
        SlashCommandOption(name="championnat2",
            description="2eme championnat à parier",
            type=interactions.OptionType.STRING,
            required=True, choices=[
                SlashCommandChoice(name='LFL', value='LFL'),
                SlashCommandChoice(name='LEC', value='LEC'),
                SlashCommandChoice(name='LTA', value='LTA')])])
    
    async def inscription_pronostic(self,
                                    ctx:SlashContext,
                                    championnat1,
                                    championnat2):
        
    
        await ctx.defer()

        if championnat1 == championnat2:
            return await ctx.send('Tu dois choisir 2 championnats différents')
        

        df = pd.DataFrame([{'joueur' : int(ctx.author_id),
                           'championnat1' : championnat1,
                           'championnat2' : championnat2}])
        

        sauvegarde_bdd(df, 'pronostic_joueurs', 'append', index=False)
        
        
        await ctx.send('Inscription terminée')




    @competition_lol.subcommand('pronostic',
                                sub_cmd_description='Pronostic')
    
    async def do_pronostic(self,
                            ctx:SlashContext):
        
        
        modals = await generation_modal_pronostic(ctx)

        await ctx.send_modal(modal=modals[0])
        modal_ctx: interactions.ModalContext = await ctx.bot.wait_for_modal(modals[0])

        # # extract the answers from the responses dictionary
        # short_text = modal_ctx.responses["short_text"]
        # long_text = modal_ctx.responses["long_text"]

        # await modal_ctx.send(f"Ok", ephemeral=False)    


    @modal_callback("modal_pronostic0")
    async def on_modal_answer(self, ctx : ModalContext, text_pronostic0, text_pronostic1, text_pronostic2, text_pronostic3, text_pronostic4):
        # await ctx.send(f'Ok : Tu as choisi {text_pronostic0} ')

        button_1 = interactions.Button(
            style=interactions.ButtonStyle.PRIMARY,
            label="Pronostics suivants",
            custom_id="button_1")

        await ctx.send(f'Tes votes sont **{text_pronostic0}** / **{text_pronostic1}** / **{text_pronostic2}** / **{text_pronostic3}** / **{text_pronostic4}**. Tu peux passer à la suite', components=button_1, ephemeral=True)

    
    @interactions.component_callback('button_1')
    async def button_click_handler(self, ctx : interactions.ComponentContext):
        modals = await generation_modal_pronostic(ctx)

        if len(modals) > 1:
            await ctx.send_modal(modals[1])
        
        else:
            await ctx.send('Tes votes sont validés')

        await ctx.edit(ctx.message, components=[])

        if len(modals) > 1:
            modal_ctx: interactions.ModalContext = await ctx.bot.wait_for_modal(modals[1])

    @modal_callback("modal_pronostic1")
    async def on_modal_answer2(self, ctx : ModalContext, text_pronostic5, text_pronostic6, text_pronostic7, text_pronostic8, text_pronostic9):
        # await ctx.send(f'Ok : Tu as choisi {text_pronostic0} ')

        button_2 = interactions.Button(
            style=interactions.ButtonStyle.GREEN,
            label="Pronostics suivants (2)",
            custom_id="button_2")
        await ctx.send(f'Tes votes sont **{text_pronostic5}** / **{text_pronostic6}** / **{text_pronostic7}** / **{text_pronostic8}** / **{text_pronostic9}**. Tu peux passer à la suite', components=button_2, ephemeral=True)

    
    @interactions.component_callback('button_2')
    async def button_click_handler2(self, ctx : interactions.ComponentContext):
        modals = await generation_modal_pronostic(ctx)

        if len(modals) > 2:
            await ctx.send_modal(modals[2])
        
        else:
            await ctx.send('Tes votes sont validés', ephemeral=True)

        await ctx.edit(ctx.message, components=[])

        if len(modals) > 2:
            modal_ctx: interactions.ModalContext = await ctx.bot.wait_for_modal(modals[2])





def setup(bot):
    LolPronostic(bot)
