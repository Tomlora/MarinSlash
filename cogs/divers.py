import os

import matplotlib.pyplot as plt

import numpy as np
import plotly.express as px
from discord.ext import commands

from discord_slash.utils.manage_components import *
from discord_slash import cog_ext, SlashContext
from fonctions.gestion_fichier import loadData
from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd

import main
from fonctions.date import jour_de_la_semaine
from datetime import datetime
import time




chan_general = 768637526176432158


class Divers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash(name="hello", description="Saluer le bot")
    async def hello(self, ctx : SlashContext):
        buttons = [
            create_button(
                style=ButtonStyle.blue,
                label="Marin",
                custom_id="Marin",
                emoji="😂"
            ),
            create_button(
                style=ButtonStyle.green,
                label="Tomlora",
                custom_id="non"
            )
        ]
        action_row = create_actionrow(*buttons)
        fait_choix = await ctx.send("Faites votre choix !", components=[action_row])

        def check(m):
            return m.author_id == ctx.author.id and m.origin_message.id == fait_choix.id

        button_ctx = await wait_for_component(self.bot, components=action_row, check=check)
        if button_ctx.custom_id == "Marin":
            await button_ctx.edit_origin(content="Bravo !")
            print(button_ctx.custom_id)
        else:
            await button_ctx.edit_origin(content="...")
            

    @cog_ext.cog_slash(name="quiz", description="Reponds au quizz")
    async def quiz(self, ctx : SlashContext):
        select = create_select(
            options=[
                create_select_option("Dawn", value="1", emoji="😂"),
                create_select_option("Exorblue", value="2", emoji="😏"),
                create_select_option("Tomlora", value="3", emoji="💛"),
                create_select_option("Ylarabka", value="4", emoji="🦊"),
                create_select_option("Djingo le egay", value="5", emoji="💚")
            ],
            placeholder="Choisis un emoji...",
            min_values=1,
            max_values=1
        )
        fait_choix = await ctx.send("Qui est le meilleur joueur ici ?",
                                    components=[create_actionrow(select)])

        def check(m):
            return m.author_id == ctx.author.id and m.origin_message.id == fait_choix.id

        choice_ctx = await wait_for_component(self.bot, components=select, check=check)

        if choice_ctx.values[0] == "3":
            await choice_ctx.send("Bonne réponse ! 🦊")
        else:
            await choice_ctx.send("Mauvaise réponse... 😒")

    @cog_ext.cog_slash(name="ping", description="Latence du bot")
    async def ping(self, ctx : SlashContext):
        await ctx.send(
            f"pong \n Latence : `{round(float(self.bot.latency), 3)}` ms")
      
    @cog_ext.cog_slash(name="serverInfo", description="Infos général du serveur")
    async def serverInfo(self, ctx):
        server = ctx.guild
        numberOfTextChannels = len(server.text_channels)
        numberOfVoiceChannels = len(server.voice_channels)
        serverDescription = server.description
        numberOfPerson = server.member_count
        serverName = server.name
        message = f"Le serveur **{serverName}** contient *{numberOfPerson}* personnes ! \nLa description du serveur est {serverDescription}. \nCe serveur possède {numberOfTextChannels} salons écrit et {numberOfVoiceChannels} salon vocaux."
        await ctx.send(message)
        
    @cog_ext.cog_slash(name="graph_test", description="Latence du bot")
    @main.isOwner2_slash()
    async def graph_test(self, ctx, test):
        numero = str(test)

        x_labels = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
        votes_list = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']

        if numero == str(1):
            fig = plt.figure()
            ax = fig.add_axes([0, 0, 1, 1])
            ax.bar(x_labels, votes_list)
            # plt.show()

            plt.savefig(fname='plot')

            await ctx.send(file=discord.File('plot.png'))
            os.remove('plot.png')



        elif numero == str(2):

            xvals = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
            yvals = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']

            plt.clf()
            xList = []
            yList = []
            for varx in xvals:
                xList.append(varx)
            for vary in yvals:
                yList.append(vary)
            xList.sort()
            yList.sort()
            x = np.array(xList)
            y = np.array(yList)
            fig, ax = plt.subplots()
            ax.set(xlim=(1, 10), ylim=(1, 10))
            ax.plot(x, y)
            arr = np.vstack((x, y))
            plt.plot(arr[0], arr[1])
            plt.title(f'Graph')
            plt.savefig(fname='plot')
            await ctx.send(file=discord.File('plot.png'))
            os.remove('plot.png')

        elif numero == str(3):

            x = [1, 2, 2, 3, 4, 4, 4, 4, 4, 5, 5]
            plt.hist(x, range=(0, 5), bins=5, color='yellow',
                     edgecolor='red')
            plt.xlabel('valeurs')
            plt.ylabel('nombres')
            plt.title('Exemple d\' histogramme simple')

            plt.savefig(fname='plot')
            await ctx.send(file=discord.File('plot.png'))
            os.remove('plot.png')

        elif numero == str(4):
            df = px.data.tips()
            fig = px.pie(df, values='tip', names='day')
            # fig.show()
            fig.write_image('plot.png')
            await ctx.send(file=discord.File('plot.png'))
            os.remove('plot.png')
            
    @commands.command()
    async def img(self, ctx, *, img:str):
        await ctx.send(file=discord.File(f'./img/{img}.jpg'))  
        
        
    @cog_ext.cog_slash(name="test", description="Reponds au quizz")
    async def test(self, ctx):
        
        await ctx.send(f'{ctx.author.id}')
        await ctx.send(f'{ctx.author.name}')
        


def setup(bot):
    bot.add_cog(Divers(bot))
