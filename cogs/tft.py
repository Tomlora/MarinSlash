
from discord.ext import commands, tasks

import pandas as pd
import main
import warnings
from discord_slash.utils.manage_components import *

from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd
from tqdm import tqdm
import requests
import json

from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice





warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'

import os



my_region = 'euw1'
region = "europe"


dict_rankid = {"BRONZE IV" : 1,
               "BRONZE III" : 2,
               "BRONZE II" : 3,
               "BRONZE I" : 4,
               "SILVER IV" : 5,
               "SILVER III" : 6,
               "SILVER II": 7,
               "SILVER I" : 8,
               "GOLD IV" : 9,
               "GOLD III" : 10,
               "GOLD II" : 11,
               "GOLD I" : 12,
               "PLATINUM IV" : 13,
               "PLATINUM III" : 14,
               "PLATINUM II" : 15,
               "PLATINUM I" : 16,
               "DIAMOND IV" : 17,
               "DIAMOND III" : 18,
               "DIAMOND II" : 19,
               "DIAMOND I" : 20}


headers = {"X-Riot-Token": "RGAPI-cfa6cf64-0335-43d4-babc-7d54abca77c2"}

def get_puuidTFT(summonername):
    me = requests.get(f'https://{my_region}.api.riotgames.com/tft/summoner/v1/summoners/by-name/{summonername}', headers=headers).json()
    return me['puuid']


def get_stats_ranked(summonername):
    me = requests.get(f'https://{my_region}.api.riotgames.com/tft/summoner/v1/summoners/by-name/{summonername}', headers=headers).json()
    me = me['id']
    
    stats = requests.get(f'https://{my_region}.api.riotgames.com/tft/league/v1/entries/by-summoner/{me}', headers=headers).json()
    return stats
    
    

def matchtft_by_puuid(summonerName, idgames: int):
    puuid = get_puuidTFT(summonerName)
    liste_matchs = requests.get(f'https://{region}.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids?start=0&count=20', headers=headers).json()
    last_match = liste_matchs[idgames]
    match = requests.get(f'https://{region}.api.riotgames.com/tft/match/v1/matches/{last_match}', headers=headers).json()
    match = pd.DataFrame(match)
    return match, last_match, puuid


dict_rankid = {"BRONZE IV" : 1,
               "BRONZE III" : 2,
               "BRONZE II" : 3,
               "BRONZE I" : 4,
               "SILVER IV" : 5,
               "SILVER III" : 6,
               "SILVER II": 7,
               "SILVER I" : 8,
               "GOLD IV" : 9,
               "GOLD III" : 10,
               "GOLD II" : 11,
               "GOLD I" : 12,
               "PLATINUM IV" : 13,
               "PLATINUM III" : 14,
               "PLATINUM II" : 15,
               "PLATINUM I" : 16,
               "DIAMOND IV" : 17,
               "DIAMOND III" : 18,
               "DIAMOND II" : 19,
               "DIAMOND I" : 20,
               "MASTER I" : 21,
               "GRANDMASTER I" : 22,
               'CHALLENGER I' : 23}
    
    


class TFT(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.my_taskTFT.start()

 

    # ----------------------------- test

    @tasks.loop(minutes=1, count=None)
    async def my_taskTFT(self):
        await self.updatetft()

        
     
    def stats_TFT(self, summonername, idgames:int=0):
        match_detail, id_match, puuid = matchtft_by_puuid(summonername, idgames)
        
        # identifier le joueur via son puuid
        
        dic = {
            (match_detail['info']['participants'][0]['puuid']): 0,
            (match_detail['info']['participants'][1]['puuid']): 1,
            (match_detail['info']['participants'][2]['puuid']): 2,
            (match_detail['info']['participants'][3]['puuid']): 3,
            (match_detail['info']['participants'][4]['puuid']): 4,
            (match_detail['info']['participants'][5]['puuid']): 5,
            (match_detail['info']['participants'][6]['puuid']): 6,
            (match_detail['info']['participants'][7]['puuid']): 7,
        }
        
        thisQ = ' '
        

        thisId = dic[puuid]
        
        stats_joueur = match_detail['info']['participants'][thisId]
        
        # classé ?
        
        thisQId = match_detail['info']['queue_id']
        
        if thisQId == 1100:
            thisQ == "RANKED"
        else:
            thisQ == "NORMAL"
            
        # Durée
        
        thisTime = round(match_detail['info']['game_length'] / 60, 0)
        
        augments = stats_joueur['augments']
        
        msg_augment = ''
        
        for augment in augments:
            augment = augment.replace('TFT6_Augment_', '').replace('TFT7_Augment_', '')
            msg_augment = f'{msg_augment} | {augment}'
        
        # Classement
        
        classement = stats_joueur['placement']
        
        
        # Stats
        
        last_round = stats_joueur['last_round']
        level = stats_joueur['level']
        joueurs_elimines = stats_joueur['players_eliminated']
        gold_restants = stats_joueur['gold_left']     

     

            
        # Stats
        
        profil = get_stats_ranked(summonername)[0]
        
        wins = profil['wins']
        losses = profil['losses']
        wr = round((wins/(int(wins)+int(losses)))*100,0)
        tier = profil['tier']
        rank = profil['rank']
        lp = profil['leaguePoints']
        
        # Gain/Perte de LP
        
        suivi_profil = lire_bdd('suiviTFT', 'dict')
        
        
        
        try:
            lp_before_this_game = int(suivi_profil[summonername]['LP'])
            difLP = lp - lp_before_this_game
        except:
            lp_before_this_game = 0
            difLP = lp - lp_before_this_game
            
        if difLP > 0:
            difLP = "+" + str(difLP)
        elif difLP < 0:
            difLP = str(difLP)
            
        classement_old = suivi_profil[summonername]['tier'] + " " + suivi_profil[summonername]['rank']
        classement_new = tier + " " + rank
        
                
        if dict_rankid[classement_old] > dict_rankid[classement_new]: # 19-18
            difLP = 100 + lp - int(suivi_profil[summonername]['LP'])
            difLP = "Démote / -" + str(difLP)


        elif dict_rankid[classement_old] < dict_rankid[classement_new]:
            difLP = 100 - lp + int(suivi_profil[summonername]['LP'])
            difLP = "Promotion / +" + str(difLP)


        suivi_profil[summonername]['tier'] = tier
        suivi_profil[summonername]['rank'] = rank
        suivi_profil[summonername]['LP'] = lp
                    
        sauvegarde_bdd(suivi_profil, 'suiviTFT')

            
        
        
        
        
        # Embed
        
        summonername = summonername.upper()
        
        if (summonername == 'NAMIYEON') or (summonername == 'ZYRADELEVINGNE') or (summonername == 'CHATOBOGAN'):
            color = discord.Color.gold()
        elif summonername == 'DJINGO':
            color = discord.Color.orange()
        elif summonername == 'TOMLORA':
            color = discord.Color.dark_green()
        elif summonername == 'YLARABKA':
            color = discord.Colour.from_rgb(253, 119, 90)
        elif (summonername == 'LINÒ') or (summonername == 'LORDOFCOUBI') or (summonername == 'NUKETHESTARS'):
            color = discord.Colour.from_rgb(187, 112, 255)
        elif (summonername == 'EXORBLUE'):
            color = discord.Colour.from_rgb(223, 55, 93)
        elif (summonername == 'KULBUTOKÉ'):
            color = discord.Colour.from_rgb(42, 188, 248)
        elif (summonername == 'KAZSC'):
            color = discord.Colour.from_rgb(245, 68, 160)
        elif (summonername == 'CHGUIZOU'):
            color = discord.Colour.from_rgb(127, 0, 255)
        else:
            color = discord.Color.blue()
        
        
        
        embed = discord.Embed(
                title=f"** {summonername} ** vient de finir ** {classement}ème ** sur TFT", color=color)
        
        embed.add_field(name="Durée de la game :",
                            value=f'{thisTime} minutes')
        
        embed.add_field(name="Augments : ",
                            value=msg_augment, inline=False)
        
        # Stats
        embed.add_field(name=f'Current rank : {tier} {rank} | {lp}LP ({difLP})', value=f'winrate : {wr}% \nVictoires : {wins} | Defaites : {losses} ', inline=False)
        
        
        # on va créer un dataframe pour les sort plus facilement
        
        df_traits = pd.DataFrame(stats_joueur['traits'])
        df_traits = df_traits.sort_values(by='tier_current', ascending=False)
        
        #[0] est l'index
        for set in df_traits.iterrows():
            name = set[1]['name'].replace('Set7_', '')
            tier_current = set[1]['tier_current']
            tier_total = set[1]['tier_total']
            nb_units = set[1]['num_units']
            
            embed.add_field(name=name, value=f"Tier: {tier_current} / {tier_total} \nNombre d'unités: {nb_units}")
            
        # dic_rarity = {1 : "Blanc",  
        #               2 : "Vert",
        #               3:"Bleu",
        #               4:"Violet",
        #               5:"Gold"}

       
        embed.add_field(name="Stats : ", value=f'Gold restants : {gold_restants} \n\
                        Level : {level} \n\
                        Dernier round : {last_round}\n\
                        Joueurs éliminés : {joueurs_elimines}', inline=False)  
        
        # pareil ici
        
        df_mobs = pd.DataFrame(stats_joueur['units'])
        df_mobs = df_mobs.sort_values(by='tier', ascending=False)
        
        for mob in df_mobs.iterrows():
            monster_name = mob[1]['character_id'].replace('TFT7_', '')
            monster_tier = mob[1]['tier']
            embed.add_field(name=f'{monster_name}', value=f'Tier : {monster_tier}')
        
        
        embed.set_footer(text=f'Version {main.Var_version} by Tomlora - Match {id_match}')
        
       

        return embed
    
    
    @cog_ext.cog_slash(name="gameTFT",description="Recap TFT",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True),
                                create_option(name="idgames", description="numero de la game", option_type=4, required=False)])
    async def gameTFT(self, ctx, summonername, idgames:int=0):
        
        await ctx.defer(hidden=False)
    
        embed = self.stats_TFT(summonername, idgames)
        
        await ctx.send(embed=embed)
        
        
    async def printLiveTFT(self, summonername):

        
        embed = self.stats_TFT(summonername, idgames=0)
        
        channel = self.bot.get_channel(int(main.chan_tft))
        
        if embed != {}:
            await channel.send(embed=embed)

               
    async def updatetft(self):
        data = lire_bdd('trackerTFT', 'dict')
        for key, value in data.items():
            match_detail, id_match, puuid = matchtft_by_puuid(key, 0)
            if str(value['id']) != id_match:  # value -> ID de dernière game enregistrée dans id_data != ID de la dernière game via l'API Rito / #key = summonername // value = numéro de la game
                try:
                    await self.printLiveTFT(key)
                except:
                    print(f"TFT : Message non envoyé car le joueur {key} a fait une partie avec moins de 10 joueurs ou un mode désactivé")
                data[key]['id'] = id_match
        data = pd.DataFrame.from_dict(data, orient="index")
        sauvegarde_bdd(data, 'trackerTFT')

    @cog_ext.cog_slash(name="tftadd",description="Ajoute le joueur au suivi",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    async def tftadd(self, ctx, *, summonername):
        # try:
            data = lire_bdd('trackerTFT', 'dict')
            suivi_profil = lire_bdd('suiviTFT', 'dict')
            
            await ctx.defer(hidden=False)
            
            profil = get_stats_ranked(summonername)[0]
        
            tier = profil['tier']
            rank = profil['rank']
            lp = profil['leaguePoints']
            match_detail, id_match, puuid = matchtft_by_puuid(summonername, 0)
            data[summonername] = {'id' : id_match}   # ajout du summonername (clé) et de l'id de la dernière game(getId)
            suivi_profil[summonername] = {'LP' : lp, 'tier': tier, 'rank': rank}
            data = pd.DataFrame.from_dict(data, orient="index")
            suivi_profil = pd.DataFrame.from_dict(suivi_profil, orient="index")
            sauvegarde_bdd(data, 'trackerTFT')
            sauvegarde_bdd(suivi_profil, 'suiviTFT')

            await ctx.send(summonername + " was successfully added to live-feed!")
        # except:
            # await ctx.send("Oops! There is no summoner with that name!")

    @cog_ext.cog_slash(name="tftremove", description="Supprime le joueur du suivi",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    async def tftremove(self, ctx, *, summonername):
        data = lire_bdd('trackerTFT', 'dict')
        if summonername in data: del data[summonername] #                                                                                             "")]  # si le summonername est présent dans la data, on supprime la data de ce summonername
        data = pd.DataFrame.from_dict(data, orient="index", columns=['id'])
        sauvegarde_bdd(data, 'trackerTFT')

        await ctx.send(summonername + " was successfully removed from live-feed!")

    @cog_ext.cog_slash(name='tftlist', description='Affiche la liste des joueurs suivis')
    async def tftlist(self, ctx):

        data = lire_bdd('trackerTFT', 'dict')
        response = ""

        for key in data.keys():
            response += key.upper() + ", "

        response = response[:-2]
        embed = discord.Embed(title="Live feed list", description=response, colour=discord.Colour.blurple())

        await ctx.send(embed=embed)
     

def setup(bot):
    bot.add_cog(TFT(bot))
