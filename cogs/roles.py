import interactions
from interactions import Extension, SlashContext, SlashCommandChoice, SlashCommandOption, slash_command, listen
from fonctions.gestion_bdd import get_guild_data, lire_bdd_perso
from discord.utils import get
from fonctions.channels_discord import identifier_role_by_name
from fonctions.params import Version, saison

# Activity au lancement du bot


class roles(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot
        
    @listen()
    async def on_startup(self):
        
        role_ranked = {'NON-CLASSE' : '#000000',
                       'FER' : '#686868',
                       'BRONZE' : '#a37f69',
                       'SILVER' : '#c0c0c0',
                       'GOLD' : '#ffca00',
                       'PLATINUM' : '#34c064',
                       'EMERALD' : '#45d3c3',
                       'DIAMOND' : '#398aeb',
                       'MASTER' : '#ba67da',
                       'GRANDMASTER' : '#e64758',
                       'CHALLENGER' : '#20f1f8'}
        
        data = get_guild_data()

        for server_id in data.fetchall():

            server : interactions.Guild = await self.bot.fetch_guild(server_id[0])
        
            liste_roles = []
            for role in server.roles:
                liste_roles.append(role.name)
                    
            for name, color in role_ranked.items():  
                    
                if not name in liste_roles:  
                    role_in_ranked = await server.create_role(name=name,
                                                                color=interactions.Color.from_hex(color),
                                                                permissions=None,
                                                                mentionable=True,
                                                                reason="Ranks LoL")
                    for channel in server.channels:
                        try:
                            await channel.set_permission(role_in_ranked, view_channel=False, send_messages=False, speak=False)
                        except:
                            pass



    @slash_command(name='lol_attribuer_role', description='attribuer un role',
                   default_member_permissions=interactions.Permissions.MANAGE_GUILD)
    async def attribuer_role(self, ctx:SlashContext):     
        
        df = lire_bdd_perso(f'''SELECT tracker.discord, suivi_s{saison}.index, suivi_s{saison}.tier from tracker
                    INNER JOIN suivi_s{saison} on suivi_s{saison}.index = tracker.index 
                    WHERE tracker.server_id = {int(ctx.guild.id)} ''', index_col='discord').transpose()  
        
        for discord_id, data in df.iterrows():
            member = await ctx.guild.fetch_member(discord_id)
            old_role = await identifier_role_by_name(ctx.guild, 'BRONZE')
            await member.remove_role(old_role)
            role = await identifier_role_by_name(ctx.guild, data['tier'].upper())
            
            await member.add_role(role)
            await ctx.send(f'Le role {role.name} a été attribué à {member.global_name} | {member.nickname}')
        
        

def setup(bot):
    roles(bot)
