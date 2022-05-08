import discord
from discord.ext import commands, tasks

import datetime
import calendar
import main
import pandas as pd
import asyncio
from datetime import datetime
from fonctions.gestion_fichier import loadDataFL, loadDataRate, writeDataFL, writeDataRate
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice

# Certaines cmd devraient être réservés en message privé (prendre exemple sur match_of_the_week)
# Comment ajouter LEC/LFL/LCS ?
# https://lol.fandom.com/wiki/Special:RunQuery/MatchCalendarExport?MCE%5B1%5D=LEC%2F2022+Season%2FSpring+Season&_run= s'aider de ça -> transformer en fichier CSV (schedule.csv)

# Paramètres

settings_game = loadDataFL('settings')
Nb_points = settings_game['Nb_points']
semaine = settings_game['semaine']


# src : https://oracleselixir.com/tools/downloads
chemin = "FL/2022_LoL_esports_match_data_from_OraclesElixir_20220414.csv"
data = pd.read_csv(chemin)


# Utiliser les variables jour pour les alarmes.
# Utiliser ces variables pour empecher les paris d'une compétition lorsque nous sommes dans un jour de match
jour_de_match = {'LEC': ['Friday', 'Saturday'],
                 'LCS': ['Saturday', 'Sunday'],
                 'LFL': ['Tuesday', 'Wednesday'],
                 'MSI': ['Tuesday', 'Wednesday']}



year = 2022


# Modifier valeur dans une df df.loc[condition / colonne]
# df.loc[df['index'] == "tomlora", "wins"] = "334"



def liste_en_str(liste):
    str = ' | '.join(liste)
    return str


class Fantasy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminder.start()
        
# ------------------------------------------------- Alarm

    roleLEC = "<@&956612773868077106>"
    roleLFL = "<@&956613314731991100>"
    roleLCS = "<@&956613191956324384>"
    messageLFL = "La LFL va commencer sur OTP ! " + roleLFL + "\n https://www.twitch.tv/otplol_"
    messageEUM = "Les EUM vont commencer sur OTP ! " + roleLFL + "\n https://www.twitch.tv/otplol_"
    messageLCS = "Les LCS vont commencer sur LCS ! " + roleLCS + "\n https://www.twitch.tv/lcs"
    messageLEC = "La LEC va commencer sur OTP/LEC ! " + roleLEC + "\n https://www.twitch.tv/lec  \n https://www.twitch.tv/otplol_"
    messageMSI = "Le MSI va commencer sur OTP/LEC ! " + roleLEC + " " + roleLCS + "\n https://www.twitch.tv/otplol_"
    
    

    def findDay(self, date):
        born = datetime.strptime(date, '%d %m %Y').weekday()
        return calendar.day_name[born]

    def alarm(self, h, m, message):
        currentHour = str(datetime.datetime.now().hour)
        currentMinute = str(datetime.datetime.now().minute)
        if currentHour == str(h) and currentMinute == str(m):
            channel = self.bot.get_channel(main.chan_lol)
            return channel.send(message)
        else:
            return False

    @tasks.loop(minutes=1, count=None)
    async def reminder(self):
        
        currentHour = str(datetime.now().hour)
        currentMonth = str(datetime.now().month)
        currentYear = str(datetime.now().year)
        currentDay = str(datetime.now().day)
        currentMinute = str(datetime.now().minute)
        currentJour = str(self.findDay(str(currentDay + ' ' + currentMonth + " " + currentYear)))


        if self.bot.get_channel(main.chan_lol):
            if currentJour in jour_de_match['MSI'] and currentHour == str(9):
                try:
                    await self.alarm(9, 55, self.messageEUM)
                except:
                    return False


    @cog_ext.cog_slash(name="alarm_lol",
                       description="Permet d'être ping pour les alarmes",
                       options=[create_option(name="competition", description="Quelle alarme ?", option_type=3, required=True, choices=[
                                    create_choice(name="LEC", value="LEC"),
                                    create_choice(name='Main Kayn', value='Main Kayn'),
                                    create_choice(name='LCS', value='LCS'),
                                    create_choice(name='LFL', value='LFL')])])
                       
    async def alarm_lol(self, ctx, competition: str):

        liste = ['LEC', 'Main Kayn', 'LCS', 'LFL']
        user = ctx.author
        role = discord.utils.get(ctx.guild.roles, name=competition)
        if competition in liste:
            if role in user.roles:
                await user.remove_roles(role)
                await ctx.send(f' Le rang {role} a été retiré !')
            else:
                await user.add_roles(role)
                await ctx.send(f'Le rang {role} a été ajouté !')
        else:
            await ctx.send(f"Le rôle {competition} n'existe pas ou tu n'as pas les droits nécessaires")

    @alarm_lol.error
    async def info_error_alarm(self, ctx, error):
        if isinstance(error, commands.CommandError):
            await ctx.send(f"La competition n'a pas ete precisée : Tu as le choix entre LEC / LFL / LCS / Main Kayn")
        
    @commands.command(brief="DB Rito")
    async def loldb(self, ctx):
        await ctx.send('https://docs.google.com/spreadsheets/d/1Y7k5kQ2AegbuyiGwEPsa62e883FYVtHqr6UVut9RC4o/pubhtml#')
        
    @cog_ext.cog_slash(name="schedule", description="schedule")
    async def schedule(self, ctx):
        schedule = "FL/schedule.csv"
        schedule = pd.read_csv(schedule)
        subject = schedule['Subject'].str.split(pat=" ", expand=True)
        date = schedule['Start Date'].str.split(pat="-", expand=True)
        schedule[['Competition', 'Année', 'Split', '-', 'Equipe1', 'vs', 'Equipe2']] = subject
        schedule[['Année', 'Mois', 'Jour']] = date
        schedule[['Année', 'Mois', 'Jour']] = schedule[['Année', 'Mois', 'Jour']].astype('int64')
        schedule['match'] = schedule['Equipe1'] + "/" + schedule['Equipe2']
        schedule.drop(['Subject', '-', 'vs', 'Start Date'], axis=1, inplace=True)
        schedule = schedule[schedule['Mois'] == 1]
        dict_schedule = schedule[['Mois', 'Competition', 'match', 'equipe gagnante', 'points_mises']].to_dict('index')

        print(dict_schedule)


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
        # nan => vainqueur parié, 0 => points pariés
        data[user] = {'Points' : Nb_points, 
                      1:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      2:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      3:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      4:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      5:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      6:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      7:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      8:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      9:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      10:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      11:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      12:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      13:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      14:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      15:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      16:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      17:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}},
                      18:{'LEC': {'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LFL':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]},
                         'LCS':{'VIT/MAD' : ['nan', 0], 'SK/RGE' : ['nan', 0], 'G2/XL' : ['nan', 0], 'MSF/AST' : ['nan', 0], 'BDS/FNC' : ['nan', 0]}}}
        writeDataFL(data)
        await ctx.send(f'Le joueur {user} a été ajouté !')
        
        
    @cog_ext.cog_slash(name="bet", description="test",                        
                       options=[create_option(name="competition", description="Quel compétition", option_type=3, required=True, choices=[
                                    create_choice(name="LEC", value="LEC"),
                                    create_choice(name='LFL', value='LFL'),
                                    create_choice(name='LCS', value='LCS')])])
    @main.isOwner2_slash()
    async def bet(self, ctx, competition='LEC'):
        user = str(ctx.author)
        # settings
        semaine = loadDataFL('settings')['semaine']
        
        await ctx.send(f'Pari pour la semaine {str(semaine)}')
        
        #data
        data = loadDataFL()
        
        # rate
        rate = loadDataRate()
        
        channel = ctx.channel
        author = ctx.author
        
        def check(m):
            return m.author == author and m.channel == channel
        
        for match in data[user][semaine][competition].keys():
            cote = rate[semaine][match]
            await channel.send(f' Quel victoire pour {match} {cote} ?')

            try:
                msg = await self.bot.wait_for('message', timeout=60, check=check)
                await channel.send('Score enregistré!'.format(msg))
                msg = str(msg.content).split()
                equipe_gagnante = msg[0]
                points_mises = int(msg[1])
                data[user]['Points'] = data[user]['Points'] - points_mises
                points_user = data[user]['Points']
                data[user][semaine][competition][match] = [equipe_gagnante, points_mises]
                await channel.send(f'Il te reste {points_user} points à miser ')
            except asyncio.TimeoutError:
                await msg.delete()
                await ctx.send("Annulé")
        writeDataFL(data)
        await channel.send(f'Enregistré pour les matchs de la semaine {semaine}')
        
    @cog_ext.cog_slash(name="my_bet", description="test")
    async def my_bet(self, ctx):
        user = str(ctx.author)
        semaine = loadDataFL('settings')['semaine']
        data = loadDataFL()
        rate = loadDataRate()

        
        embed = discord.Embed(title=f"Pari du joueur {user} pour la semaine {str(semaine)}", color=discord.Color.gold())
        
        for competition in ['LEC', 'LFL', 'LCS']:
        
            for match, pari in data[user][semaine][competition].items():
                equipe_gagnante = pari[0]
                points_mises = pari[1]
                embed.add_field(name=match + " " + str(rate[semaine][match]),
                                    value=f"Equipe misée : {equipe_gagnante} | Points misés : {points_mises}", inline=True)
            
        await ctx.send(embed=embed)
            
    
        
    
    @cog_ext.cog_slash(name="help_fantasy",description="Test")
    @main.isOwner2_slash()
    async def help_fantasy(self, ctx):
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
        print(data[user][1]) # ensemble des paris du joueur pour la semaine 1, quelque soit la compétition
        print('-------')
        print(data[user][1]['LEC'].keys()) # match de la semaine 1 en LEC
        data[user][1]['LEC']['VIT/MAD'] = ['VIT', 5] # proposer vita gagnant et 5 pts
        writeDataFL(data)
        await ctx.send('Done')
        
    @cog_ext.cog_slash(name="maj_cote",description="Test")
    @main.isOwner2_slash()
    async def maj_cote(self, ctx):
        # [cote vita, cote mad]
        data = {1:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                2:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                3:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                4:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                5:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                6:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                7:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                8:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                9:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                10:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                11:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                12:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                13:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                14:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                15:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                16:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                17:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}},
                18:{'LEC':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LFL':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]},
                   'LCS':{'VIT/MAD' : [1, 1.5], 'SK/RGE' : [1, 1.5], 'G2/XL' : [1, 1.5], 'MSF/AST' : [1, 1.5], 'BDS/FNC' : [1, 1.5]}}}

        writeDataRate(data)
        
        
        await ctx.send('Fait !')
        
    @cog_ext.cog_slash(name="cote",
                       description="Test",
                    )
    @main.isOwner2_slash()
    async def cote(self, ctx):
        data = loadDataRate()
        settings = loadDataFL('settings')
        semaine = settings['semaine']
        
        response = ""
        
        for competition in ['LEC', 'LFL', 'LCS']:
 
            for key, value in data[semaine][competition].items():
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
        embed = discord.Embed(title="Liste joueurs", description=response, colour=discord.Colour.blurple())

        await ctx.send(embed=embed)
        
    @cog_ext.cog_slash(name="match_of_the_week", description="Test")
    @commands.dm_only()
    async def match_of_the_week(self, ctx):
        user = ""
        user = str(ctx.author)
        
        settings = loadDataFL('settings')
        semaine = settings['semaine']
        competition = 'LEC'
        
        data = loadDataFL()
        match = ""
        
        for key in data[user][semaine][competition].keys():
            match = match + key + " , "
        
        await ctx.send(str(match))
        
    @cog_ext.cog_slash(name="settings",
                       description="Test")
    @main.isOwner2_slash()
    async def settings(self, ctx):
        settings = {'Nb_points': 50,
                    'semaine': 1}
        writeDataFL(settings, 'settings')
        await ctx.send('Fait !')
        
    @match_of_the_week.error
    async def match_of_the_week_error(self, ctx, error):
        if isinstance(error, commands.PrivateMessageOnly):
            await ctx.send("Cette commande n'est activée qu'en message privé")
            

        


def setup(bot):
    bot.add_cog(Fantasy(bot))
