
from discord.ext import commands
from interactions import CommandContext
from fonctions.channels_discord import chan_discord




def isOwner_slash(ctx: CommandContext):
    """A utiliser pour des if dans des commandes personnalisées"""
    chan_discord_id = chan_discord(int(ctx.guild.id))
    id_tom = chan_discord_id.id_owner
    id_owner2 = chan_discord_id.id_owner2
    return ctx.author.id in [id_tom, id_owner2]

# Plus élaboré (msg général)


def isOwner2_slash():
    """A utiliser en tant que décorateur"""
    async def predicate(ctx: CommandContext):
        chan_discord_id = chan_discord(int(ctx.guild.id))
        id_tom = chan_discord_id.id_owner
        id_owner2 = chan_discord_id.id_owner2
        if not ctx.author.id in [id_tom, id_owner2]:
            await ctx.send("Cette commande est réservée au propriétaire du bot")
        return ctx.author.id in [id_tom, id_owner2]

    return commands.check(predicate)
