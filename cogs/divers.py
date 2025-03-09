from fonctions.permissions import *
from datetime import datetime, timedelta
from fonctions.mute import DatabaseHandler
from interactions import SlashCommandOption, Extension, SlashContext, Task, IntervalTrigger
import interactions
from fonctions.gestion_bdd import get_guild_data
import os
from interactions import listen, slash_command
from fonctions.gestion_bdd import requete_perso_bdd
from fonctions.permissions import isOwner_slash
import re
import pytz


class Divers(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self.database_handler = DatabaseHandler()
        self.api_key_openai = os.environ.get('openai')

    @listen()
    async def on_startup(self):

        self.check_for_unmute.start()


    @listen()
    async def createMutedRole(self, ctx: SlashContext):
        
        mutedRole = await ctx.guild.create_role(name="Muted",
                                                permissions=interactions.Permissions(
                                                    send_messages=False,
                                                    speak=False),
                                                reason="Creation du role Muted pour mute des gens.")
        for channel in await ctx.guild.get_all_channels():
            await channel.set_permissions(mutedRole, send_messages=False, speak=False)
        return mutedRole

    @listen()
    async def getMutedRole(self, ctx):
        roles = ctx.guild.roles
        for role in roles:
            if role.name == "Muted":
                return role

        return await self.createMutedRole(ctx)

    @Task.create(IntervalTrigger(minutes=1))
    async def check_for_unmute(self):
        # print("Checking en cours...")
        data = get_guild_data()
        for server_id in data.fetchall():
            
            guild = await self.bot.fetch_guild(server_id[0])

            active_tempmute = self.database_handler.active_tempmute_to_revoke(
                int(guild.id))
            if len(active_tempmute) > 0:
                muted_role = await self.get_muted_role(guild)
                for row in active_tempmute:
                    member = await guild.get_member(row["user_id"])
                    self.database_handler.revoke_tempmute(row["id"])
                    await member.remove_role(role=muted_role, guild_id=guild.id)


    @slash_command(name="ping", description="Latence du bot")
    async def ping(self, ctx: SlashContext):
        await ctx.send(
            f"pong \n Latence : `{round(float(self.bot.latency), 3)}` ms")

    @slash_command(name='spank',
                                    description='spank un membre',
                                    default_member_permissions=interactions.Permissions.MANAGE_GUILD,
                                    options=[
                                        SlashCommandOption(
                                            name='member',
                                            description='membre discord',
                                            type=interactions.OptionType.USER,
                                            required=True),
                                        SlashCommandOption(
                                            name='reason',
                                            description='motif du spank',
                                            type=interactions.OptionType.STRING,
                                            required=False
                                        )])
    async def spank_slash(self,
                          ctx: SlashContext,
                          member: interactions.User,
                          reason="Aucune raison n'a été renseignée"):
        
        tz = pytz.timezone('Europe/Paris')
        if isOwner_slash(ctx):

            muted_role = await self.get_muted_role(ctx.guild)
            self.database_handler.add_tempmute(int(member.id), int(ctx.guild_id),
                                               datetime.now(tz) + timedelta(seconds=60))
            await member.add_role(role=muted_role, guild_id=ctx.guild_id)
            if reason == "Aucune raison n'a été renseignée":
                description = f"{member.mention} a été spank par {ctx.author.nickname}"
            else:
                description = f"{member.mention} a été spank par {ctx.author.nickname} pour {reason}"
            embed = interactions.Embed(description=description,
                                       color=interactions.Color.random())
            print("Une personne a été spank")

            await ctx.send(embeds=embed)
        else:
            id = ctx.author.id
            muted_role = await self.get_muted_role(ctx.guild)
            self.database_handler.add_tempmute(int(id), int(ctx.guild_id),
                                               datetime.now(tz) + timedelta(seconds=60))
            await ctx.author.add_role(role=muted_role, guild_id=ctx.guild_id)
            description = f"Bien essayé. {ctx.author.nickname} s'est prank lui-même"

            embed = interactions.Embed(description=description,
                                       color=interactions.Color.random())
            print("Une personne s'est spank elle-même")

            await ctx.send(embeds=embed)



    @slash_command(name="mute",
                                    description="mute someone for x secondes",
                                    default_member_permissions=interactions.Permissions.MUTE_MEMBERS,
                                    options=[
                                        SlashCommandOption(
                                            name="member",
                                            description="membre du discord",
                                            type=interactions.OptionType.USER,
                                            required=True),
                                        SlashCommandOption(
                                            name="seconds",
                                            description="Temps de mute en secondes",
                                            type=interactions.OptionType.INTEGER,
                                            required=True),
                                        SlashCommandOption(
                                            name="reason",
                                            description="reason",
                                            type=interactions.OptionType.STRING,
                                            required=False
                                        )
                                    ])
    async def mute_time(self,
                        ctx: SlashContext,
                        member: interactions.Member,
                        seconds: int,
                        reason: str = "Aucune raison n'a été renseignée"):


        muted_role = await self.get_muted_role(ctx.guild)
        self.database_handler.add_tempmute(int(member.id), int(ctx.guild_id),
                                               datetime.now(pytz.timezone('Europe/Paris')) + timedelta(seconds=seconds))
        await member.add_role(role=muted_role, guild_id=ctx.guild_id)

        if reason == "Aucune raison n'a été renseignée":
            description = f"{member.mention} a été muté pour {seconds} secondes ! 🎙"
        else:
            description = f"{member.mention} a été muté pour {seconds} secondes ! 🎙"
        embed = interactions.Embed(description=description,
                                       color=interactions.Color.random())

        await ctx.send(embeds=embed)

    @slash_command(name='my_cool_modal')
    async def my_cool_modal(self, ctx : SlashContext):
        my_modal = interactions.Modal(
            interactions.ShortText(label="Short Input Text", custom_id="short_text"),
            interactions.ParagraphText(label="Long Input Text", custom_id="long_text"),
            title="My Modal",
            custom_id="my_modal",
        )
        await ctx.send_modal(modal=my_modal)
        modal_ctx: interactions.ModalContext = await ctx.bot.wait_for_modal(my_modal)

        # extract the answers from the responses dictionary
        short_text = modal_ctx.responses["short_text"]
        long_text = modal_ctx.responses["long_text"]

        await modal_ctx.send(f"Short text: {short_text}, Paragraph text: {long_text}", ephemeral=True)
        
    
    @slash_command(name='steal',
                   description='steal_emote',
                   options=[SlashCommandOption(name='id_message',
                                               description='Url du message dans le même salon',
                                               type=interactions.OptionType.STRING,
                                               required=True)])
    
    async def steal_emote(self,
                          ctx : SlashContext,
                          id_message : str):
        
    
        message = await ctx.channel.fetch_message(id_message)

        # Regex pour détecter les emojis personnalisés
        emoji_pattern = re.compile(r"<(a?):(\w+):(\d+)>")
        matches = emoji_pattern.findall(message.content)

        if not matches:
            await ctx.send("Aucun emoji personnalisé trouvé dans ce message.")
            return
        
        emoji_links = []
        for animated, name, emoji_id in matches:
            file_format = "gif" if animated else "png"
            url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{file_format}"
            emoji_links.append(f"{name}: {url}")

        await ctx.send("\n".join(emoji_links))
        
            
    @slash_command(name="ban_list",
                                    description="Gère la ban list",
                                    default_member_permissions=interactions.Permissions.MANAGE_GUILD,
                                    options=[
                                        SlashCommandOption(
                                            name="utilisateur",
                                            description="membre discord",
                                            type=interactions.OptionType.USER,
                                            required=True),
                                        SlashCommandOption(name='action',
                                               description='true = banned',
                                               type=interactions.OptionType.BOOLEAN,
                                               required=True),
                                    ])
    async def modifier_banlist(self,
                        ctx: SlashContext,
                        utilisateur : interactions.User,
                        action:bool):
        


        discord_id = int(utilisateur.id)
        row_affected = requete_perso_bdd('UPDATE tracker SET banned = :action where discord = :discord_id',
                                             dict_params={'action' : action, 'discord_id' : str(discord_id)},
                                             get_row_affected=True) 
            
        if row_affected > 0:
            await ctx.send(f'Modification effectuée pour {utilisateur.mention}')
            if action:
                await utilisateur.send('Tu as été banni des fonctionnalités de Marin.')
            else:
                await utilisateur.send('Tu as été débanni des fonctionnalités de Marin.')
        else:
            await ctx.send('Pas de compte associé')


        
                    

            
def setup(bot):
    Divers(bot)
