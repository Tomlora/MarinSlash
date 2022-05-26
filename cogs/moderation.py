import discord
from discord.ext import commands





class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    # en construction


def setup(bot):
    bot.add_cog(Moderation(bot))