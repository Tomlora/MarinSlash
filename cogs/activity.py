import discord
from discord.ext import commands
from fonctions.date import heure_actuelle
from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd

import main

# Activity au lancement du bot

class activity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.on_ready = self.bot.event(self.on_ready)

    async def on_ready(self):
        currentHour, currentMinute = heure_actuelle()
        print(f'Le bot {self.bot.user} est connecté au serveur ({currentHour}:{currentMinute})')
        await self.bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.listening, name='My Dress Up Darling'))

        
        for guild in self.bot.guilds:
            text_channel_list = []
            for channel in guild.text_channels:
                text_channel_list.append(channel.id)
            
            # on vérifie que le serveur est enregistré
            data = lire_bdd_perso(f'SELECT server_id from channels_discord', index_col='server_id').transpose()
        
            if not int(guild.id) in data.index:
                requete_perso_bdd(f'''INSERT INTO public.channels_discord(
	            server_id, id_owner, id_owner2, chan_pm, chan_tracklol, chan_accueil, chan_twitch, chan_lol, chan_tft, chan_lol_others, role_admin)
	            VALUES (:server_id, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :chan);''',
             {'server_id' : guild.id, 'chan' : text_channel_list[0]})

                
            
            print(f' Channels connectées => Name : {guild.name} | Id : {guild.id} | Chan1 : {text_channel_list[0]}')
            
               
        if not main.check_for_unmute.is_running():    
            await main.check_for_unmute.start()

def setup(bot):
    bot.add_cog(activity(bot))
