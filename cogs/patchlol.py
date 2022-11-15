from discord.ext import commands, tasks
from discord_slash.utils.manage_components import *
from fonctions.patch import PatchNote
from discord_slash.utils.manage_components import *
from fonctions.gestion_bdd import get_data_bdd, requete_perso_bdd
from main import chan_lol

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
        version = get_data_bdd("SELECT version from patchnotes").mappings().all()[0]['version']

        
        # Si les versions sont différentes, on update:
        
        if version != patch_actuel.version_patch:
            
            # MAJ de la BDD
            
            requete_perso_bdd('UPDATE patchnotes SET version = :version', {'version' : patch_actuel.version_patch})          
            
            # Embed
            
            embed = discord.Embed(title=f"Le patch {patch_actuel.version_patch} est disponible ! ", color=discord.Color.blue())
            embed.set_image(url=patch_actuel.overview_image)
            
            embed.add_field(name="Details", value=f"[Lien du patch]({patch_actuel.link})")
            
            try:
                await channel.send(embed=embed)
            except:
                print('Erreur au lancement du bot... Réessai dans 10 minutes')
                
                
    # @cog_ext.cog_slash(name="patch_detail",
    #                    description="Detail du dernier patch")
    # async def patch_detail(self, ctx):
        
    #     patch_actuel = PatchNote()
        
    #     embed = discord.Embed(title=f"Detail Patch {patch_actuel.version_patch}")
    #     # patch_actuel.detail_patch
                 


def setup(bot):
    bot.add_cog(Patchlol(bot))