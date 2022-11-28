
from fonctions.patch import PatchNote
import interactions
from interactions import Extension
from interactions.ext.tasks import IntervalTrigger, create_task
from fonctions.gestion_bdd import (get_data_bdd,
                                   requete_perso_bdd,
                                   get_guild_data)
from fonctions.channels_discord import chan_discord


class Patchlol(Extension):
    def __init__(self, bot):
        self.bot : interactions.Client = bot
    
    @interactions.extension_listener
    async def on_start(self):
        self.task1 = create_task(IntervalTrigger(60*10))(self.update_patch)
        self.task1.start()



    async def update_patch(self):
        
        patch_actuel = PatchNote()
        
        await patch_actuel.get_data()
        
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

            data = get_data_bdd(f'''SELECT DISTINCT tracker.server_id from tracker 
                    INNER JOIN channels_module on tracker.server_id = channels_module.server_id
                    where channels_module.league_ranked = true''').fetchall()
            
            for server_id in data.fetchall():
                
                guild = await interactions.get(client=self.bot,
                                                        obj=interactions.Guild,
                                                        object_id=server_id[0])            
                discord_server_id = chan_discord(guild.id)
                channel = await interactions.get(client=self.bot,
                                                        obj=interactions.Channel,
                                                        object_id=discord_server_id.tracklol)

                await channel.send(embeds=embed)

                
def setup(bot):
    Patchlol(bot)