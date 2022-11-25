import os
import interactions
import asyncio
import discord
from discord.ext import commands

from fonctions.channels_discord import chan_discord
from fonctions.gestion_bdd import requete_perso_bdd



# Duplicate table
# https://popsql.com/learn-sql/postgresql/how-to-duplicate-a-table-in-postgresql

Var_version = 8.0

# Paramètres

token = os.environ.get('discord_tk')  # https://www.youtube.com/watch?v=IolxqkL7cD8
id_bot = os.environ.get('bot_marin')




bot = interactions.Client(token=token, intents=interactions.Intents.ALL)

# bot.remove_command('help')

chan_discord_id = chan_discord(494217748046544906)

# à faire passer en bdd
id_tom = chan_discord_id.id_owner
id_dawn = chan_discord_id.id_owner2
chan_pm = chan_discord_id.chan_pm
chan_tracklol = chan_discord_id.tracklol
chan_kangourou = chan_discord_id.chan_accueil
chan_twitch = chan_discord_id.twitch
chan_lol = chan_discord_id.lol
chan_tft = chan_discord_id.tft
chan_lol_others = chan_discord_id.lol_others

# même chose
guildid = chan_discord_id.server_id
role_admin = chan_discord_id.role_admin

@bot.event
async def on_message(message):
    if not isinstance(message.channel, discord.abc.PrivateChannel):
        role = discord.utils.get(message.guild.roles, name="Muted")

    if (isinstance(message.channel, discord.abc.PrivateChannel)) and (int(message.author.id) != int(id_bot)):
        channel_pm = bot.get_channel(chan_pm)
        date = str(message.created_at)
        date_short = date[:-7]
        embed = discord.Embed(title=f"Message privé reçu de la part de {message.author}",
                              description=f"{message.content}",
                              color=discord.Color.blue())
        embed.set_thumbnail(url=message.author.avatar_url)
        embed.set_footer(text=f'< userid : {message.author.id} >  < date : {date_short} >')
        await channel_pm.send(embed=embed)

    if not isinstance(message.channel, discord.abc.PrivateChannel):

        if role in message.author.roles:
            await message.delete()
            
        
    await bot.process_commands(
        message)  # Overriding the default provided on_message forbids any extra commands from running. To fix this, add a bot.process_commands(message) line at the end of your on_message.

@bot.event
async def on_guild_join(guild : discord.Guild):

        text_channel_list = []
        for channel in guild.text_channels:
            text_channel_list.append(channel.id)
        
        requete_perso_bdd(f'''INSERT INTO public.channels_discord(
                    server_id, id_owner, id_owner2, chan_pm, chan_tracklol, chan_accueil, chan_twitch, chan_lol, chan_tft, chan_lol_others, role_admin)
                    VALUES (:server_id, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :chan);''',
                {'server_id' : guild.id, 'chan' : text_channel_list[0]})
        
@bot.event
async def on_guild_remove(guild : discord.Guild):
       
        requete_perso_bdd(f'''DELETE FROM channels_discord where server_id = :server_id''', {'server_id' : guild.id})

@bot.event
async def on_member_join(member : discord.Member):
    '''Lorsque un nouveau user rejoint le discord'''
    guild = member.guild
    chan_discord_pm = chan_discord(guild.id)
    channel = bot.get_channel(chan_discord_pm.chan_accueil)
    
    embed = discord.Embed(title=f'Bienvenue chez les {guild.name}',
                          description=f'Hello {member.name}, tu es notre {guild.member_count}ème membre !',
                          color=discord.Color.blue())
    embed.set_thumbnail(url=member.avatar_url)
    embed.set_footer(text=f'Version {Var_version} by Tomlora')
     
    await channel.send(embed=embed)

 
@bot.event
async def on_member_remove(member : discord.Member):
    '''Lorsque un nouveau user quitte le discord'''
    guild = member.guild
    chan_discord_pm = chan_discord(guild.id)
    channel = bot.get_channel(chan_discord_pm.chan_accueil)
    
    embed = discord.Embed(title=f'Départ des {guild.name}',
                          description=f'Au revoir {member.name}, nous sommes encore {guild.member_count} membres !',
                          color=discord.Color.blue())
    embed.set_thumbnail(url=member.avatar_url)
    embed.set_footer(text=f'Version {Var_version} by Tomlora')
    
    await channel.send(embed=embed)




@bot.event
async def on_command_error(ctx: interactions.CommandContext, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Cette commande n'existe pas")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("Tu n'as pas les permissions nécessaires")
    elif isinstance(error, commands.PrivateMessageOnly):
        await ctx.send("Cette commande n'est activée qu'en message privé")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f' {error}')
    else:
        embed = interactions.Embed(title='Erreur', description=f'Description: \n `{error}`',
                              color=242424)
        await ctx.send(embeds=embed)


# -------------------------------- Modération

# Bannissement
@bot.command(name='ban', description='bannir')
@commands.has_permissions(ban_members=True)
async def ban(ctx, user: discord.User, *, reason="Aucune raison n'a été renseignee"):
    await ctx.guild.ban(user, reason=reason)
    await ctx.send(f"{user} à été ban pour la raison suivante : {reason}.")





# Mute




# @bot.command(name='spank')
# async def spank(ctx, member: discord.Member, reason="Aucune raison n'a été renseignée"):
#     if isOwner(ctx):
#         muted_role = await get_muted_role(ctx.guild)
#         database_handler.add_tempmute(member.id, ctx.guild.id,
#                                       datetime.datetime.utcnow() + datetime.timedelta(seconds=60))
#         await member.add_roles(muted_role)
#         if reason == "Aucune raison n'a été renseignée":
#             description = f"{member} a été spank par {ctx.author.name}"
#         else:
#             description = f"{member} a été spank par {ctx.author.name} pour {reason}"
#         embed = discord.Embed(description=description,
#                               color=discord.Colour.from_rgb(255, 255, 0))
#         print("Une personne a été spank")

#         await ctx.send(embed=embed)
#     else:
#         id = ctx.message.author.id
#         muted_role = await get_muted_role(ctx.guild)
#         database_handler.add_tempmute(id, ctx.guild.id,
#                                       datetime.datetime.utcnow() + datetime.timedelta(seconds=60))
#         await ctx.author.add_roles(muted_role)
#         description = f"Bien essayé. {ctx.author.name} s'est prank lui-même"

#         embed = discord.Embed(description=description,
#                               color=discord.Colour.from_rgb(255, 255, 0))
#         print("Une personne s'est spank elle-même")

#         await ctx.send(embed=embed)


        

# # delete msg
# @bot.command(name='clear', description='clear msg')
# @isOwner2()
# async def clear(ctx, number_of_messages: int):
#     messages = await ctx.channel.history(
#         limit=number_of_messages + 1).flatten()  # permet de récupérer l'historique. Flatten permet de créer une liste unique

#     for each_message in messages:
#         await each_message.delete()


bot.load('interactions.ext.files')

for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        # bot.load_extension(f'cogs.{filename[:-3]}')
        bot.load(f'cogs.{filename[:-3]}')

# bot.run(discord_token)
bot.start()
