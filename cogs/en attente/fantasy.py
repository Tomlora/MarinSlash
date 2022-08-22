import discord
from discord.ext import commands, tasks

import calendar

import main
import pandas as pd
import numpy as np
import asyncio
from datetime import datetime
from fonctions.date import jour_de_la_semaine, heure_actuelle
from fonctions.gestion_fichier import loadDataFL, loadDataRate, writeDataFL, writeDataRate
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice
import os

from fonctions.gestion_bdd import lire_bdd, sauvegarde_bdd
from fonctions.gestion_base_oracle import loaddata_oracle, rechargement_data_oracle
from fonctions.date import alarm, jour_de_la_semaine, date_du_jour

import dataframe_image as dfi


# Certaines cmd devraient être réservés en message privé (prendre exemple sur match_of_the_week)

# https://lol.fandom.com/wiki/Special:RunQuery/MatchCalendarExport?MCE%5B1%5D=LEC%2F2022+Season%2FSpring+Season&_run= s'aider de ça -> transformer en fichier CSV (schedule.csv)

# Paramètres

settings_game = loadDataFL('settings')
Nb_points = settings_game['Nb_points']


# src : https://oracleselixir.com/tools/downloads



# Utiliser les variables jour pour les alarmes.
# Utiliser ces variables pour empecher les paris d'une compétition lorsque nous sommes dans un jour de match
jour_de_match = {'LEC': ['Friday', 'Saturday'],
                 'LCS': ['Saturday', 'Sunday'],
                 'LFL': ['Wednesday', 'Thursday']}





year = 2022


# Modifier valeur dans une df df.loc[condition / colonne]
# df.loc[df['index'] == "tomlora", "wins"] = "334"



def liste_en_str(liste):
    str = ' | '.join(liste)
    return str

def schedule():
        ecart_lec = 1
        ecart_lfl = 21
        ecart_lcs = 4
        schedule = "FL/schedule.csv"
        schedule = pd.read_csv(schedule)
        schedule['Start Date'] = pd.to_datetime(schedule['Start Date'])
        schedule['Week'] = schedule['Start Date'].dt.isocalendar().week
        schedule['Jour'] = schedule['Start Date'].dt.day
        schedule['Année'] = schedule['Start Date'].dt.year
        schedule['Mois'] = schedule['Start Date'].dt.month
        subject = schedule['Subject'].str.split(pat=" ", expand=True)
        schedule[['Competition', 'Année', 'Split', '-', 'Equipe1', 'vs', 'Equipe2']] = subject
        schedule['match'] = schedule['Equipe1'] + "/" + schedule['Equipe2']
        schedule.drop(['Subject', '-', 'vs', 'Start Date'], axis=1, inplace=True)
        
        schedule['Week'] = np.where(schedule['Competition'] == 'LEC', schedule['Week'] - ecart_lec, schedule['Week'])
        schedule['Week'] = np.where(schedule['Competition'] == 'LCS', schedule['Week'] - ecart_lcs, schedule['Week'])
        schedule['Week'] = np.where(schedule['Competition'] == 'LFL', schedule['Week'] - ecart_lfl, schedule['Week'])
        
        schedule['Start Time'] = pd.to_datetime(schedule['Start Time'])
        schedule['Heures'] = schedule['Start Time'].dt.hour
        schedule['minutes'] = schedule['Start Time'].dt.minute
        
        return schedule
    



class Fantasy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminder.start()
        
# ------------------------------------------------- Alarm


    
    @tasks.loop(minutes=1, count=None)
    async def reminder(self):
        channel = self.bot.get_channel(main.chan_lol)

        if channel: # si le channel est disponible
            data_schedule = schedule()
            jour = datetime.now().day
            month = datetime.now().month
            heure_now, minutes_now = heure_actuelle()
            data_match = data_schedule[(data_schedule['Heures'] == heure_now) & (data_schedule['Jour'] == jour) & (data_schedule['Mois'] == month) & (data_schedule['minutes'] == minutes_now)]

            if not data_match.empty: # si la data n'est pas vide, il y a un match !
                role = {'LEC' : "<@&956612773868077106>", 'LFL' : "<@&956613314731991100>", "LCS" : "<@&956613191956324384>"}
    
                msg = {'LFL' : "https://www.twitch.tv/otplol_",
                    'LCS' : "https://www.twitch.tv/lcs",
                    'LEC' : "https://www.twitch.tv/lec  \n https://www.twitch.tv/otplol_"}
                competition = data_match['Competition'].iloc[0]
                equipe1 = data_match['Equipe1'].iloc[0]
                equipe2 = data_match['Equipe2'].iloc[0]
                heure = data_match['Heures'].iloc[0]
                minutes = data_match['minutes'].iloc[0]
                
                if minutes == 0:  # pas besoin d'afficher les minutes              
                    msg = await channel.send(f'Le match {equipe1} / {equipe2} en {competition} est prévue à {heure}H. \n {msg[competition]}')
                    await msg.edit(suppress=True) # supprime l'embed généré par l'url
                else:
                    msg = await channel.send(f'Le match {equipe1} / {equipe2} en {competition} est prévue à {heure}H{minutes}. \n {msg[competition]}')
                    await msg.edit(suppress=True) # supprime l'embed généré par l'url
            else:
                pass                        
    
    @cog_ext.cog_slash(name="schedule_xl",
                       description="Available only for Tomlora")
    @main.isOwner2_slash()
    async def schedule_xl(self,ctx):
        data = schedule()
        data.to_excel('FL/schedule_modif.xlsx')
        await ctx.send('Done !')
                
    


    # @cog_ext.cog_slash(name="alarm_lol",
    #                    description="Permet d'être ping pour les alarmes",
    #                    options=[create_option(name="competition", description="Quelle alarme ?", option_type=3, required=True, choices=[
    #                                 create_choice(name="LEC", value="LEC"),
    #                                 create_choice(name='Main Kayn', value='Main Kayn'),
    #                                 create_choice(name='LCS', value='LCS'),
    #                                 create_choice(name='LFL', value='LFL')])])
                       
    # async def alarm_lol(self, ctx, competition: str):

    #     liste = ['LEC', 'Main Kayn', 'LCS', 'LFL']
    #     user = ctx.author
    #     role = discord.utils.get(ctx.guild.roles, name=competition)
    #     if competition in liste:
    #         if role in user.roles:
    #             await user.remove_roles(role)
    #             await ctx.send(f' Le rang {role} a été retiré !')
    #         else:
    #             await user.add_roles(role)
    #             await ctx.send(f'Le rang {role} a été ajouté !')
    #     else:
    #         await ctx.send(f"Le rôle {competition} n'existe pas ou tu n'as pas les droits nécessaires")

    # @alarm_lol.error
    # async def info_error_alarm(self, ctx, error):
    #     if isinstance(error, commands.CommandError):
    #         await ctx.send(f"La competition n'a pas ete precisée : Tu as le choix entre LEC / LFL / LCS / Main Kayn")
        
    @commands.command(brief="DB Rito")
    async def loldb(self, ctx):
        await ctx.send('https://docs.google.com/spreadsheets/d/1Y7k5kQ2AegbuyiGwEPsa62e883FYVtHqr6UVut9RC4o/pubhtml#')
        
    @cog_ext.cog_slash(name="schedule_test", description="schedule")
    async def schedule_test(self, ctx):
        df = schedule()
        print(df)
        op1 = df['Equipe1'].values
        op2 = df['Equipe2'].values
        print(op1)
        print(op2)
        print(op1[1])

        
    
    @cog_ext.cog_slash(name="liste_joueurs",
                       description="Liste des joueurs d'une compétition",
                       options=[create_option(name="competition", description= "Quelle compétition ? Si non renseigné : affiche LEC/LCS/LFL", option_type=3, required=False),
                                create_option(name="split", description="Spring ou summer ?", option_type=3, required=False, choices=[
                                    create_choice(name="spring", value="Spring"),
                                    create_choice(name="summer", value="Summer")])])
    async def liste_joueurs(self, ctx, competition = None, split="Summer"):
        
        await ctx.defer(hidden=False)
        
        
        data_oracle = loaddata_oracle()

        if competition is None:
            competition = ['LEC', 'LCS', 'LFL']
        else:
            competition = [competition]



        for value in competition:

            embed = discord.Embed(
                title=str(value), color=discord.Colour.blue())

            data_joueurs = data_oracle[data_oracle['league'] == value]
            data_joueurs = data_joueurs[data_joueurs['split'] == split]

            liste_equipe = data_joueurs['teamname'].unique()

            for equipe in liste_equipe:

                data_equipe = data_joueurs[data_joueurs['teamname'] == equipe]

                liste_joueur = data_equipe['playername'].dropna().unique()

                liste_joueur = liste_en_str(liste_joueur)

                embed.add_field(name=str(equipe), value=str(liste_joueur) + "\n", inline=False)

            await ctx.send(embed=embed)

    @cog_ext.cog_slash(name="fantasy_add", description="Ajoute son compte Discord au jeu de la Fantasy")

    async def fantasy_add(self, ctx):
        user = ""
        user = str(ctx.author)
        data = loadDataFL()

        if user in data.keys():
            await ctx.send('Tu es déjà inscrit !')
        else:
            data[user] = {'Points' : Nb_points}
            writeDataFL(data)
            # ajouter un rank (fantasy)
            # role = discord.utils.get(ctx.guild.roles, name=competition)
            # await user.add_roles(role)
            await ctx.send(f'Le joueur {user} a été ajouté !')
        
        
    @cog_ext.cog_slash(name="fantasy_bet", description="Permet de miser au jeu de la Fantasy pour la semaine en cours",                        
                       options=[create_option(name="competition", description="Quelle compétition", option_type=3, required=True, choices=[
                                    create_choice(name="LEC", value="LEC"),
                                    create_choice(name='LFL', value='LFL'),
                                    create_choice(name='LCS', value='LCS')])])

    async def fantasy_bet(self, ctx, competition='LEC'):
        erreur = False
        user = str(ctx.author)
        
        jour = jour_de_la_semaine()
        
        await ctx.defer(hidden=False)
        
        
        if jour in jour_de_match[competition]: #empeche de parier les jours de matchs
            await ctx.send(f"Des matchs se jouent en {competition} aujourd'hui. Les paris sont donc bloqués")
        else:
            # settings
            semaine_data = loadDataFL('settings')['semaine'][competition]
            
            #data
            data = loadDataFL()
                
            # rate
            rate = loadDataRate()
            schedule_date = schedule()
                
            channel = ctx.channel
            author = ctx.author
            
            match_liste = ""
            match_bet = []
            liste_equipe1 = []
            liste_equipe2 = []
            z = 0
            
            for semaine in range(semaine_data, semaine_data+2):
                schedule_date = schedule_date[schedule_date['Competition'] == competition]
                op1 = schedule_date['Equipe1'].values
                op2 = schedule_date['Equipe2'].values
                for j in range((semaine-1)*5,semaine*5):
                    liste_equipe1.append(op1[j])
                    liste_equipe2.append(op2[j])
                equipe1 = [op1[i] for i in range((semaine-1)*5, semaine*5)]
                equipe2 = [op2[i] for i in range((semaine-1)*5, semaine*5)]
                
                for match in range(0, len(equipe1)):
                    match_liste = match_liste + str(z) + ":" + str(equipe1[match]) + "/" + str(equipe2[match]) + "\n"
                    match_bet.append(str(equipe1[match]) + "/" + str(equipe2[match]))
                    z = z + 1
                    
                
            
            await ctx.send(f'Pari pour la journée {str(semaine_data)} \n' + match_liste)
            
                
            def check(m):
                return m.author == author and m.channel == channel
            
            points = data[user]['Points']
                
            await channel.send(f'Tu peux miser au maximum `{points} points`. \n La réponse doit être au format `<numero_match> <equipe gagnante> <points mises> ` \n Tu peux faire plusieurs pronos sous la forme : \n`<numero_match> <equipe gagnante> <points mises> <numero_match> <equipe gagnante> <points mises>...` ')

                    
            try:
                msg = await self.bot.wait_for('message', timeout=60, check=check)
                await channel.send('Validé'.format(msg))
                msg = str(msg.content).split()
                
                # 1 = numero
                # 2 = vainqueur
                # 3 = mise

                
                for i in range(0,len(msg), 3):
                    numero = int(msg[i])
                    equipe_gagnante = msg[i+1]
                    points_mises = int(msg[i+2])

                    
                    data[user]['Points'] = data[user]['Points'] - points_mises
                    
                    if data[user]['Points'] < 0: # Si le joueur n'a plus de points, on ne peut pas continuer.
                        await ctx.send(f"Erreur, tu n'as pas assez de points. {data[user]['Points']} \nAnnulation des paris.")
                        erreur = True
                        break
                    
                    # if not equipe_gagnante in liste_equipe1 or not equipe_gagnante in liste_equipe2:
                    #     erreur = True
                    #     await channel.send(f'Erreur : Tu as mal écrit une équipe. Annulation des paris.')
                    #     break 
                    
                    # on enregistre le score
                    semaine_bet = semaine_data
                    if numero > 4: # à partir du 6ème match, semaine suivante
                        semaine_bet = semaine_bet + 1
                    
                    try:
                        data[user][semaine_bet][competition][match_bet[numero]] = [equipe_gagnante, points_mises]
                    except KeyError: # Si erreur, il n'a jamais misé sur ces matchs
                        try:
                            data[user][semaine_bet][competition] = {match_bet[numero] : [equipe_gagnante, points_mises]}    
                        except KeyError: # Si erreur, le joueur n'a jamais misé pour cette compétition.
                            data[user][semaine_bet] = {competition : {match_bet[numero] : [equipe_gagnante, points_mises]}}
                        
                
            except asyncio.TimeoutError:
                await msg.delete()
                await ctx.send("Annulé")
        
        if erreur is False:
            writeDataFL(data)
            await channel.send(f"Il te reste {data[user]['Points']} points")

    
    @cog_ext.cog_context_menu(name="FantasyDB")
    async def FantasyDB(self, ctx):
        data_schedule = schedule()
        data = loadDataFL()
        cote = loadDataRate()
        print('Schedule : ')
        print(data_schedule)
        print('Fantasy :')
        print(data)
        print('Rate :')
        print(cote)
            
        
    @cog_ext.cog_slash(name="fantasy_my_bet", description="Affiche mes paris")
    async def fantasy_my_bet(self, ctx):
        user = str(ctx.author)
        
        data = loadDataFL()
        rate = loadDataRate()

        
        embed = discord.Embed(title=f"Pari du joueur {user} pour la semaine en cours", color=discord.Color.gold())
        
        for competition in ['LEC', 'LFL', 'LCS']:
            semaine_data = loadDataFL('settings')['semaine'][competition]
            
            embed.add_field(name="Competition", value=competition, inline=False)
        
            try:
                for semaine in range(semaine_data, semaine_data + 2):
                    embed.add_field(name="Semaine", value=str(semaine), inline=False)
                    for match, pari in data[user][semaine][competition].items():
                        equipe_gagnante = pari[0]
                        points_mises = pari[1]
                        embed.add_field(name=match + " " + str(rate[str(semaine)][competition][match]),
                                            value=f"Equipe misée : {equipe_gagnante} | Points misés : {points_mises}", inline=True)
            except KeyError: # cela veut dire que le joueur n'a pas misé pour la compétition
                pass
            
        await ctx.send(embed=embed)
        
    @cog_ext.cog_slash(name="fantasy_results",
                       description="Resultat des matchs [Réservé aux administrateurs]",
                       options=[create_option(name="competition", description = "competition", option_type=3, required=True),
                                create_option(name="match1", description = "match 1", option_type=3, required=True),
                                create_option(name="match2", description = "competition", option_type=3, required=True),
                                create_option(name="match3", description = "competition", option_type=3, required=True),
                                create_option(name="match4", description = "competition", option_type=3, required=True),
                                create_option(name="match5", description = "competition", option_type=3, required=True)])
    @main.isAdmin_slash()
    async def fantasy_results(self, ctx, competition, match1, match2, match3, match4, match5):
        
        data = loadDataFL()
        rate = loadDataRate()
        schedule_date = schedule()
        vainqueur = [match1, match2, match3, match4, match5]
        
        dict_bdd = dict()
        
        
        semaine = loadDataFL('settings')['semaine'][competition]
        
        
       

        schedule_date = schedule_date[schedule_date['Competition'] == competition]
        op1 = schedule_date['Equipe1'].values
        op2 = schedule_date['Equipe2'].values
        
        await ctx.defer(hidden=False)
        
        list_keys = list(data.keys())
        
        for i in range(0, 5):
            msg = ""
            equipe1 = op1[i]
            equipe2 = op2[i]
            match = str(equipe1) + "/" + str(equipe2)
            cote_equipe1 = rate[str(semaine)][competition][match][0]
            cote_equipe2 = rate[str(semaine)][competition][match][1]
            

            

        
            for joueur in data.keys():
                points = data[joueur]['Points']
                if i == 0:
                    points_avant_match = points
                    print(data[joueur][semaine][competition])
                try: # A tester.. Il faut un mécanisme dans le cas où le joueur n'a pas misé sur cette compétition
                    match_joueur = data[joueur][semaine][competition][match]
                    points_mises = data[joueur][semaine][competition][match][1]
                except:
                    points_mises = '0'
                    pass
                
                if vainqueur[i] == equipe1:
                    cote = cote_equipe1
                else:
                    cote = cote_equipe2
                
                # on vérifie le résultat

                if match_joueur[0] == vainqueur[i]:
                    points_gagnes = points_mises * cote
                    points = points + points_gagnes
                    msg_win = f'Le joueur {joueur} a bien parié pour le match {match}\n** Points misés ** : {points_mises} pour une côte à {cote}\nTu gagnes donc {points_gagnes} points \n** Total ** :{points}\n'
                    if points_mises != 0:
                        msg = msg + msg_win
                elif match_joueur[0] != vainqueur[i] and points_mises != '0':
                    points = points - points_mises
                    msg_lose = f'Le joueur {joueur} a mal parié pour le match {match}\n Tu perds donc la totalité des points misées : {str(points_mises)}. \n Total:{str(points)}\n'
                    if points_mises != 0:
                        msg = msg + msg_lose

                        
                data[joueur]['Points'] = points
                
                dict_bdd[joueur] = {'semaine': int(semaine), 'points' : points}
                
                
                if joueur == list_keys[-1]:    # si on est à la dernière clé
                    await ctx.send(f'{match} :\n{msg}')
                
                
                if i == 4:  # quand on arrive à la fin
                    dif_points = points - points_avant_match    # diff de points avant/après cette semaine
                    await ctx.send(f'Le différenciel de points pour {joueur} sur cette semaine est de : {str(dif_points)}')
                    
        # on sauvegarde le tout
        
        # la data du joueur
        writeDataFL(data)
        # le nombre de points de cette semaine pour le suivi
        sauvegarde_bdd(dict_bdd, 'Fantasy_points', "append")
        #maj de la semaine
        settings = loadDataFL('settings')
        settings['semaine'][competition] = settings['semaine'][competition] + 1
        writeDataFL(settings, 'settings')
            
    
        
    
    @cog_ext.cog_slash(name="fantasy_help",description="Test [Réservé aux administrateurs]")

    async def fantasy_help(self, ctx):
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
        
    @cog_ext.cog_slash(name="fantasy_maj_cote",description="Permet de mettre à jour l'ensemble des côtes [Réservé aux administrateurs]")
    @main.isOwner2_slash()
    async def fantasy_maj_cote(self, ctx):
        
        
        cote = {}
        for i in range(1,19):
            

            schedule_date = schedule()
            schedule_lec = schedule_date[schedule_date['Competition'] == 'LEC']
            schedule_lfl = schedule_date[schedule_date['Competition'] == 'LFL']
            schedule_lcs = schedule_date[schedule_date['Competition'] == 'LCS']
            #rajouter critère semaine
            op1_lec = schedule_lec['Equipe1'].values
            op2_lec = schedule_lec['Equipe2'].values
            op1_lfl = schedule_lfl['Equipe1'].values
            op2_lfl = schedule_lfl['Equipe2'].values
            op1_lcs = schedule_lcs['Equipe1'].values
            op2_lcs = schedule_lcs['Equipe2'].values
                
            dict = {'LEC' : {str(op1_lec[0]) + "/" + str(op2_lec[0]) : [1.5,1.5]}, 'LFL' : {str(op1_lfl[0]) + "/" + str(op2_lfl[0]) : [1.5,1.5]}, 'LCS' : {str(op1_lcs[0]) + "/" + str(op2_lcs[0]) : [1.5,1.5]}}
            
            if i == 1:
                
                dict['LEC'] = {str(op1_lec[j]) + "/" + str(op2_lec[j]) : [1.5,1.5] for j in range(0,5)}
                dict['LFL'] = {str(op1_lfl[j]) + "/" + str(op2_lfl[j]) : [1.5,1.5] for j in range(0,5)}
                dict['LCS'] = {str(op1_lcs[j]) + "/" + str(op2_lcs[j]) : [1.5,1.5] for j in range(0,5)}
                
            else:
                dict['LEC'] = {str(op1_lec[j]) + "/" + str(op2_lec[j]) : [1.5,1.5] for j in range((i-1)*5,i*5)}
                dict['LFL'] = {str(op1_lfl[j]) + "/" + str(op2_lfl[j]) : [1.5,1.5] for j in range((i-1)*5,i*5)}
                dict['LCS'] = {str(op1_lcs[j]) + "/" + str(op2_lcs[j]) : [1.5,1.5] for j in range((i-1)*5,i*5)}
                
                
            cote[i] = dict
            

        writeDataRate(cote)
        

        
        
        await ctx.send('Fait !')
        
    @cog_ext.cog_slash(name="fantasy_cote",
                       description="Voir les côtes des matchs de la semaine",
                    )

    async def fantasy_cote(self, ctx):
        data = loadDataRate()
        settings = loadDataFL('settings')
        
        
        response = ""
        
        for competition in ['LEC', 'LFL', 'LCS']:
            semaine_data = settings['semaine'][competition]
            
            response += f'** {competition} : ** \n'
            
            for semaine in range(semaine_data, semaine_data+2):
                response += f'__ Jour {str(semaine)} : __\n'
                for key, value in data[str(semaine)][competition].items():
                    response += str(key) + " : " + str(value) + "\n"
        
        embed = discord.Embed(title=f"Côte des matchs du jour {str(semaine_data)} à {str(semaine_data+1)}  ", description=response, colour=discord.Colour.blurple())
            
        await ctx.send(embed=embed)
            
        
    @cog_ext.cog_slash(name="fantasy_classement",
                       description="Permet de voir le classement de la Fantasy")
    async def fantasy_classement(self, ctx):
        
        data = loadDataFL()
        response = ""

        for key, value in data.items():
            response += key.upper() + " : " + str(data[key]['Points'])  + " points , "

        # response = response[:-2]
        embed = discord.Embed(title="Liste joueurs", description=response, colour=discord.Colour.blurple())

        await ctx.send(embed=embed)
        
        
    # @commands.dm_only() entre le cog et le async
    # @fantasy_match_of_the_week.error
    # async def match_of_the_week_error(self, ctx, error):
    #     if isinstance(error, commands.PrivateMessageOnly):
    #         await ctx.send("Cette commande n'est activée qu'en message privé")
        
    @cog_ext.cog_slash(name="settings",
                       description="Test")
    @main.isOwner2_slash()
    async def settings(self, ctx):
        settings = {'Nb_points': 50,
                    'semaine': {'LEC' : 1, 'LCS' : 1, 'LFL': 1}}
        writeDataFL(settings, 'settings')
        await ctx.send('Fait !')
        
        
        
    @cog_ext.cog_slash(name="stats_game_pro", description="Recap d'une game compétitif",
                        options=[create_option(name="gameid", description = "Exemple :  ESPORTSTMNT01_2690210", option_type=3, required=True)])
                                # create_option(name="split", description = "Quel split", option_type=3, required=True, choices=[
                                #     create_choice(name="spring", value="Spring"),
                                #     create_choice(name="summer", value="Summer")])])
    async def stats_game_pro(self, ctx, gameid):
        
        await ctx.defer(hidden=False)
        
        rechargement_data_oracle()
        
        data_oracle = loaddata_oracle()
        
        data_oracle = data_oracle[data_oracle['split'].isin(['Spring', 'Summer'])]
        
        data_oracle['split'] = np.where(data_oracle['patch'] < 12.09, 'Spring', data_oracle['split']) # Correction dû à des games "summer" donné au "spring"
        
        data_oracle['gamelength'] = ((data_oracle['gamelength']/60)) % 60 # Durée des games en minutes plutôt qu'en seconde
        
        df_joueurs = data_oracle[data_oracle['position'] != 'team'] # on veut les joueurs
        
        # df_joueurs = df_joueurs[df_joueurs['split'] == split]
        
        def stats_game(df, gameid):
            df = df[df['gameid'] == gameid][['playername', 'gamelength','champion','kills','deaths','assists', 'doublekills', 'triplekills', 'quadrakills', 'pentakills',
            'firstblood', 'team kpm', 'damagetochampions', 'dpm', 'damageshare', 'wardsplaced', 'visionscore', 'totalgold', 'total cs', 'cspm',
            'golddiffat15', 'xpdiffat15', 'csdiffat15', 'csat15']]
            dfi.export(df, 'image.png', max_cols=-1, table_conversion="matplotlib")
            
        stats_game(df_joueurs, gameid)
        
        await ctx.send(file=discord.File('image.png'))
        
        os.remove('image.png')
        
        
    @cog_ext.cog_slash(name="stats_joueur_pro", description="Recap d'un joueur pro",
                        options=[create_option(name="joueur", description = "Exemple :  ESPORTSTMNT01_2690210", option_type=3, required=True),
                                create_option(name="split", description = "Le split", option_type=3, required=True, choices=[
                                    create_choice(name="spring", value="Spring"),
                                    create_choice(name="summer", value="Summer")]),
                                create_option(name="methode", description = "Methode d'affichage", option_type=3, required=True, choices=[
                                    create_choice(name="par game", value="Par game"),
                                    create_choice(name="moyenne", value="Moyenne")])])
    async def stats_joueur_pro(self, ctx, joueur, methode, split):
        
        await ctx.defer(hidden=False)
        
        rechargement_data_oracle()
        
        data_oracle = loaddata_oracle()
        
        data_oracle = data_oracle[data_oracle['split'].isin(['Spring', 'Summer'])]
        
        data_oracle['split'] = np.where(data_oracle['patch'] < 12.09, 'Spring', data_oracle['split']) # Correction dû à des games "summer" donné au "spring"
        
        data_oracle['gamelength'] = ((data_oracle['gamelength']/60)) % 60 # Durée des games en minutes plutôt qu'en seconde
        
        df_joueurs = data_oracle[data_oracle['position'] != 'team'] # on veut les joueurs
        
        df_joueurs = df_joueurs[df_joueurs['split'] == split]
        
        
        if methode == "Par game":
            df = df_joueurs[df_joueurs['playername'] == joueur][['playername', 'gamelength','champion','kills','deaths','assists', 'doublekills', 'triplekills', 'quadrakills', 'pentakills',
                'firstblood', 'team kpm', 'damagetochampions', 'dpm', 'damageshare', 'wardsplaced', 'visionscore', 'totalgold', 'total cs', 'cspm',
                'golddiffat15', 'xpdiffat15', 'csdiffat15', 'csat15']]
            
        elif methode == "Moyenne":
            df = df_joueurs.groupby(['playername', 'champion']).agg(
                {'gamelength' : 'mean', 'champion' : 'count', 'kills' : 'sum', 'deaths' : 'sum', 'assists' : 'sum', 'doublekills': 'sum', 'triplekills' : 'sum', 'quadrakills' : 'sum', 'pentakills' : 'sum',
                'firstblood' : 'sum', 'team kpm' : 'mean', 'damagetochampions' : 'mean', 'dpm' : 'mean', 'damageshare' : 'mean', 'wardsplaced' : 'mean', 'visionscore' : 'mean', 'totalgold' : 'mean', 'total cs' : 'mean', 'cspm' : 'mean',
                'golddiffat15' : 'mean', 'xpdiffat15' : 'mean', 'csdiffat15' : 'mean', 'csat15' : 'mean'})

            df['kills_avg'] = df['kills']/df['champion']
            df['deaths_avg'] = df['deaths']/df['champion']
            df['assists_avg'] = df['assists']/df['champion']
            df = df.loc[joueur]
            
        dfi.export(df, 'image.png', max_cols=-1, max_rows=-1, table_conversion="matplotlib")
        
        await ctx.send(file=discord.File('image.png'))
        
        os.remove('image.png')
        
    

def setup(bot):
    bot.add_cog(Fantasy(bot))