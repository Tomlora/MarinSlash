import discord
from discord.ext import commands





class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    # @commands.command()
    # async def aaa(self, ctx):
    #     embed = discord.Embed(title="Marin Bot",
    #                           description="Bot custom",
    #                           color=discord.Color.blue())
    #     embed.set_thumbnail(url="https://i.imgur.com/83zgdVz.jpg")
    #     embed.set_footer(text="Version 1.0 by Tomlora")
    #     await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Moderation(bot))