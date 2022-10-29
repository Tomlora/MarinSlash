import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice

from fonctions.gestion_base_oracle import loaddata_oracle, rechargement_data_oracle

import main
import mwclient
import urllib.request
import json
import re
import pandas as pd
import ast
import os
import warnings
import datetime

# à faire : https://lol.fandom.com/wiki/Special:CargoTables/RosterRumors


warnings.simplefilter('ignore')

def extraire_variables_imbriquees(df, colonne):
    # Vocabulaire à connaitre : liste/dictionnaire en compréhension
    df[colonne] = [ast.literal_eval(str(item)) for index, item in df[colonne].iteritems()]

    df = pd.concat([df.drop([colonne], axis=1), df[colonne].apply(pd.Series)], axis=1)
    return df


class Leaguepedia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.site = mwclient.Site('lol.fandom.com', path='/')
        self.recharge_oracle.start()
        
    
    @tasks.loop(hours=1, count=None)
    async def recharge_oracle(self):
        '''Rechargement base oracle elixir'''
        currentHour = str(datetime.datetime.now().hour)
        
        if currentHour == str(13):   
            rechargement_data_oracle()

    @cog_ext.cog_slash(name="league_avatar", description="Photo d'un joueur")
    async def leagueavatar(self, ctx, player):
        
        def get_filename_url_to_open(site, filename, player, size=None):
            pattern = r'.*src\=\"(.+?)\".*'
            size = '|' + str(size) + 'px' if size else ''
            to_parse_text = '[[File:{}|link=%s]]'.format(filename, size)
            result = site.api('parse', title='Main Page',
                            text=to_parse_text, disablelimitreport=1)
            parse_result_text = result['parse']['text']['*']

            url = re.match(pattern, parse_result_text)[1]
            #In case you would like to save the image in a specific location, you can add the path after 'url,' in the line below.
            urllib.request.urlretrieve(url, player + '.png')


        response = self.site.api('cargoquery',
                                limit=1,
                                tables="PlayerImages",
                                fields="FileName",
                                where='Link="%s"' % player,
                                format="json"
                                )
        parsed = json.dumps(response)
        decoded = json.loads(parsed)
        url = str(decoded['cargoquery'][0]['title']['FileName'])
        get_filename_url_to_open(self.site, url, player)
        
        await ctx.send(file=discord.File(player + '.png'))
        
        os.remove(player + '.png')
        
        
    @cog_ext.cog_slash(name="lol_mercato", description="Les derniers mouvements",
                        options=[create_option(name="league", description= "Trié sur une league ?", option_type=3, required=False)])
    async def lol_mercato(self, ctx, league:str=""):
        
        # On récupère les dernières infos mercato sur Leaguepedia
        response = self.site.api('cargoquery',
        limit = 500,
        tables = "RosterChanges=RC",
        fields = "RC.Tournaments, RC.Date_Sort, RC.Player, RC.Direction, RC.Team, RC.Role",
        order_by = "RC.Date_Sort DESC"
    )

        ctx.defer(hidden=False)
        parsed = json.dumps(response)
        decoded = json.loads(parsed)

        data_mercato = pd.DataFrame(decoded['cargoquery'])
        data_mercato = extraire_variables_imbriquees(data_mercato, 'title')

        # Date :
        data_mercato['Date Sort'] = pd.to_datetime(data_mercato['Date Sort'])
        data_mercato['Jour'] = data_mercato['Date Sort'].dt.day
        data_mercato['Année'] = data_mercato['Date Sort'].dt.year
        data_mercato['Mois'] = data_mercato['Date Sort'].dt.month
        data_mercato.drop(['Date Sort'], axis=1, inplace=True)
        data_mercato
        
        # On ouvre la data oracle qui permet d'identifier les équipes et leurs régions

        data_oracle = loaddata_oracle()

        data_equipe = data_oracle[['teamname', 'league']].drop_duplicates().set_index('teamname')

        data_mercato['Competition'] = data_mercato['Team'].map(data_equipe.to_dict()['league'])
        
        # On map des mots anglais par français
        
        data_mercato['Direction'] = data_mercato['Direction'].map({'Join' : 'Rejoint', 'Leave' : 'Quitte'})
        
        if not league == "": # Si tri sur une league
            data_mercato = data_mercato[data_mercato['Competition'] == league]
        
        embed = discord.Embed(
                title="Mercato", color=discord.Color.orange())

        for key, value in data_mercato.head(10).iterrows():
            player = value['Player']
            action = value['Direction']
            equipe = value['Team']
            mois = value['Mois']
            jour = value['Jour']
            competition = value['Competition']
            role = value['Role']
            
            embed.add_field(name=player, value=f'{action} {equipe} ({competition}) en tant que {role} le {jour}-{mois}', inline=False)
            
        await ctx.send(embed=embed)
        
        
        

def setup(bot):
    bot.add_cog(Leaguepedia(bot))
