
from discord.ext import commands
from interactions import CommandContext
from fonctions.channels_discord import chan_discord

chan_discord_id = chan_discord(494217748046544906)
id_tom = chan_discord_id.id_owner
id_dawn = chan_discord_id.id_owner2

# Simple.. A utiliser pour des cmd personnalisées
def isOwner(ctx):
    """A utiliser pour des if dans des commandes personnalisées"""
    return ctx.message.author.id == id_tom

def isOwner_slash(ctx: CommandContext):
    """A utiliser pour des if dans des commandes personnalisées"""
    return ctx.author.id == id_tom

# Plus élaboré (msg général)
def isOwner2():
    """A utiliser en tant que décorateur"""
    async def predicate(ctx):
        if not ctx.message.author.id == id_tom:
            await ctx.send("Cette commande est réservée au propriétaire du bot")
        return ctx.message.author.id == id_tom

    return commands.check(predicate)

# Plus élaboré (msg général)
def isOwner2_slash():
    """A utiliser en tant que décorateur"""
    async def predicate(ctx : CommandContext):
        if not ctx.author.id == id_tom:
            await ctx.send("Cette commande est réservée au propriétaire du bot")
        return ctx.author.id == id_tom

    return commands.check(predicate)

def isAdmin_slash():
    """A utiliser en tant que décorateur"""
    async def predicate(ctx : CommandContext):
        if not ctx.author.id in [id_tom,id_dawn]:
            await ctx.send("Cette commande est réservée au propriétaire du bot")
        return ctx.author.id in [id_tom, id_dawn]

    return commands.check(predicate)