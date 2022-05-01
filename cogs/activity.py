import discord
from discord.ext import commands

import main

Var_version = 1.0


class activity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.on_ready = self.bot.event(self.on_ready)

    async def on_ready(self):
        print(f'Le bot {main.bot.user} est connecté au serveur')
        await main.bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.listening, name='My Dress Up Darling'))

        for guild in main.bot.guilds:
            print(f' Channels connectées : {guild.name}')

        await main.check_for_unmute.start()


def setup(bot):
    bot.add_cog(activity(bot))
