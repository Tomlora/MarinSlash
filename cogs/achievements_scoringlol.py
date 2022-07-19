import discord
from main import isOwner2
from discord.ext import commands
import pandas as pd
import pickle
from sklearn import linear_model
from sklearn.model_selection import train_test_split
import seaborn as sns
import numpy as np
from matplotlib import pyplot as plt
import os
import plotly.express as px
from fonctions.gestion_fichier import loadData, writeData
from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd
import pickle

from discord_slash import cog_ext, SlashContext



from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice



        
def unifier_joueur(df, colonne):
    df[colonne] = df[colonne].replace('nukethestars', 'state')
    df[colonne] = df[colonne].replace('linò', 'state')
    df[colonne] = df[colonne].replace('namiyeon', 'dawn')
    df[colonne] = df[colonne].replace('chatobogan', 'dawn')

    return df



def ajouter_game(role, df, pseudo, kills, deaths, assists, kp, wardsplaced, wardskilled, pink, cs, csm, score: 0):
    df = df.append({'Role': role, 'Pseudo': pseudo, 'Kills': kills, 'Deaths': deaths
                       , 'Assists': assists, 'KP': kp, 'WardsPlaced': wardsplaced, 'WardsKilled': wardskilled
                       , 'Pink': pink, 'cs': cs, 'csm': csm, 'Score': score}, ignore_index=True)
    return df


def find_modele_ml(role):
    reg = pickle.load(open(f'./obj/ML/reg_{role}.pkl', 'rb'))
    return reg

def scoring(role, pseudo, kills, deaths, assists, kp, wardsplaced, wardskilled, pink, cs, csm):


    variables = ['Kills', 'Deaths', 'Assists', 'KP', 'WardsPlaced', 'WardsKilled', 'Pink', 'cs', 'csm']

    reg = find_modele_ml(role)

    df_predict = pd.DataFrame(
        columns=['Role', 'Pseudo', 'Kills', 'Deaths', 'Assists', 'KP', 'WardsPlaced', 'WardsKilled', 'Pink', 'cs',
                 'csm',
                 'Score'])
    df_predict = ajouter_game(role, df_predict, pseudo, kills, deaths, assists, kp, wardsplaced, wardskilled, pink, cs,
                              csm,
                              0)

    predict = round(reg.predict(df_predict[variables].values)[0], 2)

    return predict

def scoring_correlation(role):
    dict = loadData('scoring')

    df = pd.DataFrame.from_dict(dict)
    df = df[df['Role'] == role]

    df[['Kills', 'Deaths', 'Assists', 'WardsPlaced', 'WardsKilled', 'Pink', 'cs']] = df[
        ['Kills', 'Deaths', 'Assists', 'WardsPlaced', 'WardsKilled', 'Pink', 'cs']].astype(int)
    df[['KP', 'csm', 'Score']] = df[['KP', 'csm', 'Score']].astype(float)

    plt.figure(figsize=(15, 10))

    df_corr = df.corr()

    mask = np.zeros_like(df_corr, dtype=bool)
    mask[np.triu_indices_from(mask)] = True

    heatmap = sns.heatmap(df_corr, mask=mask, square=True, cmap='coolwarm', annot=True, fmt=".2f",
                          annot_kws={'size': 8})
    heatmap.set(title='Analyse OP.GG ' + str(role))

    return heatmap

class Achievements_scoringlol(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @cog_ext.cog_slash(name="achievements",
                       description="Voir les couronnes acquis par les joueurs",
                       options=[create_option(name="records", description= "Afficher le cumul des records ?", option_type=3, required=True, choices=[
                           create_choice(name="oui", value="oui"),
                           create_choice(name="non", value="non")
                            ])])
    async def achievements(self, ctx, records):
        

        # Succes
        suivi = lire_bdd('suivi', 'dict')
        records1 = lire_bdd('records', 'dict')
        records2 = lire_bdd('records2', 'dict')

        settings = lire_bdd('achievements_settings', 'dict')

        df = pd.DataFrame(suivi)
        df = df.transpose().reset_index()
        
        await ctx.defer(hidden=False)

        # Records
        if records == "oui":
            df2 = pd.DataFrame(records1).transpose()
            df3 = pd.DataFrame(records2).transpose()


            plt.figure(figsize=(15, 8))

            df2 = pd.concat([df2, df3])

            df2 = unifier_joueur(df2, 'Joueur')

            df2_count = df2.groupby(by=['Joueur']).count().reset_index()

            df2_count = df2_count.sort_values(by='Score', ascending=False)

            df2_count = df2_count[df2_count['Joueur'] != "Tomlora"]  # Records non-pris

            fig = px.bar(df2_count, y='Score', x='Joueur', title="Records", color='Joueur')
            fig.update_layout(showlegend=False)
            fig.write_image('plot.png')

        df = df[df['games'] >= settings['Nb_games']['Score']]
        df['Achievements_par_game'] = df['Achievements'] / df['games']

        df.sort_values(by=['Achievements_par_game'], ascending=[False], inplace=True)

        joueur = df['index'].to_dict()

        
        result = ""

        # for id, key in joueur.items():
        for key in joueur.values():
            try:
                if suivi[key]['Achievements'] > 0:
                    achievements = suivi[key]['Achievements']
                    games = suivi[key]['games']
                    achievements_par_game = round(achievements / games, 2)
                    
                    if result == "":
                        result = "** " + key + " ** : " + str(achievements) + " :crown: en " + str(games) + " games (" + str(achievements_par_game) + " :crown: / games)\n"
                    else:
                        result = result + "** " + key + " ** : " + str(achievements) + " :crown: en " + str(games) + " games (" + str(achievements_par_game) + " :crown: / games)\n"
                    

            except:
                suivi[key]['Achievements'] = 0
                suivi[key]['games'] = 0

                # writeData(suivi, 'suivi')
                sauvegarde_bdd(suivi, 'suivi')
            
        await ctx.send(f"Couronnes (SoloQ only et {settings['Nb_games']['Score']} games minimum) :\n" + result)


        if records == "oui":
            await ctx.send('Informations : Les records de la page 3 ne sont pas comptabilisés', file=discord.File('plot.png'))
            os.remove('plot.png')

    @cog_ext.cog_slash(name="achievements_regles",
                       description="Conditions pour débloquer des couronnes")
    async def achievements_regles(self, ctx):

        settings = lire_bdd('achievements_settings', 'dict')

        partie0 = f":gear: Nombre de games minimum : {settings['Nb_games']['Score']} \n"
        partie1 = f":crown: Pentakill : {settings['Pentakill']['Score']} \n :crown: Quadrakill : {settings['Quadrakill']['Score']} \n :crown: KDA >= {settings['KDA']['Score']} \n :crown: Ne pas mourir \n :crown: KP >= {settings['KP']['Score']}% \n"
        partie2 = f":crown: Vision/min >= {settings['Vision/min(support)']['Score']} (support) | {settings['Vision/min(autres)']['Score']} (autres) \n :crown: CS/min >= {settings['CS/min']['Score']} \n"
        partie3 = f":crown: Avantage vision >= {settings['Avantage_vision(support)']['Score']}% (support) | {settings['Avantage_vision(autres)']['Score']}% (autres) \n"
        partie4 = f":crown: % DMG équipe > {settings['%_dmg_équipe']['Score']}% \n :crown: % dmg tank >= {settings['%_dmg_tank']['Score']}% \n"
        partie5 = f":crown: Solokills >= {settings['Solokills']['Score']} \n :crown: Total Heals sur alliés >= {settings['Total_Heals_sur_alliés']['Score']} \n"
        partie6 = f":crown: CS d'avance sur ton adversaire durant la game >= {settings['CSAvantage']['Score']} \n :crown: Ecart de niveau sur ton adversaire >= {settings['Ecart_Level']['Score']} \n"
        partie7 = f":crown: Contribution à la destruction des tours >= {settings['Participation_tower']['Score']}% \n :crown: Dragon >= {settings['Dragon']['Score']}"
        partie8 = f":crown: Danse avec l'Herald \n :crown: Perfect Game" 

        embed = discord.Embed(title="** Règles : **", color=discord.Colour.gold())
        embed.add_field(name="Parametres", value=partie0, inline=False)
        embed.add_field(name="Couronnes disponibles", value=partie1 + partie2 + partie3 + partie4 + partie5 + partie6 + partie7 + partie8, inline=False)

        await ctx.send(embed=embed)
   

 

       
    @commands.command()
    @isOwner2()
    async def update_machinelearning(self, ctx):

        df = pd.DataFrame(
            columns=['Role', 'Pseudo', 'Kills', 'Deaths', 'Assists', 'KP', 'WardsPlaced', 'WardsKilled', 'Pink', 'cs',
                     'csm', 'Score'])

        # Support

        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 0, 3, 31, 0.79, 67, 12, 17, 20, 0.5, 7.8)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 1, 1, 10, 0.79, 30, 3, 8, 10, 0.3, 7.12)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 4, 4, 18, 0.4, 45, 7, 11, 20, 0.6, 7.84)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 5, 0, 21, 0.59, 42, 8, 12, 22, 0.7, 9.34)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 1, 4, 16, 0.35, 49, 12, 8, 18, 0.6, 5.81)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 3, 4, 14, 0.65, 53, 12, 12, 26, 0.8, 6.7)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 2, 8, 20, 0.42, 63, 15, 15, 25, 0.7, 6.57)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 4, 2, 21, 0.69, 49, 8, 11, 11, 0.3, 7.72)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 5, 5, 19, 0.65, 36, 6, 8, 14, 0.5, 6.39)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 1, 2, 21, 0.59, 65, 19, 14, 27, 0.8, 8.59)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 5, 4, 27, 0.74, 42, 7, 9, 22, 0.7, 9.18)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 4, 0, 14, 0.82, 26, 6, 6, 10, 0.4, 7.94)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 0, 4, 19, 0.42, 33, 4, 9, 8, 0.2, 6.9)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 4, 5, 24, 0.68, 64, 19, 14, 39, 1.1, 7.71)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 1, 5, 18, 0.58, 33, 13, 9, 17, 0.7, 7.25)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 5, 2, 25, 0.59, 74, 13, 17, 20, 0.5, 8.09)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 7, 8, 21, 0.53, 57, 13, 14, 26, 0.7, 7.41)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 3, 2, 15, 0.62, 37, 8, 11, 14, 0.6, 8.47)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 5, 5, 23, 0.68, 47, 3, 15, 24, 0.6, 7.31)
        df = ajouter_game('SUPPORT', df, 'Nami Yeon', 6, 6, 32, 0.70, 75, 17, 16, 35, 0.9, 8.34)
        df = ajouter_game('SUPPORT', df, 'Millanah', 6, 9, 13, 0.54, 31, 11, 0, 76, 1.9, 6.20)
        df = ajouter_game('SUPPORT', df, 'Vinine Rain', 4, 2, 13, 0.52, 25, 11, 5, 35, 1.1, 7.88)
        df = ajouter_game('SUPPORT', df, 'Kyugure', 1, 10, 12, 0.43, 31, 11, 3, 24, 0.7, 5.17)
        df = ajouter_game('SUPPORT', df, 'Fiddlestick irl', 0, 9, 1, 0.07, 25, 3, 2, 15, 0.5, 3.65)
        df = ajouter_game('SUPPORT', df, 'Shobo Kok', 3, 6, 6, 0.3, 27, 19, 1, 55, 1.7, 6.44)
        df = ajouter_game('SUPPORT', df, 'Andrea Pucci', 0, 8, 19, 0.61, 34, 15, 10, 49, 1.5, 6.18)
        df = ajouter_game('SUPPORT', df, 'guzz', 22, 9, 5, 0.60, 48, 15, 1, 79, 2.1, 7.55)
        df = ajouter_game('SUPPORT', df, 'Dadapon', 1, 7, 12, 0.59, 14, 7, 4, 57, 1.8, 5.55)
        df = ajouter_game('SUPPORT', df, 'SFS NoobT', 14, 9, 7, 0.48, 13, 5, 1, 62, 2.1, 7.05)
        df = ajouter_game('SUPPORT', df, 'This is Soo', 2, 9, 16, 0.64, 27, 16, 4, 45, 1.3, 5.50)
        df = ajouter_game('SUPPORT', df, 'Thresh Sol', 1, 7, 17, 0.55, 16, 3, 1, 14, 0.5, 4.76)
        df = ajouter_game('SUPPORT', df, 'Bduyendaria', 2, 5, 7, 0.43, 30, 7, 5, 28, 1.1, 5.74)
        df = ajouter_game('SUPPORT', df, 'R3V ANG3L', 1, 8, 7, 0.32, 15, 7, 3, 61, 1.9, 5.35)
        df = ajouter_game('SUPPORT', df, 'Endé', 2, 7, 14, 0.3, 57, 27, 13, 65, 0.3, 6.77)
        df = ajouter_game('SUPPORT', df, 'loulou0701', 6, 4, 13, 0.5, 30, 17, 5, 29, 0.9, 7.57)
        df = ajouter_game('SUPPORT', df, 'Ezekiel', 2, 5, 17, 0.73, 27, 9, 6, 14, 0.4, 6.39)
        df = ajouter_game('SUPPORT', df, 'Pilgrim', 5, 3, 12, 0.52, 33, 14, 8, 44, 1.5, 8.72)
        df = ajouter_game('SUPPORT', df, 'kazAbunga', 0, 6, 9, 0.53, 41, 4, 10, 9, 0.3, 5.21)
        df = ajouter_game('SUPPORT', df, 'Angry Land', 0, 6, 8, 0.50, 24, 6, 4, 19, 0.7, 4.80)
        df = ajouter_game('SUPPORT', df, 'Kiroulpé', 4, 2, 14, 0.67, 18, 7, 3, 12, 0.4, 8.06)
        df = ajouter_game('SUPPORT', df, 'Pueblo x C', 4, 2, 13, 0.5, 23, 1, 6, 41, 1.5, 8.02)
        df = ajouter_game('SUPPORT', df, 'Princess Ja', 1, 5, 11, 0.67, 11, 2, 2, 2, 0.1, 4.22)
        df = ajouter_game('SUPPORT', df, 'Tobiseus', 3, 5, 3, 0.86, 7, 2, 1, 19, 0.2, 5.57)
        df = ajouter_game('SUPPORT', df, 'maari', 3, 3, 8, 0.42, 11, 1, 3, 10, 0.7, 6.14)
        df = ajouter_game('SUPPORT', df, '5all elite', 1, 5, 21, 0.54, 55, 8, 14, 45, 101, 6.18)
        df = ajouter_game('SUPPORT', df, 'SGirbi', 2, 6, 8, 0.40, 38, 39, 1, 161, 3.8, 6.75)
        df = ajouter_game('SUPPORT', df, 'Janna supp', 5, 4, 31, 0.86, 24, 3, 4, 6, 0.2, 7.03)
        df = ajouter_game('SUPPORT', df, '3hd', 4, 8, 12, 0.53, 27, 9, 3, 72, 2.2, 6.01)
        df = ajouter_game('SUPPORT', df, 'TrippinJ', 0, 5, 2, 0.18, 22, 2, 5, 30, 1.0, 5.12)
        df = ajouter_game('SUPPORT', df, 'hewfplit', 2, 2, 18, 0.65, 23, 4, 7, 4, 0.1, 7.41)
        df = ajouter_game('SUPPORT', df, 'kk2kwz', 10, 5, 9, 0.43, 30, 9, 9, 39, 1.2, 7.70)
        df = ajouter_game('SUPPORT', df, 'With a smile', 5, 11, 2, 0.23, 32, 9, 7, 26, 0.8, 6.14)
        df = ajouter_game('SUPPORT', df, 'typefaller', 1, 3, 9, 0.38, 20, 5, 4, 27, 1.2, 6.51)
        df = ajouter_game('SUPPORT', df, 'Agua de merda', 1, 7, 6, 0.33, 15, 7, 4, 25, 1.1, 5.41)
        df = ajouter_game('SUPPORT', df, 'Brukseles', 0, 5, 21, 0.47, 24, 5, 5, 28, 0.9, 6.42)
        df = ajouter_game('SUPPORT', df, 'Yobany shef', 4, 9, 15, 0.61, 35, 5, 5, 19, 0.6, 6.24)
        df = ajouter_game('SUPPORT', df, 'Abaka', 0, 3, 14, 0.52, 16, 5, 3, 13, 0.5, 6.7)
        df = ajouter_game('SUPPORT', df, 'Trakun', 4, 6, 2, 0.46, 21, 6, 3, 32, 1.3, 6.5)
        df = ajouter_game('SUPPORT', df, 'NormanLOL', 1, 5, 16, 0.55, 27, 7, 3, 38, 1.5, 6.59)
        df = ajouter_game('SUPPORT', df, 'Imperus', 1, 4, 7, 0.57, 11, 15, 4, 46, 1.8, 6.80)
        df = ajouter_game('SUPPORT', df, 'idsf', 0, 3, 15, 0.56, 23, 4, 2, 32, 1.3, 5.89)
        df = ajouter_game('SUPPORT', df, 'Bragaintl', 2, 2, 6, 0.57, 19, 8, 3, 43, 1.7, 7.21)
        df = ajouter_game('SUPPORT', df, 'Kind of god', 3, 13, 11, 0.5, 37, 6, 5, 30, 0.9, 5.71)
        df = ajouter_game('SUPPORT', df, 'Des7r0', 0, 7, 27, 0.52, 24, 7, 1, 34, 1.0, 6.15)
        df = ajouter_game('SUPPORT', df, 'MabzZ', 7, 8, 15, 0.58, 34, 7, 7, 30, 0.8, 7.2)
        df = ajouter_game('SUPPORT', df, 'Karzow', 2, 5, 25, 0.77, 26, 8, 6, 31, 0.9, 6.46)
        df = ajouter_game('SUPPORT', df, 'burn in fires', 3, 8, 17, 0.49, 21, 4, 0, 36, 1.1, 6.66)
        df = ajouter_game('SUPPORT', df, 'CD9', 0, 8, 16, 0.5, 27, 7, 9, 12, 0.4, 5.38)
        df = ajouter_game('SUPPORT', df, 'DarkHeaven', 3, 9, 12, 0.45, 59, 13, 13, 46, 1.2, 6.85)
        df = ajouter_game('SUPPORT', df, 'TrollKarl', 1, 6, 11, 0.32, 39, 10, 8, 23, 0.6, 5.9)
        df = ajouter_game('SUPPORT', df, 'Arrancabrita', 3, 2, 14, 0.45, 26, 6, 2, 45, 1.5, 8.99)
        df = ajouter_game('SUPPORT', df, 'sofmega', 0, 9, 7, 0.35, 22, 6, 3, 8, 0.3, 3.53)
        df = ajouter_game('SUPPORT', df, 'Feedmeme', 2, 3, 18, 0.50, 33, 9, 5, 33, 0.9, 7.56)
        df = ajouter_game('SUPPORT', df, 'TKS Karda', 2, 8, 13, 0.52, 35, 8, 5, 40, 1.1, 4.90)
        df = ajouter_game('SUPPORT', df, 'Satan Hell', 4, 4, 18, 0.56, 16, 2, 2, 11, 0.4, 6.64)
        df = ajouter_game('SUPPORT', df, 'Mushroom', 9, 10, 3, 0.48, 24, 8, 1, 35, 1.2, 6.05)
        df = ajouter_game('SUPPORT', df, 'Renata D', 5, 11, 12, 0.4, 28, 6, 9, 49, 1.4, 6.78)
        df = ajouter_game('SUPPORT', df, 'OSRS is b', 1, 5, 19, 0.65, 23, 10, 0, 18, 0.5, 5.66)
        df = ajouter_game('SUPPORT', df, 'Knuspriger', 11, 2, 9, 0.48, 31, 6, 4, 40, 1.6, 8.98)
        df = ajouter_game('SUPPORT', df, 'Brezeilito', 4, 11, 2, 0.33, 12, 10, 4, 27, 1.1, 4.47)
        df = ajouter_game('SUPPORT', df, 'Nysderoy', 1, 3, 12, 0.48, 26, 6, 6, 16, 0.6, 6.91)
        df = ajouter_game('SUPPORT', df, 'El Fotos', 3, 5, 2, 0.5, 29, 5, 3, 42, 1.6, 6.08)
        df = ajouter_game('SUPPORT', df, 'Festivalbar96', 1, 8, 9, 0.40, 44, 11, 3, 58, 1.9, 6.30)
        df = ajouter_game('SUPPORT', df, 'Exalted Orb', 1, 7, 16, 0.89, 23, 12, 7, 40, 1.3, 6.15)
        df = ajouter_game('SUPPORT', df, 'Sc S4ntos', 4, 9, 22, 0.54, 45, 18, 9, 54, 1.4, 6.64)
        df = ajouter_game('SUPPORT', df, 'mp3gear', 1, 3, 31, 0.63, 49, 15, 1, 19, 0.5, 5.98)
        df = ajouter_game('SUPPORT', df, 'Tomlora', 0, 5, 2, 0.22, 12, 0, 2, 14, 0.7, 3.55)
        df = ajouter_game('SUPPORT', df, 'Tomlora', 3, 8, 18, 0.58, 20, 5, 3, 48, 1.4, 6.07)
        df = ajouter_game('SUPPORT', df, 'WeeeZy', 7, 6, 26, 0.62, 21, 3, 4, 41, 1.2, 7.1)
        df = ajouter_game('SUPPORT', df, 'Tomlora', 11, 1, 13, 0.59, 13, 1, 3, 42, 1.7, 8.87)

        df = ajouter_game('ADC', df, 'Tomlora', 5, 4, 5, 0.48, 9, 5, 2, 204, 7, 6.35)
        df = ajouter_game('ADC', df, 'Gumayusi', 7, 5, 9, 0.62, 13, 5, 6, 201, 6.9, 7.24)
        df = ajouter_game('ADC', df, 'Tomlora', 6, 7, 6, 0.39, 2, 1, 1, 206, 7.2, 5.64)
        df = ajouter_game('ADC', df, 'Ren Insane', 8, 6, 10, 0.44, 6, 6, 1, 206, 7.2, 7.22)
        df = ajouter_game('ADC', df, 'Tomlora', 4, 7, 3, 0.27, 7, 0, 2, 164, 5.7, 4.15)
        df = ajouter_game('ADC', df, 'Honor5don', 12, 4, 5, 0.52, 9, 3, 2, 216, 7.5, 8.20)
        df = ajouter_game('ADC', df, 'Tomlora', 7, 4, 9, 0.38, 10, 6, 4, 204, 7.2, 7.61)
        df = ajouter_game('ADC', df, 'BadAnka', 1, 7, 3, 0.15, 11, 4, 2, 199, 7, 4.73)
        df = ajouter_game('ADC', df, 'Tomlora', 7, 4, 7, 0.37, 7, 3, 1, 221, 7, 6.59)
        df = ajouter_game('ADC', df, 'tAmeno', 5, 8, 9, 0.54, 11, 1, 1, 193, 6.1, 5.29)
        df = ajouter_game('ADC', df, 'Tomlora', 3, 5, 1, 0.57, 4, 0, 1, 86, 5.6, 5.47)
        df = ajouter_game('ADC', df, 'huidwni', 5, 1, 3, 0.31, 4, 0, 0, 100, 6.6, 5.23)
        df = ajouter_game('ADC', df, 'Tomlora', 9, 3, 2, 0.32, 8, 1, 3, 231, 8.2, 6.71)
        df = ajouter_game('ADC', df, 'Segee', 6, 6, 6, 0.67, 10, 2, 1, 252, 9, 6.62)
        df = ajouter_game('ADC', df, 'Tomlora', 21, 2, 7, 0.68, 17, 10, 5, 380, 8.9, 9.53)
        df = ajouter_game('ADC', df, 'BlueLit', 4, 13, 6, 0.40, 14, 4, 1, 253, 5.9, 4.32)
        df = ajouter_game('ADC', df, 'd33rtuoz', 9, 2, 9, 0.58, 6, 2, 0, 212, 7.4, 6.87)
        df = ajouter_game('ADC', df, 'Tomlora', 11, 4, 4, 0.58, 7, 1, 1, 211, 9.2, 7.99)
        df = ajouter_game('ADC', df, 'Twerk like', 3, 5, 5, 0.38, 6, 3, 0, 133, 5.8, 4.75)
        df = ajouter_game('ADC', df, 'Tomlora', 12, 6, 11, 0.51, 10, 1, 3, 183, 6.1, 7.07)
        df = ajouter_game('ADC', df, 'Danyy', 6, 10, 9, 0.48, 12, 4, 3, 210, 7, 5.88)
        df = ajouter_game('ADC', df, 'Tomlora', 10, 1, 2, 0.44, 7, 1, 3, 182, 7.7, 8.59)
        df = ajouter_game('ADC', df, 'h34f0', 2, 5, 4, 0.46, 7, 1, 1, 109, 4.6, 4.31)
        df = ajouter_game('ADC', df, 'd33rtuoz', 9, 2, 9, 0.58, 6, 2, 0, 212, 7.4, 6.87)
        df = ajouter_game('ADC', df, 'Tomlora', 8, 3, 8, 0.52, 6, 2, 1, 211, 8.1, 7.32)
        df = ajouter_game('ADC', df, 'Sgt', 5, 6, 5, 0.71, 10, 4, 4, 209, 8, 6.22)
        df = ajouter_game('ADC', df, 'Tomlora', 11, 2, 7, 0.67, 6, 0, 4, 187, 7.4, 8.13)
        df = ajouter_game('ADC', df, 'i am in ag', 11, 2, 15, 0.50, 12, 4, 2, 266, 7.7, 8.28)
        df = ajouter_game('ADC', df, 'Tomlora', 4, 12, 8, 0.43, 11, 2, 4, 187, 5.4, 4.81)
        df = ajouter_game('ADC', df, 'Djingo', 5, 6, 13, 0.43, 20, 6, 7, 272, 6.9, 7.62)
        df = ajouter_game('ADC', df, 'Homme Jaune', 6, 8, 8, 0.35, 15, 7, 2, 222, 5.6, 5.96)
        df = ajouter_game('ADC', df, 'Tomlora', 9, 6, 4, 0.46, 11, 4, 3, 241, 6.9, 6.24)
        df = ajouter_game('ADC', df, 'L3mme', 7, 7, 14, 0.55, 12, 4, 1, 220, 6.3, 6.07)
        df = ajouter_game('ADC', df, 'Tomlora', 2, 2, 1, 0.38, 2, 0, 2, 120, 7.8, 5.41)
        df = ajouter_game('ADC', df, 'minglemun', 4, 1, 4, 0.47, 4, 0, 1, 95, 6.2, 5.85)
        df = ajouter_game('ADC', df, 'Tomlora', 8, 4, 15, 0.50, 7, 2, 4, 195, 6.4, 6.65)
        df = ajouter_game('ADC', df, '5Meliodas', 8, 6, 4, 0.44, 11, 4, 2, 256, 8.4, 6.26)
        df = ajouter_game('ADC', df, 'Elixir of Iron', 14, 10, 7, 0.40, 7, 6, 1, 182, 5.9, 6.56)
        df = ajouter_game('ADC', df, 'Heaummotion', 10, 11, 6, 0.52, 5, 1, 0, 199, 6.5, 5.36)
        df = ajouter_game('ADC', df, 'Kevvek9', 5, 9, 13, 0.50, 8, 9, 2, 196, 6.0, 6.28)
        df = ajouter_game('ADC', df, 'Not Draven', 14, 8, 4, 0.50, 5, 3, 0, 224, 6.9, 5.71)
        df = ajouter_game('ADC', df, 'Tornn', 13, 6, 5, 0.42, 9, 1, 0, 218, 7, 7.01)
        df = ajouter_game('ADC', df, '4Paw', 0, 9, 6, 0.21, 13, 2, 3, 178, 5.7, 4.33)
        df = ajouter_game('ADC', df, 'Make it Evil', 3, 8, 4, 0.37, 9, 2, 2, 187, 6.4, 5.11)
        df = ajouter_game('ADC', df, 'Willi', 6, 1, 7, 0.35, 1, 0, 0, 241, 8.2, 6.47)
        df = ajouter_game('ADC', df, 'Caitlyn II', 22, 11, 13, 0.71, 1, 6, 1, 341, 7.3, 6.42)
        df = ajouter_game('ADC', df, 'Z1YAD', 17, 12, 10, 0.49, 10, 10, 1, 309, 6.6, 6.55)
        df = ajouter_game('ADC', df, 'I will be3', 4, 9, 6, 0.67, 12, 3, 1, 166, 5.2, 5.67)
        df = ajouter_game('ADC', df, 'Artist diff', 8, 5, 6, 0.48, 8, 5, 2, 252, 8, 8.3)
        df = ajouter_game('ADC', df, 'THC Rellekt', 17, 8, 13, 0.73, 13, 5, 1, 249, 6.7, 8.08)
        df = ajouter_game('ADC', df, 'Katanab', 6, 11, 7, 0.34, 12, 3, 0, 165, 4.5, 4.29)
        df = ajouter_game('ADC', df, 'Tomlora', 7, 6, 7, 0.61, 8, 3, 4, 231, 7, 6.15)
        df = ajouter_game('ADC', df, 'Bluefonic', 9, 0, 7, 0.53, 16, 2, 5, 332, 10, 8.28)
        df = ajouter_game('ADC', df, 'Tomlora', 1, 8, 3, 0.50, 8, 1, 2, 119, 4.7, 5.03)
        df = ajouter_game('ADC', df, 'Newdi91', 5, 2, 12, 0.61, 5, 0, 0, 210, 8.3, 6.63)
        df = ajouter_game('ADC', df, 'Tomlora', 3, 6, 1, 0.31, 7, 2, 3, 149, 6.4, 5.19)
        df = ajouter_game('ADC', df, 'SK Toplaner', 7, 1, 5, 0.4, 4, 4, 0, 202, 8.7, 7.64)
        df = ajouter_game('ADC', df, 'Tomlora', 7, 2, 3, 0.42, 7, 1, 1, 166, 7.8, 7.76)
        df = ajouter_game('ADC', df, 'Orlin A', 1, 5, 1, 0.15, 6, 1, 1, 122, 5.8, 4.39)
        df = ajouter_game('ADC', df, 'Orlin A', 3, 6, 8, 0.33, 7, 1, 3, 133, 5.8, 6.19)
        df = ajouter_game('ADC', df, 'Orlin A', 6, 6, 5, 0.85, 6, 0, 3, 148, 6.5, 6.20)
        df = ajouter_game('ADC', df, 'Orlin A', 0, 6, 7, 0.37, 4, 3, 1, 148, 6.4, 5.48)
        df = ajouter_game('ADC', df, 'Orlin A', 6, 4, 4, 0.56, 8, 2, 3, 162, 7.0, 7.12)
        df = ajouter_game('ADC', df, 'Tomlora', 17, 9, 10, 0.71, 5, 0, 1, 188, 6.0, 6.11)
        df = ajouter_game('ADC', df, 'Neryx', 11, 6, 17, 0.64, 10, 5, 1, 232, 7.4, 6.96)

        # MID

        df = ajouter_game('MID', df, 'Yeji', 10, 5, 4, 0.58, 5, 2, 4, 127, 6, 8.16)
        df = ajouter_game('MID', df, 'Jorge', 6, 8, 2, 0.62, 7, 1, 2, 128, 6, 5.77)
        df = ajouter_game('MID', df, 'Siberiman', 1, 9, 5, 0.46, 6, 3, 2, 99, 4.3, 4.57)
        df = ajouter_game('MID', df, 'David', 11, 5, 3, 0.47, 8, 3, 2, 137, 5.9, 8.16)
        df = ajouter_game('MID', df, 'Bjoerk', 2, 4, 3, 0.63, 7, 0, 1, 196, 7.8, 5.46)
        df = ajouter_game('MID', df, 'Lesburg', 10, 1, 4, 0.50, 9, 2, 1, 162, 6.4, 7.87)
        df = ajouter_game('MID', df, 'Taksedo', 8, 4, 7, 0.65, 4, 2, 2, 224, 6.8, 7.0)
        df = ajouter_game('MID', df, 'NoHands', 6, 4, 9, 0.50, 5, 2, 0, 176, 5.3, 5.19)
        df = ajouter_game('MID', df, 'Keelali', 4, 7, 7, 0.24, 11, 4, 6, 188, 6.2, 6.63)
        df = ajouter_game('MID', df, 'MaybeAeros', 3, 8, 7, 0.37, 9, 2, 0, 215, 7.0, 5.46)
        df = ajouter_game('MID', df, 'tanri', 2, 3, 2, 0.50, 3, 0, 1, 91, 5.9, 4.72)
        df = ajouter_game('MID', df, 'Adolf Lee', 5, 1, 1, 0.35, 7, 1, 4, 121, 7.9, 9.07)
        df = ajouter_game('MID', df, 'REBROW', 3, 4, 2, 0.62, 11, 6, 2, 274, 7.9, 5.48)
        df = ajouter_game('MID', df, 'Beecee', 9, 7, 13, 0.58, 12, 2, 1, 216, 6.2, 6.56)
        df = ajouter_game('MID', df, 'wlh', 14, 8, 4, 0.42, 5, 3, 0, 167, 6.1, 7.08)
        df = ajouter_game('MID', df, 'Kooun', 5, 8, 4, 0.45, 7, 1, 1, 130, 4.7, 5.13)
        df = ajouter_game('MID', df, 'ixhyati', 4, 6, 5, 0.43, 12, 3, 2, 199, 6.8, 5.06)
        df = ajouter_game('MID', df, 'iKent', 9, 2, 6, 0.58, 12, 2, 4, 235, 8.1, 8.25)
        df = ajouter_game('MID', df, 'Shobi', 5, 7, 5, 0.32, 9, 0, 3, 214, 7.5, 5.69)
        df = ajouter_game('MID', df, 'MihoMiho', 4, 7, 7, 0.27, 7, 1, 0, 141, 5, 5.25)
        df = ajouter_game('MID', df, 'Squishy', 1, 6, 8, 0.35, 9, 1, 0, 192, 6.7, 4.88)
        df = ajouter_game('MID', df, 'Courtnya', 4, 4, 9, 0.39, 10, 5, 1, 202, 7.1, 7.01)
        df = ajouter_game('MID', df, 'TNL', 9, 8, 2, 0.26, 11, 1, 2, 196, 6.9, 5.17)
        df = ajouter_game('MID', df, 'Goergel', 10, 5, 7, 0.63, 10, 6, 2, 212, 7.5, 7.83)
        df = ajouter_game('MID', df, 'Heroic', 9, 8, 6, 0.39, 10, 2, 2, 258, 8.2, 7.04)
        df = ajouter_game('MID', df, 'LedLegend', 8, 6, 4, 0.46, 9, 0, 1, 191, 6.1, 5.13)
        df = ajouter_game('MID', df, 'ElvisJ', 8, 3, 10, 0.55, 4, 2, 0, 211, 7.1, 6.62)
        df = ajouter_game('MID', df, 'Winneland', 4, 7, 4, 0.47, 4, 3, 0, 182, 6.1, 4.89)
        df = ajouter_game('MID', df, 'HFN', 3, 6, 4, 0.44, 13, 2, 4, 250, 8.9, 7.32)
        df = ajouter_game('MID', df, 'Calvon', 2, 7, 5, 0.26, 8, 2, 0, 181, 6.4, 4.68)
        df = ajouter_game('MID', df, 'Gabibo', 13, 3, 6, 0.56, 13, 2, 4, 163, 5.8, 8.66)
        df = ajouter_game('MID', df, 'physikneo', 1, 11, 1, 0.11, 7, 0, 0, 176, 6.3, 3.57)
        df = ajouter_game('MID', df, 'Ln Grizzle', 0, 6, 1, 0.14, 2, 0, 0, 76, 5, 3.36)
        df = ajouter_game('MID', df, 'Yeji', 12, 1, 4, 0.62, 4, 0, 0, 114, 7.5, 6.92)
        df = ajouter_game('MID', df, 'Yeji', 10, 4, 10, 0.49, 14, 3, 0, 321, 7.5, 6.64)
        df = ajouter_game('MID', df, 'Johen', 3, 7, 8, 0.44, 16, 7, 2, 332, 7.8, 5.84)
        df = ajouter_game('MID', df, 'Yeji', 8, 6, 12, 0.48, 12, 7, 2, 168, 5.1, 6.91)
        df = ajouter_game('MID', df, 'Yeji', 9, 6, 6, 0.50, 12, 3, 2, 212, 6.5, 6.43)
        df = ajouter_game('MID', df, 'Yeji', 19, 6, 16, 0.66, 16, 3, 3, 218, 6, 7.95)
        df = ajouter_game('MID', df, 'Yeji', 7, 10, 11, 0.45, 9, 2, 0, 208, 5.7, 4.51)
        df = ajouter_game('MID', df, 'Yeji', 12, 3, 5, 0.59, 4, 2, 2, 133, 5.3, 7.08)
        df = ajouter_game('MID', df, 'Yeji', 6, 8, 2, 0.53, 2, 6, 2, 162, 6.4, 5.72)
        df = ajouter_game('MID', df, 'Yeji', 9, 15, 6, 0.37, 10, 2, 1, 247, 6.6, 4.60)
        df = ajouter_game('MID', df, 'Yeji', 21, 6, 8, 0.52, 13, 4, 1, 303, 8.1, 8.19)
        df = ajouter_game('MID', df, 'Yeji', 11, 9, 7, 0.35, 7, 5, 2, 190, 6.2, 6.4)
        df = ajouter_game('MID', df, 'Yeji', 11, 12, 8, 0.61, 11, 0, 3, 160, 5.2, 6.24)
        df = ajouter_game('MID', df, 'Yeji', 14, 3, 7, 0.64, 5, 0, 0, 178, 7.8, 7.68)
        df = ajouter_game('MID', df, 'Yeji', 3, 9, 1, 0.31, 6, 1, 0, 105, 4.6, 4.21)
        df = ajouter_game('MID', df, 'Djingo', 13, 4, 6, 0.44, 36, 5, 11, 305, 6.7, 7.55)
        df = ajouter_game('MID', df, 'Jiba', 4, 11, 15, 0.50, 13, 2, 4, 145, 4.6, 6.29)
        df = ajouter_game('MID', df, 'Ylarabka', 20, 9, 15, 0.51, 17, 10, 6, 271, 6.1, 7.6)
        
        # JUNGLE
        
        df = ajouter_game('JUNGLE', df, 'wtplo', 8, 12, 15, 0.49, 8, 0, 0, 152, 4.1, 4.9)
        df = ajouter_game('JUNGLE', df, 'wtplo', 16, 10, 12, 0.53, 16, 10 , 12, 238, 6.4, 7.7)
        df = ajouter_game('JUNGLE', df, 'wtplo', 3, 3, 23, 0.59, 3, 3, 3, 139, 4.7, 7.3)
        df = ajouter_game('JUNGLE', df, 'wtplo', 8, 10, 6, 0.39, 6, 4, 6, 135, 4.5, 6.1)
        df = ajouter_game('JUNGLE', df, 'wtplo', 12, 4, 8, 0.53, 5, 8, 1, 217, 6.9, 7.9)
        df = ajouter_game('JUNGLE', df, 'wtplo', 4, 9, 9, 0.35, 3, 1, 2, 190, 6, 5.2)
        df = ajouter_game('JUNGLE', df, 'wtplo', 8, 0, 5, 0.37, 2, 1, 1, 166, 8.2, 8.3)
        df = ajouter_game('JUNGLE', df, 'wtplo', 1, 5, 3, 0.4, 5, 0, 0, 110, 5.4, 4.2)
        df = ajouter_game('JUNGLE', df, 'wtplo', 7, 11, 10, 0.53, 10, 5, 0, 197, 5.2, 5.2)
        df = ajouter_game('JUNGLE', df, 'wtplo', 14, 5, 14, 0.61, 4, 11, 5, 205, 5.4, 8.4)
        df = ajouter_game('JUNGLE', df, 'wtplo', 6, 13, 14, 0.48, 0, 2, 0, 154, 4.7, 5.2)
        df = ajouter_game('JUNGLE', df, 'wtplo', 9, 12, 19, 0.44, 4, 4, 2, 162, 4.9, 6.8)
        df = ajouter_game('JUNGLE', df, 'wtplo', 5, 8, 13, 0.47, 10, 3, 17, 199, 5.2, 6.0)
        df = ajouter_game('JUNGLE', df, 'wtplo', 8, 4, 29, 0.84, 2, 2, 1, 177, 4.6, 7.5)
        df = ajouter_game('JUNGLE', df, 'wtplo', 6, 9, 3, 0.60, 7, 6, 2, 188, 6.2, 5.8)
        df = ajouter_game('JUNGLE', df, 'wtplo', 12, 3, 8, 0.39, 16, 6, 7, 103, 3.4, 8)
        df = ajouter_game('JUNGLE', df, 'wtplo', 6, 9, 3, 0.6, 7, 6, 2, 188, 6.2, 5.8)
        df = ajouter_game('JUNGLE', df, 'wtplo', 12, 3, 8, 0.65, 16, 6, 7, 103, 3.4, 8)
        df = ajouter_game('JUNGLE', df, 'wtplo', 8, 10, 6, 0.39, 6, 4, 6, 135, 4.5, 6.1)
        df = ajouter_game('JUNGLE', df, 'wtplo', 2, 8, 7, 0.41, 4, 4, 5, 106, 4.4, 5.4)
        df = ajouter_game('JUNGLE', df, 'wtplo', 8, 4, 10, 0.56, 4, 5, 4, 133, 5.5, 7.6)
        df = ajouter_game('JUNGLE', df, 'wtplo', 15, 10, 8, 0.59, 12, 1, 4, 206, 5.9, 6.9)
        df = ajouter_game('JUNGLE', df, 'wtplo', 8, 9, 3, 0.25, 1, 6, 0, 206, 5.9, 5.8)
        df = ajouter_game('JUNGLE', df, 'wtplo', 6, 4, 7, 0.41, 4, 5, 3, 176, 6.6, 7.1)
        df = ajouter_game('JUNGLE', df, 'wtplo', 7, 4, 4, 0.44, 6, 6, 4, 134, 5.0, 7.0)
        df = ajouter_game('JUNGLE', df, 'wtplo', 6, 3, 15, 0.53, 1, 4, 0, 240, 8.2, 7.4)
        df = ajouter_game('JUNGLE', df, 'wtplo', 13, 7, 10, 0.79, 2, 2, 1, 128, 4.4, 6.2)
        df = ajouter_game('JUNGLE', df, 'wtplo', 5, 8, 7, 0.52, 4, 8, 4, 181, 4.9, 6.0)
        df = ajouter_game('JUNGLE', df, 'wtplo', 4, 3, 13, 0.46, 8, 6, 6, 181, 4.9, 7.3)
        df = ajouter_game('JUNGLE', df, 'wtplo', 17, 4, 8, 0.6, 4, 2, 1, 149, 6.3, 8.5)
        df = ajouter_game('JUNGLE', df, 'wtplo', 3, 10, 7, 0.56, 3, 3, 2, 83, 3.5, 5.8)
        df = ajouter_game('JUNGLE', df, 'wtplo', 6, 12, 10, 0.55, 10, 2, 2, 87, 3.4, 5.6)
        df = ajouter_game('JUNGLE', df, 'wtplo', 10, 5, 6, 0.35, 7, 4, 1, 207, 8, 8.1)
        df = ajouter_game('JUNGLE', df, 'wtplo', 12, 7, 9, 0.72, 6, 1, 6, 152, 5.6, 7.5)
        df = ajouter_game('JUNGLE', df, 'wtplo', 8, 7, 7, 0.31, 7, 4, 1, 156, 5.8, 5.9)
        df = ajouter_game('JUNGLE', df, 'wtplo', 16, 3, 9, 0.6, 4, 4, 1, 166, 6.6, 7.7)
        df = ajouter_game('JUNGLE', df, 'wtplo', 2, 10, 5, 0.58, 2, 5, 2, 114, 4.5, 5.1)
        df = ajouter_game('JUNGLE', df, 'wtplo', 3, 10, 5, 0.31, 11, 2, 5, 126, 4.3, 5.1)
        df = ajouter_game('JUNGLE', df, 'wtplo', 6, 3, 17, 0.56, 7, 2, 3, 132, 4.5, 7.9)
        df = ajouter_game('JUNGLE', df, 'wtplo', 5, 5, 7, 0.4, 7, 5, 6, 146, 4.7, 5.3)
        df = ajouter_game('JUNGLE', df, 'wtplo', 12, 2, 6, 0.67, 10, 1, 1, 182, 5.9, 8.1)
        df = ajouter_game('JUNGLE', df, 'wtplo', 4, 6, 7, 0.57, 5, 4, 5, 117, 4.2, 6.0)
        df = ajouter_game('JUNGLE', df, 'wtplo', 2, 1, 8, 0.24, 3, 3, 2, 210, 7.6, 7.8)
        df = ajouter_game('JUNGLE', df, 'wtplo', 6, 3, 7, 0.31, 6, 1, 5, 243, 10, 7.5)
        df = ajouter_game('JUNGLE', df, 'wtplo', 13, 8, 0, 0.68, 8, 1, 1, 105, 4.3, 6.6)
        df = ajouter_game('JUNGLE', df, 'wtplo', 13, 7, 9, 0.45, 9, 4, 8, 316, 8.6, 8.1)
        df = ajouter_game('JUNGLE', df, 'wtplo', 7, 10, 6, 0.43, 1, 9, 0, 205, 5.6, 5.6)
        df = ajouter_game('JUNGLE', df, 'wtplo', 8, 8, 11, 0.4, 10, 8, 9, 243, 6.3, 7.4)
        df = ajouter_game('JUNGLE', df, 'wtplo', 5, 10, 11, 0.5, 24, 9, 13, 176, 4.6, 7.0)
        df = ajouter_game('JUNGLE', df, 'wtplo', 14, 6, 14, 0.82, 11, 2, 11, 218, 7.0, 8.7)
        df = ajouter_game('JUNGLE', df, 'wtplo', 10, 8, 3, 0.59, 11, 4, 4, 225, 7.3, 7.1)
        
        dict = df.to_dict()
        


        for role in ['ADC', 'MID', 'JUNGLE', 'SUPPORT']:
            df_role = df[df['Role'] == role]

            df_role[['Kills', 'Deaths', 'Assists', 'WardsPlaced', 'WardsKilled', 'Pink', 'cs']] = df_role[
                ['Kills', 'Deaths', 'Assists', 'WardsPlaced', 'WardsKilled', 'Pink', 'cs']].astype(int)
            df_role[['KP', 'csm', 'Score']] = df_role[['KP', 'csm', 'Score']].astype(float)

            variables = ['Kills', 'Deaths', 'Assists', 'KP', 'WardsPlaced', 'WardsKilled', 'Pink', 'cs', 'csm']

            x_data = df_role[variables]
            y = df_role['Score']

            x_train, x_test, y_train, y_test = train_test_split(x_data.values, y, test_size=0.33, random_state=42)

            reg = linear_model.LinearRegression()
            reg.fit(x_train, y_train)
            
            pickle.dump(reg, open(f'./obj/ML/reg_{role}.pkl', 'wb'))
        

        writeData(dict, 'scoring')

        await ctx.send('ML update !')

    @cog_ext.cog_slash(name="scoring", description="Calcule ton score en fonction des stats associés",
                       options=[create_option(name="role", description= "Role ingame", option_type=3, required=True, choices=[
                                create_choice(name="top", value="TOP"),
                                create_choice(name="jgl", value="JUNGLE"),
                                create_choice(name="mid", value="MID"),
                                create_choice(name="adc", value="ADC"),
                                create_choice(name="support", value="SUPPORT")]),
                                create_option(name="pseudo", description= "Pseudo ingame", option_type=3, required=True),
                                create_option(name="kills", description= "Nombre de kills", option_type=4, required=True),
                                create_option(name="deaths", description= "Nombre de morts", option_type=4, required=True),
                                create_option(name="assists", description= "Nombre d assists", option_type=3, required=True),
                                create_option(name="kp", description= "KP en %", option_type=float, required=True),
                                create_option(name="wardsplaced", description= "Nombre de wards posée", option_type=int, required=True),
                                create_option(name="wardskilled", description= "Nombre de wards détruite ?", option_type=int, required=True),
                                create_option(name="pink", description= "Nombre de pinks", option_type=4, required=True),
                                create_option(name="cs", description= "Farming", option_type=4, required=True),
                                create_option(name="csm", description= "Farming par minute", option_type=float, required=True)])
    async def scoring(self, ctx, role, pseudo, kills, deaths, assists, kp:float, wardsplaced, wardskilled, pink, cs, csm:float):
        role = role.upper()
        result = scoring(role, pseudo, kills, deaths, assists, kp, wardsplaced, wardskilled, pink, cs, csm)
        await ctx.send(result)


    @cog_ext.cog_slash(name="scoring_corr", description="Explication du calcul du score",
                                options=[create_option(name="role", description= "Role ingame", option_type=3, required=True, choices=[
                                create_choice(name="top", value="TOP"),
                                create_choice(name="jgl", value="JUNGLE"),
                                create_choice(name="mid", value="MID"),
                                create_choice(name="adc", value="ADC"),
                                create_choice(name="support", value="SUPPORT")])])
    async def scoring_corr(self, ctx, role):
        # Présente la matrice de corrélation du calcul du score
        role = role.upper()
        heatmap = scoring_correlation(role)

        plt.savefig(fname='plot')

        await ctx.send(file=discord.File('plot.png'))
        os.remove('plot.png')


def setup(bot):
    bot.add_cog(Achievements_scoringlol(bot))
