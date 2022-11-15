import pandas as pd
import numpy as np
from discord.ext import commands, tasks
from discord_slash.utils.manage_components import *
from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd, requete_perso_bdd
import main
from discord_slash import cog_ext
from discord_slash.utils.manage_commands import create_option, create_choice
import datetime



dict_points = {41 : [11, -19],
                               42 : [12, -18],
                               43 : [13, -17],
                               44 : [14, -16],
                               45 : [15, -15],
                               46 : [16, -15],
                               47 : [17, -15],
                               48 : [18, -15],
                               49 : [19, -15],
                               50 : [20, -15],
                               51 : [21, -15],
                               52 : [22, -15],
                               53 : [23, -15],
                               54 : [24, -15],
                               55 : [25, -15],
                               56 : [26, -14],
                               57 : [27, -13],
                               58 : [28, -12],
                               59 : [29, -11]} 

elo_lp = {'IRON' : 0,
        'BRONZE' : 1,
        'SILVER' : 2,
        'GOLD' : 3,
        'PLATINUM' : 4,
        'DIAMOND' : 5,
        'MASTER' : 6,
        'GRANDMASTER' : 7,
        'CHALLENGER' : 8,
        'FIRST_GAME' : 0}


chan_general = 768637526176432158


class Aram(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lolsuivi_aram.start()


    @cog_ext.cog_slash(name="classement_aram",description="classement en aram")
    async def ladder_aram(self, ctx):        

        suivi_aram = lire_bdd('ranked_aram', 'dict')
        
        await ctx.defer(hidden=False)

        df = pd.DataFrame.from_dict(suivi_aram)
        df = df.transpose().reset_index()

        df.sort_values('lp', ascending=False, inplace=True)

        embed = discord.Embed(title="Suivi LOL", description='ARAM', colour=discord.Colour.blurple())

        for key in df['index']:
            
            wr = round((suivi_aram[key]['wins'] / suivi_aram[key]['games'])*100,2)
            
            kda = round((suivi_aram[key]['k'] + suivi_aram[key]['a']) / suivi_aram[key]['d'],2)
            
            
            if suivi_aram[key]['activation']:
                embed.add_field(name=str(f"{key} ({suivi_aram[key]['lp']} LP) [{suivi_aram[key]['rank']}]"),
                            value="V : " + str(suivi_aram[key]['wins']) + " | D : " + str(suivi_aram[key]['losses']) + " | WR :  "
                                                + str(wr) + "% | KDA : " + str(kda), inline=False)
            else:
                embed.add_field(name=str(f"{key} ({suivi_aram[key]['lp']} LP) [{suivi_aram[key]['rank']}] [Désactivé]"),
                            value="V : " + str(suivi_aram[key]['wins']) + " | D : " + str(suivi_aram[key]['losses']) + " | WR :  "
                                                + str(wr) + "% | KDA : " + str(kda), inline=False)
                                                    
        embed.set_footer(text=f'Version {main.Var_version} by Tomlora')  

        await ctx.send(embed=embed)
        

    @cog_ext.cog_slash(name='ranked_aram', description='Activation/Désactivation',
                       options=[create_option(name='summonername', description="nom ingame", option_type=3, required=True),
                                create_option(name="activation", description="True : Activé / False : Désactivé", option_type=5, required=True)])
    
    async def update_activation(self, ctx, summonername:str, activation:bool):
        
        summonername = summonername.lower()
        
        try:
            requete_perso_bdd('UPDATE ranked_aram SET activation = :activation WHERE index = :index', {'activation' : activation, 'index' : summonername})
            if activation:
                await ctx.send('Ranked activé !')
            else:
                await ctx.send('Ranked désactivé !')
        except KeyError:
            await ctx.send('Joueur introuvable')
            

            
    @cog_ext.cog_slash(name="help_aram", description='Help ranked aram')
    async def help_aram(self, ctx):
        
        texte_general = " La ranked aram commence automatiquement après la première game. Pour désactiver, il est possible d'utiliser **/ranked_aram.** après la première partie \n" + \
                        "Le suivi est possible en tapant **/classement_aram**"
                        
        await ctx.defer(hidden=False)
        
        embed = discord.Embed(title = 'Help Aram', description='Règle', colour = discord.Colour.blurple())
        
        embed.add_field(name='Déroulement général', value=texte_general)
        
        embed2 = discord.Embed(title='Palier', description="Rang", color=discord.Colour.blue())
        
        embed2.add_field(name='IRON', value="LP < 100")
        embed2.add_field(name='BRONZE', value="100 < LP < 200")
        embed2.add_field(name='SILVER', value="200 < LP < 300")
        embed2.add_field(name='GOLD', value="300 < LP < 500")
        embed2.add_field(name='PLATINUM', value="500 < LP < 800")
        embed2.add_field(name='DIAMOND', value="800 < LP < 1200")
        embed2.add_field(name='MASTER', value="1200 < LP < 1600")
        embed2.add_field(name='GRANDMASTER', value="1600 < LP < 2000")
        embed2.add_field(name='CHALLENGER', value="2000 < LP")

        embed3 = discord.Embed(title='Calcul points', description="MMR", color=discord.Colour.orange())
        
        embed3.add_field(name="5 premières games", value=f"5 premières games \n" + 
                         "V : **+50**  | D : **0**", inline=False)
        
        calcul_points = "WR **<40%** - V : **+10** | D : **-20** \n"
       
        for key, value in dict_points.items():
           calcul_points = calcul_points + f" WR **{key}%** - V : **+{value[0]}** | D : **{value[1]}** \n"
        
        calcul_points = calcul_points + "WR **>60%** - V : **+30** / D : **-10**"
        
        embed3.add_field(name='Calcul des points', value=calcul_points, inline=False)
        
        bonus_elo = ""
        for key, value in elo_lp.items():
            bonus_elo = bonus_elo + f"{key} : **-{value}** \n"
        
        embed3.add_field(name="Malus elo", value=bonus_elo, inline=False)
        
        await ctx.send(embed=embed)
        await ctx.send(embed=embed2)
        await ctx.send(embed=embed3)
           
    @cog_ext.cog_slash(name='carton', description='Activation/Désactivation',
                       options=[create_option(name='couleur', description="nom ingame", option_type=3, required=True, choices=[
                                create_choice(name='vert', value='vert'),
                                create_choice(name='rouge', value='rouge')]),
                                create_option(name="summonername", description="True : Activé / False : Désactivé", option_type=3, required=True),
                                create_option(name='nombre', description='nombre de lp', option_type=4, required=True)])
    async def carton(self, ctx, couleur:str, summonername:str, nombre:int):
        if main.isOwner_slash(ctx):
            if couleur == 'vert':
                requete_perso_bdd('UPDATE ranked_aram SET lp = lp + :nombre WHERE index = :summonername', {'nombre' : nombre, 'summonername' : summonername.lower()})
                msg = f'Les LP pour {summonername} ont été ajoutés.'
            if couleur == 'rouge':
                requete_perso_bdd('UPDATE ranked_aram SET lp = lp - :nombre WHERE index = :summonername', {'nombre' : nombre, 'summonername' : summonername.lower()})
                msg = f'Les LP pour {summonername} ont été retirés.'
        else:
            requete_perso_bdd('UPDATE ranked_aram SET lp = lp - 1 WHERE index = :summonername', {'summonername' : summonername.lower()})
            msg = 'Bien essayé ! Tu perds 1 lp.'
        
        embed = discord.Embed(description=msg,
                              color=discord.Colour.from_rgb(255, 255, 0))

        await ctx.send(embed=embed)
        
    @tasks.loop(hours=1, count=None)
    async def lolsuivi_aram(self):

        currentHour = str(datetime.datetime.now().hour)

        if currentHour == str(3):
            
            # le suivi est déjà maj par game/update... Pas besoin de le refaire ici..

            suivi = lire_bdd('ranked_aram', 'dict')
            suivi_24h = lire_bdd('ranked_aram_24h', 'dict')
            
            
            # df = lire_bdd_perso("""SELECT * from suivi WHERE tier != 'Non-classe'""").transpose().reset_index()
            df = pd.DataFrame.from_dict(suivi)
            df = df.transpose().reset_index()
            
            # df_24h = lire_bdd_perso("""SELECT * from suivi_24h WHERE tier != 'Non-classe'""").transpose().reset_index()
            df_24h = pd.DataFrame.from_dict(suivi_24h)
            df_24h = df_24h.transpose().reset_index()

            

            # Pour l'ordre de passage
            df['tier_pts'] = 0
            df['tier_pts'] = np.where(df.rank == 'IRON', 0, df.tier_pts)
            df['tier_pts'] = np.where(df.rank == 'BRONZE', 1, df.tier_pts)
            df['tier_pts'] = np.where(df.rank == 'SILVER', 2, df.tier_pts)
            df['tier_pts'] = np.where(df.rank == 'GOLD', 3, df.tier_pts)
            df['tier_pts'] = np.where(df.rank == 'PLATINUM', 4, df.tier_pts)
            df['tier_pts'] = np.where(df.rank == 'DIAMOND', 5, df.tier_pts)
            df['tier_pts'] = np.where(df.rank == 'MASTER', 6, df.tier_pts)

            
            df.sort_values(by=['tier_pts', 'lp'], ascending=[False, False], inplace=True)

            joueur = df['index'].to_dict()


            embed = discord.Embed(title="Suivi ARAM LOL", description='Periode : 24h', colour=discord.Colour.blurple())
            totalwin = 0
            totaldef = 0
            totalgames = 0
            


            for key in joueur.values():

                try:
                        # suivi est mis à jour par update et updaterank. On va donc prendre le comparer à suivi24h
                    wins = int(suivi_24h[key]['wins'])
                    losses = int(suivi_24h[key]['losses'])
                    nbgames = wins + losses
                    LP = int(suivi_24h[key]['lp'])
                    tier_old = str(suivi_24h[key]['rank'])
                except:
                    wins = 0
                    losses = 0
                    nbgames = 0
                    LP = 0
                    tier_old = 'IRON'

                    # on veut les stats soloq

                tier = str(suivi[key]['rank'])

                difwins = int(suivi[key]['wins']) - wins
                diflosses = int(suivi[key]['losses']) - losses
                difLP = int(suivi[key]['lp']) - LP
                totalwin = totalwin + difwins
                totaldef = totaldef + diflosses
                totalgames = totalwin + totaldef
                    
                    # evolution

                if elo_lp[tier_old] > elo_lp[tier]: # 19-18
                    difLP = "Démote / -" + str(difLP)
                    emote = ":arrow_down:"

                elif elo_lp[tier_old] < elo_lp[tier]:
                    difLP = "Promotion / +" + str(difLP)
                    emote = ":arrow_up:"
                            
                elif elo_lp[tier_old] == elo_lp[tier]:
                    if difLP > 0:
                        emote = ":arrow_up:"
                    elif difLP < 0:
                        emote = ":arrow_down:"
                    elif difLP == 0:
                        emote = ":arrow_right:"
                                

                embed.add_field(name=str(key) + " ( " + tier + " )",
                                        value="V : " + str(suivi[key]['wins']) + "(" + str(difwins) + ") | D : "
                                            + str(suivi[key]['losses']) + "(" + str(diflosses) + ") | LP :  "
                                            + str(suivi[key]['lp']) + "(" + str(difLP) + ")    " + emote, inline=False)
                                           

            sauvegarde_bdd(suivi, 'ranked_aram_24h')
            channel_tracklol = self.bot.get_channel(int(main.chan_lol_others)) 
            
            embed.set_footer(text=f'Version {main.Var_version} by Tomlora')  

            await channel_tracklol.send(embed=embed)
            await channel_tracklol.send(f'Sur {totalgames} games -> {totalwin} victoires et {totaldef} défaites')



def setup(bot):
    bot.add_cog(Aram(bot))
