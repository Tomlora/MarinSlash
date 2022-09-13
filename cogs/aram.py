import pandas as pd
import numpy as np
from discord.ext import commands
from discord_slash.utils.manage_components import *
from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd
import main
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option, create_choice


chan_general = 768637526176432158


class Aram(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash(name="classement_aram",description="classement en aram")
    async def ladder_aram(self, ctx):        

        suivi_aram = lire_bdd('ranked_aram', 'dict')
        
        await ctx.defer(hidden=False)

        df = pd.DataFrame.from_dict(suivi_aram)
        df = df.transpose().reset_index()

        embed = discord.Embed(title="Suivi LOL", description='ARAM', colour=discord.Colour.blurple())

        for key in df['index']:
            
            embed.add_field(name=str(key),
                            value="V : " + str(suivi_aram[key]['wins']) + " | D : " + str(suivi_aram[key]['losses']) + " | LP :  "
                                                + str(suivi_aram[key]['lp']), inline=False)
                                                    
        embed.set_footer(text=f'Version {main.Var_version} by Tomlora')  

        await ctx.send(embed=embed)
        

    @cog_ext.cog_slash(name='ranked_aram', description='Activation/Désactivation',
                       options=[create_option(name='summonername', description="nom ingame", option_type=4, required=True),
                                create_option(name="activation", description="True : Activé / False : Désactivé", option_type=5, required=True)])
    
    async def update_activation(self, ctx, summonername:str, activation:bool):
        
        summonername = summonername.lower()
        suivi_aram = lire_bdd('ranked_aram', 'dict')
        
        try:
            suivi_aram[summonername]['activation'] = activation
            sauvegarde_bdd(suivi_aram, 'ranked_aram')
            if activation:
                await ctx.send('Ranked activé !')
            else:
                await ctx.send('Ranked désactivé !')
        except KeyError:
            await ctx.send('Joueur introuvable')

        


def setup(bot):
    bot.add_cog(Aram(bot))
