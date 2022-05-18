import discord
from discord.ext import commands
import os
import pickle
from fonctions.date import heure_actuelle

import main



class activity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.on_ready = self.bot.event(self.on_ready)

    async def on_ready(self):
        currentHour, currentMinute = heure_actuelle()
        print(f'Le bot {main.bot.user} est connecté au serveur ({currentHour}:{currentMinute})')
        await main.bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.listening, name='My Dress Up Darling'))

        for guild in main.bot.guilds:
            print(f' Channels connectées => Name : {guild.name} | Id : {guild.id}')
            
            if not os.path.exists(f'./config/{guild.id}'):
                os.makedirs(f'./config/{guild.id}')
                
                dict_id = {
                    'id_tom' : 298418038460514314,
                    'chan_pm' : 534111278923513887,
                    'chan_tracklol' : 953814193658789918,
                    'chan_kangourou' : 498598293140537374,
                    'chan_twitch' : 540501033684828160,
                    'chan_lol' : 540501033684828160
                    }
                with open(f'./config/{guild.id}/config.pkl', 'wb+') as f:
                    pickle.dump(dict_id, f, protocol=0)
                       
            

        await main.check_for_unmute.start()

def setup(bot):
    bot.add_cog(activity(bot))
