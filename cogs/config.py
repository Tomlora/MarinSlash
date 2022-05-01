import discord
from discord.ext import commands
import main
import linecache

Var_version = 1.0

params = main.params

nb_params = 12


class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Affiche la version du bot")
    @main.isOwner2()
    async def parametres(self, ctx):

        embed = discord.Embed(title="Config", description="Id : ", color=discord.Color.blue())

        for i in range(1, nb_params, 2):
            titre = linecache.getline(params, i)
            value = linecache.getline(params, i + 1)
            embed.add_field(name=titre, value=str(value), inline=False)
        embed.set_footer(text=f'Version {main.Var_version} by Tomlora')
        await ctx.send(embed=embed)

    @commands.command()
    @main.isOwner2()
    async def parametres_modif(self, ctx, parametre, id):

        nom = self.bot.get_channel(int(id))

        for i in range(0, nb_params, 2):
            file = open(params, "r")
            lignes = file.readlines()
            file.close()
            if str(parametre + '\n') == str(lignes[i]):
                lignes[i + 1] = str(id + '\n')
                file = open(params, "w")
                file.writelines(lignes)
        file.close()
        await ctx.send(f' Le channel {nom} a été assignée pour le paramètre {parametre}')


def setup(bot):
    bot.add_cog(Config(bot))
