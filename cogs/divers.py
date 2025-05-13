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
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageSequence
from fonctions.gestion_bdd import lire_bdd_perso



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


    @slash_command(name="solokilldawn",
                   description='Commande personnalisée')
    
    async def solokilldawn(self, ctx: SlashContext):
        df = lire_bdd_perso(f'''
                SELECT sum(solokills)
                FROM matchs
                INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                and mode = 'RANKED'
                where discord = '111147548760133632' ''',index_col=None).T

        # 1. Ouvrir l'image
        image = Image.open("./img/meme_oie.png").convert('RGBA')  # Remplace par le chemin de ton image

        # Calque transparent pour l’ombre
        shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)

        # 3. Texte, positions et police
        texts = [
            ("Combien de solokills ?", (50, 50)),
            (str(df.iloc[0,0].astype(int)), (320, 430))
        ]

        # Police
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 40)  # Ubuntu 18.04
        except OSError:
            try:
                font = ImageFont.truetype("arial.ttf", 40)  # Windows
            except OSError:
                font = ImageFont.truetype("AppleSDGothicNeo.ttc", 40)  # MacOS

 

        # Couleur de l’ombre + décalages multiples
        shadow_color = (0, 0, 0, 200)  # Plus opaque que 255 = trop si flou
        offsets = [(4, 4), (5, 5), (6, 6)]  # Empilement d’ombres

        # Dessiner l'ombre plusieurs fois pour la renforcer
        for dx, dy in offsets:
            for text, (x, y) in texts:
                shadow_draw.text((x + dx, y + dy), text, font=font, fill=shadow_color)

        # Flouter l'ombre (augmenter le radius la rend plus forte)
        blurred_shadow = shadow_layer.filter(ImageFilter.GaussianBlur(radius=6))

        # Combiner ombre + image d’origine
        combined = Image.alpha_composite(image, blurred_shadow)

        # Ajouter le texte principal en blanc
        final_draw = ImageDraw.Draw(combined)
        for text, (x, y) in texts:
            final_draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

        # Afficher ou enregistrer
        combined.save('stats_dawn.png') # Affiche l'image

        file = interactions.File(f'stats_dawn.png')

        await ctx.send(files=file)
                   

    @slash_command(name="solokilldjingo",
                   description='Commande personnalisée')
    
    async def solokilldjingo(self, ctx: SlashContext):
        df = lire_bdd_perso(f'''
                SELECT sum(solokills)
                FROM matchs
                INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                and mode = 'RANKED'
                where discord = '267403725029507073' ''',index_col=None).T

        # Charger le GIF
        gif = Image.open("img/djingo.gif")

        # Police
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 40)  # Ubuntu 18.04
        except OSError:
            try:
                font = ImageFont.truetype("arial.ttf", 40)  # Windows
            except OSError:
                font = ImageFont.truetype("AppleSDGothicNeo.ttc", 40)  # MacOS

        # Taille de l’image
        width, height = gif.size
        frames = []
        background = Image.new("RGBA", gif.size)

        # Nombre total de frames
        frame_count = sum(1 for _ in ImageSequence.Iterator(gif))

        # Déplacement total en x et y (du bas-droit vers haut-gauche)
        start_x, start_y = width - 200, height - 80  # départ bas-droit (ajuste si besoin)
        end_x, end_y = 50, 50                        # fin haut-gauche
        dx = (end_x - start_x) / frame_count
        dy = (end_y - start_y) / frame_count

        for i, frame in enumerate(ImageSequence.Iterator(gif)):
            # Frame complète pour éviter les superpositions
            current = background.copy()
            frame_rgba = frame.convert("RGBA")
            current.paste(frame_rgba, (0, 0), frame_rgba)

            # Position diagonale animée
            x = start_x + dx * i
            y = start_y + dy * i

            # Ombre renforcée
            shadow_layer = Image.new("RGBA", gif.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_layer)
            # for offset in [(4, 4), (5, 5), (6, 6)]:
            #     shadow_draw.text((x + offset[0], y + offset[1]), str(df.iloc[0,0].astype(int)), font=font, fill=(0, 0, 0, 180))

            blurred_shadow = shadow_layer.filter(ImageFilter.GaussianBlur(radius=3))

            # Fusion ombre + image
            combined = Image.alpha_composite(current, blurred_shadow)

            # Ajouter texte blanc
            draw = ImageDraw.Draw(combined)
            draw.text((x, y), str(df.iloc[0,0].astype(int)), font=font, fill=(255, 255, 255, 255))

            frames.append(combined)

        # Enregistrer le GIF final
        frames[0].save(
            "stats_djingo.gif",
            save_all=True,
            append_images=frames[1:],
            duration=gif.info.get("duration", 100),
            loop=0,
            disposal=2
        )
        file = interactions.File(f'stats_djingo.gif')

        await ctx.send(files=file)





                    

            
def setup(bot):
    Divers(bot)
