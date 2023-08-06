import os
import interactions
from discord.ext import commands
from discord.utils import get
from requests.exceptions import HTTPError
from fonctions.gestion_bdd import requete_perso_bdd, lire_bdd_perso
from fonctions.channels_discord import chan_discord
from fonctions.params import Version
import traceback
from interactions.api.events import MessageCreate, GuildJoin, GuildLeft, MemberAdd, MemberRemove
from interactions import listen


# Duplicate table
# https://popsql.com/learn-sql/postgresql/how-to-duplicate-a-table-in-postgresql


# Paramètres

# https://www.youtube.com/watch?v=IolxqkL7cD8
token = os.environ.get('discord_tk')
id_bot = os.environ.get('bot_marin')


bot = interactions.Client(token=token, intents=interactions.Intents.ALL)


@listen()
async def on_message_create(message: MessageCreate):
    """Event qui se déclenche à l'envoi d'un msg

    Parameters
    ----------
    message : interactions.Message
    """

    channel = message.message.channel     # get id channel
    # identification du channel

    # si le msg n'est pas en dm et qu'il n'est pas le bot
    if (channel.type != interactions.ChannelType.DM) and (int(message.message.author.id) != int(id_bot)):

        guild : interactions.Guild = message.message.guild
        role = get(guild.roles, name="Muted")  # get the muted role
        role = await guild.fetch_role(role)

        if role.id in message.message.author.roles:  # si l'user a le role mute, on supprime son msg
            await message.message.delete()

    # await bot.process_commands(
    #     message)  # Overriding the default provided on_message forbids any extra commands from running. To fix this, add a bot.process_commands(message) line at the end of your on_message.


@listen()
async def on_guild_create(guild: GuildJoin):
    """Event qui se déclenche lorsque le bot rejoint un serveur, ou redétecte un serveur indisponible.

    Parameters
    ----------
    guild : interactions.Guild
    """

    # on_guild_create peut marcher si le serveur n'est pas disponible, on va donc check si on l'a dans la bdd ou pas.
    if lire_bdd_perso(f'''SELECT server_id from channels_discord where server_id = {int(guild.guild_id)}''', index_col='server_id').shape[1] != 1:
        # si on l'a pas, on l'ajoute
        text_channel_list = []
            
        text_channel_list = [channel.id for channel in guild.guild.channels]



        requete_perso_bdd(f'''INSERT INTO channels_discord(
                        server_id, id_owner, id_owner2, chan_pm, chan_tracklol, chan_accueil, chan_twitch, chan_lol, chan_tft, chan_lol_others, role_admin)
                        VALUES (:server_id, :tom, :admin, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :role_admin);
                        INSERT INTO channels_module(server_id)
                        VALUES (:server_id);''',
                          {'server_id': int(guild.guild_id),
                           'chan': int(text_channel_list[0]),
                           'tom': 298418038460514314,
                           'admin': int(guild.guild.get_owner().id),
                           'role_admin': 0})

    else:  # si on l'a déjà, il vient de rejoindre à nouveau le serveur.
        requete_perso_bdd(f'''UPDATE channels_module SET activation = :activation where server_id = :server_id''', {'server_id': int(guild.guild_id),
                                                                                                                   'activation': 'true'})


@listen()
async def on_guild_delete(guild: GuildLeft):
    """Event qui se déclenche quand le bot quitte un serveur

    Parameters
    ----------
    guild : interactions.Guild
    """
    requete_perso_bdd(f'''UPDATE channels_module SET activation = :activation where server_id = :server_id''', {'server_id': int(guild.guild_id),
                                                                                                                'activation': 'false'})


@listen()
async def on_guild_member_add(member: MemberAdd):
    """Event qui se déclenche quand un membre rejoint un serveur

    Parameters
    ----------
    member : interactions.Member
    """

    # get le serveur discord
    chan_discord_pm = chan_discord(int(member.guild.id))

    guild = await bot.fetch_guild(member.guild.id)
    # identifier le channel d'accueil
    
    channel = await bot.fetch_channel(chan_discord_pm.chan_accueil)
    # msg de bienvenue

    embed = interactions.Embed(title=f'Bienvenue chez les {guild.name}',
                               description=f'Hello {member.member.nickname}, tu es notre {guild.member_count}ème membre !',
                               color=interactions.Color.random())
    embed.set_thumbnail(url=member.member.avatar.as_url())
    embed.set_footer(text=f'Version {Version} by Tomlora')

    await channel.send(embeds=embed)


@listen()
async def on_guild_member_remove(member: MemberRemove):
    """Event qui se déclenche quand un membre quitte un serveur

    Parameters
    ----------
    member : interactions.Member"""

    # get le serveur discord
    chan_discord_pm = chan_discord(int(member.guild.id))
    
    guild = await bot.fetch_guild(member.guild.id)
    # identifier le channel d'accueil
    
    channel = await bot.fetch_channel(chan_discord_pm.chan_accueil)
    
    # msg de départ
    embed = interactions.Embed(title=f'Départ des {guild.name}',
                               description=f'Au revoir {member.member.nickname}, nous sommes encore {guild.member_count} membres !',
                               color=interactions.Color.random())
    embed.set_thumbnail(url=member.member.avatar.as_url())
    embed.set_footer(text=f'Version {Version} by Tomlora')

    await channel.send(embeds=embed)


# @listen()
# async def on_command_error(ctx: interactions.CommandContext, error: commands.errors):
#     """Event qui se déclenche lorsque le bot rencontre une erreur. """"""

#     Parameters
#     ----------
#     ctx : interactions.CommandContext
#     error : commands.errors
#     """

#     if isinstance(error, commands.CommandNotFound):
#         await ctx.send("Cette commande n'existe pas")
#     elif isinstance(error, commands.MissingPermissions):
#         await ctx.send("Tu n'as pas les permissions nécessaires")
#     elif isinstance(error, commands.PrivateMessageOnly):
#         await ctx.send("Cette commande n'est activée qu'en message privé")
#     elif isinstance(error, commands.CommandOnCooldown):
#         await ctx.send(f' {error}')
#     elif isinstance(error, HTTPError):
#         print('httperror')
#         await ctx.send('Trop de requêtes')
#     else:
#         traceback.print_exception(type(error), error, error.__traceback__)
#         embed = interactions.Embed(title='Erreur', description=f'Description: \n `{error}`',
#                                    color=interactions.Color.RED)
#         await ctx.send(embeds=embed)


# Fix pour intégrer des img locales dans les embed
# bot.load_extension('interactions.ext.files')

for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        # bot.load_extension(f'cogs.{filename[:-3]}')
        bot.load_extension(f'cogs.{filename[:-3]}')

# bot.run(discord_token)
bot.start()
