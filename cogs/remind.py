import asyncio
from fonctions.permissions import *
from discord.utils import get
import datetime
from fonctions.mute import DatabaseHandler
from interactions import Option, Extension, CommandContext, Choice
import interactions
from interactions.ext.wait_for import wait_for, wait_for_component, setup as stp
from interactions.ext.tasks import IntervalTrigger, create_task
import datetime
from fonctions.gestion_bdd import get_guild_data, requete_perso_bdd, lire_bdd_perso
import cv2
import numpy as np
import os
from fonctions.channels_discord import convertion_temps, mention
from fonctions.date import heure_actuelle, time_actuelle

reminders = {}


class Divers(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        stp(self.bot)
        self.database_handler = DatabaseHandler()

    @interactions.extension_listener
    async def on_start(self):

        self.task1 = create_task(IntervalTrigger(60))(self.remind_call)
        self.task1.start()

    # @interactions.extension_command(name='remindme_ponctuel',
    #                                 description="Rappel ponctuel",
    #                                 options=[
    #                                     Option(
    #                                         name='msg',
    #                                         description='msg dans le rappel',
    #                                         type=interactions.OptionType.STRING,
    #                                         required=True
    #                                     ),
    #                                     Option(
    #                                         name='time',
    #                                         description="Duree (Format h/m/s). Par exemple, 1h20 s'écrit 1h20m",
    #                                         type=interactions.OptionType.STRING,
    #                                         required=True),
    #                                     Option(
    #                                         name='public',
    #                                         description='public ou private ?',
    #                                         type=interactions.OptionType.BOOLEAN,
    #                                         required=False
    #                                     )])
    # async def remindme_ponctuel(self,
    #                             ctx: CommandContext,
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

    # @interactions.extension_command(name='remindme_delete_ponctuel',
    #                                 description="Supprimer un rappel ponctuel",
    #                                 options=[Option(
    #                                     name='numero_rappel',
    #                                     description='numero du rappel obtenu avec remind_list',
    #                                     type=interactions.OptionType.INTEGER,
    #                                     required=True
    #                                 )])
    # async def remindme_delete(self,
    #                          ctx: CommandContext,
    #                          numero_rappel: int):
    #     if ctx.author.id not in reminders:
    #         await ctx.send("Vous n'avez pas de rappels enregistrés.", ephemeral=True)
    #     else:
    #         reminders[ctx.author.id].pop(numero_rappel)
    #         await ctx.send('Fait !')

    # @interactions.extension_command(name='remindme_list_ponctuel',
    #                                 description="Liste des rappels ponctuels")
    # async def list_reminders(self, ctx: CommandContext):
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

    @interactions.extension_command(name='remindme',
                                    description="Rappel à répéter",
                                    options=[
                                        Option(
                                            name='msg',
                                            description='msg dans le rappel',
                                            type=interactions.OptionType.STRING,
                                            required=True
                                        ),
                                        Option(
                                            name='heure',
                                            description="Heure",
                                            type=interactions.OptionType.INTEGER,
                                            required=True),
                                        Option(
                                            name='minute',
                                            description='Minute',
                                            type=interactions.OptionType.INTEGER,
                                            required=True
                                        ),
                                        Option(name='repetition',
                                               description='Combien de fois ? (1 à 365)',
                                               type=interactions.OptionType.INTEGER,
                                               min_value=1,
                                               max_value=365,
                                               required=True),
                                        Option(name='jour',
                                               description='quel jour ?',
                                               type=interactions.OptionType.STRING,
                                               required=False,
                                               choices=[
                                                   Choice(name='Lundi', value='1'),
                                                   Choice(name='Mardi', value='2'),
                                                   Choice(name='Mercredi', value='3'),
                                                   Choice(name='Jeudi', value='4'),
                                                   Choice(name='Vendredi', value='5'),
                                                   Choice(name='Samedi', value='6'),
                                                   Choice(name='Dimanche', value='7'),
                                                   Choice(name='Tous', value='0')
                                               ]),
                                        Option(
                                            name='channel',
                                            description='dans quel channel écrire le msg ? (si public)',
                                            type=interactions.OptionType.CHANNEL,
                                            required=False),
                                        Option(
                                            name='public',
                                            description='rappel public ou en mp ?',
                                            type=interactions.OptionType.BOOLEAN,
                                            required=False)
                                    ])
    async def remindme_quotidien(self,
                                 ctx: CommandContext,
                                 msg: str,
                                 heure: int,
                                 minute: int,
                                 repetition: int,
                                 jour:str = '0',
                                 channel: interactions.Channel = None,
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
                           'jour' : int(jour)})

        await ctx.send(f'Rappel enregistré pour {heure}:{minute}', ephemeral=True)

    @interactions.extension_command(name='remindme_list',
                                    description="Rappel à répéter")
    async def remindme_quotidien_list(self,
                                      ctx: CommandContext):

        await ctx.defer(ephemeral=True)

        df = lire_bdd_perso('SELECT * from remind where "user" = %(user_id)s and repetition >= 1',
                            index_col='id',
                            params={'user_id': int(ctx.author.id)}).transpose()

        if len(df) >= 1:
            msg = 'Rappels actifs : \n'

            for id_rappel, infos_rappel in df.iterrows():
                channel = await interactions.get(self.bot,
                                                 interactions.Channel,
                                                 object_id=infos_rappel['channel'])
                guild = await interactions.get(self.bot,
                                               interactions.Guild,
                                               object_id=infos_rappel['guild'])
                
                dict_day = {1 : 'Lundi', 2: 'Mardi', 3: 'Mercredi', 4: 'Jeudi', 5: 'Vendredi', 6 : 'Samedi', 7 : 'Dimanche', 0 : 'Tous les jours'}

                if infos_rappel["public"]:
                    msg += f'__Rappel {id_rappel}__ prévue à **{infos_rappel["heure"]}:{infos_rappel["minute"]}** {dict_day[infos_rappel["jour"]]} {infos_rappel["repetition"]} fois dans **{guild.name}** | Public : **Oui ({channel.name})** : \n {infos_rappel["msg"]} \n '
                else:
                    msg += f'__Rappel {id_rappel}__ prévue à **{infos_rappel["heure"]}:{infos_rappel["minute"]}** {dict_day[infos_rappel["jour"]]} {infos_rappel["repetition"]} fois dans **{guild.name}** | Channel **{channel.name}** : \n {infos_rappel["msg"]} \n '

            await ctx.send(msg, ephemeral=True)

        else:
            await ctx.send('Pas de rappel actif', ephemeral=True)
            
    @interactions.extension_command(name='remindme_delete',
                                    description="Rappel quotidien à supprimer",
                                    options=[
                                        Option(name='id_rappel',
                                               description='numero du rappel',
                                               type=interactions.OptionType.INTEGER,
                                               required=True)
                                    ])
    async def remindme_quotidien_delete(self,
                                      ctx: CommandContext,
                                      id_rappel : int):

        await ctx.defer(ephemeral=True)
        
        params = {'user_id': int(ctx.author.id),
                'id_rappel' : id_rappel}

        df = lire_bdd_perso('SELECT * from remind where "user" = %(user_id)s and "id" = %(id_rappel)s',
                            index_col='id',
                            params=params).transpose()

        if len(df) >= 1:

            requete_perso_bdd('''UPDATE remind SET repetition = 0
                              WHERE "user" = :user_id AND "id" = :id_rappel''',
                              dict_params=params)
            
            await ctx.send(f'Le rappel **{id_rappel}** a été désactivé', ephemeral=True)

        else:
            await ctx.send('Pas de rappel identifié à ton nom', ephemeral=True)

    async def remind_call(self):
        heure, minute = heure_actuelle()
        jour = datetime.datetime.now().isoweekday()
        
        df = lire_bdd_perso('''SELECT * from remind
                            where heure = %(heure)s
                            and minute = %(minute)s
                            and repetition >= 1
                            and jour in (0, %(jour)s)''',
                            index_col='id',
                            params={'heure': heure,
                                    'minute': minute,
                                    'jour' : jour}).transpose()

        if len(df) >= 1:  # s'il y a des données

            for id_rappel, infos_rappel in df.iterrows():
                # on cherche l'user qui a le rappel
                user = await interactions.get(self.bot,
                                              interactions.User,
                                              object_id=infos_rappel['user'])

                if infos_rappel['public']:
                    # on cherche le channel à envoyer le rappel
                    channel = await interactions.get(self.bot,
                                                     interactions.Channel,
                                                     object_id=infos_rappel['channel'])

                    await channel.send(f'__Rappel__ {mention(user.id, "membre")} : {infos_rappel["msg"]} ')
                else:
                    await user.send(f'__Rappel__ : {infos_rappel["msg"]}')

                # le rappel a été effectué, on le diminue de 1
                requete_perso_bdd(
                    'UPDATE remind SET repetition = repetition - 1 where id = :id ', {'id': id_rappel})


def setup(bot):
    Divers(bot)
