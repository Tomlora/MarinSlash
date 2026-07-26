import interactions
import pandas as pd
from interactions import Extension, listen, Task, IntervalTrigger, slash_command, SlashContext, SlashCommandOption
from aiohttp import ClientSession
from fonctions.gestion_bdd import sauvegarde_bdd, lire_bdd_perso, requete_perso_bdd
from fonctions.proplay_sources import (
    DEFAULT_PRO_LEAGUES,
    fetch_leaguepedia_players,
    fetch_trackingthepros_accounts,
    fetch_trackingthepros_players,
    merge_proplayer_sources,
)
from fonctions.lolpros import fetch_lolpros_accounts, merge_account_sources
from fonctions.word import suggestion_word
from datetime import datetime
from dateutil import tz


class LoLProplay(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @listen()
    async def on_startup(self):
        self.update_pro_database.start()

    @Task.create(IntervalTrigger(hours=12))
    async def update_pro_database(self):
        if datetime.now().weekday() != 0:  # Que le lundi
            return

        print('Update Database Proplayers...')
        timezone = tz.gettz('Europe/Paris')
        updated_at = datetime.now(timezone)

        async with ClientSession() as session:
            # Leaguepedia est la source roster principale et fonctionne même si TTP est KO.
            df_leaguepedia = await fetch_leaguepedia_players(
                session,
                DEFAULT_PRO_LEAGUES,
            )

            # TrackingThePros n'est plus bloquant : il enrichit les infos et comptes.
            df_tracking = await fetch_trackingthepros_players(session)

            if df_leaguepedia.empty and df_tracking.empty:
                print('Update Database Proplayers annulée : Leaguepedia et TrackingThePros indisponibles.')
                return

            df_pro_origin = lire_bdd_perso(
                '''SELECT * from data_proplayers''',
                index_col='plug',
            ).T

            df_pro = merge_proplayer_sources(
                df_pro_origin,
                df_tracking,
                df_leaguepedia,
                updated_at=updated_at,
            )

            if df_pro.empty:
                print('Update Database Proplayers annulée : fusion vide.')
                return

            # La table joueurs est sauvegardée avant les sources de comptes :
            # une panne LoLPros/TTP ne peut donc plus bloquer la mise à jour roster.
            sauvegarde_bdd(df_pro, 'data_proplayers')
            print(
                f'data_proplayers mise à jour : {len(df_pro)} joueurs '
                f'({len(df_leaguepedia)} Leaguepedia, {len(df_tracking)} TrackingThePros).'
            )

            # Aucun appel Riot ici. Les URLs LoLPros sont résolues via Leaguepedia
            # et TTP reste une deuxième source additive quand il répond.
            df_lolpros_accounts = await fetch_lolpros_accounts(
                session,
                df_leaguepedia['plug'].tolist(),
            )
            if not df_tracking.empty:
                df_ttp_accounts = await fetch_trackingthepros_accounts(
                    session,
                    df_tracking['plug'].tolist(),
                )
            else:
                df_ttp_accounts = pd.DataFrame(columns=['joueur', 'compte', 'region'])

            df_accounts = merge_account_sources(
                df_lolpros_accounts,
                df_ttp_accounts,
            )

            if not df_accounts.empty:
                df_accounts_origin = lire_bdd_perso(
                    '''SELECT * from data_acc_proplayers''',
                    index_col=['joueur', 'compte'],
                ).T

                df_accounts.set_index(['joueur', 'compte'], inplace=True)
                df_accounts_origin = pd.concat([
                    df_accounts_origin[~df_accounts_origin.index.isin(df_accounts.index)],
                    df_accounts,
                ])

                df_accounts_origin.reset_index(inplace=True)
                df_accounts_origin.drop_duplicates(
                    subset=['joueur', 'compte', 'region'],
                    inplace=True,
                )

                sauvegarde_bdd(
                    df_accounts_origin.drop(columns='index', errors='ignore'),
                    'data_acc_proplayers',
                )
                print(
                    f'data_acc_proplayers mise à jour : {len(df_accounts)} comptes '
                    f'({len(df_lolpros_accounts)} LoLPros, {len(df_ttp_accounts)} TrackingThePros).'
                )
            else:
                print('LoLPros et TrackingThePros comptes indisponibles : data_acc_proplayers conservée.')

        print('Update Database Proplayers terminée !')


    @slash_command(name='lol_pro', description='Pro League of Legends')
    async def lol_pro(self, ctx: SlashContext):
        pass

    # @lol_pro.subcommand("update_joueur",
    #                        sub_cmd_description="Mettre à jour son equipe",
    #                        options=[
    #                            SlashCommandOption(name="joueur",
    #                                               description="Nom du joueur",
    #                                               type=interactions.OptionType.STRING,
    #                                               required=True),
    #                             SlashCommandOption(name="equipe",
    #                                               description="Nouvel equipe",
    #                                               type=interactions.OptionType.STRING,
    #                                               required=True)])
    # async def update_joueur(self,
    #                  ctx: SlashContext,
    #                  joueur,
    #                  equipe):

    #     await ctx.defer(ephemeral=False)             

    #     nb_row = requete_perso_bdd(f'''UPDATE public.data_proplayers SET team_plug = '{equipe}' where plug = '{joueur}' ''', get_row_affected=True)

    #     if nb_row > 0:
    #         await ctx.send(f'Database modifiée. {joueur} rejoint {equipe}')
    #     else:
    #         liste_joueur = lire_bdd_perso( '''SELECT plug from public.data_proplayers ''', index_col=None ).T['plug'].to_list()
    #         suggestion = suggestion_word(joueur, liste_joueur)
    #         await ctx.send(f'Joueur introuvable. Souhaitais-tu dire : **{suggestion}**')


    @lol_pro.subcommand("add_compte",
                           sub_cmd_description="Ajouter un compte d'un joueur",
                           options=[
                               SlashCommandOption(name="compte",
                                                  description="Compte du joueur sans tag",
                                                  type=interactions.OptionType.STRING,
                                                  required=True),
                                SlashCommandOption(name="joueur",
                                                  description="Nouvel equipe",
                                                  type=interactions.OptionType.STRING,
                                                  required=True)])
    async def add_compte(self,
                     ctx: SlashContext,
                     compte,
                     joueur):
        
        await ctx.defer(ephemeral=False)
        
        df = lire_bdd_perso( '''SELECT plug from public.data_proplayers ''', index_col=None ).T
        df_index = lire_bdd_perso( '''SELECT index from public.data_acc_proplayers ''', index_col=None ).T
        index = df_index['index'].max()
        liste_joueur = df['plug'].to_list()

        if joueur in liste_joueur:
            requete_perso_bdd('''INSERT INTO public.data_acc_proplayers(
                                index, joueur, compte, region)
                                VALUES (:index, :joueur, :compte, 'EUW') ''',
                                dict_params={'index' : index + 1,
                                             'joueur' : joueur,
                                             'compte' : compte})
            
            await ctx.send('Ajouté')
        
        else:
            suggestion = suggestion_word(joueur, liste_joueur)
            await ctx.send(f'Joueur introuvable. Souhaitais-tu dire : **{suggestion}**')


    @lol_pro.subcommand("add_joueur",
                           sub_cmd_description="Ajouter un nouveau joueur",
                           options=[
                               SlashCommandOption(name="joueur",
                                                  description="Joueur",
                                                  type=interactions.OptionType.STRING,
                                                  required=True),
                                SlashCommandOption(name="team",
                                                  description="Son equipe",
                                                  type=interactions.OptionType.STRING,
                                                  required=True),
                                SlashCommandOption(name="compte",
                                                  description="Son compte",
                                                  type=interactions.OptionType.STRING,
                                                  required=True), 
                                SlashCommandOption(name="role",
                                                  description="Son role",
                                                  type=interactions.OptionType.STRING,
                                                  required=True)])
    async def add_joueur(self,
                     ctx: SlashContext,
                     joueur,
                     team,
                     compte,
                     role):
        

        await ctx.defer(ephemeral=False)
        df = lire_bdd_perso( '''SELECT index, plug from public.data_proplayers ''', index_col=None ).T
        index = df['index'].max()
        liste_joueur = df['plug'].to_list()

        if joueur in liste_joueur:
            await ctx.send('Joueur déjà présent')
                   
        else:
            requete_perso_bdd('''INSERT INTO public.data_proplayers(
                                index, current, home, role, accounts, team_plug, plug, "rankHigh", "rankHighNum", "rankHighLP", "rankHighLPNum")
                                VALUES (:index, 'None', 'None', :role, 1, :team, :joueur, 'Challenger', 999999, 999999, 999999); ''',
                                dict_params={'index' : index + 1,
                                             'role' : role,
                                             'joueur' : joueur,
                                             'team' : team})
            
            requete_perso_bdd('''INSERT INTO public.data_acc_proplayers(
                                index, joueur, compte, region)
                                VALUES (:index, :joueur, :compte, 'EUW') ''',
                                dict_params={'index' : index + 1,
                                             'joueur' : joueur,
                                             'compte' : compte})
            
            await ctx.send('Ajouté')

    @lol_pro.subcommand("search",
                           sub_cmd_description="Chercher un joueur",
                           options=[
                               SlashCommandOption(name="joueur",
                                                  description="Joueur",
                                                  type=interactions.OptionType.STRING,
                                                  required=True)])
    async def search_joueur(self,
                     ctx: SlashContext,
                     joueur):
        

        await ctx.defer(ephemeral=False)
        df_joueur = lire_bdd_perso( f'''SELECT team_plug, plug, role from public.data_proplayers where plug like '%{joueur}%' ''', index_col=None ).T
        df_compte = lire_bdd_perso( f'''SELECT compte from public.data_acc_proplayers where region = 'EUW' and joueur like '%{joueur}%' ''', index_col=None ).T.drop_duplicates()

        if df_joueur.empty:
            await ctx.send('Joueur introuvable')
        
        else:
            txt = 'Joueurs trouvés : \n'

            for index, data in df_joueur.iterrows():
                txt += f'{data["plug"]} ({data["team_plug"]}) : {data["role"]}  \n'

            txt += '\nComptes trouvés : \n'

            for index, data in df_compte.iterrows():
                if index % 5 == 0:
                    txt += '\n'
                txt += f' {data["compte"]} |'


            await ctx.send(txt)
                   

    
    

def setup(bot):
    LoLProplay(bot)
