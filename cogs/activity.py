import discord
from discord.ext import commands
import os
import pickle
from fonctions.date import heure_actuelle

import main

# Activity au lancement du bot

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
            
        if not main.check_for_unmute.is_running():    
            await main.check_for_unmute.start()

def setup(bot):
    bot.add_cog(activity(bot))
