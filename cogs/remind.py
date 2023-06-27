from fonctions.permissions import *
from discord.utils import get
import datetime
from fonctions.mute import DatabaseHandler
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, slash_command, listen, Task, IntervalTrigger
import interactions
import datetime
from fonctions.gestion_bdd import get_guild_data, requete_perso_bdd, lire_bdd_perso
from fonctions.channels_discord import mention
from fonctions.date import heure_actuelle

reminders = {}


class Divers(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self.database_handler = DatabaseHandler()

    @listen()
    async def on_startup(self):

        self.remind_call.start()

    # @slash_command(name='remindme_ponctuel',
    #                                 description="Rappel ponctuel",
    #                                 options=[
    #                                     SlashCommandOption(
    #                                         name='msg',
    #                                         description='msg dans le rappel',
    #                                         type=interactions.OptionType.STRING,
    #                                         required=True
    #                                     ),
    #                                     SlashCommandOption(
    #                                         name='time',
    #                                         description="Duree (Format h/m/s). Par exemple, 1h20 s'écrit 1h20m",
    #                                         type=interactions.OptionType.STRING,
    #                                         required=True),
    #                                     SlashCommandOption(
    #                                         name='public',
    #                                         description='public ou private ?',
    #                                         type=interactions.OptionType.BOOLEAN,
    #                                         required=False
    #                                     )])
    # async def remindme_ponctuel(self,
    #                             ctx: SlashContext,
    #                             msg: str,
    #                             time: str,
    #                             public: bool = False):

    #     try:
    #         duree = await convertion_temps(ctx, time)
    #     except:
    #         pass

    #     channel = ctx.channel

    #     if ctx.author.id not in reminders: # s'il n'a pas de rappel, on crée une liste avec l'id discord dans notre dict
    #         reminders[ctx.author.id] = []

    #     current_time = time_actuelle()
    #     reminders[ctx.author.id].append((msg, duree, current_time))
    #     await ctx.send(f'Le rappel est programmé dans {duree} secondes', ephemeral=True)
    #     await asyncio.sleep(duree)
    #     if public:
    #         await channel.send(msg)
    #     else:
    #         await ctx.author.send(msg)
    #     reminders[ctx.author.id].pop(0)

    # @slash_command(name='remindme_delete_ponctuel',
    #                                 description="Supprimer un rappel ponctuel",
    #                                 options=[SlashCommandOption(
    #                                     name='numero_rappel',
    #                                     description='numero du rappel obtenu avec remind_list',
    #                                     type=interactions.OptionType.INTEGER,
    #                                     required=True
    #                                 )])
    # async def remindme_delete(self,
    #                          ctx: SlashContext,
    #                          numero_rappel: int):
    #     if ctx.author.id not in reminders:
    #         await ctx.send("Vous n'avez pas de rappels enregistrés.", ephemeral=True)
    #     else:
    #         reminders[ctx.author.id].pop(numero_rappel)
    #         await ctx.send('Fait !')

    # @slash_command(name='remindme_list_ponctuel',
    #                                 description="Liste des rappels ponctuels")
    # async def list_reminders(self, ctx: SlashContext):
    #     if ctx.author.id not in reminders:
    #         await ctx.send("Vous n'avez pas de rappels enregistrés.", ephemeral=True)
    #     else:
    #         if len(reminders[ctx.author.id]) > 0:

    #             for i, reminder in enumerate(reminders[ctx.author.id]):
    #                 msg, delay, current_time = reminder
    #                 delay_total = current_time + \
    #                     datetime.timedelta(seconds=delay)
    #                 await ctx.send(f'Rappel #{i+1}: "{msg}" à {delay_total.strftime("%d/%m/%Y %H:%M:%S")} secondes', ephemeral=True)
    #         else:
    #             await ctx.send('Tous les rappels ont été executés.', ephemeral=True)

    @slash_command(name='remindme',
                   description='Rappel ponctuel')
    async def rappel(self, ctx: SlashContext):
        pass

    @rappel.subcommand('add',
                       sub_cmd_description="Rappel à répéter",
                       options=[
                           SlashCommandOption(
                               name='msg',
                               description='msg dans le rappel',
                               type=interactions.OptionType.STRING,
                               required=True
                           ),
                           SlashCommandOption(
                               name='heure',
                               description="Heure",
                               type=interactions.OptionType.INTEGER,
                               required=True),
                           SlashCommandOption(
                               name='minute',
                               description='Minute',
                               type=interactions.OptionType.INTEGER,
                               required=True
                           ),
                           SlashCommandOption(name='repetition',
                                              description='Combien de fois ? (1 à 365)',
                                              type=interactions.OptionType.INTEGER,
                                              min_value=1,
                                              max_value=365,
                                              required=True),
                           SlashCommandOption(name='jour',
                                              description='quel jour ?',
                                              type=interactions.OptionType.STRING,
                                              required=False,
                                              choices=[
                                                  SlashCommandChoice(
                                                      name='Lundi', value='1'),
                                                  SlashCommandChoice(
                                                      name='Mardi', value='2'),
                                                  SlashCommandChoice(
                                                      name='Mercredi', value='3'),
                                                  SlashCommandChoice(
                                                      name='Jeudi', value='4'),
                                                  SlashCommandChoice(
                                                      name='Vendredi', value='5'),
                                                  SlashCommandChoice(
                                                      name='Samedi', value='6'),
                                                  SlashCommandChoice(
                                                      name='Dimanche', value='7'),
                                                  SlashCommandChoice(
                                                      name='Tous', value='0')
                                              ]),
                           SlashCommandOption(
                               name='channel',
                               description='dans quel channel écrire le msg ? (si public)',
                               type=interactions.OptionType.CHANNEL,
                               required=False),
                           SlashCommandOption(
                               name='public',
                               description='rappel public ou en mp ?',
                               type=interactions.OptionType.BOOLEAN,
                               required=False)
                       ])
    async def remindme_quotidien(self,
                                 ctx: SlashContext,
                                 msg: str,
                                 heure: int,
                                 minute: int,
                                 repetition: int,
                                 jour: str = '0',
                                 channel: interactions.BaseChannel = None,
                                 public: bool = False):

        user_id = int(ctx.author.id)
        guild_id = int(ctx.guild_id)

        if channel == None:
            channel_id = int(ctx.channel_id)
        else:
            channel_id = int(channel.id)

        requete_perso_bdd('''INSERT INTO remind(
                            guild, channel, heure, minute, repetition, "user", public, msg, jour)
                            VALUES (:guild_id, :channel_id, :heure, :minute, :repetition, :user_id, :public, :msg, :jour);''',
                          {'guild_id': guild_id,
                           'channel_id': channel_id,
                           'heure': heure,
                           'minute': minute,
                           'repetition': repetition,
                           'user_id': user_id,
                           'public': public,
                           'msg': msg,
                           'jour': int(jour)})

        await ctx.send(f'Rappel enregistré pour {heure}:{minute}', ephemeral=True)

    @rappel.subcommand('liste',
                   sub_cmd_description="Liste des rappels")
    async def remindme_quotidien_list(self,
                                      ctx: SlashContext):

        await ctx.defer(ephemeral=True)

        df = lire_bdd_perso(f'SELECT * from remind where "user" = {int(ctx.author.id)} and repetition >= 1',
                            index_col='id',
                            ).transpose()

        if len(df) >= 1:
            msg = 'Rappels actifs : \n'

            for id_rappel, infos_rappel in df.iterrows():

                channel = await self.bot.fetch_channel(infos_rappel['channel'])

                guild = await self.bot.fetch_guild(infos_rappel['guild'])

                dict_day = {1: 'Lundi', 2: 'Mardi', 3: 'Mercredi', 4: 'Jeudi',
                            5: 'Vendredi', 6: 'Samedi', 7: 'Dimanche', 0: 'Tous les jours'}

                if infos_rappel["public"]:
                    msg += f'__Rappel {id_rappel}__ prévue à **{infos_rappel["heure"]}:{infos_rappel["minute"]}** {dict_day[infos_rappel["jour"]]} {infos_rappel["repetition"]} fois dans **{guild.name}** | Public : **Oui ({channel.name})** : \n {infos_rappel["msg"]} \n '
                else:
                    msg += f'__Rappel {id_rappel}__ prévue à **{infos_rappel["heure"]}:{infos_rappel["minute"]}** {dict_day[infos_rappel["jour"]]} {infos_rappel["repetition"]} fois dans **{guild.name}** | Channel **{channel.name}** : \n {infos_rappel["msg"]} \n '

            await ctx.send(msg, ephemeral=True)

        else:
            await ctx.send('Pas de rappel actif', ephemeral=True)

    @rappel.subcommand('delete',
                   sub_cmd_description="Rappel quotidien à supprimer",
                   options=[
                       SlashCommandOption(name='id_rappel',
                                          description='numero du rappel',
                                          type=interactions.OptionType.INTEGER,
                                          required=True)
                   ])
    async def remindme_quotidien_delete(self,
                                        ctx: SlashContext,
                                        id_rappel: int):

        await ctx.defer(ephemeral=True)

        nb_row = requete_perso_bdd(f'''UPDATE remind SET repetition = 0
                              WHERE "user" = {int(ctx.author.id)} AND "id" = {id_rappel}''', get_row_affected=True)

        if nb_row > 0:
            await ctx.send(f'Le rappel **{id_rappel}** a été désactivé', ephemeral=True)
        else:
            await ctx.send('Pas de rappel identifié à ton nom', ephemeral=True)

    @Task.create(IntervalTrigger(minutes=1))
    async def remind_call(self):
        heure, minute = heure_actuelle()
        jour = datetime.datetime.now().isoweekday()

        df = lire_bdd_perso(f'''SELECT * from remind
                            where heure = {heure}
                            and minute = {minute}
                            and repetition >= 1
                            and jour in (0, {jour})''',
                            index_col='id',
                            ).transpose()

        if len(df) >= 1:  # s'il y a des données

            for id_rappel, infos_rappel in df.iterrows():
                # on cherche l'user qui a le rappel

                user = await self.bot.fetch_user(infos_rappel['user'])

                if infos_rappel['public']:
                    # on cherche le channel à envoyer le rappel

                    channel = await self.bot.fetch_channel(infos_rappel['channel'])

                    await channel.send(f'__Rappel__ {mention(user.id, "membre")} : {infos_rappel["msg"]} ')
                else:
                    await user.send(f'__Rappel__ : {infos_rappel["msg"]}')

                # le rappel a été effectué, on le diminue de 1
                requete_perso_bdd(
                    'UPDATE remind SET repetition = repetition - 1 where id = :id ', {'id': id_rappel})


def setup(bot):
    Divers(bot)
