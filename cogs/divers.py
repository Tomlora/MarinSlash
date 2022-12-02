import asyncio
from fonctions.permissions import *
from discord.utils import get
import datetime
from fonctions.mute import DatabaseHandler
from interactions import Option, Extension, CommandContext
import interactions
from interactions.ext.wait_for import wait_for, wait_for_component, setup as stp
from interactions.ext.tasks import IntervalTrigger, create_task
import datetime
from fonctions.gestion_bdd import get_guild_data
import cv2
import numpy as np
import os
import io


class Divers(Extension):
    def __init__(self, bot):
        self.bot : interactions.Client = bot
        stp(self.bot)
        self.database_handler = DatabaseHandler()
        
    @interactions.extension_listener
    async def on_start(self):

        self.task1 = create_task(IntervalTrigger(60))(self.check_for_unmute)
        self.task1.start()
        
        
        
    @interactions.extension_listener
    async def createMutedRole(self, ctx:CommandContext):
        mutedRole = await ctx.guild.create_role(name="Muted",
                                                permissions=interactions.Permissions(
                                                    send_messages=False,
                                                    speak=False),
                                                reason="Creation du role Muted pour mute des gens.")
        for channel in await ctx.guild.get_all_channels():
            await channel.set_permissions(mutedRole, send_messages=False, speak=False)
        return mutedRole

    @interactions.extension_listener
    async def getMutedRole(self,ctx):
        roles = ctx.guild.roles
        for role in roles:
            if role.name == "Muted":
                return role

        return await self.createMutedRole(ctx)    

    

    async def check_for_unmute(self):
        # print("Checking en cours...")
        data = get_guild_data()
        for server_id in data.fetchall():
            
            guild = await interactions.get(client=self.bot,
                                                      obj=interactions.Guild,
                                                      object_id=server_id[0])        

            active_tempmute = self.database_handler.active_tempmute_to_revoke(int(guild.id))
            if len(active_tempmute) > 0:
                muted_role = await self.get_muted_role(guild)
                for row in active_tempmute:
                    member = await guild.get_member(row["user_id"])
                    self.database_handler.revoke_tempmute(row["id"])
                    await member.remove_role(role=muted_role, guild_id=guild.id)

    @interactions.extension_command(name="hello", description="Saluer le bot")
    async def hello(self, ctx : CommandContext):
        buttons = [
            interactions.Button(
                style=interactions.ButtonStyle.PRIMARY,
                label="Marin",
                custom_id="Marin",
                emoji=interactions.Emoji(name="😂")
            ),
            interactions.Button(
                style=interactions.ButtonStyle.SUCCESS,
                label="Tomlora",
                custom_id="non",
                emoji=interactions.Emoji(name="👑")
            )
        ]
        
        await ctx.send("Qui est le meilleur joueur ici ?",
                                    components=buttons)

        async def check(button_ctx):
            # return m.author_id == ctx.author.id and m.origin_message.id == fait_choix.id
                if int(button_ctx.author.user.id) == int(ctx.author.user.id):
                    return True
                await ctx.send("I wasn't asking you!", ephemeral=True)
                return False
        
            
        try:
            # Like before, this wait_for listens for a certain event, but is made specifically for components.
            # Although, this returns a new Context, independent of the original context.
            button_ctx: interactions.ComponentContext = await self.bot.wait_for_component(
                components=buttons, check=check, timeout=30
            )
            await button_ctx.send(button_ctx.data.custom_id)
            # With this new Context, you're able to send a new response.
        except asyncio.TimeoutError:
            # When it times out, edit the original message and remove the button(s)
            return await ctx.edit(components=[])

    @interactions.extension_command(name="quiz", description="Reponds au quizz")
    async def quiz(self, ctx : CommandContext):
        select = interactions.SelectMenu(
            options=[
                interactions.SelectOption(label="Dawn", value="1", emoji=interactions.Emoji(name='😂')),
                interactions.SelectOption(label="Exorblue", value="2", emoji=interactions.Emoji(name='😏')),
                interactions.SelectOption(label="Tomlora", value="3", emoji=interactions.Emoji(name='💛')),
                interactions.SelectOption(label="Ylarabka", value="4", emoji=interactions.Emoji(name='🦊')),
                interactions.SelectOption(label="Djingo le egay", value="5", emoji=interactions.Emoji(name='💚'))
            ],
            custom_id='quizz_selected',
            placeholder="Choisis un emoji...",
            min_values=1,
            max_values=1
        )
        await ctx.send("Qui est le meilleur joueur ici ?",
                                    components=select)

        async def check(button_ctx):
                if int(button_ctx.author.user.id) == int(ctx.author.user.id):
                    return True
                await ctx.send("I wasn't asking you!", ephemeral=True)
                return False
            
        try:
            button_ctx: interactions.ComponentContext = await self.bot.wait_for_component(
                components=select, check=check, timeout=30
            )
            if button_ctx.data.values[0] == "3":
                await button_ctx.send("Bonne réponse ! 🦊")
            else:
                await button_ctx.send("Mauvaise réponse... 😒")
            # With this new Context, you're able to send a new response.
        except asyncio.TimeoutError:
            # When it times out, edit the original message and remove the button(s)
            return await ctx.edit(components=[])


    @interactions.extension_command(name="ping", description="Latence du bot")
    async def ping(self, ctx : CommandContext):
        await ctx.send(
            f"pong \n Latence : `{round(float(self.bot.latency), 3)}` ms")
      
    
    @interactions.extension_command(name='spank',
                                    description='spank un membre',
                                    options=[Option(
                                        name='member',
                                        description='membre discord',
                                        type=interactions.OptionType.USER,
                                        required=True),
                                             Option(
                                        name='reason',
                                        description='motif du spank',
                                        type=interactions.OptionType.STRING,
                                        required=False
                                    )])
    
    async def spank_slash(self, ctx:CommandContext, member: interactions.Member, reason="Aucune raison n'a été renseignée"):
        if isOwner_slash(ctx):

            muted_role = await self.get_muted_role(ctx.guild)
            self.database_handler.add_tempmute(int(member.id), int(ctx.guild_id),
                                        datetime.datetime.utcnow() + datetime.timedelta(seconds=60))
            await member.add_role(role=muted_role, guild_id=ctx.guild_id)
            if reason == "Aucune raison n'a été renseignée":
                description = f"{member.name} a été spank par {ctx.author.name}"
            else:
                description = f"{member.name} a été spank par {ctx.author.name} pour {reason}"
            embed = interactions.Embed(description=description,
                                color=interactions.Color.red())
            print("Une personne a été spank")

            await ctx.send(embeds=embed)
        else:
            id = ctx.author.id
            muted_role = await self.get_muted_role(ctx.guild)
            self.database_handler.add_tempmute(int(id), int(ctx.guild_id),
                                        datetime.datetime.utcnow() + datetime.timedelta(seconds=60))
            await ctx.author.add_role(role=muted_role, guild_id=ctx.guild_id)
            description = f"Bien essayé. {ctx.author.name} s'est prank lui-même"

            embed = interactions.Embed(description=description,
                                color=interactions.Color.red())
            print("Une personne s'est spank elle-même")

            await ctx.send(embeds=embed)
            
    @interactions.extension_command(name="test_channel", description="test_channel")
    async def test_channel(self, ctx : CommandContext):
        if isOwner_slash(ctx):
            
            permission = [interactions.Overwrite(
                                        id=int(ctx.author.id),
                                        type=1, # user
                                        allow=interactions.Permissions.VIEW_CHANNEL | interactions.Permissions.SEND_MESSAGES | interactions.Permissions.ATTACH_FILES),
                         interactions.Overwrite(
                                        id=ctx.guild_id, # le rôle everyone a le même id que le serveur
                                        type=0, # role
                                        deny=interactions.Permissions.VIEW_CHANNEL),
                         interactions.Overwrite(
                             id=773517279328993290,
                             type=0, # role
                             allow=interactions.Permissions.VIEW_CHANNEL | interactions.Permissions.SEND_MESSAGES | interactions.Permissions.ATTACH_FILES)]
            

            await ctx.guild.create_channel(name="chan de test",
                                     type=interactions.ChannelType.GUILD_TEXT,
                                     # Catégorie où le channel est crée
                                     parent_id=450771619648897034,
                                     # Permission
                                    permission_overwrites=permission)
            
            # await new_chan.send('nouveau channel')
        else:
            await ctx.send("Tu n'as pas les droits")
            


    # @bot.command(name='mute', description='mute someone')
    # @commands.has_permissions(ban_members=True)
    # async def mute(self, ctx, member: discord.Member, *, reason="Aucune raison n'a été renseigné"):
    #     mutedRole = await self.getMutedRole(ctx)
    #     await member.add_roles(mutedRole, reason=reason)
    #     await ctx.send(f"{member.mention} a été mute !")


    # @bot.command(name='unmute', description='unmute someone')
    # @commands.has_permissions(ban_members=True)
    # async def unmute(self, ctx, member: discord.Member, *, reason="Aucune raison n'a été renseigné"):
    #     mutedRole = await self.getMutedRole(ctx)
    #     await member.remove_roles(mutedRole, reason=reason)
    #     await ctx.send(f"{member.mention} a été unmute !")
    
    @interactions.extension_listener
    async def get_muted_role(self, guild: interactions.Guild) -> interactions.Role:
        
        role = get(guild.roles, name="Muted")
        if role is not None:
            return role
        else:
            permissions = interactions.Permissions(send_messages=False)
            role = await guild.create_role(name="Muted", permissions=permissions)
            return role


    @interactions.extension_command(name="mute_time",
                                    description="mute someone for x secondes",
                                    options=[Option(
                                        name="member",
                                        description="membre du discord",
                                        type=interactions.OptionType.USER,
                                        required=True),
                                             Option(
                                        name="seconds",
                                        description="Temps de mute en secondes",
                                        type=interactions.OptionType.INTEGER,
                                        required=True),
                                             Option(
                                        name="reason",
                                        description="reason",
                                        type=interactions.OptionType.STRING,
                                        required=False
                                             )
                                    ])
    async def mute_time(self, ctx : CommandContext, member: interactions.Member, seconds: int, reason :str = "Aucune raison n'a été renseignée"):
    
        if await ctx.has_permissions(interactions.Permissions.MUTE_MEMBERS):
            muted_role = await self.get_muted_role(ctx.guild)
            self.database_handler.add_tempmute(int(member.id), int(ctx.guild_id),
                                        datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds))
            await member.add_role(role=muted_role, guild_id=ctx.guild_id)

            if reason == "Aucune raison n'a été renseignée":
                description = f"{member.mention} a été muté pour {seconds} secondes ! 🎙"
            else:
                description = f"{member.mention} a été muté pour {seconds} secondes ! 🎙"
            embed = interactions.Embed(description=description,
                                color=interactions.Color.red())
            
            await ctx.send(embeds=embed)
    
    @interactions.extension_command(name='my_cool_modal')
    async def my_cool_modal(self, ctx):
        modal =interactions.Modal(
        title="Application Form",
        custom_id="mod_app_form",
        components=[interactions.TextInput(
            style=interactions.TextStyleType.SHORT,
            label='Combien font 1+1 ?',
            custom_id='math',
            min_length=1,
            max_length=3)],
        )
    
        await ctx.popup(modal)
    
    @interactions.extension_modal('mod_app_form')
    async def modal_response(self, ctx, response:str):
        await ctx.send(f'Tu as répondu {response}')
        
    @interactions.extension_command(name='remove_background',
                                    description="supprime le background d'une image",
                                    options=[Option(
                                        name='image',
                                        description='image au format png ou jpg',
                                        type=interactions.OptionType.ATTACHMENT,
                                        required=True
                                    )])
    async def remove_background(self, ctx:CommandContext, image:interactions.Attachment):
        
        if not image.filename.endswith('.png') and not image.filename.endswith('.jpg'):
            return await ctx.send("Incompatible. Il faut une image au format png ou jpg")
        
        await ctx.defer(ephemeral=False)
        
        file = await image.download()
        
        with open('image_original.png', 'wb') as outfile:
            outfile.write(file.getbuffer())
        
        # load image
        img = cv2.imread('image_original.png')
        
        # convert to graky
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # threshold input image as mask
        mask = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY)[1]

        # negate mask
        mask = 255 - mask

        # apply morphology to remove isolated extraneous noise
        # use borderconstant of black since foreground touches the edges
        kernel = np.ones((3,3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # anti-alias the mask -- blur then stretch
        # blur alpha channel
        mask = cv2.GaussianBlur(mask, (0,0), sigmaX=2, sigmaY=2, borderType = cv2.BORDER_DEFAULT)

        # linear stretch so that 127.5 goes to 0, but 255 stays 255
        mask = (2*(mask.astype(np.float32))-255.0).clip(0,255).astype(np.uint8)

        # put mask into alpha channel
        result = img.copy()
        result = cv2.cvtColor(result, cv2.COLOR_BGR2BGRA)
        result[:, :, 3] = mask

        # save resulting masked image
        cv2.imwrite('image.png', result)
        
        files = interactions.File('image.png')
        
        await ctx.send(files=files)
        
        os.remove('image_original.png')
        os.remove('image.png')


def setup(bot):
    Divers(bot)
