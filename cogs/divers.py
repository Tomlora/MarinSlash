import asyncio
from fonctions.permissions import *
from discord.utils import get
import datetime
from fonctions.mute import DatabaseHandler
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, Task, IntervalTrigger
import interactions
import datetime
from fonctions.gestion_bdd import get_guild_data
import cv2
import numpy as np
import os
from aiohttp import ClientSession, ClientError
from interactions import listen, slash_command
from fonctions.gestion_bdd import requete_perso_bdd
from fonctions.permissions import isOwner_slash

import aiohttp
import asyncio
import async_timeout

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

    @slash_command(name="hello",
                                    description="Saluer le bot")
    async def hello(self, ctx: SlashContext):
        buttons = [
            interactions.Button(
                style=interactions.ButtonStyle.PRIMARY,
                label="Marin",
                custom_id="Marin",
                emoji=interactions.PartialEmoji(name="😂")
            ),
            interactions.Button(
                style=interactions.ButtonStyle.SUCCESS,
                label="Tomlora",
                custom_id="Oui",
                emoji=interactions.PartialEmoji(name="👑")
            )
        ]

        await ctx.send("Qui est le meilleur joueur ici ?",
                       components=buttons)

        async def check(button_ctx : interactions.api.events.internal.Component):
            # return m.author_id == ctx.author.id and m.origin_message.id == fait_choix.id
        
            if int(button_ctx.ctx.author.user.id) == int(ctx.author.user.id):
                return True
            await ctx.send("I wasn't asking you!", ephemeral=True)
            return False

        try:
            # Like before, this wait_for listens for a certain event, but is made specifically for components.
            # Although, this returns a new Context, independent of the original context.
            button_ctx: interactions.api.events.internal.Component = await self.bot.wait_for_component(
                components=buttons, check=check, timeout=30
            )
            
            await button_ctx.ctx.send(button_ctx.ctx.custom_id)
            # With this new Context, you're able to send a new response.
        except asyncio.TimeoutError:
            # When it times out, edit the original message and remove the button(s)
            return await ctx.edit(components=[])

    # @slash_command(name="quiz",
    #                                 description="Reponds au quizz")
    # async def quiz(self, ctx: SlashContext):
    #     select = interactions.StringSelectMenu(
    #         options=[
    #             interactions.StringSelectOption(
    #                 label="Dawn", value="1", emoji=interactions.PartialEmoji(name='😂')),
    #             interactions.StringSelectOption(
    #                 label="Exorblue", value="2", emoji=interactions.PartialEmoji(name='😏')),
    #             interactions.StringSelectOption(
    #                 label="Tomlora", value="3", emoji=interactions.PartialEmoji(name='💛')),
    #             interactions.StringSelectOption(
    #                 label="Ylarabka", value="4", emoji=interactions.PartialEmoji(name='🦊')),
    #             interactions.StringSelectOption(
    #                 label="Djingo le egay", value="5", emoji=interactions.PartialEmoji(name='💚'))
    #         ],
    #         custom_id='quizz_selected',
    #         placeholder="Choisis un emoji...",
    #         min_values=1,
    #         max_values=1
    #     )
    #     await ctx.send("Qui est le meilleur joueur ici ?",
    #                    components=select)

    #     async def check(button_ctx : interactions.api.events.internal.Component ):
    #         if int(button_ctx.author.user.id) == int(ctx.author.user.id):
    #             return True
    #         await ctx.send("I wasn't asking you!", ephemeral=True)
    #         return False

    #     try:
    #         button_ctx: interactions.api.events.internal.Component  = await self.bot.wait_for_component(
    #             components=select, check=check, timeout=30
    #         )
            
    #         if button_ctx.ctx.values[0] == "3":
    #             await button_ctx.ctx.send("Bonne réponse ! 🦊")
    #         else:
    #             await button_ctx.ctx.send("Mauvaise réponse... 😒")
    #         # With this new Context, you're able to send a new response.
    #     except asyncio.TimeoutError:
    #         # When it times out, edit the original message and remove the button(s)
    #         return await ctx.edit(components=[])

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
        if isOwner_slash(ctx):

            muted_role = await self.get_muted_role(ctx.guild)
            self.database_handler.add_tempmute(int(member.id), int(ctx.guild_id),
                                               datetime.datetime.utcnow() + datetime.timedelta(seconds=60))
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
                                               datetime.datetime.utcnow() + datetime.timedelta(seconds=60))
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
                                               datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds))
        await member.add_role(role=muted_role, guild_id=ctx.guild_id)

        if reason == "Aucune raison n'a été renseignée":
            description = f"{member.mention} a été muté pour {seconds} secondes ! 🎙"
        else:
            description = f"{member.mention} a été muté pour {seconds} secondes ! 🎙"
        embed = interactions.Embed(description=description,
                                       color=interactions.Color.random())

        await ctx.send(embeds=embed)

    @slash_command(name='my_cool_modal')
    async def my_cool_modal(self, ctx):
        modal = interactions.Modal(
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

    # @interactions.extension_modal('mod_app_form')
    # async def modal_response(self,
    #                          ctx,
    #                          response: str):
    #     await ctx.send(f'Tu as répondu {response}')

    @slash_command(name='remove_background',
                                    description="supprime le background d'une image",
                                    options=[SlashCommandOption(
                                        name='image',
                                        description='image au format png ou jpg',
                                        type=interactions.OptionType.ATTACHMENT,
                                        required=True
                                    )])
    async def remove_background(self,
                                ctx: SlashContext,
                                image: interactions.Attachment):

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
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # anti-alias the mask -- blur then stretch
        # blur alpha channel
        mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=2,
                                sigmaY=2, borderType=cv2.BORDER_DEFAULT)

        # linear stretch so that 127.5 goes to 0, but 255 stays 255
        mask = (2*(mask.astype(np.float32)) -
                255.0).clip(0, 255).astype(np.uint8)

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
        

    @slash_command(name="hug",
                                    description="Faire un calin",
                                    options=[
                                        SlashCommandOption(name="membre",
                                                    description="Nom du joueur",
                                                    type=interactions.OptionType.USER, required=True),
                                        SlashCommandOption(name="intensite",
                                                    description="Intensité",
                                                    type=interactions.OptionType.INTEGER,
                                                    required=True,
                                                    min_value=0,
                                                    max_value=10)])
    async def hug(self,
                   ctx: SlashContext,
                   membre: interactions.User,
                   intensite: int):
        if intensite <= 0:
            msg = "(っ˘̩╭╮˘̩)っ" + membre.mention
        elif intensite <= 3:
            msg = "(っ´▽｀)っ" + membre.mention
        elif intensite <= 6:
            msg = "╰(*´︶`*)╯" + membre.mention
        elif intensite <= 9:
            msg = "(つ≧▽≦)つ" + membre.mention
        elif intensite >= 10:
            msg = "(づ￣ ³￣)づ{} ⊂(´・ω・｀⊂)".format(membre.mention)
            
        await ctx.send(msg)
        
    

    @slash_command(name="ask_gpt3",
                                    description="Pose une question à une IA",
                                    options=[
                                        SlashCommandOption(
                                            name="question",
                                            description="Question",
                                            type=interactions.OptionType.STRING,
                                            required=True),
                                        SlashCommandOption(name='private',
                                               description='Réponse publique ou privée',
                                               type=interactions.OptionType.BOOLEAN,
                                               required=False),
                                    ])
    async def ask_gpt3(self,
                        ctx: SlashContext,
                        question : str,
                        private:bool=False):
        
        await ctx.defer(ephemeral=private)

        delay = 30
        clientSession = aiohttp.ClientSession()
    
        header = {'Content-Type' : 'application/json',
                'Authorization' : f'Bearer {self.api_key_openai}'}
        
        try:
            async with async_timeout.timeout(delay=delay):
                async with clientSession.post(headers=header,
                                        url='https://api.openai.com/v1/chat/completions',
                                        json={
                                    'model' : 'gpt-3.5-turbo',
                                    'messages' : [{'role' : 'user',
                                                   'content' : question}]
                                            }) as session:
                    try:                        
                        if session.status == 200:
                            reponse = await session.json()
                            reponse = reponse['choices'][0]['message']['content']
                            
                            embed = interactions.Embed()
                            embed.add_field(name=f'**{question}**', value=f'```{reponse}```')
                            
                            await ctx.send(embeds=embed)
                            
                            # await ctx.send(f"Question : **{question}**\n{reponse}")
                            await clientSession.close()
                        else:
                            await ctx.send("La requête n'a pas fonctionné", ephemeral=True)
                            await clientSession.close()
                    except Exception as e:
                            await ctx.send("Une erreur est survenue", ephemeral=True)
                            await clientSession.close()
        except asyncio.TimeoutError as e:
            await ctx.send('Erreur : Délai dépassé. Merci de reposer la question')
            await clientSession.close()
            
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
