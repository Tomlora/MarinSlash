import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from riotwatcher import LolWatcher
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option
import pandas as pd
import ast
import os
import requests # Riotwatcher n'a pas les challenges donc on va faire une requests.get

api_key_lol = os.environ.get('API_LOL')  # https://www.youtube.com/watch?v=IolxqkL7cD8

lol_watcher = LolWatcher(api_key_lol)
my_region = 'euw1'
region = "EUROPE"
import main

def extraire_variables_imbriquees(df, colonne):
    # Vocabulaire à connaitre : liste/dictionnaire en compréhension
    df[colonne] = [ast.literal_eval(str(item)) for index, item in df[colonne].iteritems()]

    df = pd.concat([df.drop([colonne], axis=1), df[colonne].apply(pd.Series)], axis=1)
    return df

def get_data_challenges():
    data_challenges = requests.get(f'https://{my_region}.api.riotgames.com/lol/challenges/v1/challenges/config?api_key={api_key_lol}') # regroupe tous les défis
    data_challenges = data_challenges.json()
    data_challenges = pd.data_challengesFrame(data_challenges)
    data_challenges = extraire_variables_imbriquees(data_challenges, 'localizedNames')
    data_challenges = data_challenges[['id', 'state', 'thresholds', 'fr_FR']]
    data_challenges = extraire_variables_imbriquees(data_challenges, 'fr_FR')
    data_challenges = extraire_variables_imbriquees(data_challenges, 'thresholds')
    data_challenges = data_challenges[['id', 'state','name', 'shortDescription', 'description', 'IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']] # on change l'ordre
    return data_challenges

def get_puuid(summonername:str):
    me = lol_watcher.summoner.by_name(my_region, summonername)
    puuid = me['puuid']
    return puuid

def get_data_joueur(summonername):
    puuid = get_puuid(summonername)
    data_joueur = requests.get(f'https://{my_region}.api.riotgames.com/lol/challenges/v1/player-data/{puuid}?api_key={api_key_lol}')
    data_joueur = data_joueur.json()
    data_total_joueur = data_joueur['totalPoints'] #dict
    data_joueur_category = pd.DataFrame(['categoryPoints'])
    data_joueur_challenges = pd.DataFrame(data_joueur['challenges'])
    data_joueur_challenges.drop(['position', 'playersInLevel'], axis=1, inplace=True) # colonnes vides // # il faudra mapper les challenges id avec get_data_challenges
    return data_total_joueur, data_joueur_category, data_joueur_challenges




class Challenges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @cog_ext.cog_slash(name="challenges_test",
                       description="Defis ingame",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    async def challenges_test(self, ctx, summonername:str):
        total, category, challenges = get_data_joueur(summonername)
        print(challenges)
    
        
        
    



def setup(bot):
    bot.add_cog(Challenges(bot))
