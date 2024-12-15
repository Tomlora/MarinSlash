import sys
import aiohttp
import pandas as pd
import warnings
import interactions
from interactions import SlashCommandOption, Extension, SlashContext, slash_command
from fonctions.params import saison
from fonctions.channels_discord import verif_module
from fonctions.permissions import isOwner_slash
import traceback
import psycopg2.errors
from fonctions.gestion_bdd import requete_perso_bdd, lire_bdd_perso, get_tag
from fonctions.match import getId_with_puuid, get_summonerinfo_by_puuid, get_summoner_by_riot_id




warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'


class LolAccount(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot



    @slash_command(name='lol_compte', description='Gère ton compte League of Legends')
    async def lol_compte(self, ctx: SlashContext):
        pass

    @lol_compte.subcommand("add",
                           sub_cmd_description="Ajoute le joueur au suivi",
                           options=[
                               SlashCommandOption(name="riot_id",
                                                  description="Nom du joueur",
                                                  type=interactions.OptionType.STRING,
                                                  required=True),
                                SlashCommandOption(name="riot_tag",
                                                  description="Tag",
                                                  type=interactions.OptionType.STRING,
                                                  required=True)])
    async def loladd(self,
                     ctx: SlashContext,
                     riot_id,
                     riot_tag):

        discord_id = int(ctx.author.id)
        df_banned = lire_bdd_perso(f'''SELECT discord, banned from tracker WHERE discord = '{discord_id}' and banned = true''', index_col=None)
        
        try:
            if verif_module('league_ranked', int(ctx.guild.id)) and df_banned.empty:
                riot_id = riot_id.lower().replace(' ', '')
                riot_tag = riot_tag.upper()
                session = aiohttp.ClientSession()
                me = await get_summoner_by_riot_id(session, riot_id, riot_tag)
                puuid = me['puuid']
                info_account = await get_summonerinfo_by_puuid(puuid, session)
                requete_perso_bdd(f'''
                                INSERT INTO tracker(index, id, discord, server_id, puuid, riot_id, riot_tagline, id_league) VALUES (:riot_id, :id, :discord, :guilde, :puuid, :riot_id, :riot_tagline, :id_league); 
                                ''',
                                  {'riot_id' : riot_id,
                                    'id': await getId_with_puuid(puuid, session),
                                   'discord': int(ctx.author.id),
                                   'guilde': int(ctx.guild.id),
                                   'puuid': puuid,
                                   'riot_id' : riot_id,
                                   'riot_tagline' : riot_tag,
                                   'id_league' : info_account['id']})
                
                requete_perso_bdd(f'''
                                INSERT INTO suivi_s{saison}(
                                index, wins, losses, "LP", tier, rank, serie, wins_jour, losses_jour, "LP_jour", tier_jour, rank_jour)
                                VALUES ( (SELECT id_compte from tracker where riot_id = '{riot_id}' and riot_tagline = '{riot_tag}' ), 0, 0, 0, 'Non-classe', 0, 0, 0, 0, 0, 'Non-classe', 0);
                                                       
                                INSERT INTO ranked_aram_s{saison}(
                                index, wins, losses, lp, games, k, d, a, activation, rank, serie, wins_jour, losses_jour, lp_jour, rank_jour)
                                VALUES ( (SELECT id_compte from tracker where riot_id = '{riot_id}' and riot_tagline = '{riot_tag}'), 0, 0, 0, 0, 0, 0, 0, True, 'IRON', 0, 0, 0, 0, 'IRON'); ''')

                await ctx.send(f"{riot_id} #{riot_tag} a été ajouté avec succès au live-feed!")
                await session.close()
            else:
                await ctx.send("Module désactivé pour ce serveur ou tu n'as pas l'autorisation")
        except psycopg2.errors.CardinalityViolation:
            await ctx.send('Ce compte est déjà inscrit')
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
            traceback_msg = ''.join(traceback_details)
            print(traceback_msg)
            await ctx.send("Oops! Ce joueur n'existe pas ou n'a pas joué depuis très longtemps.")
            

    @lol_compte.subcommand('mes_parametres',
                           sub_cmd_description='Affiche les paramètres du tracker pour mes comptes')
    async def tracker_mes_parametres(self,
                                     ctx: SlashContext):

        df = lire_bdd_perso(
            f'''SELECT index, activation, spec_tracker, challenges, insights, server_id, nb_challenges, affichage, riot_id, riot_tagline, save_records FROM tracker WHERE discord = '{int(ctx.author.id)}' and banned = false ''').transpose()

        await ctx.defer(ephemeral=True)
        if df.empty:
            await ctx.send("Tu n'as pas encore ajouté de compte ou tu es banni", ephemeral=True)
        else:
            txt = f'{df.shape[0]} comptes :'
            for joueur, data in df.iterrows():
                guild = await self.bot.fetch_guild(data['server_id'])

                if data['affichage'] == 1:
                    affichage = 'mode classique'
                elif data['affichage'] == 2:
                    affichage = 'mode beta'
                txt += f'\n**{data["riot_id"]} #{data["riot_tagline"]}** ({guild.name}): Tracking : **{data["activation"]}** ({affichage})  | Spectateur tracker : **{data["spec_tracker"]}** | Challenges : **{data["challenges"]}** (Affiché : {data["nb_challenges"]}) | Insights : **{data["insights"]}** | Records : **{data["save_records"]}**'

            await ctx.send(txt, ephemeral=True)

        # Y a-t-il des challenges exclus ?

        df_exclusion = lire_bdd_perso(f'''SELECT challenge_exclusion.*, challenges.name, tracker.riot_id from challenge_exclusion
                            LEFT join tracker on challenge_exclusion.index = tracker.id_compte
                            INNER join challenges on challenge_exclusion."challengeId" = challenges."challengeId"
                            WHERE tracker.discord = '{int(ctx.author.id)}' or challenge_exclusion.index = -1 ''', index_col='id').transpose()

        if df_exclusion.empty:
            await ctx.send("Tu n'as aucun challenge exclu", ephemeral=True)
        else:
            df_exclusion.sort_values('index', inplace=True)
            df_exclusion['riot_id'].fillna('TOUS', inplace=True)
            txt_exclusion = ''.join(
                f'\n- {data["riot_id"]} : **{data["name"]}** '
                for row, data in df_exclusion.iterrows()
            )
            await ctx.send(f'Challenges exclus : {txt_exclusion}', ephemeral=True)

    @lol_compte.subcommand('modifier_parametres',
                           sub_cmd_description='Activation/Désactivation du tracker',
                           options=[
                               SlashCommandOption(name='riot_id',
                                                  description="nom ingame",
                                                  type=interactions.OptionType.STRING,
                                                  required=True),
                               SlashCommandOption(name='riot_tag',
                                                  description="tag",
                                                  type=interactions.OptionType.STRING,
                                                  required=False),
                               SlashCommandOption(name="tracker_fin",
                                                  description="Tracker qui affiche le recap de la game en fin de partie",
                                                  type=interactions.OptionType.BOOLEAN,
                                                  required=False),
                               SlashCommandOption(name="tracker_debut",
                                                  description="Tracker en début de partie",
                                                  type=interactions.OptionType.BOOLEAN,
                                                  required=False),
                               SlashCommandOption(name="tracker_challenges",
                                                  description="Tracker challenges",
                                                  type=interactions.OptionType.BOOLEAN,
                                                  required=False),
                               SlashCommandOption(name='ranked_aram',
                                                   description='Ranked en aram',
                                                   type=interactions.OptionType.BOOLEAN,
                                                   required=False),
                               SlashCommandOption(name='nb_challenges',
                                                  description='Nombre de challenges à afficher dans le recap (entre 1 et 20)',
                                                  type=interactions.OptionType.INTEGER,
                                                  required=False,
                                                  min_value=1,
                                                  max_value=20),
                               SlashCommandOption(name="insights",
                                                  description="Insights dans le recap",
                                                  type=interactions.OptionType.BOOLEAN,
                                                  required=False),
                                SlashCommandOption(name="records",
                                                  description="Prendre en compte dans les records",
                                                  type=interactions.OptionType.BOOLEAN,
                                                  required=False)])
    async def tracker_config(self,
                             ctx: SlashContext,
                             riot_id: str,
                             riot_tag: str = None,
                             tracker_fin: bool = None,
                             tracker_debut: bool = None,
                             tracker_challenges: bool = None,
                             ranked_aram: bool = None,
                             insights: bool = None,
                             nb_challenges: int = None,
                             records: bool = None):
        

        if riot_tag == None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')

        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper()

        await ctx.defer(ephemeral=False)

        try:
            discord_id = int(lire_bdd_perso(f"SELECT discord from public.tracker where riot_id = '{riot_id}' and riot_tagline = '{riot_tag}' ", index_col=None).iloc[0].values[0])
        except:
            return await ctx.send('Erreur : Ce compte est introuvable')

        if isOwner_slash(ctx) or discord_id == int(ctx.author.id):

            if tracker_fin != None:

                nb_row = requete_perso_bdd('UPDATE tracker SET activation = :activation WHERE riot_id = :riot_id and riot_tagline = :riot_tag ', {
                    'activation': tracker_fin, 'riot_id': riot_id, 'riot_tag' : riot_tag}, get_row_affected=True)
                if nb_row > 0:
                    if tracker_fin:
                        await ctx.send('Tracker fin de game activé !')
                    else:
                        await ctx.send('Tracker fin de game désactivé !')
                else:
                    await ctx.send('Joueur introuvable')

            if tracker_debut != None:

                nb_row = requete_perso_bdd('UPDATE tracker SET spec_tracker = :activation WHERE riot_id = :riot_id and riot_tagline = :riot_tag', {
                    'activation': tracker_debut, 'riot_id': riot_id, 'riot_tag' : riot_tag}, get_row_affected=True)
                if nb_row > 0:
                    if tracker_debut:
                        await ctx.send('Tracker debut de game activé !')
                    else:
                        await ctx.send('Tracker debut de game désactivé !')
                else:
                    await ctx.send('Joueur introuvable')

            if tracker_challenges != None:

                nb_row = requete_perso_bdd('UPDATE tracker SET challenges = :activation WHERE riot_id = :riot_id and riot_tagline = :riot_tag', {
                    'activation': tracker_challenges, 'riot_id': riot_id, 'riot_tag' : riot_tag}, get_row_affected=True)
                if nb_row > 0:
                    if tracker_challenges:
                        await ctx.send('Tracker challenges activé !')
                    else:
                        await ctx.send('Tracker challenges désactivé !')
                else:
                    await ctx.send('Joueur introuvable')
            
            if ranked_aram != None:
                nb_row = requete_perso_bdd(f'UPDATE ranked_aram_s{saison} SET activation = :activation WHERE index = (select id_compte from tracker where riot_id = :riot_id and riot_tagline = :riot_tag)',
                                            {'activation': ranked_aram, 'riot_id': riot_id, 'riot_tag' : riot_tag}, get_row_affected=True)
                if nb_row > 0:
                    if ranked_aram:
                        await ctx.send('Ranked aram activé')
                    else:
                        await ctx.send('Ranked aram désactivé')
                
                else:
                    await ctx.send('Compte introuvable')

            if insights != None:

                nb_row = requete_perso_bdd('UPDATE tracker SET insights = :activation WHERE riot_id = :riot_id and riot_tagline = :riot_tag', {
                    'activation': insights, 'riot_id': riot_id, 'riot_tag' : riot_tag}, get_row_affected=True)
                if nb_row > 0:
                    if insights:
                        await ctx.send('Insights activé !')
                    else:
                        await ctx.send('Insights désactivé !')
                else:
                    await ctx.send('Joueur introuvable')

            if nb_challenges != None:

                nb_row = requete_perso_bdd('UPDATE tracker SET nb_challenges = :activation WHERE riot_id = :riot_id and riot_tagline = :riot_tag', {
                    'activation': nb_challenges, 'riot_id': riot_id, 'riot_tag' : riot_tag}, get_row_affected=True)

                if nb_row > 0:
                    await ctx.send(f'Nombre de challenges affichés : ** {nb_challenges} ** !')

                else:
                    await ctx.send('Joueur introuvable')
                    
            if records != None:

                nb_row = requete_perso_bdd('UPDATE tracker SET save_records = :activation WHERE riot_id = :riot_id and riot_tagline = :riot_tag', {
                    'activation': records, 'riot_id': riot_id, 'riot_tag' : riot_tag}, get_row_affected=True)
                if nb_row > 0:
                    if records:
                        await ctx.send('Records activés pour ce compte')
                    else:
                        await ctx.send('Records désactivés pour ce compte')
                else:
                    await ctx.send('Joueur introuvable')

            if (
                tracker_fin is None
                and tracker_debut is None
                and tracker_challenges is None
                and insights is None
                and nb_challenges is None
                and ranked_aram is None
                and records is None
            ):
                await ctx.send('Tu dois choisir une option !')
        
        else:
            ctx.send("Tu tentes de modifier un compte dont tu n'as pas l'autorisation")

    @lol_compte.subcommand("color",
                           sub_cmd_description="Modifier la couleur du recap",
                           options=[SlashCommandOption(name="riot_id",
                                                       description="Nom du joueur",
                                                       type=interactions.OptionType.STRING,
                                                       required=True),
                                    SlashCommandOption(name="riot_tag",
                                                       description="Tag",
                                                       type=interactions.OptionType.STRING,
                                                       required=True),
                                    SlashCommandOption(name="rouge",
                                                       description="R",
                                                       type=interactions.OptionType.INTEGER,
                                                       required=True),
                                    SlashCommandOption(name="vert",
                                                       description="G",
                                                       type=interactions.OptionType.INTEGER,
                                                       required=True),
                                    SlashCommandOption(name="bleu",
                                                       description="B",
                                                       type=interactions.OptionType.INTEGER,
                                                       required=True)])
    async def lolcolor(self,
                       ctx: SlashContext,
                       riot_id: str,
                       riot_tag: str,
                       rouge: int,
                       vert: int,
                       bleu: int):

        await ctx.defer(ephemeral=False)

        params = {'rouge': rouge, 'vert': vert,
                  'bleu': bleu, 'riot_id': riot_id.lower(), 'riot_tagline' : riot_tag}
        nb_row = requete_perso_bdd(
            'UPDATE tracker SET "R" = :rouge, "G" = :vert, "B" = :bleu WHERE riot_id = :riot_id and riot_tagline = :riot_tagline',
            params,
            get_row_affected=True,
        )

        if nb_row > 0:
            await ctx.send(f' La couleur du joueur {riot_id} a été modifiée.')
        else:
            await ctx.send(f" Le joueur {riot_id} n'est pas dans la base de données.")


def setup(bot):
    LolAccount(bot)