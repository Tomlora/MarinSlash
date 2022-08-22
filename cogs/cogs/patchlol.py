# import os

# import matplotlib.pyplot as plt

# import numpy as np
import plotly.express as px
from discord.ext import commands, tasks


from discord_slash.utils.manage_components import *
from discord_slash import cog_ext, SlashContext

from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd
from fonctions.patch import PatchNote

from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice

from main import Var_version, chan_lol






class Patchlol(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.my_task_patch.start()
        
        
    @tasks.loop(minutes=10, count=None)
    async def my_task_patch(self):
        await self.update_patch()

 
    @commands.command()
    async def update_patch(self):
        channel = self.bot.get_channel(chan_lol)
        patch_actuel = PatchNote()
        
        # Version chargée dans la bdd
        version_bdd = lire_bdd('patchnotes', 'dict')
        version = version_bdd['1\n']['version']
        
        # Si les versions sont différentes, on update:
        
        if version != patch_actuel.version_patch:
            
            # MAJ de la BDD
            version_bdd['1\n']['version'] = patch_actuel.version_patch
            
            
            # Embed
            
            embed = discord.Embed(title=f"Le patch {patch_actuel.version_patch} est disponible ! ", color=discord.Color.blue())
            embed.set_image(url=patch_actuel.overview_image)
            
            embed.add_field(name="Details", value=f"[Lien du patch]({patch_actuel.link})")
            
            try:
                await channel.send(embed=embed)
                sauvegarde_bdd(version_bdd, 'patchnotes')
            except:
                print('Erreur au lancement du bot... Réessai dans 10 minutes')
                
                
    @cog_ext.cog_slash(name="patch_detail",
                       description="Detail du dernier patch")
    async def patch_detail(self, ctx):
        
        patch_actuel = PatchNote()
        
        embed = discord.Embed(title=f"Detail Patch {patch_actuel.version_patch}")
        # patch_actuel.detail_patch
                 


def setup(bot):
    bot.add_cog(Patchlol(bot))