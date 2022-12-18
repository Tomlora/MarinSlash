import os
import interactions
from discord.ext import commands
from discord.utils import get
from requests.exceptions import HTTPError
from fonctions.gestion_bdd import requete_perso_bdd, lire_bdd_perso
from fonctions.channels_discord import chan_discord
from fonctions.params import Version
import traceback




# Duplicate table
# https://popsql.com/learn-sql/postgresql/how-to-duplicate-a-table-in-postgresql



# Paramètres

token = os.environ.get('discord_tk')  # https://www.youtube.com/watch?v=IolxqkL7cD8
id_bot = os.environ.get('bot_marin')




bot = interactions.Client(token=token, intents=interactions.Intents.ALL)


@bot.event
async def on_message_create(message : interactions.Message):
    channel = message.channel_id
    channel = await interactions.get(client=bot,
                                                      obj=interactions.Channel,
                                                      object_id=channel)

    if (channel.type != interactions.ChannelType.DM) and (int(message.author.id) != int(id_bot)):
        
        guild = await message.get_guild()
        role = get(guild.roles, name="Muted")
        
        
        if role.id in message.member.roles:
            await message.delete()
            
            
        
    # await bot.process_commands(
    #     message)  # Overriding the default provided on_message forbids any extra commands from running. To fix this, add a bot.process_commands(message) line at the end of your on_message.

@bot.event
async def on_guild_create(guild : interactions.Guild):


        # on_guild_create peut marcher si le serveur n'est pas disponible, on va donc check si on l'a dans la bdd ou pas.
        if lire_bdd_perso(f'''SELECT server_id from channels_discord where server_id = {int(guild.id)}''', index_col='server_id').shape[1] != 1:
        # si on l'a pas, on l'ajoute
            text_channel_list = []
            for channel in await guild.get_all_channels():
                text_channel_list.append(channel.id)
            
            
            requete_perso_bdd(f'''INSERT INTO channels_discord(
                        server_id, id_owner, id_owner2, chan_pm, chan_tracklol, chan_accueil, chan_twitch, chan_lol, chan_tft, chan_lol_others, role_admin)
                        VALUES (:server_id, :tom, :admin, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :role_admin);
                        INSERT INTO channels_module(server_id)
                        VALUES (:server_id);''',
                    {'server_id' : int(guild.id),
                     'chan' : int(text_channel_list[0]),
                     'tom' : 298418038460514314,
                     'admin' : int(guild.owner_id),
                    'role_admin' : 0})
        
        else: # si on l'a déjà, il vient de rejoindre à nouveau le serveur.
            requete_perso_bdd(f'''UPDATE channels_module SET activation = :activation where server_id = :server_id''', {'server_id' : int(guild.id),
                                                                                                              'activation' : 'true'})
        
@bot.event
async def on_guild_delete(guild : interactions.Guild):
        requete_perso_bdd(f'''UPDATE channels_module SET activation = :activation where server_id = :server_id''', {'server_id' : int(guild.id),
                                                                                                              'activation' : 'false'})

@bot.event
async def on_guild_member_add(member : interactions.Member):
    '''Lorsque un nouveau user rejoint le discord'''


    chan_discord_pm = chan_discord(int(member.guild_id))
    
    guild = await interactions.get(client=bot,
                                    obj=interactions.Guild,
                                    object_id=member.guild_id)
    channel = await interactions.get(client=bot,
                                    obj=interactions.Channel,
                                    object_id=chan_discord_pm.chan_accueil)
    
    embed = interactions.Embed(title=f'Bienvenue chez les {guild.name}',
                          description=f'Hello {member.name}, tu es notre {guild.member_count}ème membre !',
                          color=interactions.Color.blurple())
    embed.set_thumbnail(url=member.avatar_url)
    embed.set_footer(text=f'Version {Version} by Tomlora')

    await channel.send(embeds=embed)

 
@bot.event
async def on_guild_member_remove(member : interactions.Member):
    '''Lorsque un nouveau user quitte le discord'''

    chan_discord_pm = chan_discord(int(member.guild_id))
    guild = await interactions.get(client=bot,
                                    obj=interactions.Guild,
                                    object_id=member.guild_id)
    channel = await interactions.get(client=bot,
                                    obj=interactions.Channel,
                                    object_id=chan_discord_pm.chan_accueil)
    
    embed = interactions.Embed(title=f'Départ des {guild.name}',
                          description=f'Au revoir {member.name}, nous sommes encore {guild.member_count} membres !',
                          color=interactions.Color.blurple())
    embed.set_thumbnail(url=member.avatar_url)
    embed.set_footer(text=f'Version {Version} by Tomlora')

    await channel.send(embeds=embed)



@bot.event
async def on_command_error(ctx: interactions.CommandContext, error : commands.errors):
    
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Cette commande n'existe pas")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("Tu n'as pas les permissions nécessaires")
    elif isinstance(error, commands.PrivateMessageOnly):
        await ctx.send("Cette commande n'est activée qu'en message privé")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f' {error}')
    elif isinstance(error, HTTPError):
        print('httperror')
        await ctx.send('Trop de requêtes')
    else:
        traceback.print_exception(type(error), error, error.__traceback__)
        embed = interactions.Embed(title='Erreur', description=f'Description: \n `{error}`',
                              color=interactions.Color.red())
        await ctx.send(embeds=embed)


# -------------------------------- Modération
       
# # delete msg
# @bot.command(name='clear', description='clear msg')
# @isOwner2()
# async def clear(ctx, number_of_messages: int):
#     messages = await ctx.channel.history(
#         limit=number_of_messages + 1).flatten()  # permet de récupérer l'historique. Flatten permet de créer une liste unique

#     for each_message in messages:
#         await each_message.delete()


# Fix pour intégrer des img locales dans les embed
bot.load('interactions.ext.files')

for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        # bot.load_extension(f'cogs.{filename[:-3]}')
        bot.load(f'cogs.{filename[:-3]}')

# bot.run(discord_token)
bot.start()
