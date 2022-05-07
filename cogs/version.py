import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
import main



class Version(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash(name="versioninfo", description="Version du bot")
    async def _versioninfo(self, ctx : SlashContext):
        embed = discord.Embed(title="Marin Bot",
                              description="Bot custom",
                              color=discord.Color.blue())
        embed.set_thumbnail(url="https://i.imgur.com/83zgdVz.jpg")
        embed.set_footer(text=f'Version {main.Var_version} by Tomlora')
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Version(bot))
