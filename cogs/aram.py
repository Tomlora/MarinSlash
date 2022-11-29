import pandas as pd
from fonctions.gestion_bdd import (lire_bdd,
                                   requete_perso_bdd,
                                   lire_bdd_perso,
                                   get_data_bdd)
import datetime
from fonctions.channels_discord import chan_discord
import interactions
from interactions import Choice, Option, Extension, CommandContext
from fonctions.permissions import isOwner_slash
from interactions.ext.tasks import IntervalTrigger, create_task
from fonctions.params import Version


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


class Aram(Extension):
    def __init__(self, bot ):
        self.bot: interactions.Client = bot

    @interactions.extension_listener
    async def on_start(self):
        self.task1 = create_task(IntervalTrigger(60*60))(self.lolsuivi_aram)
        self.task1.start()
        
        
    @interactions.extension_command(name="classement_aram",description="classement en aram")
    async def ladder_aram(self, ctx:CommandContext):        

        suivi_aram = lire_bdd('ranked_aram', 'dict')
        
        await ctx.defer(ephemeral=False)

        df = pd.DataFrame.from_dict(suivi_aram)
        df = df.transpose().reset_index()

        df.sort_values('lp', ascending=False, inplace=True)

        embed = interactions.Embed(title="Suivi LOL", description='ARAM', color=interactions.Color.blurple())

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
                                                    
        embed.set_footer(text=f'Version {Version} by Tomlora')  

        await ctx.send(embeds=embed)
        

    @interactions.extension_command(name='ranked_aram',
                                    description='Activation/Désactivation',
                       options=[Option(
                                    name='summonername',
                                    description="nom ingame",
                                    type=interactions.OptionType.STRING,
                                    required=True),
                                Option(
                                    name="activation",
                                    description="True : Activé / False : Désactivé",
                                    type=interactions.OptionType.BOOLEAN,
                                    required=True)])
    
    async def update_activation(self,
                                ctx:CommandContext,
                                summonername:str, activation:bool):
        
        summonername = summonername.lower()
        
        try:
            requete_perso_bdd('UPDATE ranked_aram SET activation = :activation WHERE index = :index', {'activation' : activation, 'index' : summonername})
            if activation:
                await ctx.send('Ranked activé !')
            else:
                await ctx.send('Ranked désactivé !')
        except KeyError:
            await ctx.send('Joueur introuvable')
            

            
    @interactions.extension_command(name="help_aram",
                                    description='Help ranked aram')
    async def help_aram(self, ctx:CommandContext):
        
        texte_general = " La ranked aram commence automatiquement après la première game. Pour désactiver, il est possible d'utiliser **/ranked_aram.** après la première partie \n" + \
                        "Le suivi est possible en tapant **/classement_aram**"
                        
        await ctx.defer(ephemeral=False)
        
        embed = interactions.Embed(title = 'Help Aram', description='Règle', color = interactions.Color.blurple())
        
        embed.add_field(name='Déroulement général', value=texte_general)
        
        embed2 = interactions.Embed(title='Palier', description="Rang", color=interactions.Color.blue())
        
        embed2.add_field(name='IRON', value="LP < 100")
        embed2.add_field(name='BRONZE', value="100 < LP < 200")
        embed2.add_field(name='SILVER', value="200 < LP < 300")
        embed2.add_field(name='GOLD', value="300 < LP < 500")
        embed2.add_field(name='PLATINUM', value="500 < LP < 800")
        embed2.add_field(name='DIAMOND', value="800 < LP < 1200")
        embed2.add_field(name='MASTER', value="1200 < LP < 1600")
        embed2.add_field(name='GRANDMASTER', value="1600 < LP < 2000")
        embed2.add_field(name='CHALLENGER', value="2000 < LP")

        embed3 = interactions.Embed(title='Calcul points', description="MMR", color=interactions.Color.orange())
        
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
        
        await ctx.send(embeds=embed)
        await ctx.send(embeds=embed2)
        await ctx.send(embeds=embed3)
           
    @interactions.extension_command(name='carton',
                       description='Activation/Désactivation',
                       options=[
                           Option(
                           name='couleur',
                            description="vert = + / rouge = -",
                            type=interactions.OptionType.STRING,
                            required=True, choices=[
                                Choice(name='vert', value='vert'),
                                Choice(name='rouge', value='rouge')]),
                            Option(
                                name="summonername",
                                description="nom ingame",
                                type=interactions.OptionType.STRING,
                                required=True),
                            Option(
                                name='nombre',
                                description='nombre de lp',
                                type=interactions.OptionType.INTEGER,
                                required=True)])
    async def carton(self, ctx:CommandContext, couleur:str, summonername:str, nombre:int):
        if isOwner_slash(ctx):
            if couleur == 'vert':
                requete_perso_bdd('UPDATE ranked_aram SET lp = lp + :nombre WHERE index = :summonername', {'nombre' : nombre, 'summonername' : summonername.lower()})
                msg = f'Les LP pour {summonername} ont été ajoutés.'
            if couleur == 'rouge':
                requete_perso_bdd('UPDATE ranked_aram SET lp = lp - :nombre WHERE index = :summonername', {'nombre' : nombre, 'summonername' : summonername.lower()})
                msg = f'Les LP pour {summonername} ont été retirés.'
        else:
            requete_perso_bdd('UPDATE ranked_aram SET lp = lp - 1 WHERE index = :summonername', {'summonername' : summonername.lower()})
            msg = 'Bien essayé ! Tu perds 1 lp.'
 
        embed = interactions.Embed(description=msg,
                              color=interactions.Color.blurple())

        await ctx.send(embeds=embed)
        
    async def lolsuivi_aram(self):

        currentHour = str(datetime.datetime.now().hour)

        if currentHour == str(3):
            
            data = get_data_bdd(f'''SELECT DISTINCT tracker.server_id from tracker 
                    INNER JOIN channels_module on tracker.server_id = channels_module.server_id
                    where channels_module.league_aram = true''').fetchall()
            
            for server_id in data:
                
                guild = await interactions.get(client=self.bot,
                                                        obj=interactions.Guild,
                                                        object_id=server_id[0])  

                
                chan_discord_id = chan_discord(int(guild.id))
            
            # le suivi est déjà maj par game/update... Pas besoin de le refaire ici..

                df = lire_bdd_perso(f'''SELECT suivi.index, suivi.wins, suivi.losses, suivi.lp, suivi.rank, tracker.server_id from ranked_aram as suivi 
                                        INNER join tracker ON tracker.index = suivi.index 
                                        where tracker.server_id = {int(guild.id)} ''')
                df_24h = lire_bdd_perso(f'''SELECT suivi.index, suivi.wins, suivi.losses, suivi.lp, suivi.rank, tracker.server_id from ranked_aram_24h as suivi
                                        INNER join tracker ON tracker.index = suivi.index 
                                        where tracker.server_id = {int(guild.id)} ''')
                    
                if df.shape[1] > 0: # s'il y a des données

                    df = df.transpose().reset_index()
                    
                    df_24h = df_24h.transpose().reset_index()

                    def changement_tier(x):
                        dict_chg_tier = {'IRON' : 1,
                        'BRONZE' : 1,
                        'SILVER' : 2,
                        'GOLD' : 3,
                        'PLATINUM' : 4,
                        'DIAMOND' : 5,
                        'MASTER' : 6}
                        return dict_chg_tier[x]

                    # Pour l'ordre de passage
                    df['tier_pts'] = df['rank'].apply(changement_tier)

                    sql = ''
                    df.sort_values(by=['tier_pts', 'lp'], ascending=[False, False], inplace=True)

                    suivi = df.set_index('index').transpose().to_dict()
                    suivi_24h = df_24h.set_index('index').transpose().to_dict()
                    joueur = suivi.keys()

                    embed = interactions.Embed(title="Suivi ARAM LOL", description='Periode : 24h', color=interactions.Color.blurple())
                    totalwin = 0
                    totaldef = 0
                    totalgames = 0
                


                    for key in joueur:


                        # suivi est mis à jour par update et updaterank. On va donc prendre le comparer à suivi24h
                        wins = int(suivi_24h[key]['wins'])
                        losses = int(suivi_24h[key]['losses'])
                        nbgames = wins + losses
                        LP = int(suivi_24h[key]['lp'])
                        tier_old = str(suivi_24h[key]['rank'])


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
                                            
                        if difwins + diflosses > 0: # si supérieur à 0, le joueur a joué
                            sql += f'''UPDATE ranked_aram_24h SET wins = {suivi[key]['wins']}, losses = {suivi[key]['losses']}, lp = {suivi[key]['lp']}, rank = '{tier}' where index = '{key}';'''
                                                            
                    
                    channel_tracklol = await interactions.get(client=self.bot,
                                                      obj=interactions.Channel,
                                                      object_id=chan_discord_id.lol_others) 
                        
                    embed.set_footer(text=f'Version {Version} by Tomlora')  

                    await channel_tracklol.send(embeds=embed)
                    await channel_tracklol.send(f'Sur {totalgames} games -> {totalwin} victoires et {totaldef} défaites')



def setup(bot):
    Aram(bot)
