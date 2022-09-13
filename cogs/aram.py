import pandas as pd
import numpy as np
from discord.ext import commands
from discord_slash.utils.manage_components import *
from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd
import main
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option, create_choice
from cogs.leagueoflegends import dict_points, elo_lp


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
            
            wr = round(suivi_aram[key]['wins'] / suivi_aram[key]['games'],2)
            
            kda = round(suivi_aram[key]['k'] + suivi_aram[key]['a'] / suivi_aram[key]['d'],1)
            
            embed.add_field(name=str(f"{key} ({suivi_aram[key]['lp']} LP) [{suivi_aram[key]['rank']}]"),
                            value="V : " + str(suivi_aram[key]['wins']) + " | D : " + str(suivi_aram[key]['losses']) + " | WR :  "
                                                + str(wr) + " | KDA : " + str(kda), inline=False)
                                                    
        embed.set_footer(text=f'Version {main.Var_version} by Tomlora')  

        await ctx.send(embed=embed)
        

    @cog_ext.cog_slash(name='ranked_aram', description='Activation/Désactivation',
                       options=[create_option(name='summonername', description="nom ingame", option_type=3, required=True),
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
            

            
    @cog_ext.cog_slash(name="help_aram", description='Help ranked aram')
    async def help_aram(self, ctx):
        
        texte_general = " La ranked aram commence automatiquement après la première game. Pour désactiver, il est possible d'utiliser /ranked_aram. \n" + \
                        "Le suivi est possible en tapant /classement_aram"
        
        embed = discord.Embed(title = 'Help Aram', description='Règle', colour = discord.Colour.blurple())
        
        embed.add_field(name='Déroulement général', value=texte_general)
        
        embed2 = discord.Embed(title='Palier', description="Rang", color=discord.Colour.blue())
        
        embed2.add_field(name='IRON', values="LP < 100")
        embed2.add_field(name='BRONZE', values="100 < LP < 200")
        embed2.add_field(name='SILVER', values="200 < LP < 300")
        embed2.add_field(name='GOLD', values="300 < LP < 500")
        embed2.add_field(name='PLATINE', values="500 < LP < 800")
        embed2.add_field(name='DIAMOND', values="800 < LP < 1200")
        embed2.add_field(name='MASTER', values="1200 < LP < 1600")
        embed2.add_field(name='GRANDMASTER', values="1600 < LP < 2000")
        embed2.add_field(name='CHALLENGER', values="2000 < LP")

        embed3 = discord.Embed(title='Calcul points', description="MMR", color=discord.Colour.orange())
        
        embed3.add_field(name="5 premières games", description=f"5 premières games \n" + 
                         "Victoires : 50 points | Defaites : 0 points")
        
        calcul_points = "WR < 40% - V : + 10 | D : - 20 \n"
       
        for key, value in dict_points:
           calcul_points = calcul_points + f" = WR {key}% - V : + {value[0]} | D : {value[1]} \n"
        
        calcul_points = calcul_points + "WR > 60% - V : +30 / D : -10"
        
        embed3.add_field(name='Calcul des points', value="calcul_points")
        
        bonus_elo = ""
        for key, value in elo_lp:
            bonus_elo = bonus_elo + f" Bonus/Malus {key} : {value} \n"
        
        embed3.add_field(name="Bonus elo", value=bonus_elo)
        
        await ctx.send(embed=embed)
        await ctx.send(embed=embed2)
        await ctx.send(embed=embed3)

        
                #         if games <=5:
                #     if str(match_info.thisWinId) == 'True':
                #         points = 50
                #     else:
                #         points = 0
                
                # elif wr > 60:
                #     if str(match_info.thisWinId) == 'True':
                #         points = 30
                #     else:
                #         points = -10
                        
                # elif wr < 40:
                #     if str(match_info.thisWinId) == "True":
                #         points = 10
                #     else:
                #         points = -20
                # else:
                #     if str(match_info.thisWinId) == "True":
                #         points = dict_points[int(wr)][0]
                #     else:
                #         points = dict_points[int(wr)][1]
                        
                # lp = lp_actual + points
                        



def setup(bot):
    bot.add_cog(Aram(bot))
