import interactions
from interactions import Extension, listen, Task, IntervalTrigger, slash_command, SlashContext, SlashCommandOption
import pandas as pd
from aiohttp import ClientSession
from fonctions.gestion_bdd import sauvegarde_bdd, lire_bdd_perso, requete_perso_bdd
from fonctions.word import suggestion_word


class LoLProplay(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @listen()
    async def on_startup(self):
        self.update_pro_database.start()

    @Task.create(IntervalTrigger(hours=12))
    async def update_pro_database(self):

        session = ClientSession()
        data = await session.get('https://www.trackingthepros.com/d/list_players?filter_region=ALL&')

        txt = await data.json()

        df_pro = pd.DataFrame(txt['data'])

        df_pro.drop(['DT_RowId', 'name', 'online', 'gameID', 'onStream','onlineNum'], axis=1, inplace=True)

        # NOTE : Prevoir 15m

        df_final = pd.DataFrame(columns=['joueur', 'compte'])

        for name_joueur in df_pro['name_plug']:

            try:
                df_rank = pd.read_html(f'https://www.trackingthepros.com/player/{name_joueur}/')[1][[0]]
                
                df_rank.columns = ['compte']
                
                df_rank['joueur'] = name_joueur 
                
                df_final = pd.concat([df_final, df_rank])
            except:
                # print('erreur', f'{name_joueur}')
                continue

        # filtre

        df_final = df_final[~df_final['compte'].str.contains('Inactive')]

        df_final['region'] = df_final['compte'].str.extract(r'\[(.*?)\]', expand=False) # extrait les regions

        df_final['compte'] = df_final['compte'].str.replace(r'\[.*?\]', '', regex=True) # les supprime des pseudos

        df_final['compte'] = df_final['compte'].apply(lambda x: x[1:] if x.startswith(' ') else x) # laisse un espace vide


        df_pro.rename(columns={'id' : 'index', 'position' : 'role', 'name_plug' : 'plug', 'current_region' : 'current', 'home_region' : 'home', 'highest_lp' : 'rankHighLP', 'highest_rank' : 'rankHighLPNum', "player_accounts" : 'accounts'} , inplace=True)

        # df_pro.set_index('index', inplace=True)

        df_pro = df_pro[['current', 'home', 'role', 'accounts', 'team_plug', 'plug', 'rankHigh', 'rankHighNum', 'rankHighLP', 'rankHighLPNum']]


        # upsert

        df_pro_origin = lire_bdd_perso('''SELECT * from data_proplayers''', index_col='plug').T

        df_pro.set_index('plug', inplace=True)

        df_pro_origin = pd.concat([df_pro_origin[~df_pro_origin.index.isin(df_pro.index)], df_pro])

        df_pro_origin = df_pro_origin.reset_index()[['current', 'home', 'role', 'accounts', 'team_plug', 'plug', 'rankHigh', 'rankHighNum', 'rankHighLP', 'rankHighLPNum']]

        sauvegarde_bdd(df_pro_origin,
                'data_proplayers')
        
        df_final.reset_index(inplace=True, drop=True)

        # upsert

        df_final_origin = lire_bdd_perso('''SELECT * from data_acc_proplayers''', index_col=['joueur', 'compte']).T
        
        df_final.set_index(['joueur', 'compte'], inplace=True)

        df_final_origin = pd.concat([df_final_origin[~df_final_origin.index.isin(df_final.index)], df_final])

        df_final_origin.drop_duplicates(subset=['joueur', 'compte', 'region'], inplace=True)

        df_final_origin.reset_index(inplace=True)


        sauvegarde_bdd(df_final_origin.drop(columns='index'), 'data_acc_proplayers')


    @slash_command(name='lol_pro', description='Pro League of Legends')
    async def lol_pro(self, ctx: SlashContext):
        pass

    @lol_pro.subcommand("update_joueur",
                           sub_cmd_description="Mettre à jour son equipe",
                           options=[
                               SlashCommandOption(name="joueur",
                                                  description="Nom du joueur",
                                                  type=interactions.OptionType.STRING,
                                                  required=True),
                                SlashCommandOption(name="equipe",
                                                  description="Nouvel equipe",
                                                  type=interactions.OptionType.STRING,
                                                  required=True)])
    async def update_joueur(self,
                     ctx: SlashContext,
                     joueur,
                     equipe):

        await ctx.defer(ephemeral=False)             

        nb_row = requete_perso_bdd(f'''UPDATE public.data_proplayers SET team_plug = '{equipe}' where plug = '{joueur}' ''', get_row_affected=True)

        if nb_row > 0:
            await ctx.send(f'Database modifiée. {joueur} rejoint {equipe}')
        else:
            liste_joueur = lire_bdd_perso( '''SELECT plug from public.data_proplayers ''', index_col=None ).T['plug'].to_list()
            suggestion = suggestion_word(joueur, liste_joueur)
            await ctx.send(f'Joueur introuvable. Souhaitais-tu dire : **{suggestion}**')


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
