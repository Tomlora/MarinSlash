import os

import matplotlib.pyplot as plt

import numpy as np
import plotly.express as px
from discord.ext import commands
import urllib
import main
import json
import pandas as pd
import pygal

from discord_slash.utils.manage_components import *
from discord_slash import cog_ext, SlashContext

def opendatasw():
    f = open('./SW/siege.json', encoding="utf8") #on ouvre le fichier
        
    data = json.load(f)  # on charge la data
    
    return data
    



chan_general = 768637526176432158


class SummonersWars(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash(name="uploadsource", description="Private")
    @main.isOwner2_slash()
    async def uploadsource(self, ctx, url):
        if '.json' in str(url):
            file = urllib.request.urlretrieve(url,"./SW/siege.json")
        else:
            await ctx.send("Erreur, le fichier n'est pas au format json")
        
        await ctx.send('Done')
        
    @cog_ext.cog_slash(name="generalsw", description="test")
    @main.isOwner2_slash()
    async def generalsw(self, ctx):
        
        data = opendatasw()
        data = data['matchup_info']['guild_list']  # data qui nous intéresse
        df1 = pd.DataFrame(data)  # on transpose en dataframe pour pandas

        pd.set_option('display.max_columns', None)  # permet de ne pas cacher les colonnes avec des "..."
        #print(df1)  # la totalité de la bd

        Guilde1 = df1.loc[
            0]  # Toutes les infos de la première ligne etc... on pourrait rajouter [nom_colonne] pour avoir une infos précise.
        Guilde2 = df1.loc[1]
        Guilde3 = df1.loc[2]


        # def PresentationGuilde(Guilde):
        #     print(Guilde["guild_name"] + " : " + chr(10) + str(Guilde) + chr(10))


        def NbAttaquesUtilisees(Guilde):
            Attaque_max = Guilde["play_member_count"] * 10  # Nombre d'attaque max
            Pourcent_attaques_utilisees = (Guilde['attack_count'] / Attaque_max) * 100  # % attaque utilisees
            Pourcent_attaques_utilisees = round(Pourcent_attaques_utilisees, 2)  # 2 chiffres après la virgule
            # print(Guilde["guild_name"] + " : " + chr(10) + str(Guilde['attack_count']) + " attaques utilisées / " + str(
            #     Attaque_max) + ", soit " + str(Pourcent_attaques_utilisees) + " % " + chr(10))  # Message final
            
        # NbAttaquesUtilisees(Guilde1)
        # NbAttaquesUtilisees(Guilde2)
        # NbAttaquesUtilisees(Guilde3)
        
        Solid_gauge = pygal.SolidGauge(inner_radius=0.75, half_pie=True)  # half_pie coupe le cercle en deux.


        def Attaques_en_cours_pygal(Guilde, Solid_gauge):
            Solid_gauge.title = 'Nb atk'
            Solid_gauge.add(Guilde["guild_name"], [{'value': Guilde['attack_count'], 'max_value': 250}])


        Attaques_en_cours_pygal(Guilde1, Solid_gauge)
        Attaques_en_cours_pygal(Guilde2, Solid_gauge)
        Attaques_en_cours_pygal(Guilde3, Solid_gauge)
        
        
        Solid_gauge.render_to_png('solid_gauge.png')
        
        await ctx.send(file=discord.File('solid_gauge.png'))
        os.remove('solid_gauge.png')
        
    @cog_ext.cog_slash(name="atksw", description="test")
    @main.isOwner2_slash()
    async def atksw(self, ctx):
        
        channel = ctx.channel
            
        data = opendatasw()
        data = data['attack_log']['log_list'][0]['battle_log_list']  # data qui nous intéresse
        df1 = pd.DataFrame(data)  # on transpose en dataframe pour pandas

        nb_victoire = df1[df1["win_lose"] == 1]  # permet une dataframe qui ne contient que les victoires
        nb_victoire = len(nb_victoire)  # nombre de lignes pour connaitre le nombre de victoires

        nb_defaite = df1[df1["win_lose"] == 2]
        nb_defaite = len(nb_defaite)

        await ctx.send(f'La guilde a réussi {nb_victoire} combats et a perdu {nb_defaite} combats')

        df1_membre = df1.set_index("wizard_name")  # on index par rapport aux membres

        df1_victoire = df1_membre[df1_membre["win_lose"] == 1].groupby(
            "wizard_name").count()  # permet d'additionner le nombre de victoires en fonction des membres par exemple
        df1_defaite = df1_membre[df1_membre["win_lose"] == 2].groupby(
            "wizard_name").count()  # permet d'additionner le nombre de victoires en fonction des membres par exemple
        df1_atks_counts = df1_membre.groupby(by="wizard_name").count()  # compte le nombre de combats

        # on renomme (surement un moyen plus facile)
        df1_victoire = df1_victoire.rename(columns={'win_lose': 'win'})
        df1_defaite = df1_defaite.rename(columns={'win_lose': 'lose'})
        df1_atks_counts = df1_atks_counts.rename(columns={'win_lose': 'nb atks'})

        # on retient les deux colonnes qui nous intéressent : l'index et le résultat du combat
        df1_victoire = df1_victoire['win']
        df1_defaite = df1_defaite['lose']
        df1_atks_counts = df1_atks_counts['nb atks']

        # on les concatène
        pdList = [df1_victoire, df1_defaite, df1_atks_counts]
        df1_resultats = pd.concat(pdList, axis=1)

        # on remplace les Na par des 0
        df1_resultats = df1_resultats.fillna(0)

        # la colonne lose est en float. Nous voulons un tableau complet en int64 :
        df1_resultats['lose'] = df1_resultats['lose'].astype('int64')

        # on veut le % d'attaques réussies :
        df1_resultats['% réussi'] = (df1_resultats['win'] / df1_resultats['nb atks'])*100

        # print(df1_resultats)

        bar_chart = pygal.HorizontalBar()
        bar_chart.title = '% attaques réussies'

        # lorsqu'on boucle sur une dataframe, on boucle sur les colonnes... L'index étant une colonne à part, on réinitialise pour pouvoir faire notre graphique :


        fig = px.bar(df1_resultats, x=df1_resultats.index, y="% réussi", title=" % d'atk réussis", color=df1_resultats.index, text_auto=True)
        
        fig.write_image('bar_chart.png')
        await channel.send(file=discord.File('bar_chart.png'))
        os.remove('bar_chart.png')
        
    @cog_ext.cog_slash(name="defensesw", description="test")
    @main.isOwner2_slash()
    async def defensesw(self, ctx):
        channel = ctx.channel
        data = opendatasw()
        data = data['defense_log']['log_list'][0]['battle_log_list']  # data qui nous intéresse
        df1 = pd.DataFrame(data)  # on transpose en dataframe pour pandas

        pd.set_option('display.max_columns', None)  # permet de ne pas cacher les colonnes avec des "..."

        nb_defenses_reussies = df1[df1["win_lose"] == 1]  # permet une dataframe qui ne contient que les victoires
        nb_defenses_reussies = len(nb_defenses_reussies)  # nombre de lignes pour connaitre le nombre de victoires

        nb_defenses_ratées = df1[df1["win_lose"] == 2]
        nb_defenses_ratées = len(nb_defenses_ratées)

        await ctx.send(f'La guilde a réussi {nb_defenses_reussies} défenses et a perdu {nb_defenses_ratées} défenses')

        df1_membre = df1.set_index("wizard_name")  # on index par rapport aux membres

        df1_défenses_réussies = df1_membre[df1_membre["win_lose"] == 1].groupby(
            "wizard_name").count()  # permet d'additionner le nombre de victoires en fonction des membres par exemple
        df1_défenses_ratées = df1_membre[df1_membre["win_lose"] == 2].groupby(
            "wizard_name").count()  # permet d'additionner le nombre de victoires en fonction des membres par exemple
        df1_defs_counts = df1_membre.groupby(by="wizard_name").count()  # compte le nombre de combats

        # on renomme (surement un moyen plus facile)
        df1_défenses_réussies = df1_défenses_réussies.rename(columns={'win_lose': 'défenses réussies'})
        df1_défenses_ratées = df1_défenses_ratées.rename(columns={'win_lose': 'défenses ratées'})
        df1_defs_counts = df1_defs_counts.rename(columns={'win_lose': 'nb defs'})

        # on retient les deux colonnes qui nous intéressent : l'index et le résultat du combat
        df1_défenses_réussies = df1_défenses_réussies['défenses réussies']
        df1_défenses_ratées = df1_défenses_ratées['défenses ratées']
        df1_defs_counts = df1_defs_counts['nb defs']

        # on les concatène
        pdList = [df1_défenses_réussies, df1_défenses_ratées, df1_defs_counts]
        df1_resultats = pd.concat(pdList, axis=1)

        # on remplace les Na par des 0
        df1_resultats = df1_resultats.fillna(0)

        # la colonne lose est en float. Nous voulons un tableau complet en int64 :
        df1_resultats[['défenses réussies', 'défenses ratées']] = df1_resultats[['défenses réussies', 'défenses ratées']].astype('int64')


        # on veut le % de défenses réussies :

        df1_resultats['% réussi'] = ((df1_resultats['défenses réussies'] / df1_resultats['nb defs'])*100).astype('int64')
        

        fig = px.bar(df1_resultats, x=df1_resultats.index, y="% réussi", title=" % de défense réussis", color=df1_resultats.index, text_auto=True)


        
        fig.write_image('bar_chart.png')
        await channel.send(file=discord.File('bar_chart.png'))
        os.remove('bar_chart.png')
        
    @cog_ext.cog_slash(name="basesw", description="test")
    @main.isOwner2_slash()
    async def basesw(self, ctx):
            
        data = opendatasw()
        data_base = data['matchup_info']['base_list']   #data qui nous intéresse
        data_base = pd.DataFrame(data_base)  # on transpose en dataframe pour pandas
        
        data_guilde = data['matchup_info']['guild_list']   #data qui nous intéresse
        df_guilde = pd.DataFrame(data_guilde) # on transpose en dataframe pour pandas
        df_guilde = df_guilde[{'guild_id', 'guild_name'}]  #j'ai besoin de l'id de la guilde et du nom pour pouvoir le changer dans ma data_base

        # Cette data va servir à remplacer les valeurs numériques (id des guildes) par leur nom... Plus lisible :
        data_de_remplacement = {
            df_guilde['guild_id'].iloc[0]: df_guilde['guild_name'].iloc[0],
            df_guilde['guild_id'].iloc[1]: df_guilde['guild_name'].iloc[1],
            df_guilde['guild_id'].iloc[2]: df_guilde['guild_name'].iloc[2]
        }

        data_base['guild_id'] = data_base['guild_id'].map(data_de_remplacement) # on remplace les valeurs

        data_base = data_base[{'guild_id', 'base_number'}] # on n'a besoin que de deux colonnes
        data_base_count = data_base.groupby('guild_id').count() # on groupe puis on compte le nombre de base

         # Graphique

        data_base_count = data_base_count.reset_index() # on reset l'index pour pouvoir utiliser guild_id dans notre graphique

        
        fig = px.pie(data_base_count, values='base_number', names="guild_id", title='Nombre de bases')
        fig.update_traces(textinfo='value', textfont_size=20)
        
        print(ctx.guild.id)
        print(data_base_count)

        
        fig.write_image('pie_chart.png')
        await ctx.send(file=discord.File('pie_chart.png'))
        os.remove('pie_chart.png')
        
        
        
        
        


def setup(bot):
    bot.add_cog(SummonersWars(bot))
