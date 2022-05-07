import discord
from discord.ext import commands
import main
import linecache
from fonctions.gestion_fichier import loadConfig, writeConfig

Var_version = 1.0

params = main.params

nb_params = 12


class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Affiche la version du bot")
    @main.isOwner2()
    async def parametres(self, ctx):
        
        nom = self.bot.get_channel(id)

        embed = discord.Embed(title="Config", description=(f'Serveur {ctx.guild.name} ({ctx.guild.id})'), color=discord.Color.blue())
    

        data = loadConfig(ctx)
        for titre, value in data.items():
            embed.add_field(name=titre, value=str(value), inline=False)
        embed.set_footer(text=f'Version {main.Var_version} by Tomlora')
        await ctx.send(embed=embed)

    @commands.command()
    @main.isOwner2()
    async def parametres_modif(self, ctx, parametre, id:int):

        data = loadConfig(ctx)
        nom = self.bot.get_channel(id)
        
        data['parametre'] = id

        writeConfig(ctx, data)
        
        await ctx.send(f' Le channel {nom} a été assignée pour le paramètre {parametre} pour le serveur {ctx.guild.name}')


def setup(bot):
    bot.add_cog(Config(bot))
