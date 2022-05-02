import asyncio
import linecache
import os

import discord
from discord.ext import commands, tasks
from discord_slash import SlashCommand, SlashContext

Var_version = 2.0

# Paramètres

token = os.environ.get('discord_tk')  # https://www.youtube.com/watch?v=IolxqkL7cD8

discord_token = token
default_intents = discord.Intents.default()
default_intents.members = True  # Vous devez activer les intents dans les paramètres du Bot

params = 'obj/params.txt'

id_bot = os.environ.get('bot_marin')

# `(msg)`  assombrit dans les embed

global id_tom
global chan_pm
global chan_tracklol
global chan_kangourou
global chan_twitch
global chan_lol

id_tom = int(linecache.getline(params, 2).strip())
chan_pm = int(linecache.getline(params, 4).strip())
chan_tracklol = int(linecache.getline(params, 6).strip())
chan_kangourou = int(linecache.getline(params, 8).strip())
chan_twitch = int(linecache.getline(params, 10).strip())
chan_lol = int(linecache.getline(params, 12).strip())

guildid = 494217748046544906
role_admin = 630771107053699132


bot = commands.Bot(command_prefix=";", intents=default_intents)
slash = SlashCommand(bot, sync_commands=True)

bot.remove_command('help')



@bot.group(invoke_without_command=True)
async def help(ctx):
    value_records = "`achievements` - Voir les couronnes acquis par les joueurs \n " \
                    "`achievements_regles` - Conditions pour débloquer des couronnes \n " \
                    "`records_list` - Voir les records détenues par les joueurs \n " \
                    "`pantheon` - Cumul des statistiques"

    value_analyselol = "`analyse` - Faire une analyse de sa game \n " \
                       "`var` - Voir des stats de fin de game \n " \
                       "`var_10games` - Voir des stats de fin de game sur 10 games"

    value_divers = "`ping` - Latence du serveur \n " \
                   "`spank` - Mute une personne durant une minute \n" \
                   "`quiz` - Quizz \n" \
                   "`serverInfo` - Info du serveur \n" \
                   "`versioninfo` - Version du bot"

    value_lolpro = "`abbedagge` - Montre un clip du meilleur joueur de 100t \n " \
                   "`competition` - Stats d'un joueur pro sur la saison \n " \
                   "`competition_game` - Stats d'un joueur pro sur une game \n" \
                   "`liste_joueurs` - Liste des joueurs pro ayant joué dans une compétition \n" \
                   "`loldb` - Contrats des joueurs"

    value_tracker = "`game` - Voir les statistiques d'une game \n" \
                    "`loladd` - Ajoute son compte au tracker \n" \
                    "`lolremove` - Retire son compte du tracker \n " \
                    "`lollist` - Joueurs suivis par le tracker \n" \
                    "`scoring` - Calcule ton score en fonction des stats associés \n " \
                    "`scoring_corr` - Explique comment est calculé le score \n" \
                    "`scoring_score` - % de confiance dans le score affiché"

    value_music = "`join` - Le DJ rejoint ton salon vocal \n" \
                  "`leave` - Le DJ quitte le salon vocal \n" \
                  "`loop` - Le DJ passe la musique en cours en boucle \n" \
                  "`now` - Musique diffusée en cours \n " \
                  "`pause` - Le DJ fait une pause \n " \
                  "`play` - Le DJ joue une nouvelle musique ou l'ajoute à la queue \n" \
                  "`queue` - Liste d'attente des musiques demandées \n" \
                  "`remove` - Retire une musique de la queue \n" \
                  "`shuffle` - ? \n" \
                  "`skip` - Skip une musique (vote pour les utilisateurs) \n" \
                  "`stop` - Le DJ stop la musique \n " \
                  "`summon` - invoque le DJ dans ton salon \n" \
                  "`volume` - Règle le volume"

    em = discord.Embed(title="Help", description="Use ;help <command> pour le détail")
    em.add_field(name="Achievements & Records", value=value_records, inline=False)
    em.add_field(name="AnalyseLoL", value=value_analyselol, inline=False)
    em.add_field(name="Divers", value=value_divers, inline=False)
    em.add_field(name="LoL Pro", value=value_lolpro, inline=False)
    em.add_field(name="Music", value=value_music, inline=False)
    em.add_field(name="Tracker LeagueofLegends", value=value_tracker, inline=False)

    await ctx.send(embed=em)

    # Achievements & Records

@help.command()
async def achievements(ctx):
    em = discord.Embed(title=";achievements", description="Faire une analyse de sa game")
    em.add_field(name="**Syntaxe**", value="`;achievements <records> `")
    em.add_field(name="**Arguments**", value="`records : 'records' pour afficher le graphique des records `", inline=False)
    em.add_field(name="**Exemples**", value="`;achievements\n;achièvements records`",
                 inline=False)

    await ctx.send(embed=em)

@help.command()
async def achievements_regles(ctx):
    em = discord.Embed(title=";achievements_règles", description="Conditions pour débloquer des couronnes")
    em.add_field(name="**Syntaxe**", value="`;achievements_règles`")

    await ctx.send(embed=em)

@help.command()
async def records_list(ctx):
    em = discord.Embed(title=";records_list", description="Voir les records détenus par les joueurs")
    em.add_field(name="**Syntaxe**", value="`;records_list`")

    await ctx.send(embed=em)


@help.command()
async def pantheon(ctx):
    em = discord.Embed(title=";records_list", description="Cumul des statistiques")
    em.add_field(name="**Syntaxe**", value="`;pantheon`")

    await ctx.send(embed=em)

    # AnalyseLoL

@help.command()
async def analyse(ctx):
    em = discord.Embed(title=";analyse", description="Faire une analyse de sa game")
    em.add_field(name="**Syntaxe**", value="`;analyse <Joueur> `")
    em.add_field(name="**Arguments**", value="`Joueur : Pseudo LoL`", inline=False)
    em.add_field(name="**Exemples**", value="`;analyse Tomlora\n;analyse Nami Yeon`",
                 inline=False)

    await ctx.send(embed=em)

@help.command()
async def var(ctx):
    em = discord.Embed(title=";var", description="Voir des stats de fin de game")
    em.add_field(name="**Syntaxe**", value="`;var <Joueur> `")
    em.add_field(name="**Arguments**", value="`Joueur : Pseudo LoL`", inline=False)
    em.add_field(name="**Exemples**", value="`;var Tomlora\n;var Nami Yeon`",
                 inline=False)

    await ctx.send(embed=em)

@help.command()
async def var_10games(ctx):
    em = discord.Embed(title=";var_10games", description="Voir des stats de fin de game sur 10 games")
    em.add_field(name="**Syntaxe**", value="`;var_10games <Joueur> `")
    em.add_field(name="**Arguments**", value="`Joueur : Pseudo LoL`", inline=False)
    em.add_field(name="**Exemples**", value="`;var_10games Tomlora\n;var_10games Nami Yeon`",
                 inline=False)

    await ctx.send(embed=em)

    # Divers

@help.command()
async def ping(ctx):
    em = discord.Embed(title=";ping", description="Latence du serveur")
    em.add_field(name="**Syntaxe**", value="`;ping`")

    await ctx.send(embed=em)

@help.command()
async def spank(ctx):
    em = discord.Embed(title=";spank", description="Mute une personne durant 1 minute")
    em.add_field(name="**Syntaxe**", value="`;spank <mention_discord> `")
    em.add_field(name="**Arguments**", value="`mention_discord : Utilisateur discord`", inline=False)
    em.add_field(name="**Exemples**", value="`;spank @Djingo\n;spank 254826684478547`",
                 inline=False)

    await ctx.send(embed=em)

@help.command()
async def quiz(ctx):
    em = discord.Embed(title=";ping", description="Quizz")
    em.add_field(name="**Syntaxe**", value="`;quiz`")

    await ctx.send(embed=em)

@help.command()
async def serverInfo(ctx):
    em = discord.Embed(title=";serverInfo", description="Info du serveur")
    em.add_field(name="**Syntaxe**", value="`;serverInfo`")

    await ctx.send(embed=em)

@help.command()
async def versioninfo(ctx):
    em = discord.Embed(title=";serverinfo", description="Version du bot")
    em.add_field(name="**Syntaxe**", value="`;versioninfo`")

    await ctx.send(embed=em)

    # LoL Pro
    
@help.command()
async def abbedagge(ctx):
    em = discord.Embed(title=";abbedagge", description="Montre un clip du meilleur joueur de 100t")
    em.add_field(name="**Syntaxe**", value="`;abbedagge`")

    await ctx.send(embed=em)

@help.command()
async def competition(ctx):
    em = discord.Embed(title=";competition", description="Stats d'un joueur pro sur la saison")
    em.add_field(name="**Syntaxe**", value="`;competition <competition> <split> <Joueur> `")
    em.add_field(name="**Arguments**", value="`competition : la competition du joueur \n"
                                             "split : spring ou summer ? \n"
                                             "joueur : Nom du joueur`", inline=False)
    em.add_field(name="**Exemples**", value="`;competition LCS Spring Bwipo\n;competition LCK Spring Faker`",
                 inline=False)

    await ctx.send(embed=em)

@help.command()
async def competition_game(ctx):
    em = discord.Embed(title=";competition_game", description="Stats d'un joueur pro sur une game")
    em.add_field(name="**Syntaxe**", value="`;competition_game <competition> <split> <game> <Joueur> `")
    em.add_field(name="**Arguments**", value="`competition : la competition du joueur \n"
                                             "split : spring ou summer ? \n"
                                             "game : numero de la game \n"
                                             "joueur : Nom du joueur`", inline=False)
    em.add_field(name="**Exemples**", value="`;competition_game LCS Spring 1 Bwipo\n;competition_game LCK Spring 8 Faker`",
                 inline=False)

    await ctx.send(embed=em)

@help.command()
async def liste_joueurs(ctx):
    em = discord.Embed(title=";liste_joueurs", description="Liste des joueurs pro ayant joué dans une compétition \n "
                                                           "Si aucune compétition n'est précisé, alors la LEC/LCS/LFL "
                                                           "sont affichés.")
    em.add_field(name="**Syntaxe**", value="`;liste_joueurs <facultatif : competition> `")
    em.add_field(name="**Arguments**", value="`competition : la competition`", inline=False)
    em.add_field(name="**Exemples**", value="`;liste_joueurs\n;liste_joueurs LEC`",
                 inline=False)

    await ctx.send(embed=em)

@help.command()
async def loldb(ctx):
    em = discord.Embed(title=";loldb", description="Contrats des joueurs")
    em.add_field(name="**Syntaxe**", value="`;loldb`")

    await ctx.send(embed=em)

    # Music

@help.command()
async def join(ctx):
    em = discord.Embed(title=";join", description="Le DJ rejoint ton salon vocal")
    em.add_field(name="**Syntaxe**", value="`;join`")

    await ctx.send(embed=em)

@help.command()
async def leave(ctx):
    em = discord.Embed(title=";leave", description="Le DJ quitte le salon vocal")
    em.add_field(name="**Syntaxe**", value="`;leave`")

    await ctx.send(embed=em)

@help.command()
async def loop(ctx):
    em = discord.Embed(title=";loop", description="Le DJ passe la musique en cours en boucle")
    em.add_field(name="**Syntaxe**", value="`;loop`")

    await ctx.send(embed=em)

@help.command()
async def now(ctx):
    em = discord.Embed(title=";now", description="Musique diffusée en cours")
    em.add_field(name="**Syntaxe**", value="`;now`")

    await ctx.send(embed=em)

@help.command()
async def pause(ctx):
    em = discord.Embed(title=";pause", description="Le DJ fait une pause")
    em.add_field(name="**Syntaxe**", value="`;pause`")

    await ctx.send(embed=em)

@help.command()
async def play(ctx):
    em = discord.Embed(title=";play", description="Le DJ joue une nouvelle musique ou l'ajoute à la queue")
    em.add_field(name="**Syntaxe**", value="`;play <url youtube>`")
    em.add_field(name="**Arguments**", value="`url : url youtube", inline=False)
    em.add_field(name="**Exemples**", value="`;play https://www.youtube.com/watch?v=p1bY3lU4jj8`",
                 inline=False)

    await ctx.send(embed=em)

@help.command()
async def queue(ctx):
    em = discord.Embed(title=";queue", description="Liste d'attente des musiques demandées")
    em.add_field(name="**Syntaxe**", value="`;queue`")

    await ctx.send(embed=em)

@help.command()
async def remove(ctx):
    em = discord.Embed(title=";remove", description="Retire une musique de la queue")
    em.add_field(name="**Syntaxe**", value="`;remove <numero>`")
    em.add_field(name="**Arguments**", value="`numero : numero de la musique dans la queue", inline=False)
    em.add_field(name="**Exemples**", value="`;remove 2`",
                 inline=False)

    await ctx.send(embed=em)

@help.command()
async def skip(ctx):
    em = discord.Embed(title=";skip", description="Vote pour skip un son. 3 votes sont nécessaires")
    em.add_field(name="**Syntaxe**", value="`;skip`")

    await ctx.send(embed=em)

@help.command()
async def summon(ctx):
    em = discord.Embed(title=";summon", description="Invoque le DJ dans ton salon")
    em.add_field(name="**Syntaxe**", value="`;summon`")

    await ctx.send(embed=em)

@help.command()
async def volume(ctx):
    em = discord.Embed(title=";volume", description="Règle le volume")
    em.add_field(name="**Syntaxe**", value="`;volume <1 à 100>`")

    await ctx.send(embed=em)

    # Tracker Leagueoflegends

@help.command()
async def game(ctx):
    em = discord.Embed(title=";game", description="Voir les statistiques d'une game")
    em.add_field(name="**Syntaxe**", value="`;game <Joueur> <numero de la game> <achievements : True/False>`")
    em.add_field(name="**Arguments**", value="`Joueur : pseudo ingame \n"
                                             "numero de la game : 0 à 10 \n"
                                             "achievements : la game doit-elle compter dans les achievements/records ?`", inline=False)
    em.add_field(name="**Exemples**", value="`;game Tomlora 0 False`",
                 inline=False)

    await ctx.send(embed=em)



@help.command()
async def loladd(ctx):
    em = discord.Embed(title=";loladd", description="Ajoute son compte au tracker")
    em.add_field(name="**Syntaxe**", value="`;loladd <Joueur>`")
    em.add_field(name="**Arguments**", value="`Joueur : pseudo ingame`", inline=False)
    em.add_field(name="**Exemples**", value="`;loladd Tomlora`",
                 inline=False)

    await ctx.send(embed=em)

@help.command()
async def lolremove(ctx):
    em = discord.Embed(title=";lolremove", description="Retire son compte au tracker")
    em.add_field(name="**Syntaxe**", value="`;lolremove <Joueur>`")
    em.add_field(name="**Arguments**", value="`Joueur : pseudo ingame`", inline=False)
    em.add_field(name="**Exemples**", value="`;lolremove Tomlora`",
                 inline=False)

    await ctx.send(embed=em)

@help.command()
async def lollist(ctx):
    em = discord.Embed(title=";loldb", description="Joueurs suivis par le tracker")
    em.add_field(name="**Syntaxe**", value="`;lollist`")

    await ctx.send(embed=em)

@help.command()
async def scoring(ctx):
    em = discord.Embed(title=";scoring", description="Calcule ton score en fonction des stats associés")
    em.add_field(name="**Syntaxe**", value="`;scoring <role> <pseudo> <kills> <deaths> <assists> <kp> <wardplaced> <wardkilled> <pink> <cs> <csm>`")
    em.add_field(name="**Arguments**", value="`Role : MID/ADC/SUPPORT \n"
                                             "pseudo : pseudo ingame \n"
                                             "kills : nb de kills \n"
                                             "deaths : nb de morts \n"
                                             "assists : nb d'assists \n"
                                             "kp : kill participation divisé par 100 \n"
                                             "wardplaced : nb de wards posées \n"
                                             "wardskilled : nb de wards détruites \n"
                                             "pink : nb de pinks acheté \n"
                                             "cs : minions tués \n"
                                             "csm : minions tués par minute`", inline=False)
    em.add_field(name="**Exemples**", value="`;scoring SUPPORT NamiYeon 1 5 18 0.56 51 10 12 14 0.41`",
                 inline=False)

    await ctx.send(embed=em)

@help.command()
async def scoring_corr(ctx):
    em = discord.Embed(title=";scoring_corr", description="Explique comment est calculé ton score")
    em.add_field(name="**Syntaxe**", value="`;scoring_corr <role>`")
    em.add_field(name="**Arguments**", value="`Role : MID/ADC/SUPPORT", inline=False)
    em.add_field(name="**Exemples**", value="`;scoring_corr SUPPORT`",
                 inline=False)

    await ctx.send(embed=em)

@help.command()
async def scoring_score(ctx):
    em = discord.Embed(title=";scoring_score", description="% de confiance dans le score affiché")
    em.add_field(name="**Syntaxe**", value="`;scoring_score <role>`")
    em.add_field(name="**Arguments**", value="`Role : MID/ADC/SUPPORT", inline=False)
    em.add_field(name="**Exemples**", value="`;scoring_score SUPPORT`",
                 inline=False)

    await ctx.send(embed=em)


@bot.event
async def on_message(message):
    if not isinstance(message.channel, discord.abc.PrivateChannel):
        role = discord.utils.get(message.guild.roles, name="Muted")

    if (isinstance(message.channel, discord.abc.PrivateChannel)) and (message.author.id != id_bot):
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
async def createMutedRole(ctx):
    mutedRole = await ctx.guild.create_role(name="Muted",
                                            permissions=discord.Permissions(
                                                send_messages=False,
                                                speak=False),
                                            reason="Creation du role Muted pour mute des gens.")
    for channel in ctx.guild.channels:
        await channel.set_permissions(mutedRole, send_messages=False, speak=False)
    return mutedRole


async def getMutedRole(ctx):
    roles = ctx.guild.roles
    for role in roles:
        if role.name == "Muted":
            return role

    return await createMutedRole(ctx)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Cette commande n'existe pas")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("Tu n'as pas les permissions nécessaires")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f' {error}')
    else:
        embed = discord.Embed(title='Erreur', description=f'Description: \n `{error}`',
                              timestamp=ctx.message.created_at, color=242424)
        await ctx.send(embed=embed)


# Général

# @bot.command()
# async def cuisiner(ctx):
#     await ctx.send("Envoyez le plat que vous voulez cuisiner")
#
#     def checkMessage(message):
#         return message.author == ctx.message.author and ctx.message.channel == message.channel
#
#     try:
#         recette = await bot.wait_for("message", timeout=10, check=checkMessage)
#     except:
#         await ctx.send("Veuillez réitérer la commande.")
#         return
#     message = await ctx.send(
#         f"La préparation de {recette.content} va commencer. Veuillez valider en réagissant avec ✅. Sinon réagissez avec ❌")
#     await message.add_reaction("✅")
#     await message.add_reaction("❌")
#
#     def checkEmoji(reaction, user):
#         return ctx.message.author == user and message.id == reaction.message.id and (
#                 str(reaction.emoji) == "✅" or str(reaction.emoji) == "❌")
#
#     try:
#         reaction, user = await bot.wait_for("reaction_add", timeout=10, check=checkEmoji)
#         if reaction.emoji == "✅":
#             await ctx.send("La recette a démarré.")
#         else:
#             await ctx.send("La recette a bien été annulé.")
#     except:
#         await ctx.send("La recette a bien été annulé.")


# -------------------------------- Modération

# Bannissement
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, user: discord.User, *, reason="Aucune raison n'a été renseignee"):
    await ctx.guild.ban(user, reason=reason)
    await ctx.send(f"{user} à été ban pour la raison suivante : {reason}.")


# Simple.. A utiliser pour des cmd personnalisées
def isOwner(ctx):
    return ctx.message.author.id == id_tom


# Plus élaboré (msg général)
def isOwner2():
    async def predicate(ctx):
        if not ctx.message.author.id == id_tom:
            await ctx.send("Cette commande est réservée au propriétaire du bot")
        return ctx.message.author.id == id_tom

    return commands.check(predicate)


# Mute

@bot.command()
@commands.has_permissions(ban_members=True)
async def mute(ctx, member: discord.Member, *, reason="Aucune raison n'a été renseigné"):
    mutedRole = await getMutedRole(ctx)
    await member.add_roles(mutedRole, reason=reason)
    await ctx.send(f"{member.mention} a été mute !")


@bot.command()
@commands.has_permissions(ban_members=True)
async def unmute(ctx, member: discord.Member, *, reason="Aucune raison n'a été renseigné"):
    mutedRole = await getMutedRole(ctx)
    await member.remove_roles(mutedRole, reason=reason)
    await ctx.send(f"{member.mention} a été unmute !")


from discord.utils import get
import datetime
from Data.database_handler import DatabaseHandler

database_handler = DatabaseHandler("database.db")


@bot.event
async def get_muted_role(guild: discord.Guild) -> discord.Role:
    role = get(guild.roles, name="Muted")
    if role is not None:
        return role
    else:
        permissions = discord.Permissions(send_messages=False)
        role = await guild.create_role(name="Muted", permissions=permissions)
        return role


@bot.command()
@commands.has_permissions(ban_members=True)
async def mute_time(ctx, member: discord.Member, seconds: int):
    muted_role = await get_muted_role(ctx.guild)
    database_handler.add_tempmute(member.id, ctx.guild.id,
                                  datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds))
    await member.add_roles(muted_role)
    await ctx.send(f"{member.mention} a été muté pour {seconds} secondes ! 🎙")


@bot.command()
async def spank(ctx, member: discord.Member, reason="Aucune raison n'a été renseignée"):
    if isOwner(ctx):
        muted_role = await get_muted_role(ctx.guild)
        database_handler.add_tempmute(member.id, ctx.guild.id,
                                      datetime.datetime.utcnow() + datetime.timedelta(seconds=60))
        await member.add_roles(muted_role)
        if reason == "Aucune raison n'a été renseignée":
            description = f"{member} a été spank par {ctx.author.name}"
        else:
            description = f"{member} a été spank par {ctx.author.name} pour {reason}"
        embed = discord.Embed(description=description,
                              color=discord.Colour.from_rgb(255, 255, 0))
        print("Une personne a été spank")

        await ctx.send(embed=embed)
    else:
        id = ctx.message.author.id
        print(id)
        muted_role = await get_muted_role(ctx.guild)
        database_handler.add_tempmute(id, ctx.guild.id,
                                      datetime.datetime.utcnow() + datetime.timedelta(seconds=60))
        await ctx.author.add_roles(muted_role)
        description = f"Bien essayé. {ctx.author.name} s'est prank lui-même"

        embed = discord.Embed(description=description,
                              color=discord.Colour.from_rgb(255, 255, 0))
        print("Une personne s'est spank elle-même")

        await ctx.send(embed=embed)


@tasks.loop(minutes=1, count=None)
async def check_for_unmute():
    # print("Checking en cours...")
    for guild in bot.guilds:
        active_tempmute = database_handler.active_tempmute_to_revoke(guild.id)
        if len(active_tempmute) > 0:
            muted_role = await get_muted_role(guild)
            for row in active_tempmute:
                member = guild.get_member(row["user_id"])
                database_handler.revoke_tempmute(row["id"])
                await member.remove_roles(muted_role)
                print('Une personne a été démuté')


# delete msg
@bot.command()
@isOwner2()
async def clear(ctx, number_of_messages: int):
    messages = await ctx.channel.history(
        limit=number_of_messages + 1).flatten()  # permet de récupérer l'historique. Flatten permet de créer une liste unique

    for each_message in messages:
        await each_message.delete()


# -------------------------------------- Import catégories

@bot.command()
@isOwner2()
async def load(ctx, name=None):
    if name:
        bot.load_extension(f'cogs.{name}')
        await ctx.send(f"Extension {name} chargée")


@bot.command()
@isOwner2()
async def unload(ctx, name=None):
    if name:
        bot.unload_extension(f'cogs.{name}')
        await ctx.send(f"Extension {name} déchargée")


@bot.command()
@isOwner2()
async def reload(ctx, name=None):
    if name:
        try:
            bot.reload_extension(f'cogs.{name}')
            await ctx.send(f"L'extension {name} a été rechargée avec succès")
        except:
            bot.load_extension(f'cogs.{name}')
            await ctx.send(f"L'extension {name} a été chargée")


for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'cogs.{filename[:-3]}')
#
# # ---- Test
#
# @bot.command()
# @isOwner2()
# async def mention(ctx):
#     await ctx.send(f'<@{id_tom}>')
#
#
# @bot.command()
# @isOwner2()
# async def question(ctx):
#     await ctx.send('Qui est PD ?')
#     channel = ctx.message.channel
#
#     def check(m):
#         return m.content == "Dawn" and m.channel == channel
#
#     try:
#         msg = await bot.wait_for('message', timeout=60, check=check)
#         await channel.send('Bonne réponse !'.format(msg))
#     except asyncio.TimeoutError:
#         await msg.delete()
#         await ctx.send("Annulé")


bot.run(discord_token)
