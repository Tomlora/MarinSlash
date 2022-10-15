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
from fonctions.gestion_bdd import lire_bdd, lire_bdd_perso
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
            "ALLIE_FEEDER" : ":monkey_face:",
                        "KDA_ARAM": ":star:",
            "KP_ARAM": ":trophy:",
            "CS_ARAM": ":ghost:",
            "CS/MIN_ARAM": ":ghost:",
            "KILLS_ARAM": ":dagger:",
            "DEATHS_ARAM": ":skull:",
            "ASSISTS_ARAM": ":crossed_swords:",
            "AVANTAGE_VISION" : ":eyes:",
            "AVANTAGE_VISION_SUPPORT" : ":eyes:",
            "VISION/MIN" : ":eyes:",
            "DEGATS_INFLIGES_ARAM": ":dart:",
            "DAMAGE_RATIO_ARAM": ":dart:",
            "DMG_TOTAL_ARAM": ":dart:",
            "% DMG_ARAM": ":magic_wand:",
            "DOUBLE_ARAM": ":two:",
            "TRIPLE_ARAM": ":three:",
            "QUADRA_ARAM": ":four:",
            "PENTA_ARAM": ":five:",
            "DUREE_GAME_ARAM": ":timer:",
            "SPELLS_USED_ARAM": ":gun:",
            "BUFFS_VOLEES_ARAM": "<:PandaWow:732316840495415398>",
            "SPELLS_EVITES_ARAM": ":white_check_mark:",
            "CS_AVANTAGE_ARAM": ":ghost:",
            "CS_AVANTAGES_ARAM": ":ghost:",
            "SOLOKILLS_ARAM": ":karate_uniform:",
            "CS_APRES_10_MIN_ARAM": ":ghost:",
            "CS/MIN_ARAM": ":ghost:",
            "SERIES_DE_KILLS_ARAM": ":crossed_swords:",
            "NB_SERIES_DE_KILLS_ARAM": ":crossed_swords:",
            "DOMMAGES_TANK_ARAM": ":shield:",
            "DOMMAGES_TANK%_ARAM": ":shield:",
            "DOMMAGES_REDUITS_ARAM": ":shield:",
            "DOMMAGES_TOWER_ARAM": ":hook:",
            "DAMAGE_RATIO_ENCAISSE_ARAM": ":shield:",
            "GOLDS_GAGNES_ARAM": ":euro:",
            "TOTAL_HEALS_ARAM": ":sparkling_heart:",
            "HEALS_SUR_ALLIES_ARAM": ":two_hearts:",
            "NBGAMES_ARAM": ":star:",
            "KILLS_MOYENNE_ARAM": ":dagger:",
            "DEATHS_MOYENNE_ARAM": ":skull:",
            "ASSISTS_MOYENNE_ARAM": ":crossed_swords:",
            "SKILLSHOTS_HIT_ARAM" : ":dart:",
            "SKILLSHOTS_DODGES_ARAM" : ":dash:",
            "NB_COURONNE_1_GAME_ARAM" : ":crown:",
            "SHIELD_ARAM" : ":shield:",
            "ALLIE_FEEDER_ARAM" : ":monkey_face:"
        }


choice_pantheon = [create_choice(name="KDA", value="KDA"),
                    create_choice(name='KDA moyenne', value='KDA moyenne'),
                    create_choice(name='vision', value='VISION'),
                    create_choice(name='vision moyenne', value='VISION moyenne'),
                    create_choice(name='CS', value='CS'),
                    create_choice(name='Solokills', value='SOLOKILLS'),
                    create_choice(name='games', value='GAMES')]
     
class Recordslol(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        
    @cog_ext.cog_slash(name="records_list",
                       description="Voir les records détenues par les joueurs",
                       options=[create_option(name="mode", description="Quel mode de jeu ?", option_type=3, required=True, choices=[
                                    create_choice(name='ranked', value='ranked'),
                                    create_choice(name='aram', value='aram')]),
                                create_option(name='saison', description='saison league of legends', option_type=4, required=False)
                                ])
    async def records_list(self, ctx, saison:int=12, mode:str='ranked'):
        
        await ctx.defer(hidden=False)

        current = 0

        fichier = lire_bdd_perso('SELECT index, "Score", "Champion", "Joueur", url from records where saison= %(saison)s AND mode=%(mode)s', params={'saison' : saison,
                                                                                                                                                     'mode' : mode}).transpose()
        
        fichier1 = fichier.iloc[:22]
        fichier2 = fichier.iloc[22:]
        
        response = ""

        embed1 = discord.Embed(title=f"Records {mode} S{saison} (Page 1/3) :bar_chart:", colour=discord.Colour.blurple())

        for key, value in fichier1.iterrows():
            valeur = ""
            if key == "DEGATS_INFLIGES":
                valeur = "{:,}".format(value['Score']).replace(',', ' ').replace('.', ',')
            elif key == "DUREE_GAME":
                valeur = str(int(round(value['Score'], 0))).replace(".", "m")
            elif key in ["KP", "% DMG", "AVANTAGE_VISION", "AVANTAGE_VISION_SUPPORT"]:
                valeur = str(value['Score']) + "%"
            else:
                valeur = int(value['Score'])
                
            if value['url'] == "na":
                embed1.add_field(name=str(emote[key]) + "" + key,
                             value=f"Records : __ {valeur} __ \n ** {value['Joueur']} ** ({value['Champion']})")
            
            else:
                embed1.add_field(name=str(emote[key]) + "" + key,
                             value=f"Records : __ [{valeur}]({value['url']}) __ \n ** {value['Joueur']} ** ({value['Champion']})")
                
                

        embed1.set_footer(text=f'Version {Var_version} by Tomlora')

        

        embed2 = discord.Embed(title=f"Records {mode} S{saison} (Page 2/3) :bar_chart:", colour=discord.Colour.blurple())

        for key, value in fichier2.iterrows():
            valeur2 = ""
            if key in ["GOLDS_GAGNES", "DOMMAGES_TANK", 'DOMMAGES_REDUITS', "DOMMAGES_TOWER", "TOTAL_HEALS", "HEALS_SUR_ALLIES"]:
                valeur2 = "{:,}".format(value['Score']).replace(',', ' ').replace('.', ',')
            elif key == "DOMMAGES_TANK%":
                valeur2 = str(value['Score']) + "%"
            elif key == "EARLY_DRAKE" or key == "EARLY_BARON":
                valeur2 = str(value['Score']).replace(".", "m")
            else:
                valeur2 = int(value['Score'])
                
            if value['url'] == 'na':
                embed2.add_field(name=str(emote[key]) + "" + key,
                             value=f"Records : __ {valeur2} __ \n ** {value['Joueur']} ** ({value['Champion']})")
                
            else:
                embed2.add_field(name=str(emote[key]) + "" + key,
                             value=f"Records : __ [{valeur2}]({value['url']}) __ \n ** {value['Joueur']} ** ({value['Champion']})")

        embed2.set_footer(text=f'Version {Var_version} by Tomlora')

        embed3 = discord.Embed(title=f"Records Cumul & Moyenne S{saison} (Page 3/3) :bar_chart: ")

        fichier3 = lire_bdd('records3', 'dict')

        df = pd.DataFrame.from_dict(fichier3)
        df.fillna(0, inplace=True)
        df.index.name = "Joueurs"
        df.reset_index(inplace=True)

        if mode == 'ranked':
            col_games = 'NBGAMES'
            col_kills = 'KILLS'
            col_deaths = 'DEATHS'
            col_assists = 'ASSISTS'
            list_avg = ['WARDS_MOYENNE', 'KILLS_MOYENNE', 'DEATHS_MOYENNE', 'ASSISTS_MOYENNE']
            col_penta = 'PENTA'
            col_quadra = 'QUADRA'
            col_solokills = 'SOLOKILLS'
            col_duree = 'DUREE_GAME'
            
        elif mode == 'aram':
            col_games = 'NBGAMES_ARAM'
            col_kills = 'KILLS_ARAM'
            col_deaths = 'DEATHS_ARAM'
            col_assists = 'ASSISTS_ARAM'
            list_avg = ['KILLS_MOYENNE', 'DEATHS_MOYENNE', 'ASSISTS_MOYENNE']
            col_penta = 'PENTA_ARAM'
            col_quadra = 'QUADRA_ARAM'
            col_solokills = 'SOLOKILLS_ARAM'
            col_duree = 'DUREE_GAME_ARAM'            
        
        # Moyenne    
        df['KILLS_MOYENNE'] = 0
        df['DEATHS_MOYENNE'] = 0
        df['ASSISTS_MOYENNE'] = 0
        df['WARDS_MOYENNE'] = 0

        df['KILLS_MOYENNE'] = np.where(df[col_games] > 0, df[col_kills] / df[col_games], 0)
        df['DEATHS_MOYENNE'] = np.where(df[col_games] > 0, df[col_deaths] / df[col_games], 0)
        df['ASSISTS_MOYENNE'] = np.where(df[col_games] > 0, df[col_assists] / df[col_games], 0)
        
        if mode == 'ARAM':
            df['WARDS_MOYENNE'] = np.where(df[col_games] > 0, df['WARDS_SCORE'] / df[col_games], 0)

       
        list_keys = []
        
        if mode == 'ranked':
            for key in fichier3.keys():
                if not "ARAM" in key.split('_'):
                    list_keys.append(key)
        elif mode == 'aram':
            for key in fichier3.keys():
                if "ARAM" in key.split('_'):
                    list_keys.append(key)
            

        def findrecord(df, key, asc):
            df = df[df[col_games] >= 10]
            if asc is True:
                df = df[df[key] > 1]

            df.sort_values(key, ascending=asc, inplace=True)

            value = df[key].iloc[0]
            joueur = df['Joueurs'].iloc[0]
            nbgames = int(df[col_games].iloc[0])

            return joueur, value, nbgames

        if df[col_games].max() >= 10:
            for key in list_keys: # durée game bug donc on le retire
                
                joueur, value, nbgames = findrecord(df, key, False)

                if key == col_games or key == col_penta or key == col_quadra or key == col_solokills:
                    value = int(value)

                elif key == col_duree:
                    # value = round(float(value), 2)
                    # value = str(value).replace(".", "h")
                    continue


                elif key in [col_kills, col_deaths, col_assists, 'WARDS_SCORE', 'WARDS_POSEES', 'WARDS_DETRUITES',
                             'WARDS_PINKS', 'CS']:
                    break

                embed3.add_field(name=str(emote[key]) + "" + str(key),
                                 value="Records : __ " + str(value) + " __ \n ** " + str(
                                     joueur) + "**")

            for key in list_avg:
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
        
        df = lire_bdd('records_personnel')[joueur]
        
        await ctx.defer(hidden=False)
        
        current = 0
        
        df_part1 = df.iloc[:18]
        df_part2 = df.iloc[18:]
        
        embed1 = discord.Embed(title=f"Records personnels {joueur} (1/3)", colour=discord.Colour.blurple())
        embed2 = discord.Embed(title=f"Records personnels {joueur} (2/3)", colour=discord.Colour.blurple())
        embed3 = discord.Embed(title=f"Records personnels ARAM {joueur} (3/3)", colour=discord.Colour.blurple())
    
        
        for key, valeur in df_part1.iteritems():
            # format
            if key in ['DAMAGE_RATIO', 'DAMAGE_RATIO_ENCAISSE', 'KP', 'AVANTAGE_VISION']:
                valeur = str(valeur) + "%"
            elif key == "DUREE_GAME":
                valeur = str(valeur).replace(".", "m")
            else:
                if not 'url' in key.split('_'):
                    valeur = int(valeur)
                
            if not 'url' in key.split('_'): # si url alors c'est un lien, pas un record
                
                if df.loc[key + '_url'] == 'na':

                    embed1.add_field(name=str(emote[key]) + " " + key,
                                value=f"Records : __ {valeur} __ ")
                
                else:
                    
                    
                    embed1.add_field(name=str(emote[key]) + " " + key,
                                value=f"Records : __ [{valeur}]({df.loc[key + '_url']}) __ ")
                    

        for key, valeur in df_part2.iteritems():
            
            if 'ARAM' in key.split('_'):
                embed_selected = embed3 # records perso aram
            else:
                embed_selected = embed2 # autre
            # format
            if key in ['DAMAGE_RATIO', 'DAMAGE_RATIO_ENCAISSE', 'KP', 'AVANTAGE_VISION']:
                valeur = str(valeur) + "%"
            elif key == "DUREE_GAME":
                valeur = str(valeur).replace(".", "m")
            else:
                if not 'url' in key.split('_'):
                    valeur = int(valeur)
                
            if not 'url' in key.split('_'): # si url alors c'est un lien, pas un record
                
                if df.loc[key + '_url'] == 'na':  # on cherche l'url associé
                    
                    embed_selected.add_field(name=str(emote[key]) + " " + key,
                                value=f"Records : __ {valeur} __ ")
                
                else:
                    
                    embed_selected.add_field(name=str(emote[key]) + " " + key,
                                value=f"Records : __ [{valeur}]({df.loc[key + '_url']}) __ ")
                    

        embed1.set_footer(text=f'Version {Var_version} by Tomlora')
        embed2.set_footer(text=f'Version {Var_version} by Tomlora')
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
        
        
    @cog_ext.cog_slash(name="pantheon",
                       description="Cumul des statistiques",
                       options=[create_option(name="stat", description="Quel stat ?", option_type=3, required=True, choices=choice_pantheon),
                                create_option(name="mode", description="Quel mode de jeu ?", option_type=3, required=True, choices=[
                                    create_choice(name='ranked', value='ranked'),
                                    create_choice(name='aram', value='aram')]),
                                create_option(name="stat2", description="Quel stat ?", option_type=3, required=False, choices=choice_pantheon),
                                create_option(name="stat3", description="Quel stat ?", option_type=3, required=False, choices=choice_pantheon),
                                create_option(name="fichier_recap", description="Fichier Excel recapitulatif", option_type=5, required=False)
                                ])
    async def pantheon(self, ctx, stat, mode:str, stat2:str="no", stat3:str="no", fichier_recap:bool=False):
        
        stat = [stat, stat2, stat3]
        
        data = lire_bdd('records3', 'dict')

        df = pd.DataFrame.from_dict(data)
        df.fillna(0, inplace=True)
        df.index.name = "Joueurs"
        df.reset_index(inplace=True)

        if mode == 'ranked':
            col_games = 'NBGAMES'
            col_kills = 'KILLS'
            col_deaths = 'DEATHS'
            col_assists = 'ASSISTS'
            list_avg = ['WARDS_MOYENNE', 'KILLS_MOYENNE', 'DEATHS_MOYENNE', 'ASSISTS_MOYENNE']
            col_penta = 'PENTA'
            col_quadra = 'QUADRA'
            col_solokills = 'SOLOKILLS'
            col_duree = 'DUREE_GAME'
            col_CS = 'CS'
            
        elif mode == 'aram':
            col_games = 'NBGAMES_ARAM'
            col_kills = 'KILLS_ARAM'
            col_deaths = 'DEATHS_ARAM'
            col_assists = 'ASSISTS_ARAM'
            list_avg = ['KILLS_MOYENNE', 'DEATHS_MOYENNE', 'ASSISTS_MOYENNE']
            col_penta = 'PENTA_ARAM'
            col_quadra = 'QUADRA_ARAM'
            col_solokills = 'SOLOKILLS_ARAM'
            col_duree = 'DUREE_GAME_ARAM'
            col_CS = 'CS_ARAM'
        # Moyenne

        df['KILLS_MOYENNE'] = 0
        df['DEATHS_MOYENNE'] = 0
        df['ASSISTS_MOYENNE'] = 0
        df['WARDS_MOYENNE'] = 0
        df['DUREE_MOYENNE'] = 0

        df['KILLS_MOYENNE'] = np.where(df[col_games] > 0, df[col_kills] / df[col_games], 0)
        df['DEATHS_MOYENNE'] = np.where(df[col_games] > 0, df[col_deaths] / df[col_games], 0)
        df['ASSISTS_MOYENNE'] = np.where(df[col_games] > 0, df[col_assists] / df[col_games], 0)
        if mode == 'ranked':
            df['WARDS_MOYENNE'] = np.where(df[col_games] > 0, df['WARDS_SCORE'] / df[col_games], 0)  
            df['WARDS_POSEES_MOYENNE'] = np.where(df[col_games] > 0, df['WARDS_POSEES'] / df[col_games], 0)
            df['WARDS_DETRUITES_MOYENNE'] = np.where(df[col_games] > 0, df['WARDS_DETRUITES'] / df[col_games], 0)
            df['WARDS_PINKS_MOYENNE'] = np.where(df[col_games] > 0, df['WARDS_PINKS'] / df[col_games], 0)
        
        df['DUREE_MOYENNE'] = np.where(df[col_games] > 0, df[col_duree] / df[col_games], 0)
        
        df['DUREE_MOYENNE'] = round(df[col_duree] * 60, 2)
        
        if mode == 'ranked':
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
                if key == col_duree:
                    df[key] = round(df[key], 2)
                fig.add_trace(
                    go.Histogram(histfunc="sum", y=df[key], x=df['Joueurs'], name=str(key), texttemplate="%{y}",
                                 textfont_size=20))
                fig.update_layout(
                    title_text=title)  # title of plot
            return fig


        try:
            if "KDA" in stat:
                variables = [col_kills, col_deaths, col_assists]

                df['KDA'] = (df[col_kills] + df[col_assists]) / df[col_deaths]
                df['KDA'] = round(df['KDA'],2)

                fig = figure_hist(variables, "KDA")

                graphique(fig, 'KDA1.png')

                fig = px.pie(df, values='KDA', names='Joueurs', title='KDA')
                fig.update_traces(textinfo='value', textfont_size=20)

                graphique(fig, 'KDA2.png')


                await ctx.send(
                    f' __ Total KDA : __ \n Kills : {int(df[col_kills].sum())} \n Morts : {int(df[col_deaths].sum())} \n Assists : {int(df[col_assists].sum())}')

            if "VISION" in stat and mode == 'ranked':
                variables = ['WARDS_POSEES', 'WARDS_DETRUITES', 'WARDS_PINKS']

                fig = figure_hist(variables, "VISION")
                
                graphique(fig, 'vision.png')

                await ctx.send(
                    f' __ Total : __ \n Wards posées : {int(df["WARDS_POSEES"].sum())} \n Wards détruites : {int(df["WARDS_DETRUITES"].sum())} \n Pinks : {int(df["WARDS_PINKS"].sum())}')

            if "VISION" in stat and mode == 'aram':
                await ctx.send('Pas de vision en aram !')
                
            if "KDA moyenne" in stat:
                variables = ['KILLS_MOYENNE', 'DEATHS_MOYENNE', 'ASSISTS_MOYENNE']

                fig = figure_hist(variables, "KDA moyenne")

                graphique(fig, 'KDA_moyenne.png')

            if "VISION moyenne" in stat and mode == 'ranked':
                variables = ['WARDS_MOYENNE']

                fig = figure_hist(variables, "VISION moyenne")

                graphique(fig, 'vision_moyenne.png')
                
                variables_avg = ['WARDS_POSEES_MOYENNE', 'WARDS_DETRUITES_MOYENNE', 'WARDS_PINKS_MOYENNE']
                
                fig2 = figure_hist(variables_avg, "VISION moyenne par joueur")
                
                graphique(fig2, 'vision_moyenne_par_joueur.png')
                
            if "VISION moyenne" in stat and mode == 'aram':
                await ctx.send('Pas de vision en aram !')

            if "CS" in stat:
                variables = [col_CS]

                fig = figure_hist(variables, col_CS)

                graphique(fig, 'CS.png')

                await ctx.send(
                    f' __ Total : __ \n CS : {int(df[col_CS].sum())}')
                
            if "SOLOKILLS" in stat:
                variables = [col_solokills]

                fig = figure_hist(variables, col_solokills)
                fig.update_xaxes(categoryorder="total descending")

                graphique(fig, 'solokills.png')

            if "GAMES" in stat:
                variables = [col_games, col_duree]
                              

                fig = figure_hist(variables, col_games)

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
