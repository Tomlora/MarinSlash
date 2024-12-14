import asyncio
from fonctions.permissions import *
from discord.utils import get
import datetime
from fonctions.mute import DatabaseHandler
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, Task, IntervalTrigger
import interactions
from fonctions.gestion_bdd import get_guild_data
import cv2
import numpy as np
import os
import pandas as pd
from aiohttp import ClientSession, ClientError
from interactions import listen, slash_command
from fonctions.gestion_bdd import requete_perso_bdd
from fonctions.permissions import isOwner_slash
import dataframe_image as dfi
from bs4 import BeautifulSoup

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

    # @slash_command(name="hello",
    #                                 description="Saluer le bot")
    # async def hello(self, ctx: SlashContext):
    #     buttons = [
    #         interactions.Button(
    #             style=interactions.ButtonStyle.PRIMARY,
    #             label="Marin",
    #             custom_id="Marin",
    #             emoji=interactions.PartialEmoji(name="😂")
    #         ),
    #         interactions.Button(
    #             style=interactions.ButtonStyle.SUCCESS,
    #             label="Tomlora",
    #             custom_id="Oui",
    #             emoji=interactions.PartialEmoji(name="👑")
    #         )
    #     ]

    #     await ctx.send("Qui est le meilleur joueur ici ?",
    #                    components=buttons)

    #     async def check(button_ctx : interactions.api.events.internal.Component):
    #         # return m.author_id == ctx.author.id and m.origin_message.id == fait_choix.id
        
    #         if int(button_ctx.ctx.author.user.id) == int(ctx.author.user.id):
    #             return True
    #         await ctx.send("I wasn't asking you!", ephemeral=True)
    #         return False

    #     try:
    #         # Like before, this wait_for listens for a certain event, but is made specifically for components.
    #         # Although, this returns a new Context, independent of the original context.
    #         button_ctx: interactions.api.events.internal.Component = await self.bot.wait_for_component(
    #             components=buttons, check=check, timeout=30
    #         )
            
    #         await button_ctx.ctx.send(button_ctx.ctx.custom_id)
    #         # With this new Context, you're able to send a new response.
    #     except asyncio.TimeoutError:
    #         # When it times out, edit the original message and remove the button(s)
    #         return await ctx.edit(components=[])

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

        
    # @interactions.extension_modal('mod_app_form')
    # async def modal_response(self,
    #                          ctx,
    #                          response: str):
    #     await ctx.send(f'Tu as répondu {response}')

    # @slash_command(name='remove_background',
    #                                 description="supprime le background d'une image",
    #                                 options=[SlashCommandOption(
    #                                     name='image',
    #                                     description='image au format png ou jpg',
    #                                     type=interactions.OptionType.ATTACHMENT,
    #                                     required=True
    #                                 )])
    # async def remove_background(self,
    #                             ctx: SlashContext,
    #                             image: interactions.Attachment):

    #     if not image.filename.endswith('.png') and not image.filename.endswith('.jpg'):
    #         return await ctx.send("Incompatible. Il faut une image au format png ou jpg")

    #     await ctx.defer(ephemeral=False)

    #     image
    #     file = await image.download()

    #     with open('image_original.png', 'wb') as outfile:
    #         outfile.write(file.getbuffer())

    #     # load image
    #     img = cv2.imread('image_original.png')

    #     # convert to graky
    #     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    #     # threshold input image as mask
    #     mask = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY)[1]

    #     # negate mask
    #     mask = 255 - mask

    #     # apply morphology to remove isolated extraneous noise
    #     # use borderconstant of black since foreground touches the edges
    #     kernel = np.ones((3, 3), np.uint8)
    #     mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    #     mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    #     # anti-alias the mask -- blur then stretch
    #     # blur alpha channel
    #     mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=2,
    #                             sigmaY=2, borderType=cv2.BORDER_DEFAULT)

    #     # linear stretch so that 127.5 goes to 0, but 255 stays 255
    #     mask = (2*(mask.astype(np.float32)) -
    #             255.0).clip(0, 255).astype(np.uint8)

    #     # put mask into alpha channel
    #     result = img.copy()
    #     result = cv2.cvtColor(result, cv2.COLOR_BGR2BGRA)
    #     result[:, :, 3] = mask

    #     # save resulting masked image
    #     cv2.imwrite('image.png', result)

    #     files = interactions.File('image.png')

    #     await ctx.send(files=files)

    #     os.remove('image_original.png')
    #     os.remove('image.png')
        

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
        
    

    # @slash_command(name="ask_gpt3",
    #                                 description="Pose une question à une IA",
    #                                 options=[
    #                                     SlashCommandOption(
    #                                         name="question",
    #                                         description="Question",
    #                                         type=interactions.OptionType.STRING,
    #                                         required=True),
    #                                     SlashCommandOption(name='private',
    #                                            description='Réponse publique ou privée',
    #                                            type=interactions.OptionType.BOOLEAN,
    #                                            required=False),
    #                                 ])
    # async def ask_gpt3(self,
    #                     ctx: SlashContext,
    #                     question : str,
    #                     private:bool=False):
        
    #     await ctx.defer(ephemeral=private)

    #     delay = 30
    #     clientSession = aiohttp.ClientSession()
    
    #     header = {'Content-Type' : 'application/json',
    #             'Authorization' : f'Bearer {self.api_key_openai}'}
        
    #     try:
    #         async with async_timeout.timeout(delay=delay):
    #             async with clientSession.post(headers=header,
    #                                     url='https://api.openai.com/v1/chat/completions',
    #                                     json={
    #                                 'model' : 'gpt-3.5-turbo',
    #                                 'messages' : [{'role' : 'user',
    #                                                'content' : question}]
    #                                         }) as session:
    #                 try:                        
    #                     if session.status == 200:
    #                         reponse = await session.json()
    #                         reponse = reponse['choices'][0]['message']['content']
                            
    #                         embed = interactions.Embed()
    #                         embed.add_field(name=f'**{question}**', value=f'```{reponse}```')
                            
    #                         await ctx.send(embeds=embed)
                            
    #                         # await ctx.send(f"Question : **{question}**\n{reponse}")
    #                         await clientSession.close()
    #                     else:
    #                         await ctx.send("La requête n'a pas fonctionné", ephemeral=True)
    #                         await clientSession.close()
    #                 except Exception as e:
    #                         await ctx.send("Une erreur est survenue", ephemeral=True)
    #                         await clientSession.close()
    #     except asyncio.TimeoutError as e:
    #         await ctx.send('Erreur : Délai dépassé. Merci de reposer la question')
    #         await clientSession.close()
            
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



    # @slash_command(name="jo_medaille",
    #                                 description="Liste des medailles au JO",
    #                                 options=[
    #                                     SlashCommandOption(name='vue_simplifiee',
    #                                            description='simplifie ou detaille ?',
    #                                            type=interactions.OptionType.BOOLEAN,
    #                                            required=False),
    #                                     SlashCommandOption(name="nb_lignes",
    #                                                 description="Nombre de lignes à afficher",
    #                                                 type=interactions.OptionType.INTEGER,
    #                                                 required=False,
    #                                                 min_value=10,
    #                                                 max_value=200)
    #                                 ])
    
    # async def medaille(self,
    #                ctx: SlashContext,
    #                vue_simplifiee:bool=True,
    #                nb_lignes: int = 50):
        
    #     await ctx.defer(ephemeral=False)


    #     session = ClientSession()

    #     if vue_simplifiee:
    #         html = await session.get('https://www.lequipe.fr/Jo-2024-paris/Jeux-Paralympiques/page-tableau-medailles/')
    #         df = pd.read_html(await html.text())[0]
    #         df.columns = ['Classement', 'a', 'Pays', 'Or', 'Argent', 'Bronze', 'Total']

    #         df.drop(columns='a', inplace=True)

    #         df.set_index(['Classement', 'Pays'], inplace=True)

    #         df = df.head(nb_lignes)

    #     else:

    #         html = await session.get('https://francetelevisions.idalgo-hosting.com/paris2024-tv/')
    #         df = pd.read_html(await html.text())[1]

    #         def cleaning_pays(x):
    #             try:
    #                 if x['Pays'].isnumeric() or x['Pays'] == '-':
    #                     x['Pays'] = f'{x["Pays"]}.{x["Pays.1"]}'
    #                     x['Pays.1'] = np.nan
    #             except AttributeError:
    #                 pass

    #             return x


    #         df = df.apply(cleaning_pays, axis=1)


    #         df = df[df['Unnamed: 6'].isna()]
    #         df.drop(columns=['Unnamed: 6'], inplace=True)
    #         df.rename(columns={'Pays.1' : 'Epreuves'}, inplace=True)

    #         df.dropna(subset=['Or', 'Argent', 'Bronze'], how='all', inplace=True)


    #         df.fillna(' ', inplace=True)

    #         df.replace('0-', '0', inplace=True)

    #         df = df.head(nb_lignes)

    #         df.set_index(['Pays', 'Epreuves'], inplace=True)

                    
    #     dfi.export(df, 'image.png',
    #                 max_cols=-1,
    #                 max_rows=-1, table_conversion="matplotlib")

    #     await ctx.send(content='https://francetelevisions.idalgo-hosting.com/paris2024-tv/', files=interactions.File('image.png'))

    #     os.remove('image.png')

    #     await session.close()
                    


    # @slash_command(name="jo_calendrier",
    #                                 description="Calendrier JO, epreuves à suivre selon journalistes FR",
    #                                     options=[
    #                                     SlashCommandOption(name='vue_simplifiee',
    #                                            description='simplifie ou detaille ?',
    #                                            type=interactions.OptionType.BOOLEAN,
    #                                            required=False)])
    
    # async def calendrier(self,
    #                ctx: SlashContext,
    #                vue_simplifiee:bool=True):
        
    #     await ctx.defer(ephemeral=False)

    #     session = ClientSession()

    #     if vue_simplifiee:
    #         html = await session.get('https://www.ouest-france.fr/jeux-olympiques/calendrier/')
    #         try:
    #             df = pd.read_html(await html.text())[0]
    #         except ValueError:
    #             txt = await html.text()
    #             print(txt)
    #             await ctx.send('Erreur')

    #         df.drop(columns=['Podium'], inplace=True)
    #         df.rename(columns={'Unnamed: 0' : 'Horaire'}, inplace=True)


    #         dfi.export(df, 'image.png',
    #                     max_cols=-1,
    #                     max_rows=-1, table_conversion="matplotlib")

    #         await ctx.send(files=interactions.File('image.png'))

    #         os.remove('image.png')
    #     else:


    #         # Étape 1 : Faire une requête HTTP pour obtenir le contenu de la page
    #         url = 'https://www.ouest-france.fr/jeux-olympiques/calendrier/'
    #         response = await session.get(url)
    #         html_content = await response.text()

    #         # Étape 2 : Parsez le contenu HTML avec BeautifulSoup
    #         soup = BeautifulSoup(html_content, 'html.parser')

    #         # Étape 3 : Trouver tous les ul avec une classe spécifique, par exemple 'my-ul-class'
    #         # ul_elements = soup.find_all('ul', class_='disciplines')


    #         # Étape 3 : Extraire les données spécifiques du HTML
    #         li_elements = soup.find_all('li')


    #         # Parcourir tous les li trouvés et extraire les informations

    #         dict_planning = {}

    #         for li in li_elements:
    #                 try:
    #                     event = li.find('span', class_='event').get_text(strip=True) 
    #                 except:
    #                     event = None
    #                 try:
    #                     phase = li.find('span', class_='name').get_text(strip=True)
    #                 except:
    #                     phase = None
    #                 try:
    #                     group = li.find('span', class_='group').get_text(strip=True)
    #                 except:
    #                     group = None

    #                 # link = li.find('a', class_='link')['href'] 
    #                 try:
    #                     time = li.find('time', class_='time').get_text(strip=True) 
    #                 except:
    #                     time = None
    #                 try:
    #                     discipline = li.find('div', class_='discipline').get_text(strip=True)
    #                 except:
    #                     discipline = None
    #                 try:
    #                     datetime_value = li.find('time', class_='time')['datetime'] 
    #                 except:
    #                     datetime_value = None

    #                 dict_planning[f'{discipline}_{event}'] = {
    #                                         'phase' : phase,
    #                                         'group' : group,
    #                                         # 'link' : link,
    #                                         'time' : time,
    #                                         'datetime' : datetime_value}

    #         df = pd.DataFrame.from_dict(dict_planning).T

    #         try:
    #             df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
    #         except ValueError:
    #             print(df)
    #             print(html_content)

    #             await ctx.send('Erreur')
    #         except KeyError:

    #             print(df)
    #             print(html_content)

    #             await ctx.send('Erreur')

    #         df['datetime'] = df['datetime'].dt.date

    #         df = df[df['datetime'] == datetime.datetime.now().date()].sort_values('time')

    #         df['phase'] = df['phase'].str.replace('Phase de groupe', 'Groupe')
    #         df['group'] = df['group'].str.replace('Groupe ', '')


    #         df1 = df[df['time'] < '17:00']
    #         df2 = df[df['time'] >= '17:00']

    #         dfi.export(df1, 'image.png',
    #                     max_cols=-1,
    #                     max_rows=-1, table_conversion="matplotlib")
            
    #         dfi.export(df2, 'image2.png',
    #                     max_cols=-1,
    #                     max_rows=-1, table_conversion="matplotlib")

    #         await ctx.send(files=[interactions.File('image.png'), interactions.File('image2.png')])

    #         os.remove('image.png')
    #         os.remove('image2.png')

    #     await session.close()
        
                    

            
def setup(bot):
    Divers(bot)
