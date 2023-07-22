import pandas as pd
from fonctions.gestion_bdd import (lire_bdd,
                                   requete_perso_bdd,
                                   lire_bdd_perso,
                                   get_data_bdd)
import datetime
from fonctions.channels_discord import chan_discord
import interactions
from interactions import listen, Task, TimeTrigger
from interactions import SlashCommandChoice, SlashCommandOption, Extension, SlashContext, slash_command
from fonctions.permissions import isOwner_slash
from fonctions.params import Version, saison, heure_aram
from fonctions.permissions import isOwner_slash
from fonctions.match import label_tier
from interactions.ext.paginators import Paginator


dict_points = {41: [11, -19],
               42: [12, -18],
               43: [13, -17],
               44: [14, -16],
               45: [15, -15],
               46: [16, -15],
               47: [17, -15],
               48: [18, -15],
               49: [19, -15],
               50: [20, -15],
               51: [21, -15],
               52: [22, -15],
               53: [23, -15],
               54: [24, -15],
               55: [25, -15],
               56: [26, -14],
               57: [27, -13],
               58: [28, -12],
               59: [29, -11]}

elo_lp = {'IRON': 0,
          'BRONZE': 1,
          'SILVER': 2,
          'GOLD': 3,
          'PLATINUM': 4,
          'EMERALD' : 5,
          'DIAMOND': 6,
          'MASTER': 7,
          'GRANDMASTER': 8,
          'CHALLENGER': 9,
          'FIRST_GAME': 0}


class Aram(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @listen()
    async def on_startup(self):
        self.lolsuivi_aram.start()
        
    @slash_command(name='lol_aram',
                   description='Commandes Aram')
    async def aram(self, ctx: SlashContext):  
        pass  



    @aram.subcommand("classement",
                   sub_cmd_description="classement en aram")
    async def ladder_aram(self, ctx: SlashContext):

        suivi_aram = lire_bdd_perso(
            f'''SELECT * from ranked_aram_s{saison} where games != 0''', format='dict')

        await ctx.defer(ephemeral=False)

        df = pd.DataFrame.from_dict(suivi_aram)
        df = df.transpose().reset_index()

        df.sort_values('lp', ascending=False, inplace=True)

        embed = interactions.Embed(
            title="Suivi LOL", description='ARAM', color=interactions.Color.random())

        for key in df['index']:

            wr = round((suivi_aram[key]['wins'] /
                       suivi_aram[key]['games'])*100, 2)

            kda = round(
                (suivi_aram[key]['k'] + suivi_aram[key]['a']) / suivi_aram[key]['d'], 2)

            if suivi_aram[key]['activation']:
                embed.add_field(name=str(f"{key} ({suivi_aram[key]['lp']} LP) [{suivi_aram[key]['rank']}]"),
                                value="V : " +
                                str(suivi_aram[key]['wins']) + " | D : " +
                                str(suivi_aram[key]['losses']) + " | WR :  "
                                + str(wr) + "% | KDA : " + str(kda), inline=False)
            else:
                embed.add_field(name=str(f"{key} ({suivi_aram[key]['lp']} LP) [{suivi_aram[key]['rank']}] [Désactivé]"),
                                value="V : " +
                                str(suivi_aram[key]['wins']) + " | D : " +
                                str(suivi_aram[key]['losses']) + " | WR :  "
                                + str(wr) + "% | KDA : " + str(kda), inline=False)

        embed.set_footer(text=f'Version {Version} by Tomlora')

        await ctx.send(embeds=embed)

    @aram.subcommand('ranked_aram',
                   sub_cmd_description='Activation/Désactivation',
                   options=[
                       SlashCommandOption(
                           name='summonername',
                           description="nom ingame",
                           type=interactions.OptionType.STRING,
                           required=True),
                       SlashCommandOption(
                           name="activation",
                           description="True : Activé / False : Désactivé",
                           type=interactions.OptionType.BOOLEAN,
                           required=True)])
    async def update_activation(self,
                                ctx: SlashContext,
                                summonername: str,
                                activation: bool):

        summonername = summonername.lower()

        try:
            requete_perso_bdd(f'UPDATE ranked_aram_s{saison} SET activation = :activation WHERE index = :index', {
                              'activation': activation, 'index': summonername})
            if activation:
                await ctx.send('Ranked activé !')
            else:
                await ctx.send('Ranked désactivé !')
        except KeyError:
            await ctx.send('Joueur introuvable')

    @aram.subcommand("help",
                   sub_cmd_description='Help ranked aram')
    async def help_aram(self, ctx: SlashContext):

        texte_general = " La ranked aram commence automatiquement après la première game. Pour désactiver, il est possible d'utiliser **/ranked_aram.** après la première partie \n" + \
                        "Le suivi est possible en tapant **/classement_aram**"

        await ctx.defer(ephemeral=False)

        embed = interactions.Embed(
            title='Help Aram', description='Règle', color=interactions.Color.random())

        embed.add_field(name='Déroulement général', value=texte_general)

        embed2 = interactions.Embed(
            title='Palier', description="Rang", color=interactions.Color.random())

        embed2.add_field(name='IRON', value="LP < 100")
        embed2.add_field(name='BRONZE', value="100 < LP < 200")
        embed2.add_field(name='SILVER', value="200 < LP < 300")
        embed2.add_field(name='GOLD', value="300 < LP < 500")
        embed2.add_field(name='PLATINUM', value="500 < LP < 800")
        embed2.add_field(name='EMERALD', value='800 < LP < 1100')
        embed2.add_field(name='DIAMOND', value="1100 < LP < 1400")
        embed2.add_field(name='MASTER', value="1400 < LP < 1600")
        embed2.add_field(name='GRANDMASTER', value="1600 < LP < 2000")
        embed2.add_field(name='CHALLENGER', value="2000 < LP")

        embed3 = interactions.Embed(
            title='Calcul points', description="MMR", color=interactions.Color.random())

        embed3.add_field(name="5 premières games", value=f"5 premières games \n" +
                         "V : **+50**  | D : **0**", inline=False)

        calcul_points = "WR **<40%** - V : **+10** | D : **-20** \n"

        for key, value in dict_points.items():
            calcul_points = calcul_points + \
                f" WR **{key}%** - V : **+{value[0]}** | D : **{value[1]}** \n"

        calcul_points = calcul_points + "WR **>60%** - V : **+30** / D : **-10**"

        embed3.add_field(name='Calcul des points',
                         value=calcul_points, inline=False)

        bonus_elo = ""
        for key, value in elo_lp.items():
            bonus_elo = bonus_elo + f"{key} : **-{value}** \n"

        embed3.add_field(name="Malus elo", value=bonus_elo, inline=False)
        
        embeds = [embed, embed2, embed3]

        paginator = Paginator.create_from_embeds(
            self.bot,
            *embeds)
        
        paginator.show_select_menu = True
        await paginator.send(ctx)

    @slash_command(name='carton',
                   description='Activation/Désactivation',
                   options=[
                       SlashCommandOption(
                           name='couleur',
                           description="vert = + / rouge = -",
                           type=interactions.OptionType.STRING,
                           required=True, choices=[
                               SlashCommandChoice(name='vert',
                                                  value='vert'),
                               SlashCommandChoice(name='rouge', value='rouge')]),
                       SlashCommandOption(
                           name="summonername",
                           description="nom ingame",
                           type=interactions.OptionType.STRING,
                           required=True),
                       SlashCommandOption(
                           name='nombre',
                           description='nombre de lp',
                           type=interactions.OptionType.INTEGER,
                           required=True)])
    async def carton(self,
                     ctx: SlashContext,
                     couleur: str,
                     summonername: str,
                     nombre: int):
        if isOwner_slash(ctx):

            summonername = summonername.lower().replace(' ', '')
            if couleur == 'vert':
                nb_row = requete_perso_bdd(f'UPDATE ranked_aram_s{saison} SET lp = lp + :nombre WHERE index = :summonername', {
                    'nombre': nombre, 'summonername': summonername}, get_row_affected=True)
                if nb_row > 0:
                    msg = f'Les LP pour {summonername} ont été ajoutés. (+{nombre})'
                else:
                    msg = "Tu n'es pas dans la base de données."
            if couleur == 'rouge':
                nb_row = requete_perso_bdd(f'UPDATE ranked_aram_s{saison} SET lp = lp - :nombre WHERE index = :summonername', {
                    'nombre': nombre, 'summonername': summonername}, get_row_affected=True)
                if nb_row > 0:
                    msg = f'Les LP pour {summonername} ont été retirés. (-{nombre})'
                else:
                    msg = "Tu n'es pas dans la base de données."
        else:
            nb_row = requete_perso_bdd(f'UPDATE ranked_aram_s{saison} SET lp = lp - 1 WHERE index = :summonername', {
                'summonername': summonername}, get_row_affected=True)
            if nb_row > 0:
                msg = 'Bien essayé ! Tu perds 1 lp.'
            else:
                msg = "Tu n'es pas dans la base de données."

        embed = interactions.Embed(description=msg,
                                   color=interactions.Color.random())

        await ctx.send(embeds=embed)

    async def update_aram24h(self):
        data = get_data_bdd(f'''SELECT DISTINCT tracker.server_id from tracker 
                    INNER JOIN channels_module on tracker.server_id = channels_module.server_id
                    where channels_module.league_aram = true''').fetchall()

        for server_id in data:

            guild = await self.bot.fetch_guild(server_id[0])

            chan_discord_id = chan_discord(int(guild.id))

            # le suivi est déjà maj par game/update... Pas besoin de le refaire ici..

            df = lire_bdd_perso(f'''SELECT suivi.index, suivi.wins, suivi.losses, suivi.lp, suivi.rank, tracker.server_id from ranked_aram_s{saison} as suivi 
                                        INNER join tracker ON tracker.index = suivi.index 
                                        where tracker.server_id = {int(guild.id)} ''')
            df_24h = lire_bdd_perso(f'''SELECT suivi.index, suivi.wins, suivi.losses, suivi.lp, suivi.rank, tracker.server_id from ranked_aram_24h as suivi
                                        INNER join tracker ON tracker.index = suivi.index 
                                        where tracker.server_id = {int(guild.id)} ''')

            if df.shape[1] > 0:  # s'il y a des données

                df = df.transpose().reset_index()

                df_24h = df_24h.transpose().reset_index()

                # Pour l'ordre de passage
                df['tier_pts'] = df['rank'].apply(label_tier)

                sql = ''
                df.sort_values(by=['tier_pts', 'lp'], ascending=[
                    False, False], inplace=True)

                suivi = df.set_index('index').transpose().to_dict()
                suivi_24h = df_24h.set_index('index').transpose().to_dict()
                joueur = suivi.keys()

                embed = interactions.Embed(
                    title="Suivi ARAM LOL", description='Periode : 24h', color=interactions.Color.random())
                totalwin = 0
                totaldef = 0
                totalgames = 0

                for key in joueur:

                    # suivi est mis à jour par update et updaterank. On va donc prendre le comparer à suivi24h
                    wins = int(suivi_24h[key]['wins'])
                    losses = int(suivi_24h[key]['losses'])
                    nbgames = wins + losses
                    LP = int(suivi_24h[key]['lp'])
                    tier_old = str(suivi_24h[key]['rank'])

                    # on veut les stats soloq

                    tier = str(suivi[key]['rank'])

                    difwins = int(suivi[key]['wins']) - wins
                    diflosses = int(suivi[key]['losses']) - losses
                    difLP = int(suivi[key]['lp']) - LP
                    totalwin += difwins
                    totaldef += diflosses
                    totalgames = totalwin + totaldef

                    # evolution

                    if elo_lp[tier_old] > elo_lp[tier]:  # 19-18
                        difLP = f"Démote (x{elo_lp[tier_old] - elo_lp[tier]}) / -{str(difLP)} "
                        emote = ":arrow_down:"

                    elif elo_lp[tier_old] < elo_lp[tier]:
                        difLP = f"Promotion (x{elo_lp[tier] - elo_lp[tier_old]}) / +{str(difLP)} "
                        emote = ":arrow_up:"

                    elif elo_lp[tier_old] == elo_lp[tier]:
                        if difLP > 0:
                            emote = ":arrow_up:"
                        elif difLP < 0:
                            emote = ":arrow_down:"
                        elif difLP == 0:
                            emote = ":arrow_right:"

                    if nbgames != 0:
                        embed.add_field(name=str(key) + " ( " + tier + " )",
                                        value=f"V : {suivi[key]['wins']} ({difwins}) | " +
                                        f"D : {suivi[key]['losses']} ({diflosses}) | " +
                                        f"LP :  {suivi[key]['lp']} ({difLP}) {emote}", inline=False)

                    if difwins + diflosses > 0:  # si supérieur à 0, le joueur a joué
                        sql += f'''UPDATE ranked_aram_24h
                            SET wins = {suivi[key]['wins']},
                            losses = {suivi[key]['losses']},
                            lp = {suivi[key]['lp']},
                            rank = '{tier}'
                            where index = '{key}';'''

                channel_tracklol = await self.bot.fetch_channel(chan_discord_id.lol_others)

                if sql != '':
                    requete_perso_bdd(sql)
                embed.set_footer(text=f'Version {Version} by Tomlora')

                if totalgames > 0:
                    await channel_tracklol.send(embeds=embed)
                    await channel_tracklol.send(f'Sur {totalgames} games -> {totalwin} victoires et {totaldef} défaites')


    @Task.create(TimeTrigger(hour=5))
    async def lolsuivi_aram(self):

        await self.update_aram24h()

    @slash_command(name="force_update_aram24h",
                   description="Réservé à Tomlora")
    async def force_update_aram(self, ctx: SlashContext):

        if isOwner_slash(ctx):
            await self.update_aram24h()
        else:
            await ctx.send("Tu n'as pas l'autorisation nécessaire.")


def setup(bot):
    Aram(bot)
