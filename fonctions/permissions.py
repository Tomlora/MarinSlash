from interactions import CommandContext
from fonctions.channels_discord import chan_discord




def isOwner_slash(ctx: CommandContext):
    """A utiliser pour des if dans des commandes personnalisées"""
    chan_discord_id = chan_discord(int(ctx.guild.id))
    id_tom = chan_discord_id.id_owner
    id_owner2 = chan_discord_id.id_owner2
    return ctx.author.id in [id_tom, id_owner2]

# Plus élaboré (msg général)

