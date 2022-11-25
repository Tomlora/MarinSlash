
from fonctions.patch import PatchNote
import interactions
from interactions.ext.tasks import IntervalTrigger, create_task
from fonctions.gestion_bdd import get_data_bdd, requete_perso_bdd
from fonctions.channels_discord import chan_discord


class Patchlol(interactions.Extension):
    def __init__(self, bot):
        self.bot : interactions.Client = bot
    
    @interactions.extension_listener
    async def on_start(self):
        self.task1 = create_task(IntervalTrigger(60*10))(self.update_patch)
        self.task1.start()



    async def update_patch(self):
        
        patch_actuel = PatchNote()
        
        # Version chargée dans la bdd
        version = get_data_bdd("SELECT version from patchnotes").mappings().all()[0]['version']

        
        # Si les versions sont différentes, on update:
        
        if version != patch_actuel.version_patch:
            
            # MAJ de la BDD
            
            requete_perso_bdd('UPDATE patchnotes SET version = :version', {'version' : patch_actuel.version_patch})          
            
            # Embed
            
            embed = interactions.Embed(title=f"Le patch {patch_actuel.version_patch} est disponible ! ", color=interactions.Color.blurple())
            embed.set_image(url=patch_actuel.overview_image)
            
            embed.add_field(name="Details", value=f"[Lien du patch]({patch_actuel.link})")
            
            for guild in self.bot.guilds:
                discord_server_id = chan_discord(guild.id)
                channel = await interactions.get(client=self.bot,
                                                        obj=interactions.Channel,
                                                        object_id=discord_server_id.tracklol)

                await channel.send(embeds=embed)

                
def setup(bot):
    Patchlol(bot)