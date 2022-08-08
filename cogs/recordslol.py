import discord
from discord.ext import commands
from main import isOwner2, isOwner2_slash, Var_version
import numpy as np
import pandas as pd
import asyncio
from discord_slash.utils.manage_components import *
import plotly.express as px
import plotly.graph_objects as go
import os
from fonctions.gestion_fichier import loadData, writeData, reset_records_help
from fonctions.gestion_bdd import lire_bdd
from discord_slash import cog_ext, SlashContext

from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice, create_permission


emote = {
            "KDA": ":star:",
            "KP": ":trophy:",
            "CS": ":ghost:",
            "CS/MIN": ":ghost:",
            "KILLS": ":dagger:",
            "DEATHS": ":skull:",
            "ASSISTS": ":crossed_swords:",
            'WARDS_SCORE': ":eye:",
            'WARDS_POSEES': ":eyes:",
            'WARDS_DETRUITES': ":mag:",
            'WARDS_PINKS': ":red_circle:",
            "AVANTAGE_VISION" : ":eyes:",
            "AVANTAGE_VISION_SUPPORT" : ":eyes:",
            "VISION/MIN" : ":eyes:",
            'DEGATS_INFLIGES': ":dart:",
            'DAMAGE_RATIO': ":dart:",
            'DMG_TOTAL': ":dart:",
            "% DMG": ":magic_wand:",
            'DOUBLE': ":two:",
            'TRIPLE': ":three:",
            'QUADRA': ":four:",
            'PENTA': ":five:",
            'DUREE_GAME': ":timer:",
            'SPELLS_USED': ":gun:",
            'BUFFS_VOLEES': "<:PandaWow:732316840495415398>",
            'SPELLS_EVITES': ":white_check_mark:",
            'CS_AVANTAGE': ":ghost:",
            'CS_AVANTAGES': ":ghost:",
            'SOLOKILLS': ":karate_uniform:",
            'CS_APRES_10_MIN': ":ghost:",
            'CS/MIN': ":ghost:",
            'SERIES_DE_KILLS': ":crossed_swords:",
            'NB_SERIES_DE_KILLS': ":crossed_swords:",
            'DOMMAGES_TANK': ":shield:",
            'DOMMAGES_TANK%': ":shield:",
            'DOMMAGES_REDUITS': ":shield:",
            'DOMMAGES_TOWER': ":hook:",
            'DAMAGE_RATIO_ENCAISSE': ":shield:",
            'GOLDS_GAGNES': ":euro:",
            'TOTAL_HEALS': ":sparkling_heart:",
            'HEALS_SUR_ALLIES': ":two_hearts:",
            'NBGAMES': ":star:",
            "KILLS_MOYENNE": ":dagger:",
            "DEATHS_MOYENNE": ":skull:",
            "ASSISTS_MOYENNE": ":crossed_swords:",
            'WARDS_MOYENNE': ":eye:",
            "EARLY_DRAKE" : ":timer:",
            "EARLY_BARON" : ":timer:",
            "SKILLSHOTS_HIT" : ":dart:",
            "SKILLSHOTS_DODGES" : ":dash:",
            "TOWER_PLATES" : ":ticket:",
            "ECART_LEVEL" : ":wave:",
            "NB_COURONNE_1_GAME" : ":crown:",
            "SERIE_VICTOIRE" : ":fire:", 
            "SHIELD" : ":shield:",
            "ALLIE_FEEDER" : ":monkey_face:"
        }

     
class Recordslol(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @cog_ext.cog_slash(name="records_list",
                       description="Voir les records détenues par les joueurs")
    async def records_list(self, ctx):
        
        await ctx.defer(hidden=False)

        current = 0

        fichier = lire_bdd('records', 'dict')

       

        response = ""

        embed1 = discord.Embed(title="Records (Page 1/3) :bar_chart:", colour=discord.Colour.blurple())

        for key, value in fichier.items():
            valeur = ""
            if key == "DEGATS_INFLIGES":
                valeur = "{:,}".format(value['Score']).replace(',', ' ').replace('.', ',')
            elif key == "DUREE_GAME":
                valeur = str(int(round(value['Score'], 0))).replace(".", "m")
            elif key in ["KP", "% DMG", "AVANTAGE_VISION", "AVANTAGE_VISION_SUPPORT"]:
                valeur = str(value['Score']) + "%"
            else:
                valeur = str(value['Score'])
            embed1.add_field(name=str(emote[key]) + "" + key,
                             value="Records : __ " + valeur + " __ \n ** " + str(
                                 value['Joueur']) + " ** (" + str(value['Champion']) + ")")

        embed1.set_footer(text=f'Version {Var_version} by Tomlora')

        fichier2 = lire_bdd('records2', 'dict')
        

        embed2 = discord.Embed(title="Records (Page 2/3) :bar_chart:", colour=discord.Colour.blurple())

        for key, value in fichier2.items():
            valeur2 = ""
            if key in ["GOLDS_GAGNES", "DOMMAGES_TANK", 'DOMMAGES_REDUITS', "DOMMAGES_TOWER", "TOTAL_HEALS", "HEALS_SUR_ALLIES"]:
                valeur2 = "{:,}".format(value['Score']).replace(',', ' ').replace('.', ',')
            elif key == "DOMMAGES_TANK%":
                valeur2 = str(value['Score']) + "%"
            elif key == "EARLY_DRAKE" or key == "EARLY_BARON":
                valeur2 = str(value['Score']).replace(".", "m")
            else:
                valeur2 = str(value['Score'])
            embed2.add_field(name=str(emote[key]) + "" + key,
                             value="Records : __ " + valeur2 + " __ \n ** " + str(
                                 value['Joueur']) + " ** (" + str(value['Champion']) + ")")

        embed2.set_footer(text=f'Version {Var_version} by Tomlora')

        embed3 = discord.Embed(title="Records Cumul & Moyenne (Page 3/3) :bar_chart: ")

        fichier3 = lire_bdd('records3', 'dict')

        df = pd.DataFrame.from_dict(fichier3)
        df.fillna(0, inplace=True)
        df.index.name = "Joueurs"
        df.reset_index(inplace=True)

        # Moyenne

        df['KILLS_MOYENNE'] = 0
        df['DEATHS_MOYENNE'] = 0
        df['ASSISTS_MOYENNE'] = 0
        df['WARDS_MOYENNE'] = 0

        df['KILLS_MOYENNE'] = np.where(df['NBGAMES'] > 0, df['KILLS'] / df['NBGAMES'], 0)
        df['DEATHS_MOYENNE'] = np.where(df['NBGAMES'] > 0, df['DEATHS'] / df['NBGAMES'], 0)
        df['ASSISTS_MOYENNE'] = np.where(df['NBGAMES'] > 0, df['ASSISTS'] / df['NBGAMES'], 0)
        df['WARDS_MOYENNE'] = np.where(df['NBGAMES'] > 0, df['WARDS_SCORE'] / df['NBGAMES'], 0)

        record3 = fichier3.keys()

        def findrecord(df, key, asc):
            df = df[df['NBGAMES'] >= 10]
            if asc is True:
                df = df[df[key] > 1]

            df.sort_values(key, ascending=asc, inplace=True)

            value = df[key].iloc[0]
            joueur = df['Joueurs'].iloc[0]
            nbgames = int(df['NBGAMES'].iloc[0])

            return joueur, value, nbgames

        if df['NBGAMES'].max() >= 10:
            for key in record3: # durée game bug donc on le retire
                joueur, value, nbgames = findrecord(df, key, False)

                if key == "NBGAMES" or key == "PENTA" or key == "QUADRA" or key == 'SOLOKILLS':
                    value = int(value)

                elif key == 'DUREE_GAME':
                    # value = round(float(value), 2)
                    # value = str(value).replace(".", "h")
                    continue


                elif key in ['KILLS', 'DEATHS', 'ASSISTS', 'WARDS_SCORE', 'WARDS_POSEES', 'WARDS_DETRUITES',
                             'WARDS_PINKS', 'CS']:
                    break

                embed3.add_field(name=str(emote[key]) + "" + str(key),
                                 value="Records : __ " + str(value) + " __ \n ** " + str(
                                     joueur) + "**")

            for key in ['WARDS_MOYENNE', 'KILLS_MOYENNE', 'DEATHS_MOYENNE', 'ASSISTS_MOYENNE']:
                joueur, value, nbgames = findrecord(df, key, False)
                value = round(float(value), 2)

                embed3.add_field(name=str(emote[key]) + "" + str(key) + " (ELEVEE)",
                                 value="Records : __ " + str(value) + " __ en " + str(nbgames) + " games \n ** " + str(
                                     joueur) + "**")

            for key in ['KILLS_MOYENNE', 'DEATHS_MOYENNE', 'ASSISTS_MOYENNE']:
                joueur, value, nbgames = findrecord(df, key, True)
                value = round(float(value), 2)

                embed3.add_field(name=str(emote[key]) + "" + str(key) + " (BASSE)",
                                 value="Records : __ " + str(value) + " __ en " + str(nbgames) + " games \n ** " + str(
                                     joueur) + "**")

        else:
            embed3.add_field(name="Indisponible", value="Aucun joueur n'a atteint le minimum requis : 10 games")

        embed3.set_footer(text=f'Version {Var_version} by Tomlora')

        self.bot.pages = [embed1, embed2, embed3]
        buttons = [u"\u2B05", u"\u27A1"]  # skip to start, left, right, skip to end

        msg = await ctx.send(embed=self.bot.pages[current])

        for button in buttons:
            await msg.add_reaction(button)
            

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", check=lambda reaction,
                                                                                      user: user == ctx.author and reaction.emoji in buttons,
                                                         timeout=30.0)
            except asyncio.TimeoutError:
                return print("Records_list terminés")
            else:
                previous_page = current

                if reaction.emoji == u"\u2B05":
                    if current > 0:
                        current -= 1

                elif reaction.emoji == u"\u27A1":
                    if current < len(self.bot.pages) - 1:
                        current += 1

                for button in buttons:
                    await msg.remove_reaction(button, ctx.author)

                if current != previous_page:
                    await msg.edit(embed=self.bot.pages[current])
                    
    @cog_ext.cog_slash(name="records_personnel",
                       description="Record personnel",
                       options=[create_option(name="joueur", description="Pseudo LoL", option_type=3, required=True)])
    async def records_personnel(self, ctx, joueur:str):
        
        joueur = joueur.lower()
        
        data = lire_bdd('records_personnel', 'dict')
        
        await ctx.defer(hidden=False)
        
        df = pd.DataFrame(data)
        df = df.loc[joueur]
        
        embed = discord.Embed(title=f"Records personnels {joueur}", colour=discord.Colour.blurple())
    
        
        for key, valeur in df.iteritems():
            # format
            if key in ['DAMAGE_RATIO', 'DAMAGE_RATIO_ENCAISSE', 'KP', 'AVANTAGE_VISION']:
                valeur = str(valeur) + "%"
            if key == "DUREE_GAME":
                valeur = str(valeur).replace(".", "m")

            embed.add_field(name=str(emote[key]) + " " + key,
                             value=f"Records : __ {valeur} __ ")

        embed.set_footer(text=f'Version {Var_version} by Tomlora')
        
        
        await ctx.send(embed=embed)
        
        
    @cog_ext.cog_slash(name="pantheon",
                       description="Cumul des statistiques",
                       options=[create_option(name="stat", description="Quel stat ?", option_type=3, required=True, choices=[
                                    create_choice(name="KDA", value="KDA"),
                                    create_choice(name='KDA moyenne', value='KDA moyenne'),
                                    create_choice(name='vision', value='VISION'),
                                    create_choice(name='vision moyenne', value='VISION moyenne'),
                                    create_choice(name='CS', value='CS'),
                                    create_choice(name='Solokills', value='SOLOKILLS'),
                                    create_choice(name='games', value='GAMES')]),
                                create_option(name="stat2", description="Quel stat ?", option_type=3, required=False, choices=[
                                    create_choice(name="KDA", value="KDA"),
                                    create_choice(name='KDA moyenne', value='KDA moyenne'),
                                    create_choice(name='vision', value='VISION'),
                                    create_choice(name='vision moyenne', value='VISION moyenne'),
                                    create_choice(name='CS', value='CS'),
                                    create_choice(name='Solokills', value='SOLOKILLS'),
                                    create_choice(name='games', value='GAMES')]),
                                create_option(name="stat3", description="Quel stat ?", option_type=3, required=False, choices=[
                                    create_choice(name="KDA", value="KDA"),
                                    create_choice(name='KDA moyenne', value='KDA moyenne'),
                                    create_choice(name='vision', value='VISION'),
                                    create_choice(name='vision moyenne', value='VISION moyenne'),
                                    create_choice(name='CS', value='CS'),
                                    create_choice(name='Solokills', value='SOLOKILLS'),
                                    create_choice(name='games', value='GAMES')]),
                                create_option(name="fichier_recap", description="Fichier Excel recapitulatif", option_type=5, required=False)
                                ])
    async def pantheon(self, ctx, stat, stat2:str="no", stat3:str="no", fichier_recap:bool=False):
        
        stat = [stat, stat2, stat3]
        
        data = lire_bdd('records3', 'dict')

        df = pd.DataFrame.from_dict(data)
        df.fillna(0, inplace=True)
        df.index.name = "Joueurs"
        df.reset_index(inplace=True)

        # Moyenne

        df['KILLS_MOYENNE'] = 0
        df['DEATHS_MOYENNE'] = 0
        df['ASSISTS_MOYENNE'] = 0
        df['WARDS_MOYENNE'] = 0
        df['DUREE_MOYENNE'] = 0

        df['KILLS_MOYENNE'] = np.where(df['NBGAMES'] > 0, df['KILLS'] / df['NBGAMES'], 0)
        df['DEATHS_MOYENNE'] = np.where(df['NBGAMES'] > 0, df['DEATHS'] / df['NBGAMES'], 0)
        df['ASSISTS_MOYENNE'] = np.where(df['NBGAMES'] > 0, df['ASSISTS'] / df['NBGAMES'], 0)
        df['WARDS_MOYENNE'] = np.where(df['NBGAMES'] > 0, df['WARDS_SCORE'] / df['NBGAMES'], 0)
                
        df['WARDS_POSEES_MOYENNE'] = np.where(df['NBGAMES'] > 0, df['WARDS_POSEES'] / df['NBGAMES'], 0)
        df['WARDS_DETRUITES_MOYENNE'] = np.where(df['NBGAMES'] > 0, df['WARDS_DETRUITES'] / df['NBGAMES'], 0)
        df['WARDS_PINKS_MOYENNE'] = np.where(df['NBGAMES'] > 0, df['WARDS_PINKS'] / df['NBGAMES'], 0)
        
        df['DUREE_MOYENNE'] = np.where(df['NBGAMES'] > 0, df['DUREE_GAME'] / df['NBGAMES'], 0)
        
        df['DUREE_MOYENNE'] = round(df['DUREE_MOYENNE'] * 60, 2)
        
        for ward_col in ['WARDS_MOYENNE', 'WARDS_POSEES_MOYENNE', 'WARDS_DETRUITES_MOYENNE', 'WARDS_PINKS_MOYENNE']:
            df[ward_col] = round(df[ward_col], 2)
        
        df.to_excel('./obj/records/pantheon.xlsx', index=False)
        
        await ctx.defer(hidden=False)
        
        liste_graph = list()
        liste_delete = list()
        
        def graphique(fig, name):
            fig.write_image(name)
            liste_delete.append(name)
            liste_graph.append(discord.File(name))

        def figure_hist(dict, title): # Fonction pour faire l'histogramme en fonction d'un dict

            fig = go.Figure()
            for key in dict:
                if key == "DUREE_GAME":
                    df[key] = round(df[key], 2)
                fig.add_trace(
                    go.Histogram(histfunc="sum", y=df[key], x=df['Joueurs'], name=str(key), texttemplate="%{y}",
                                 textfont_size=20))
                fig.update_layout(
                    title_text=title)  # title of plot
            return fig
        
        df = df[~df['Joueurs'].isin(['Kazsc', 'Personne'])] # on supprime les deux comptes fantomes


        try:
            if "KDA" in stat:
                variables = ['KILLS', 'DEATHS', 'ASSISTS']

                df['KDA'] = (df['KILLS'] + df['ASSISTS']) / df['DEATHS']
                df['KDA'] = round(df['KDA'],2)

                fig = figure_hist(variables, "KDA")

                graphique(fig, 'KDA1.png')

                fig = px.pie(df, values='KDA', names='Joueurs', title='KDA')
                fig.update_traces(textinfo='value', textfont_size=20)

                graphique(fig, 'KDA2.png')


                await ctx.send(
                    f' __ Total KDA : __ \n Kills : {int(df["KILLS"].sum())} \n Morts : {int(df["DEATHS"].sum())} \n Assists : {int(df["ASSISTS"].sum())}')

            if "VISION" in stat:
                variables = ['WARDS_POSEES', 'WARDS_DETRUITES', 'WARDS_PINKS']

                fig = figure_hist(variables, "VISION")
                
                graphique(fig, 'vision.png')

                await ctx.send(
                    f' __ Total : __ \n Wards posées : {int(df["WARDS_POSEES"].sum())} \n Wards détruites : {int(df["WARDS_DETRUITES"].sum())} \n Pinks : {int(df["WARDS_PINKS"].sum())}')

            if "KDA moyenne" in stat:
                variables = ['KILLS_MOYENNE', 'DEATHS_MOYENNE', 'ASSISTS_MOYENNE']

                fig = figure_hist(variables, "KDA moyenne")

                graphique(fig, 'KDA_moyenne.png')

            if "VISION moyenne" in stat:
                variables = ['WARDS_MOYENNE']

                fig = figure_hist(variables, "VISION moyenne")

                graphique(fig, 'vision_moyenne.png')
                
                variables_avg = ['WARDS_POSEES_MOYENNE', 'WARDS_DETRUITES_MOYENNE', 'WARDS_PINKS_MOYENNE']
                
                fig2 = figure_hist(variables_avg, "VISION moyenne par joueur")
                
                graphique(fig2, 'vision_moyenne_par_joueur.png')

            if "CS" in stat:
                variables = ['CS']

                fig = figure_hist(variables, 'CS')

                graphique(fig, 'CS.png')

                await ctx.send(
                    f' __ Total : __ \n CS : {int(df["CS"].sum())}')
                
            if "SOLOKILLS" in stat:
                variables = ['SOLOKILLS']

                fig = figure_hist(variables, "Solokills")
                fig.update_xaxes(categoryorder="total descending")

                graphique(fig, 'solokills.png')

            if "GAMES" in stat:
                variables = ['NBGAMES', 'DUREE_GAME']
                              

                fig = figure_hist(variables, 'GAMES')

                fig.write_image('plot.png')
                await ctx.send(content="Durée des games exprimée en heures", file=discord.File('plot.png'))
                os.remove('plot.png')
                
                fig = px.pie(df, values='DUREE_MOYENNE', names='Joueurs', title='DUREE MOYENNE DES GAMES')
                fig.update_traces(textinfo='value', textfont_size=20)
                fig.write_image('pie.png')
                await ctx.send(content="Durée des games exprimée en minutes", file=discord.File('pie.png'))
                os.remove('pie.png')
                
            if fichier_recap is True:
                url = "./obj/records/pantheon.xlsx"
                await ctx.send(file=discord.File(url))
                
            if len(liste_graph) >= 1: # il faut au moins un graph
                await ctx.send(files=liste_graph)
            
            for graph in liste_delete:
                os.remove(graph)
                

        except asyncio.TimeoutError:
            await stat.delete()
            await ctx.send("Annulé")


def setup(bot):
    bot.add_cog(Recordslol(bot))
