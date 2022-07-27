# import os

# import matplotlib.pyplot as plt

# import numpy as np
import plotly.express as px
from discord.ext import commands, tasks


from discord_slash.utils.manage_components import *
# from discord_slash import cog_ext, SlashContext

from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd
from fonctions.patch import PatchNote

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
        version_bdd = version_bdd['1\n']['version']
        
        # Si les versions sont différentes, on update:
        
        if version_bdd != patch_actuel.version_patch:
            
            # MAJ de la BDD
            version_bdd['1\n']['version'] = patch_actuel.version_patch
            sauvegarde_bdd(version_bdd, 'patchnotes')
            
            # Embed
            
            embed = discord.Embed(title=f"Le patch {patch_actuel.version_patch} est disponible ! ", color=discord.Color.blue())
            embed.set_image(url=patch_actuel.overview_image)
            
            embed.add_field(name="Details", value=f"[Lien du patch]({patch_actuel.link}")
            
            await channel.send(embed=embed)
            
    @commands.command()
    async def test_patch(self, ctx):
        
        version_bdd = lire_bdd('patchnotes', 'dict')
        version_bdd['1\n']['version'] = "12.12"
        sauvegarde_bdd(version_bdd, 'patchnotes')
        
        ctx.send('Fait')
        
            
        
        


def setup(bot):
    bot.add_cog(Patchlol(bot))