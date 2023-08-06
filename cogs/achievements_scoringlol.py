import pandas as pd
import os
import plotly.express as px
from fonctions.gestion_bdd import lire_bdd, lire_bdd_perso
from fonctions.params import saison
import interactions
from interactions import Extension, SlashCommandOption, SlashCommandChoice, SlashContext, slash_command
import numpy as np


class Achievements_scoringlol(Extension):
    def __init__(self, bot) -> None:
        self.bot: interactions.Client = bot

    mode_de_jeu = [SlashCommandChoice(name='ranked', value='ranked'),
                   SlashCommandChoice(name='aram', value='aram')]

    @slash_command(
        name="couronne_s12",
        description="Voir les couronnes acquis par les joueurs (Réservé s12)",
        options=[
            SlashCommandOption(
                name='mode',
                description='mode de jeu',
                type=interactions.OptionType.STRING,
                required=True,
                choices=mode_de_jeu),
            SlashCommandOption(
                name='records',
                description='afficher le cumul des records',
                type=interactions.OptionType.STRING,
                choices=[
                    SlashCommandChoice(name='ranked', value='ranked'),
                    SlashCommandChoice(name='aram', value='aram'),
                    SlashCommandChoice(name='tout', value='all'),
                    SlashCommandChoice(name='aucun', value='none')],
                required=False),
        ],
    )
    async def achievements_s12(self,
                           ctx: SlashContext,
                           mode: str,
                           records: str = 'none'):
        
        
        def unifier_joueur(df, colonne):
            # Replace with Discord ID
            replacements = {'stαte': 'state',
                            'linò': 'state',
                            'namiyeon': 'dawn',
                            'chatobogan': 'dawn',
                            'zyradelevingne': 'dawn'}

            df[colonne] = df[colonne].replace(replacements)

            return df

        # Succes
        suivi = lire_bdd(f'suivi_s12', 'dict')

        if mode == 'aram':

            settings = lire_bdd_perso(
                f'SELECT index, score_aram as score from achievements_settings')
            col_games = 'games_aram'
            col_achievements = 'Achievements_aram'
        else:
            settings = lire_bdd_perso(
                f'SELECT index, score as score from achievements_settings')
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

            df_count = lire_bdd_perso(
                sql, index_col='Joueur').transpose().reset_index()

            df_count = unifier_joueur(df_count, 'Joueur')

            fig = px.bar(df_count, 'Joueur', 'count',
                         title=f'Record pour {records}', color='Joueur')
            fig.update_layout(showlegend=False)
            fig.write_image('plot.png')

        df = df[df[col_games] >= settings['Nb_games']['score']]
        df['Achievements_par_game'] = df[col_achievements] / df[col_games]

        df.sort_values(by=['Achievements_par_game'],
                       ascending=[False], inplace=True)

        joueur = df['index'].to_dict()

        result = ""

        # for id, key in joueur.items():
        for key in joueur.values():

            if suivi[key][col_achievements] > 0:
                achievements = suivi[key][col_achievements]
                games = suivi[key][col_games]
                achievements_par_game = round(achievements / games, 2)

                if result == "":
                    result = "** " + key + " ** : " + str(achievements) + " :crown: en " + str(
                        games) + " games (" + str(achievements_par_game) + " :crown: / games)\n"
                else:
                    result = result + "** " + key + " ** : " + str(achievements) + " :crown: en " + str(
                        games) + " games (" + str(achievements_par_game) + " :crown: / games)\n"

        await ctx.send(f"Couronnes (Mode : {mode} et {int(settings['Nb_games']['score'])} games minimum) :\n" + result)

        if records in ['ranked', 'aram', 'all']:
            await ctx.send('Informations : Les records de la page 3 ne sont pas comptabilisés', files=interactions.File('plot.png'))
            os.remove('plot.png')

    @slash_command(name="couronnes_regles",
                                    description="Conditions pour débloquer des couronnes",
                                    options=[
                                        SlashCommandOption(
                                            name='mode',
                                            description='mode de jeu',
                                            type=interactions.OptionType.STRING,
                                            required=True,
                                            choices=mode_de_jeu)])
    async def achievements_regles(self,
                                  ctx: SlashContext,
                                  mode: str):

        if mode == 'aram':

            settings = lire_bdd_perso(
                f'SELECT index, score_aram as score from achievements_settings')
        else:
            settings = lire_bdd_perso(
                f'SELECT index, score as score from achievements_settings')

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

            texte_achievements = partie1 + partie2 + partie3 + \
                partie4 + partie5 + partie6 + partie7 + partie8

        embed = interactions.Embed(
            title=f"** Règles {mode}: **", color=interactions.Color.random())
        embed.add_field(name="Parametres", value=partie0, inline=False)
        embed.add_field(name="Couronnes disponibles",
                        value=texte_achievements, inline=False)

        await ctx.send(embeds=embed)

    @slash_command(name="couronnes",
                                    description="Voir le nombre de records et mvp détenu par les joueurs",
                                    options=[
                                        SlashCommandOption(
                                            name="mode",
                                            description="Quel mode de jeu ?",
                                            type=interactions.OptionType.STRING,
                                            required=True, choices=[
                                                SlashCommandChoice(name='ranked',
                                                       value='RANKED'),
                                                SlashCommandChoice(name='aram', value='ARAM'),
                                                SlashCommandChoice(name='normal', value='NORMAL'),
                                                SlashCommandChoice(name='flex', value='FLEX')]),
                                        SlashCommandOption(
                                            name='saison',
                                            description='saison league of legends',
                                            type=interactions.OptionType.INTEGER,
                                            min_value=12,
                                            max_value=saison,
                                            required=False),
                                        SlashCommandOption(
                                            name='tri',
                                            description='manière de trier',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                SlashCommandChoice(name='couronne', value='per game'),
                                                SlashCommandChoice(name='mvp', value='mvp')
                                            ]
                                        )
                                    ])
    async def achievements2(self,
                            ctx: SlashContext,
                            mode: str,
                            saison: int = saison,
                            tri:str = 'per game'):

        await ctx.defer(ephemeral=False)

        df = lire_bdd_perso(f'''SELECT distinct id, joueur, couronne, mvp from matchs where season = {saison} and mode ='{mode}' ''', index_col='id',
                            ).transpose()

        # Il y a bcp de games sans ce système de mvp. On remplace les 0 par des nan pour qu'il ne soit pas compté dans la moyene
        df['mvp'] = df['mvp'].replace({0 : np.nan})
        # on regroupe par joueur
        df = df.groupby('joueur').agg({'couronne': 'sum', 'joueur': 'count', 'mvp' : 'mean'})
        # Les joueurs n'ayant aucune game ont des NaN. On les met à 0.
        df['mvp'].fillna(0, inplace=True)

        # 5 games minimum

        df = df[df['joueur'] >= 5]

        # on calcule par game

        df['per game'] = df['couronne'] / df['joueur']
        
        
        df.sort_values(tri, ascending=False, inplace=True)

        result = f'Couronnes : Mode **{mode}** et 5 games minimum : \n'
        
        

        for joueur, stats in df.iterrows():
            
            if stats['mvp'] != 0:
                result += f"**{joueur} ** : {stats['couronne']} :crown: en {stats['joueur']} games ({round(stats['per game'],2)} :crown: / games) | Moyenne de mvp : **{round(stats['mvp'],2)}** \n"
            else:
                result += f"**{joueur} ** : {stats['couronne']} :crown: en {stats['joueur']} games ({round(stats['per game'],2)} :crown: / games) \n"

        await ctx.send(result)


def setup(bot):
    Achievements_scoringlol(bot)
