from fonctions.date import heure_actuelle
from fonctions.gestion_bdd import get_guild_data
import interactions
from interactions import Extension

# Activity au lancement du bot

class activity(Extension):
    def __init__(self, bot : interactions.Client):
        self.bot = bot
        # self.on_ready = self.bot.event(self.on_ready)

    @interactions.extension_listener
    async def on_start(self):
        currentHour, currentMinute = heure_actuelle()
        print(f'Connecté au serveur ({currentHour}:{currentMinute})')
 
        await self.bot.change_presence(interactions.ClientPresence(status=interactions.StatusType.ONLINE,
                                                                   activities=[interactions.PresenceActivity(name='My Dress Up Darling',
                                                                                                             type=interactions.PresenceActivityType.WATCHING)]))
       
    @interactions.extension_listener
    async def on_ready(self):   
        # TODO : faire via BDD 
        
        data = get_guild_data()
        
        for server_id in data.fetchall():
            
            guild = await interactions.get(client=self.bot,
                                                      obj=interactions.Guild,
                                                      object_id=server_id[0])
        # for guild in self.bot.guilds:
            text_channel_list = []
            for channel in await guild.get_all_channels():
                text_channel_list.append(channel.id)

                
            print(f' Channels connectées => Name : {guild.name} | Id : {guild.id} | Chan1 : {text_channel_list[0]}')
    
               



def setup(bot):
    activity(bot)
