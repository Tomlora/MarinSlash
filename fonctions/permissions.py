from interactions import SlashContext
from fonctions.channels_discord import chan_discord




def isOwner_slash(ctx: SlashContext):
    """A utiliser pour des if dans des commandes personnalisées"""
    chan_discord_id = chan_discord(int(ctx.guild.id))
    id_tom = chan_discord_id.id_owner
    id_owner2 = chan_discord_id.id_owner2
    return ctx.author.id in [id_tom, id_owner2]

def isOwner_or_mod_slash(ctx: SlashContext):
    """A utiliser pour des if dans des commandes personnalisées"""
    chan_discord_id = chan_discord(int(ctx.guild.id))
    id_tom = chan_discord_id.id_owner
    id_owner2 = chan_discord_id.id_owner2
    mod_role = chan_discord_id.role_admin
    return (ctx.author.id in [id_tom, id_owner2] or mod_role in ctx.author.roles) 

# Plus élaboré (msg général)

