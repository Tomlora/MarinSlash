import pandas as pd
import numpy as np
from discord.ext import commands
from discord_slash.utils.manage_components import *
from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd
import main
from discord_slash import cog_ext, SlashContext


chan_general = 768637526176432158


class Aram(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

@cog_ext.cog_slash(name="classement_aram",description="classement en aram")
async def ladder_aram(self, ctx):        

    suivi_aram = lire_bdd('ranked_aram', 'dict')

    df = pd.DataFrame.from_dict(suivi_aram)
    df = df.transpose().reset_index()

    joueur = df['index'].to_dict()


    embed = discord.Embed(title="Suivi LOL", description='ARAM', colour=discord.Colour.blurple())

    for key in joueur.values():
        
        embed.add_field(name=str(key),
                        value="V : " + str(suivi_aram[key]['wins']) + " | D : " + str(suivi_aram[key]['losses']) + " | LP :  "
                                            + str(suivi_aram[key]['LP']), inline=False)
                                                
    embed.set_footer(text=f'Version {main.Var_version} by Tomlora')  

    await ctx.send(embed=embed)


        


def setup(bot):
    bot.add_cog(Aram(bot))
