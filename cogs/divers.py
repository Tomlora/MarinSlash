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
        self.api_key_openai = os.environ.get('openai')

    # @listen()
    # async def on_startup(self):

    #     self.check_for_unmute.start()





    @slash_command(name="ping", description="Latence du bot")
    async def ping(self, ctx: SlashContext):
        await ctx.send(
            f"pong \n Latence : `{round(float(self.bot.latency), 3)}` ms")

    @slash_command(name='spank',
                                    description='spank un membre',
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
        
        duree_timeout = timedelta(minutes=1)
        if isOwner_slash(ctx):

            guild_member : interactions.Member = await ctx.guild.fetch_member(member.id)
            
            await guild_member.timeout(communication_disabled_until=duree_timeout) 
            
            
            if reason == "Aucune raison n'a été renseignée":
                description = f"{member.mention} a été spank par {ctx.author.nickname}"
            else:
                description = f"{member.mention} a été spank par {ctx.author.nickname} pour {reason}"
            embed = interactions.Embed(description=description,
                                       color=interactions.Color.random())


            await ctx.send(embeds=embed)
        else:
            author_id = ctx.author.id
            
            guild_member : interactions.Member = await ctx.guild.fetch_member(author_id)
            
            await guild_member.timeout(communication_disabled_until=duree_timeout)
            
            
            description = f"Bien essayé. {ctx.author.nickname} s'est prank lui-même"

            embed = interactions.Embed(description=description,
                                       color=interactions.Color.random())


            await ctx.send(embeds=embed)


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
        # df = lire_bdd_perso(f'''
        #                 SELECT sum(solokills),
        #                 SUM(CASE 
        #                         WHEN matchs.datetime >= date_trunc('day', NOW()) + INTERVAL '6 hours'
        #                                                 AND matchs.datetime < date_trunc('day', NOW()) + INTERVAL '30 hours'
        #                         THEN solokills 
        #                         ELSE 0 
        #                     END) AS solokills_24h
        #                 FROM matchs
        #                 INNER JOIN tracker ON tracker.id_compte = matchs.joueur
        #                 and mode = 'RANKED'
        #                 where discord = '111147548760133632' ''',index_col=None).T

        df = lire_bdd_perso(f'''
        SELECT 
            SUM(solokills),
            SUM(CASE 
                    WHEN matchs.datetime >= 
                         CASE 
                             WHEN NOW()::time < time '06:00' 
                                 THEN date_trunc('day', NOW()) - INTERVAL '18 hours'  -- hier 6h
                             ELSE date_trunc('day', NOW()) + INTERVAL '6 hours'      -- aujourd’hui 6h
                         END
                     AND matchs.datetime < 
                         CASE 
                             WHEN NOW()::time < time '06:00' 
                                 THEN date_trunc('day', NOW()) + INTERVAL '6 hours'  -- aujourd’hui 6h
                             ELSE date_trunc('day', NOW()) + INTERVAL '30 hours'     -- demain 6h
                         END
                    THEN solokills 
                    ELSE 0 
                END) AS solokills_24h
        FROM matchs
        INNER JOIN tracker ON tracker.id_compte = matchs.joueur
            AND mode = 'RANKED'
        WHERE discord = '111147548760133632' ''',index_col=None).T


        # 1. Ouvrir l'image
        image = Image.open("./img/meme_oie.png").convert('RGBA')  # Remplace par le chemin de ton image

                # Calque transparent pour l’ombre
        shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)

        nb_kills = df.iloc[0,0].astype(int)
        nb_kills_24h = df.iloc[0,1].astype(int) 

        phrase = f"{nb_kills} (+{nb_kills_24h})"

                # 3. Texte, positions et police
        texts = [
                    ("Combien de solokills ?", (50, 50)),
                    (phrase, (320, 430))
                ]

                # Police

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
