import pandas as pd
import pickle
from matplotlib import pyplot as plt
import os
import plotly.express as px
from fonctions.gestion_bdd import lire_bdd, lire_bdd_perso
import pickle
import interactions
from interactions import Choice, Option, Extension, CommandContext
        
def unifier_joueur(df, colonne):
    df[colonne] = df[colonne].replace('stαte', 'state')
    df[colonne] = df[colonne].replace('linò', 'state')
    df[colonne] = df[colonne].replace('namiyeon', 'dawn')
    df[colonne] = df[colonne].replace('chatobogan', 'dawn')
    df[colonne] = df[colonne].replace('zyradelevingne', 'dawn')

    return df


def ajouter_game(role, df, pseudo, kills, deaths, assists, kp, wardsplaced, wardskilled, pink, cs, csm, score: 0):
    df = df.append({'Role': role, 'Pseudo': pseudo, 'Kills': kills, 'Deaths': deaths
                       , 'Assists': assists, 'KP': kp, 'WardsPlaced': wardsplaced, 'WardsKilled': wardskilled
                       , 'Pink': pink, 'cs': cs, 'csm': csm, 'score': score}, ignore_index=True)
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
                 'score'])
    df_predict = ajouter_game(role, df_predict, pseudo, kills, deaths, assists, kp, wardsplaced, wardskilled, pink, cs,
                              csm,
                              0)

    predict = round(reg.predict(df_predict[variables].values)[0], 2)

    return predict




class Achievements_scoringlol(Extension):
    def __init__(self, bot) -> None:
        self.bot: interactions.Client = bot
            
    mode_de_jeu = [Choice(name='ranked', value='ranked'),
              Choice(name='aram', value='aram')]
    
    @interactions.extension_command(
        name="achievements",
        description="Voir les couronnes acquis par les joueurs",
        options=[Option(
            name='mode', 
            description='mode de jeu',
            type=interactions.OptionType.STRING,
            required=True,
            choices=mode_de_jeu),
                Option(
            name='records',
            description= 'afficher le cumul des records',
            type=interactions.OptionType.STRING,
            choices=[
                Choice(name='ranked', value='ranked'),
                Choice(name='aram', value='aram'),
                Choice(name='tout', value='all'),
                Choice(name='aucun', value='none')],
            required=False),
                ],
        )
    async def achievements(self, ctx:CommandContext, mode:str, records:str='none'):
        

        # Succes
        suivi = lire_bdd('suivi', 'dict')

        if mode == 'aram':
            
            settings = lire_bdd_perso(f'SELECT index, score_aram as score from achievements_settings')
            col_games = 'games_aram'
            col_achievements = 'Achievements_aram'
        else:
            settings = lire_bdd_perso(f'SELECT index, score as score from achievements_settings')  
            col_games = 'games'
            col_achievements = 'Achievements' 
             
    
        settings = settings.to_dict()


        df = pd.DataFrame(suivi)
        df = df.transpose().reset_index()
        
        await ctx.defer(ephemeral=False)

        # Records
        if records != 'none':
            if records in ['ranked', 'aram']:
                sql = f'''SELECT "Joueur", Count("Joueur") from records
                where mode = '{records}'
                group by "Joueur"
                order by "count" DESC'''
            
            elif records == 'all':
                sql = f'''SELECT "Joueur", Count("Joueur") from records
                group by "Joueur"
                order by "count" DESC'''

            df_count = lire_bdd_perso(sql, index_col='Joueur').transpose().reset_index()

            df_count = unifier_joueur(df_count, 'Joueur')
            
            fig = px.bar(df_count, 'Joueur', 'count', title=f'Record pour {records}', color='Joueur')
            fig.update_layout(showlegend=False)
            fig.write_image('plot.png')

        df = df[df[col_games] >= settings['Nb_games']['score']]
        df['Achievements_par_game'] = df[col_achievements] / df[col_games]

        df.sort_values(by=['Achievements_par_game'], ascending=[False], inplace=True)

        joueur = df['index'].to_dict()

        
        result = ""

        # for id, key in joueur.items():
        for key in joueur.values():

            if suivi[key][col_achievements] > 0:
                achievements = suivi[key][col_achievements]
                games = suivi[key][col_games]
                achievements_par_game = round(achievements / games, 2)
                    
                if result == "":
                    result = "** " + key + " ** : " + str(achievements) + " :crown: en " + str(games) + " games (" + str(achievements_par_game) + " :crown: / games)\n"
                else:
                    result = result + "** " + key + " ** : " + str(achievements) + " :crown: en " + str(games) + " games (" + str(achievements_par_game) + " :crown: / games)\n"
                    

        await ctx.send(f"Couronnes (Mode : {mode} et {int(settings['Nb_games']['score'])} games minimum) :\n" + result)


        if records:
            await ctx.send('Informations : Les records de la page 3 ne sont pas comptabilisés', files=interactions.File('plot.png'))
            os.remove('plot.png')
            

    @interactions.extension_command(name="achievements_regles",
                       description="Conditions pour débloquer des couronnes",
                       options=[Option(
                           name='mode',
                           description='mode de jeu',
                           type=interactions.OptionType.STRING,
                           required=True,
                           choices=mode_de_jeu)])
    async def achievements_regles(self, ctx:CommandContext, mode:str):

        if mode == 'aram':
            
            settings = lire_bdd_perso(f'SELECT index, score_aram as score from achievements_settings')
        else:
            settings = lire_bdd_perso(f'SELECT index, score as score from achievements_settings')  

        settings = settings.to_dict()

        if mode == 'aram':
            partie0 = f":gear: Nombre de games minimum : {settings['Nb_games']['score']} \n"
            partie1 = f":crown: Pentakill : {settings['Pentakill']['score']} \n :crown: Quadrakill : {settings['Quadrakill']['score']} \n :crown: KDA >= {settings['KDA']['score']} \n :crown: KP >= {settings['KP']['score']}% \n"
            partie2 = f":crown: CS/min >= {settings['CS/min']['score']} \n"
            partie3 = f":crown: % DMG équipe > {settings['%_dmg_équipe']['score']}% \n :crown: % dmg tank >= {settings['%_dmg_tank']['score']}% \n"
            partie4 = f":crown: Total Heals sur alliés >= {settings['Total_Heals_sur_alliés']['score']} \n :crown: Shield plus de {settings['Shield']['score']}"
            
            texte_achievements = partie1 + partie2 + partie3 + partie4
        else:
            partie0 = f":gear: Nombre de games minimum : {settings['Nb_games']['score']} \n"
            partie1 = f":crown: Pentakill : {settings['Pentakill']['score']} \n :crown: Quadrakill : {settings['Quadrakill']['score']} \n :crown: KDA >= {settings['KDA']['score']} \n :crown: Ne pas mourir \n :crown: KP >= {settings['KP']['score']}% \n"
            partie2 = f":crown: Vision/min >= {settings['Vision/min(support)']['score']} (support) | {settings['Vision/min(autres)']['score']} (autres) \n :crown: CS/min >= {settings['CS/min']['score']} \n"
            partie3 = f":crown: Avantage vision >= {settings['Avantage_vision(support)']['score']}% (support) | {settings['Avantage_vision(autres)']['score']}% (autres) \n"
            partie4 = f":crown: % DMG équipe > {settings['%_dmg_équipe']['score']}% \n :crown: % dmg tank >= {settings['%_dmg_tank']['score']}% \n"
            partie5 = f":crown: Solokills >= {settings['Solokills']['score']} \n :crown: Total Heals sur alliés >= {settings['Total_Heals_sur_alliés']['score']} \n"
            partie6 = f":crown: CS d'avance sur ton adversaire durant la game >= {settings['CSAvantage']['score']} \n :crown: Ecart de niveau sur ton adversaire >= {settings['Ecart_Level']['score']} \n"
            partie7 = f":crown: Contribution à la destruction des tours >= {settings['Participation_tower']['score']}% \n :crown: Dragon >= {settings['Dragon']['score']} \n"
            partie8 = f":crown: Danse avec l'Herald \n :crown: Perfect Game \n :crown: Shield plus de {settings['Shield']['score']}" 
            
            texte_achievements = partie1 + partie2 + partie3 + partie4 + partie5 + partie6 + partie7 + partie8

        embed = interactions.Embed(title=f"** Règles {mode}: **", color=interactions.Color.yellow())
        embed.add_field(name="Parametres", value=partie0, inline=False)
        embed.add_field(name="Couronnes disponibles", value=texte_achievements, inline=False)

        await ctx.send(embeds=embed)
   

def setup(bot):
    Achievements_scoringlol(bot)
