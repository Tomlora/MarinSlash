import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext
from riotwatcher import LolWatcher
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice
import pandas as pd
import ast
import os
import requests # Riotwatcher n'a pas les challenges donc on va faire une requests.get
from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd, supprimer_bdd
from fonctions.gestion_fichier import loadData
import time
import plotly.express as px
import plotly.graph_objects as go
import datetime

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
    data_challenges = pd.DataFrame(data_challenges)
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

def get_data_joueur(summonername:str):
    puuid = get_puuid(summonername)
    data_joueur = requests.get(f'https://{my_region}.api.riotgames.com/lol/challenges/v1/player-data/{puuid}?api_key={api_key_lol}')
    data_joueur = data_joueur.json()
    data_total_joueur = dict()

    data_total_joueur[summonername] = data_joueur['totalPoints'] #dict
    
    data_joueur_category = pd.DataFrame(data_joueur['categoryPoints'])

    data_joueur_challenges = pd.DataFrame(data_joueur['challenges'])
    # on ajoute le joueur
    data_joueur_category.insert(0, "Joueur", summonername)
    data_joueur_challenges.insert(0, "Joueur", summonername)
    try: # certains joueurs n'ont pas ces colonnes... impossible de dire pourquoi
        data_joueur_challenges.drop(['position', 'playersInLevel', 'achievedTime'], axis=1, inplace=True)
    except KeyError:
        data_joueur_challenges.drop(['achievedTime'], axis=1, inplace=True)
    data_challenges = get_data_challenges()
    # on fusionne en fonction de l'id :
    data_joueur_challenges = data_joueur_challenges.merge(data_challenges, left_on="challengeId", right_on='id')
    # on a besoin de savoir ce qui est le mieux dans les levels : on va donc créer une variable chiffrée représentatif de chaque niveau :
    
    dict_rankid = {"NONE" : 0,
                "IRON" : 1,
               "BRONZE" : 2,
               "SILVER" : 3,
               "GOLD" : 4,
               "PLATINUM" : 5,
               "DIAMOND" : 6,
               "MASTER": 7,
               "GRANDMASTER" : 8,
               "CHALLENGER" : 9
    }
    data_joueur_challenges['level_number'] = data_joueur_challenges['level'].map(dict_rankid)

    
    # on retient ce qu'il nous intéresse
    data_joueur_challenges[['Joueur','challengeId', 'name', 'value', 'percentile', 'level', 'level_number','state', 'shortDescription', 'description', 'IRON', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']]
    data_joueur_challenges = data_joueur_challenges.reindex(columns=['Joueur', 'challengeId', 'name', 'value', 'percentile', 'level', 'level_number','state', 'shortDescription', 'description', 'IRON', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER'])
    return data_total_joueur, data_joueur_category, data_joueur_challenges

    


class Challenges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.challenges_maj.start()
        self.defis = lire_bdd('challenges_data').transpose().sort_values(by="name", ascending=True)
        
        
    @tasks.loop(hours=1, count=None)
    async def challenges_maj(self):

        currentHour = str(datetime.datetime.now().hour)

        if currentHour == str(23):
            # pas optimal mais nécessaire pour éviter 30.000 requêtes à rito.
            
            channel = self.bot.get_channel(int(main.chan_lol))
            
            liste_summonername = loadData('id_data')
            
           
            for summonername in liste_summonername.keys():
                try:
                    total, category, challenges = get_data_joueur(summonername)
                    sauvegarde_bdd(total, 'challenges_total')
                    sauvegarde_bdd(category, 'challenges_category')
                    sauvegarde_bdd(challenges, 'challenges_data')
                    
                    time.sleep(3)
                except:
                    print(f'{summonername} : Pas de données')
            await channel.send('Les challenges ont été mis à jour.')
            
    
    @cog_ext.cog_slash(name="challenges_help", description="Explication des challenges")
    async def challenges_help(self, ctx):
        
        nombre_de_defis = len(self.defis['name'].unique())
        
        
        em = discord.Embed(title="Challenges", description="Explication des challenges")
        em.add_field(name="**Conditions**", value="`Avoir joué depuis le patch 12.9  \nDisponible dans tous les modes de jeu`")
        em.add_field(name="**Mise à jour des challenges**", value=f"`Mis à jour tous les jours avant minuit`", inline=False)
        em.add_field(name="**Defis disponibles**", value=f"`Il existe {nombre_de_defis} défis disponibles.`", inline=False)
        
        await ctx.send(embed=em)
        
    @cog_ext.cog_slash(name="challenges_liste", description="Liste des challenges")
    async def challenges_liste(self, ctx):
        
        em = discord.Embed(title="Challenges", description="Explication des challenges")
              
        for i in range(0,24):
            debut = 0 + i*10
            fin = 10 + i*10
            em.add_field(name=f"**Challenges part {i}**", value=f"`{self.defis['name'].unique()[debut:fin]}", inline=False)
            

        await ctx.send(embed=em)
        
    
    

                
    
    @cog_ext.cog_slash(name="challenges_classement", description="Classement des points de challenge")
    async def challenges_classement(self, ctx):
        
        bdd_user_total = lire_bdd('challenges_total').transpose()

        fig = px.pie(bdd_user_total, values="current", names=bdd_user_total.index, title="Points de défis")
        fig.update_traces(textinfo='label+value')
        fig.update_layout(showlegend=False)
        fig.write_image('plot.png')
        await ctx.send(file=discord.File('plot.png'))
        os.remove('plot.png')
        
    @cog_ext.cog_slash(name="challenges_profil", description="Profil du compte",
                       options=[create_option(name="summonername", description = "Nom du joueur", option_type=3, required=True)])
    async def challenges_profil(self, ctx, summonername):
        
        
        total_user, total_category, total_challenges = get_data_joueur(summonername)
        
        def stats(categorie):
            level = total_category[categorie]['level']
            points = total_category[categorie]['current']
            max_points = total_category[categorie]['max']
            percentile = round(total_category[categorie]['percentile']*100,2) # x100 car pourcentage. On retient deux chhiffres après la virgule.
            liste_stats = [categorie, level, points, max_points, percentile]
            return liste_stats
        
        await ctx.defer(hidden=False)
        
        liste_teamwork = stats('TEAMWORK')
        liste_collection = stats('COLLECTION')
        liste_expertise = stats('EXPERTISE')
        liste_imagination = stats('IMAGINATION')
        liste_veterancy = stats('VETERANCY')
        
        msg = "" #txt

        fig = go.Figure()
        i=0
        
        # dict de paramètres
        domain = {0:[0,0], 1:[0,2], 2:[1,1], 3:[2,0], 4:[2,2]} #position
        color = ["red", "blue", "yellow", "magenta", "green"] #color
        
        for argument in [liste_teamwork, liste_collection, liste_expertise, liste_imagination, liste_veterancy]:
            # dict de parametres

            
            
            msg = msg + f"{argument[0]} : ** {argument[2]} ** points / ** {argument[3]} ** possibles (niveau {argument[1]}) . Seulement {argument[4]}% des joueurs font mieux \n"
            fig.add_trace(go.Indicator(value=argument[2],
                                       title={'text' : argument[0] + " (" + argument[1] + ")", 'font' : {'size': 16}},
                                       gauge = {'axis' : {'range' : [0, argument[3]]}, 
                                                'bar' : {'color': color[i]}},
                                       mode = "number+gauge",
                                       domain = {'row':domain[i][0], 'column':domain[i][1]}))
            fig.update_layout(grid = {'rows': 3, 'columns': 3, 'pattern': "independent"})
            i = i+1
        fig.write_image('plot.png')
        await ctx.send(f'Le joueur {summonername} a : \n{msg}') #txt
        await ctx.send(file=discord.File('plot.png')) # visuel
        os.remove('plot.png')
        

        
    @cog_ext.cog_slash(name="challenges_top",
                       description="Affiche un classement pour le défi spécifié",
                       options=[create_option(name="nbpages", description= "Quel page ? Les challenges sont en ordre alphabétique", option_type=4, required=True)])
    async def challenges_top(self, ctx, nbpages:int):
        
            # 232 défis
            
            nbpages = nbpages - 1 # les users ne savent pas que ça commence à 0
            
            debut_range = 25 * nbpages
            fin_de_range = 25 * (nbpages + 1)
            
            if fin_de_range > len(self.defis): # si la range de fin est supérieure au dernier de la liste... alors on prend la fin de la liste
                fin_de_range = len(self.defis)
        
            # catégorie
            select = create_select(
                options=[create_select_option(self.defis['name'].unique()[i], value=self.defis['name'].unique()[i],
                                              description=self.defis[self.defis['name'] == self.defis['name'].unique()[i]]['shortDescription'].to_numpy()[0]) for i in range(debut_range, fin_de_range)],
                placeholder = "Choisis le défi")
                                  
            channel = ctx.channel
            
            
            
            fait_choix = await ctx.send('Choisis le défi ', components=[create_actionrow(select)])
            
            def check(m):
                return m.author_id == ctx.author.id and m.origin_message.id == fait_choix.id
            
            name = await wait_for_component(self.bot, components=select, check=check)
            
            name_answer = name.values[0]
        
            
            bdd_user_challenges = lire_bdd('challenges_data').transpose()
            # on prend les éléments qui nous intéressent
            bdd_user_challenges = bdd_user_challenges[['Joueur', 'name', 'value', 'description']]
            # on trie sur le challenge
            bdd_user_challenges = bdd_user_challenges[bdd_user_challenges['name'] == name_answer]
            description = bdd_user_challenges['description'].iloc[0] # on prend le premier pour la description
            # on fait les rank
            bdd_user_challenges['rank'] = bdd_user_challenges['value'].rank(method='min', ascending=False)
            # on les range en fonction du rang
            bdd_user_challenges = bdd_user_challenges.sort_values(by=['rank'], ascending = True)
            
            fig = px.histogram(bdd_user_challenges, x="Joueur", y="value", color="Joueur", title=name_answer, text_auto=True)
            fig.write_image('plot.png')
            
            await name.send(f'Défis : ** {name_answer} **  \nDescription : {description}')
            await channel.send(file=discord.File('plot.png'))
            os.remove('plot.png')
            
            
            

    



def setup(bot):
    bot.add_cog(Challenges(bot))
