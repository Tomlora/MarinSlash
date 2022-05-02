import discord
from discord.ext import commands
import main
import numpy as np
import pandas as pd
import asyncio
from discord_slash.utils.manage_components import *
import plotly.express as px
import plotly.graph_objects as go
import os
from fonctions.gestion_fichier import loadData, writeData, reset_records_help
from discord_slash import cog_ext, SlashContext

from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice, create_permission

Var_version = 1.0


        



class Recordslol(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        

    
    @cog_ext.cog_slash(name="records_reset", guild_ids=[494217748046544906], description="Remet à zéro les records. Reservé au propriétaire du bot")
    @main.isOwner2()
    async def records_reset(self, ctx, fichier: int):
        if fichier == 1:
            reset_records_help('KDA', 1)
            reset_records_help('KP', 1)
            reset_records_help('CS', 1)
            reset_records_help('CS/MIN', 1)
            reset_records_help('KILLS', 1)
            reset_records_help('DEATHS', 1)
            reset_records_help('ASSISTS', 1)
            reset_records_help('WARDS_SCORE', 1)
            reset_records_help('WARDS_POSEES', 1)
            reset_records_help('WARDS_DETRUITES', 1)
            reset_records_help('WARDS_PINKS', 1)
            reset_records_help('DEGATS_INFLIGES', 1)
            reset_records_help('% DMG', 1)
            reset_records_help('DOUBLE', 1)
            reset_records_help('TRIPLE', 1)
            reset_records_help('QUADRA', 1)
            reset_records_help('PENTA', 1)
            reset_records_help('DUREE_GAME', 1)
        elif fichier == 2:
            reset_records_help('SPELLS_USED', 2)
            reset_records_help('BUFFS_VOLEES', 2)
            reset_records_help('SPELLS_EVITES', 2)
            reset_records_help('MUlTIKILL_1_SPELL', 2)
            reset_records_help('SOLOKILLS', 2)
            reset_records_help('CS_APRES_10_MIN', 2)
            reset_records_help('SERIES_DE_KILLS', 2)
            reset_records_help('NB_SERIES_DE_KILLS', 2)
            reset_records_help('DOMMAGES_TANK', 2)
            reset_records_help('DOMMAGES_TANK%', 2)
            reset_records_help('DOMMAGES_REDUITS', 2)
            reset_records_help('DOMMAGES_TOWER', 2)
            reset_records_help('GOLDS_GAGNES', 2)
            reset_records_help('TOTAL_HEALS', 2)
            reset_records_help('HEALS_SUR_ALLIES', 2)

        elif fichier == 3:

            data = {"PENTA": {'Personne': 0, "Kazsc": 0}, "QUADRA": {'Personne': 0, "Kazsc": 0},
                    "NBGAMES": {'Personne': 0}, 'SOLOKILLS': {'Personne': 0}, 'DUREE_GAME': {'Personne': 0},
                    'WARDS_SCORE': {'Personne': 0}, 'WARDS_POSEES': {'Personne': 0}, 'WARDS_DETRUITES': {'Personne': 0},
                    'WARDS_PINKS': {'Personne': 0}, 'CS' : {'Personne' : 0},
                    "KILLS": {'Personne': 0}, 'DEATHS': {'Personne': 0}, 'ASSISTS': {'Personne': 0}}

            writeData(data, 'records3')

        await ctx.send(f'Records Page {str(fichier)} réinitialisé !')


    @cog_ext.cog_slash(name="records_list",
                       description="Voir les records détenues par les joueurs")
    async def records_list(self, ctx):

        current = 0

        fichier = loadData('records')

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
            'DEGATS_INFLIGES': ":dart:",
            "% DMG": ":magic_wand:",
            'DOUBLE': ":two:",
            'TRIPLE': ":three:",
            'QUADRA': ":four:",
            'PENTA': ":five:",
            'DUREE_GAME': ":timer:",
            'SPELLS_USED': ":gun:",
            'BUFFS_VOLEES': "<:PandaWow:732316840495415398>",
            'SPELLS_EVITES': ":white_check_mark:",
            'MUlTIKILL_1_SPELL': ":goal:",
            'SOLOKILLS': ":karate_uniform:",
            'CS_APRES_10_MIN': ":ghost:",
            'SERIES_DE_KILLS': ":crossed_swords:",
            'NB_SERIES_DE_KILLS': ":crossed_swords:",
            'DOMMAGES_TANK': ":shield:",
            'DOMMAGES_TANK%': ":shield:",
            'DOMMAGES_REDUITS': ":shield:",
            'DOMMAGES_TOWER': ":hook:",
            'GOLDS_GAGNES': ":euro:",
            'TOTAL_HEALS': ":sparkling_heart:",
            'HEALS_SUR_ALLIES': ":two_hearts:",
            'NBGAMES': ":star:",
            "KILLS_MOYENNE": ":dagger:",
            "DEATHS_MOYENNE": ":skull:",
            "ASSISTS_MOYENNE": ":crossed_swords:",
            'WARDS_MOYENNE': ":eye:",
        }

        response = ""

        embed1 = discord.Embed(title="Records (Page 1/3) :bar_chart:", colour=discord.Colour.blurple())

        for key, value in fichier.items():
            valeur = ""
            if key == "DEGATS_INFLIGES":
                valeur = "{:,}".format(value['Score']).replace(',', ' ').replace('.', ',')
            elif key == "DUREE_GAME":
                valeur = str(int(round(value['Score'], 0))).replace(".", "m")
            elif key == "KP" or key == "% DMG":
                valeur = str(value['Score']) + "%"
            else:
                valeur = str(value['Score'])
            embed1.add_field(name=str(emote[key]) + "" + key,
                             value="Records : __ " + valeur + " __ \n ** " + str(
                                 value['Joueur']) + " ** (" + str(value['Champion']) + ")")

        embed1.set_footer(text=f'Version {main.Var_version} by Tomlora')

        fichier2 = loadData('records2')

        embed2 = discord.Embed(title="Records (Page 2/3) :bar_chart:", colour=discord.Colour.blurple())

        for key, value in fichier2.items():
            valeur2 = ""
            if key == "GOLDS_GAGNES" or key == "DOMMAGES_TANK" or key == 'DOMMAGES_REDUITS' or key == "DOMMAGES_TOWER" or key == "TOTAL_HEALS" or key == "HEALS_SUR_ALLIES":
                valeur2 = "{:,}".format(value['Score']).replace(',', ' ').replace('.', ',')
            elif key == "DOMMAGES_TANK%":
                valeur2 = str(value['Score']) + "%"
            else:
                valeur2 = str(value['Score'])
            embed2.add_field(name=str(emote[key]) + "" + key,
                             value="Records : __ " + valeur2 + " __ \n ** " + str(
                                 value['Joueur']) + " ** (" + str(value['Champion']) + ")")

        embed2.set_footer(text=f'Version {main.Var_version} by Tomlora')

        embed3 = discord.Embed(title="Records Cumul & Moyenne (Page 3/3) :bar_chart: ")

        fichier3 = loadData('records3')

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
            for key in record3:
                joueur, value, nbgames = findrecord(df, key, False)

                if key == "NBGAMES" or key == "PENTA" or key == "QUADRA" or key == 'SOLOKILLS':
                    value = int(value)

                elif key == 'DUREE_GAME':
                    value = round(float(value), 2)
                    value = str(value).replace(".", "h")


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

        embed3.set_footer(text=f'Version {main.Var_version} by Tomlora')

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
                       description="Cumul des statistiques")
    async def pantheon(self, ctx):
        channel_answer = ctx.channel
        data = loadData('records3')

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
        df['DUREE_MOYENNE'] = np.where(df['NBGAMES'] > 0, df['DUREE_GAME'] / df['NBGAMES'], 0)
        
        df['DUREE_MOYENNE'] = round(df['DUREE_MOYENNE'] * 60, 2)
        df['WARDS_MOYENNE'] = round(df['WARDS_MOYENNE'], 2)

        buttons = [
            create_button(
                style=ButtonStyle.blue,
                label="KDA",
                custom_id="KDA",
            ),
            create_button(
                style=ButtonStyle.green,
                label="Vision",
                custom_id="VISION",
            ),
            create_button(
                style=ButtonStyle.blurple,
                label="CS",
                custom_id="CS",
            ),
        ]
        buttons2 = [
            create_button(
                style=ButtonStyle.red,
                label="KDA moyenne",
                custom_id="KDA moyenne",
            ),
            create_button(
                style=ButtonStyle.gray,
                label="Vision moyenne",
                custom_id="VISION moyenne",
            ),
            create_button(
                style=ButtonStyle.green,
                label="Temps de jeu",
                custom_id="GAMES",
            ),
        ]

        action_row = create_actionrow(*buttons)
        action_row2 = create_actionrow(*buttons2)

        fait_choix = await ctx.send(f' Quel stat cumulé veux-tu ?',
                                    components=[action_row, action_row2])

        def check(m):
            return m.author_id == ctx.author.id and m.origin_message.id == fait_choix.id

        button_ctx = await wait_for_component(self.bot, components=[action_row, action_row2], check=check)
        msg = button_ctx.custom_id

        await button_ctx.edit_origin(
            content=msg + " :", components=[])

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
            if msg == "KDA":
                variables = ['KILLS', 'DEATHS', 'ASSISTS']

                df['KDA'] = (df['KILLS'] + df['ASSISTS']) / df['DEATHS']
                df['KDA'] = round(df['KDA'],2)

                fig = figure_hist(variables, msg)

                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

                fig = px.pie(df, values='KDA', names='Joueurs', title='KDA')
                fig.update_traces(textinfo='value', textfont_size=20)
                fig.write_image('pie.png')
                await channel_answer.send(file=discord.File('pie.png'))
                os.remove('pie.png')


                await channel_answer.send(
                    f' __ Total : __ \n Kills : {int(df["KILLS"].sum())} \n Morts : {int(df["DEATHS"].sum())} \n Assists : {int(df["ASSISTS"].sum())}')

            elif msg == "VISION":
                variables = ['WARDS_POSEES', 'WARDS_DETRUITES', 'WARDS_PINKS']

                fig = figure_hist(variables, msg)
                
                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

                await channel_answer.send(
                    f' __ Total : __ \n Wards posées : {int(df["WARDS_POSEES"].sum())} \n Wards détruites : {int(df["WARDS_DETRUITES"].sum())} \n Pinks : {int(df["WARDS_PINKS"].sum())}')

            elif msg == "KDA moyenne":
                variables = ['KILLS_MOYENNE', 'DEATHS_MOYENNE', 'ASSISTS_MOYENNE']

                fig = figure_hist(variables, msg)

                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

            elif msg == "VISION moyenne":
                variables = ['WARDS_MOYENNE']

                fig = figure_hist(variables, msg)

                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

            elif msg == "CS":
                variables = ['CS']

                fig = figure_hist(variables, msg)

                fig.write_image('plot.png')
                await ctx.send(file=discord.File('plot.png'))
                os.remove('plot.png')

                await channel_answer.send(
                    f' __ Total : __ \n CS : {int(df["CS"].sum())}')

            elif msg == "GAMES":
                variables = ['NBGAMES', 'DUREE_GAME']
                              

                fig = figure_hist(variables, msg)

                fig.write_image('plot.png')
                await ctx.send('Durée des games exprimée en heures :')
                await channel_answer.send(file=discord.File('plot.png'))
                os.remove('plot.png')
                
                fig = px.pie(df, values='DUREE_MOYENNE', names='Joueurs', title='DUREE MOYENNE DES GAMES')
                fig.update_traces(textinfo='value', textfont_size=20)
                fig.write_image('pie.png')
                await ctx.send('Durée des games exprimée en minutes :')
                await channel_answer.send(file=discord.File('pie.png'))
                os.remove('pie.png')

            elif msg == "Cancel":
                await ctx.send('Cancel')

        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.send("Annulé")


def setup(bot):
    bot.add_cog(Recordslol(bot))