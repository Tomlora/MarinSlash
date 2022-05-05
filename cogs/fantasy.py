import discord
from discord.ext import commands


import main
import pandas as pd
import asyncio
from datetime import datetime
from fonctions.gestion_fichier import loadDataFL, loadDataRate, writeDataFL, writeDataRate
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice


# Paramètres

Nb_points = 50

Var_version = 1.0

# src : https://oracleselixir.com/tools/downloads
chemin = "FL/2022_LoL_esports_match_data_from_OraclesElixir_20220414.csv"
data = pd.read_csv(chemin)

year = 2022


# Modifier valeur dans une df df.loc[condition / colonne]
# df.loc[df['index'] == "tomlora", "wins"] = "334"



def liste_en_str(liste):
    str = ' | '.join(liste)
    return str


class Fantasy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(brief="DB Rito")
    async def loldb(self, ctx):
        await ctx.send('https://docs.google.com/spreadsheets/d/1Y7k5kQ2AegbuyiGwEPsa62e883FYVtHqr6UVut9RC4o/pubhtml#')

    @cog_ext.cog_slash(name="competition",
                       description="Stats d'un joueur pro sur la saison",
                       options=[create_option(name="competition", description= "Quelle compétition ?", option_type=3, required=True),
                                create_option(name="split", description="Spring ou summer ?", option_type=3, required=True, choices=[
                                    create_choice(name="spring", value="Spring"),
                                    create_choice(name="summer", value="Summer")]),
                                create_option(name="joueur", description="Nom du joueur ?", option_type=3, required=True)])
    async def competition(self, ctx, competition, split, *, joueur):
        try:
            competition = competition.upper()


            # On trie par competition
            data_joueurs = data[data['league'] == competition]

            #On trie par split
            data_joueurs = data_joueurs[data_joueurs['split'] == split]

            #On trie par année
            data_joueurs = data_joueurs[data_joueurs['year'] == year]

            # if LCS, on retire le Lock-in

            if competition == 'LCS':
                data_joueurs = data_joueurs[data_joueurs['playoffs'] == 0]

            # On trie sur le joueur qu'on a visé
            data_joueurs_text = data_joueurs[data_joueurs['playername'] == joueur]

            data_joueurs_cumul = data_joueurs_text.groupby(['playername']).sum()  # on regroupe par joueurs pour avoir ses stats

            position = data_joueurs_text['position'].iloc[0]
            teamname = data_joueurs_text['teamname'].iloc[0]
            kills = data_joueurs_cumul['kills'][0]
            deaths = data_joueurs_cumul['deaths'][0]
            assists = data_joueurs_cumul['assists'][0]
            cs = int(data_joueurs_cumul['total cs'][0])
            double = int(data_joueurs_cumul['doublekills'][0])
            triple = int(data_joueurs_cumul['triplekills'][0])
            quadra = int(data_joueurs_cumul['quadrakills'][0])
            penta = int(data_joueurs_cumul['pentakills'][0])
            fb = int(data_joueurs_cumul['firstbloodkill'][0])
            fb_encaisse = int(data_joueurs_cumul['firstbloodvictim'][0])

            if deaths != 0:
                kda = round((kills + assists)/deaths,2)
            else:
                kda = "Perfect KDA"


            embed = discord.Embed(
                title="**" + str(joueur).upper() + "**", color=discord.Colour.blue())
            embed.add_field(name="Profil", value="Equipe : " + str(teamname) + " \n Position : " + str(position),
                            inline=False)
            embed.add_field(name="Statistiques " + str(split) + " " + str(year),
                            value="KDA : " + str(kda) + " \n Kills : " + str(kills) + " \n Deaths : " + str(deaths) + " \n Assists : " + str(
                                assists) + "\n CS : " + str(cs), inline=False)
            embed.add_field(name="First Blood",
                            value="First blood effectués : " + str(fb) + " \n First blood subis : " + str(fb_encaisse),
                            inline=False)
            embed.add_field(name="Details Kills",
                            value="Double : " + str(double) + " \n Triple : " + str(triple) + " \n Quadra : " + str(
                                quadra) + "\n Penta : " + str(penta),
                            inline=False)

            embed.set_footer(text=f'Version {main.Var_version} by Tomlora')
            # returning the message for discord
            await ctx.send(embed=embed)
        except:
            await ctx.send(
                "Erreur, le format est soit mauvais, soit non-respect des majuscules. Exemple : \n  > /competition LCS Spring Bwipo")


    @cog_ext.cog_slash(name="liste_joueurs",
                       description="Stats d'un joueur pro sur la saison",
                       options=[create_option(name="competition", description= "Quelle compétition ? Si non renseigné : affiche LEC/LCS/LFL", option_type=3, required=False)])
    async def liste_joueurs(self, ctx, competition = None):

        if competition is None:
            competition = ['LEC', 'LCS', 'LFL']
        else:
            competition = [competition]



        for value in competition:

            embed = discord.Embed(
                title=str(value), color=discord.Colour.blue())

            data_joueurs = data[data['league'] == value]

            liste_equipe = data_joueurs['teamname'].unique()

            for equipe in liste_equipe:

                data_equipe = data_joueurs[data_joueurs['teamname'] == equipe]

                liste_joueur = data_equipe['playername'].dropna().unique()

                liste_joueur = liste_en_str(liste_joueur)

                embed.add_field(name=str(equipe), value=str(liste_joueur) + "\n", inline=False)

            await ctx.send(embed=embed)

    @cog_ext.cog_slash(name="competition_game",
                       description="Stats d'un joueur pro sur une game",
                       options=[create_option(name="competition", description= "Quelle compétition ?", option_type=3, required=True),
                                create_option(name="split", description="Spring ou summer ?", option_type=3, required=True, choices=[
                                    create_choice(name="spring", value="Spring"),
                                    create_choice(name="summer", value="Summer")]),
                                create_option(name="game", description="Quelle game ? La dernière étant 0", option_type=4, required=True),
                                create_option(name="joueur", description="Nom du joueur ?", option_type=3, required=True)])
    async def competition_game(self, ctx, competition, split, game, joueur):
        competition = competition.upper()

        # def check(m):
        #     return m.content == "y" and m.channel == channel

        def check(m):
            return m.content in ['y', 'n'] and m.channel == channel


        #On trie par competition
        data_joueurs = data[data['league'] == competition]

        #On trie par split
        data_joueurs = data_joueurs[data_joueurs['split'] == split]

        #On trie par année
        data_joueurs = data_joueurs[data_joueurs['year'] == year]

        # if LCS, on retire le Lock-in

        if competition == 'LCS':
            data_joueurs = data_joueurs[data_joueurs['playoffs'] == 0]

        data_joueurs_text = data_joueurs[data_joueurs['playername'] == joueur] #On trie sur le joueur visé

        data_joueurs_text = data_joueurs_text.iloc[int(game)] #On trie sur la game visée

        # data_joueurs_nombre = data_joueurs_text.groupby(['playername']).sum()  # on regroupe par joueurs

        date = data_joueurs_text['date'] #on isole la date
        date = date[:-9]  # on supprime l'heure
        date = datetime.strptime(date, "%Y-%m-%d")  # on met au format date
        date = str(date.strftime('%d-%m-%Y'))  # on change le format de la date

        await ctx.send(f' Souhaites-tu les stats de {joueur} durant sa game du {date} ? (y/n)')
        channel = ctx.message.channel
        global msg
        try:
            msg = await self.bot.wait_for('message', timeout=10, check=check)

            if msg.content == 'y':
                position = data_joueurs_text['position']
                teamname = data_joueurs_text['teamname']
                champion = data_joueurs_text['champion']

                kills = data_joueurs_text['kills']
                deaths = data_joueurs_text['deaths']
                assists = data_joueurs_text['assists']
                cs = int(data_joueurs_text['total cs'])
                double = int(data_joueurs_text['doublekills'])
                triple = int(data_joueurs_text['triplekills'])
                quadra = int(data_joueurs_text['quadrakills'])
                penta = int(data_joueurs_text['pentakills'])
                fb = int(data_joueurs_text['firstbloodkill'])
                fb_encaisse = int(data_joueurs_text['firstbloodvictim'])

                if deaths !=0:
                    kda = round((kills + assists)/deaths,2)
                else:
                    kda = "Perfect KDA"

                embed = discord.Embed(
                    title="**" + str(joueur).upper() + "**", color=discord.Colour.blue())
                embed.add_field(name="Profil", value="Equipe : " + str(teamname) + " \n Position : " + str(
                    position) + "\n Champion : " + str(champion), inline=False)
                embed.add_field(
                    name="Statistiques " + str(split) + " " + str(year) + " Game " + str(game) + " (" + str(date) + ")",
                    value="KDA : " + str(kda) + " \n Kills : " + str(kills) + " \n Deaths : " + str(deaths) + " \n Assists : " + str(
                        assists) + "\n CS : " + str(cs), inline=False)
                embed.add_field(name="First Blood",
                                value="First blood effectués : " + str(fb) + " \n First blood subis : " + str(
                                    fb_encaisse), inline=False)
                embed.add_field(name="Details Kills",
                                value="Double : " + str(double) + " \n Triple : " + str(triple) + " \n Quadra : " + str(
                                    quadra) + "\n Penta : " + str(penta),
                                inline=False)

                embed.set_footer(text=f'Version {main.Var_version} by Tomlora')
                # returning the message for discord
                await ctx.send(embed=embed)

            elif msg.content == 'n':
                await ctx.send('Annulé')

        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.send("Annulé")




    @commands.command()
    @main.isOwner2()
    async def new_game(self, ctx):

        try:
            data = loadDataFL()
            df = pd.DataFrame.from_dict(data, orient="index")

            df = df.transpose()

            print(df)

        except Exception as e:
            await ctx.send(str(e))
            
    

    @cog_ext.cog_slash(name="add_fantasy", description="Test")
    @main.isOwner2_slash()
    async def add_fantasy(self, ctx):
        user = ""
        user = str(ctx.author)
        data = loadDataFL()
        data[user] = {'Points' : Nb_points, 1:{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                      2:{'RGE/MSF' : ['nan', 0], 'BDS/XL' : ['nan', 0], 'SK/MAD' : ['nan', 0], 'G2/AST' : ['nan', 0], 'VIT/FNC' : ['nan', 0]}}
        writeDataFL(data)
        await ctx.send(f'Le joueur {user} a été ajouté !')
        
    
    @cog_ext.cog_slash(name="bet_fantasy",description="Test")
    @main.isOwner2_slash()
    async def bet_fantasy(self, ctx):
        user = str(ctx.author)        
        data = loadDataFL()
        print(data) # data entière
        print('-------')
        print(data.keys()) #liste des joueurs
        print('-------')
        print(data[user]['Points']) # points du joueur
        print('-------')
        print(data[user]) # points + ensemble des paris du joueur
        print('-------')
        print(data[user][1]) # ensemble des paris du joueur pour la semaine 1
        print('-------')
        print(data[user][1].keys()) # match de la semaine 1
        data[user][1]['VIT/MAD'] = ['VIT', 5]
        writeDataFL(data)
        await ctx.send('Done')
        
    @cog_ext.cog_slash(name="maj_cote",description="Test")
    @main.isOwner2_slash()
    async def maj_cote(self, ctx):
        data = {1:{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                2:{'RGE/MSF' : [1, 1.5], 'BDS/XL' : [1, 1.5], 'SK/MAD' : [1, 1.5], 'G2/AST' : [1, 1.5], 'VIT/FNC' : [1, 1.5]}}
        writeDataRate(data)
        
    @cog_ext.cog_slash(name="cote",description="Test")
    @main.isOwner2_slash()
    async def cote(self, ctx):
        data = loadDataRate()
        semaine = 1
        response = ""
        
        for key, value in data[semaine].items():
            response += str(key) + " : " + str(value) + "\n"
        
        embed = discord.Embed(title=f"Côte des matchs Semaine {semaine} ", description=response, colour=discord.Colour.blurple())
            
        await ctx.send(embed=embed)
            
        
    @cog_ext.cog_slash(name="list_fantasy",
                       description="Test")
    @main.isOwner2_slash()
    async def list_fantasy(self, ctx):
        
        data = loadDataFL()
        response = ""

        for key, value in data.items():
            response += key.upper() + " : " + str(data[key]['Points'])  + " points , "

        # response = response[:-2]
        embed = discord.Embed(title="Live feed list", description=response, colour=discord.Colour.blurple())

        await ctx.send(embed=embed)
        
    @cog_ext.cog_slash(name="match_of_the_week",
                       description="Test")
    @main.isOwner2_slash()
    async def match_of_the_week(self, ctx):
        user = ""
        user = str(ctx.author)
        
        data = loadDataFL()
        match = ""
        
        for key in data[user][1].keys():
            match = match + key + " , "
        
        await ctx.send(str(match))
        


def setup(bot):
    bot.add_cog(Fantasy(bot))
